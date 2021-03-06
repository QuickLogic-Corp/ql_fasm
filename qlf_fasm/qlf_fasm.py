#!/usr/bin/env python3
"""
QuickLogic qlf-series FPGA FASM to bitstream and bitstream to FASM conversion
utility.
"""
import argparse
import os
import re
import logging

import fasm

from .database import Bit, Database
from .bitstream import TextBitstream, FourByteBitstream

# =============================================================================

# Common FASM feature prefix
FEATURE_PREFIX = "fpga_top"

# Prefix used to invert all bits in a FASM feature. Has to be applied to the
# last part of a feature name.
INVERSION_PREFIX = "NOT_"

# =============================================================================

def canonical_features(set_feature):
    """ 
    Yield SetFasmFeature tuples that are of canonical form. EG width 1, and
    value 1. As opposed to the function form the fasm package this one also
    returns cleared features (of value 0)
    """

    if set_feature.start is None:
        assert set_feature.end is None
        yield fasm.SetFasmFeature(
            feature=set_feature.feature,
            start=None,
            end=None,
            value=set_feature.value,
            value_format=None,
        )

        return

    if set_feature.start is not None and set_feature.end is None:
        if set_feature.start == 0:
            yield fasm.SetFasmFeature(
                feature=set_feature.feature,
                start=None,
                end=None,
                value=set_feature.value,
                value_format=None,
            )
        else:
            yield fasm.SetFasmFeature(
                feature=set_feature.feature,
                start=set_feature.start,
                end=None,
                value=set_feature.value,
                value_format=None,
            )

        return

    assert set_feature.start is not None
    assert set_feature.start >= 0
    assert set_feature.end >= set_feature.start

    for address in range(set_feature.start, set_feature.end + 1):
        value = (set_feature.value >> (address - set_feature.start)) & 1
        if address == 0:
            yield fasm.SetFasmFeature(
                feature=set_feature.feature,
                start=None,
                end=None,
                value=value,
                value_format=None,
            )
        else:
            yield fasm.SetFasmFeature(
                feature=set_feature.feature,
                start=address,
                end=None,
                value=value,
                value_format=None,
            )

# =============================================================================


class QlfFasmException(Exception):
    """
    Generic FASM encoder/decoder exception
    """
    pass


class QlfFasmAssembler():
    """
    FASM assembler for QuickLogic QLF devices.
    """

    # A regular expression for FASM feature grid location tags. For example:
    # - "grid_clb_1__4_"
    # - "sb_20__2_"
    # - "cbx_2__5_"
    LOC_RE = re.compile(r"(?P<name>.+)_(?P<x>[0-9]+)__(?P<y>[0-9]+)_$")

    class LookupError(QlfFasmException):
        """
        FASM database lookup error exception
        """
        pass

    class FeatureConflict(QlfFasmException):
        """
        FASM feature conflict exception
        """
        pass

    def __init__(self, database, bitstream=None):
        self.database = database

        if bitstream is None:
            self.bitstream = bytearray(database.bitstream_size)
        else:
            assert len(bitstream) == database.bitstream_size
            self.bitstream = bitstream

        self.features = {}
        self.force_bit_features = {}
        self.features_by_bits = {}

    def process_fasm_line(self, line):
        """
        Assembles and updates a part of the bistream described by the given
        single FASM line object.
        """

        set_feature = line.set_feature
        if set_feature is None:
            return

        # Split the feature name into parts, check the first part
        parts = set_feature.feature.split(".")
        if len(parts) < 3 or parts[0] != FEATURE_PREFIX:
            raise self.LookupError

        # Get grid location
        match = self.LOC_RE.fullmatch(parts[1])
        if match is None:
            raise self.LookupError

        loc = (int(match.group("x")), int(match.group("y")))
        name = match.group("name")

        # This feature refers to a block (tile)
        if name.startswith("grid_"):
            name = name.replace("grid_", "")

            # Check
            if loc not in self.database.tiles:
                raise self.LookupError
            if name not in self.database.segbits:
                raise self.LookupError

            # Get segbits and offset
            tile = self.database.tiles[loc]
            segbits = self.database.segbits[name]
            region = tile["region"]
            offset = tile["offset"]

        # This feature refers to a routing interconnect
        else:
            name = name.split("_", maxsplit=1)[0]

            if loc not in self.database.routing:
                raise self.LookupError
            if name not in self.database.routing[loc]:
                raise self.LookupError

            # Get the routing resource variant
            sbox = self.database.routing[loc][name]
            segbits_name = "{}_{}".format(name, sbox["variant"])

            if segbits_name not in self.database.segbits:
                raise self.LookupError

            # Get segbits and offset
            segbits = self.database.segbits[segbits_name]
            region = sbox["region"]
            offset = sbox["offset"]

        # Add region offset
        offset += self.database.regions[region]["offset"]

        # Format the line feature and value string to be used for error
        # checking and user messaging
        line_str = next(iter(fasm.fasm_line_to_string(line)))

        # Canonicalize - split to single-bit features and process them
        # individually
        for one_feature in canonical_features(set_feature):
            assert one_feature.value in [0, 1], one_feature

            # Feature bit index
            one_feature_idx = 0
            if one_feature.start is not None:
                one_feature_idx = one_feature.start

            # Check for feature value conflict
            key = (one_feature.feature, one_feature_idx)
            if key in self.features:
                other_value, other_line_str = self.features[key]
                if one_feature.value != other_value:

                    msg = "The FASM line '{}' conflicts with '{}'".format(
                        line_str,
                        other_line_str
                    )
                    raise self.FeatureConflict(msg)

            # Track feature values
            else:
                self.features[key] = (one_feature.value, line_str)

            # Skip cleared features
            if one_feature.value == 0:
                continue

            # Format the base name, determine inversion
            base_name = one_feature.feature.split(".")

            if base_name[-1].startswith(INVERSION_PREFIX):
                base_name[-1] = base_name[-1][len(INVERSION_PREFIX):]
                is_inverted = True
            else:
                is_inverted = False

            base_name = ".".join(base_name[2:])

            # Check if the feature exists
            if base_name not in segbits:
                raise self.LookupError

            # Lookup segbits, For 1-bit features try without the index suffix
            # first.
            bits = None
            if one_feature.start in [0, None]:            
                bits = segbits[base_name].get(None, None)

            # Try with index
            if bits is None:
                bits = segbits[base_name].get(one_feature_idx, None)

            # Not found            
            if bits is None:
                raise self.LookupError

            if not len(bits):
                logging.error(
                    "ERROR: The feature '{}' didn't set/clear any bits!".format(
                    one_feature.feature
                ))

            # Apply them to the bitstream
            for bit in bits:
                address = bit.idx + offset
                value = bit.val ^ is_inverted

                # Check for conflict
                if address in self.features_by_bits:
                    if value != self.bitstream[address]:

                        new_bit_act = "set" if value else "clear"
                        org_bit_act = "set" if self.bitstream[address] else "cleared"

                        # Format the error message
                        msg = "The line '{}' wants to {} bit {} already {} by the line '{}'".format(
                            line_str,
                            new_bit_act,
                            bit.idx,
                            org_bit_act,
                            self.features_by_bits[address]
                        )
                        raise self.FeatureConflict(msg)
                else:
                    self.features_by_bits[address] = set()

                # Set/clear the bit
                self.bitstream[address] = value
                self.features_by_bits[address].add(line_str)


    def assemble_bitstream(self, fasm_lines):
        """
        Assembles the bitstream using an interable of FASM line objects
        """
        unknown_features = []

        # Process FASM lines
        for line in fasm_lines:

            try:
                self.process_fasm_line(line)
            except self.LookupError:
                unknown_features.append(line)
                continue
            except self.FeatureConflict:
                raise
            except:
                raise

        return unknown_features

# =============================================================================


class QlfFasmDisassembler():
    """
    FASM disassembler for QuickLogic QLF devices.
    """

    def __init__(self, database):
        self.bitstream = None
        self.database = database

    def match_segbits(self, segbits, offset):
        """
        Matches a segbit pattern at the given offset against the bitstream.
        """
        match = True
        for segbit in segbits:
            address = segbit.idx + offset
            assert address < len(self.bitstream)

            if self.bitstream[address] != segbit.val:
                match = False
                break

        return match

    def disassemble_bitstream(self, bitstream):
        """
        Disassembles a bistream.
        """

        features = {}

        def emit_feature(feature, width, index, value):
            """
            A helper function for FASM feature emission
            """
            if index is None:
                index = 0
            assert index < width, (index, width)

            if feature not in features:
                features[feature] = {k: 0 for k in range(width)}

            features[feature][index] = int(value)

        def convert_to_set_features(features):
            """
            Converts features to SetFasmFeature objects
            """
            set_features = []

            for feature, data in features.items():
                width = len(data)

                # Single bit
                if width == 1:
                    set_features.append(fasm.SetFasmFeature(
                        feature=feature,
                        start=None,
                        end=None,
                        value=data[0],
                        value_format=None
                    ))

                # Multi-bit
                else:
                    keys = sorted(data.keys(), reverse=True)
                    bstr = "".join(["1" if data[k] else "0" for k in keys])
                    set_features.append(fasm.SetFasmFeature(
                        feature=feature,
                        start=0,
                        end=width - 1,
                        value=int(bstr, 2),
                        value_format=fasm.ValueFormat.VERILOG_BINARY
                    ))

            return set_features

        # Check size
        assert len(bitstream) == self.database.bitstream_size
        self.bitstream = bitstream

        # Disassemble tiles
        for loc, tile in self.database.tiles.items():

            # Get segbits
            segbits_name = tile["type"]
            assert segbits_name in self.database.segbits
            segbits = self.database.segbits[segbits_name]

            # Format feature prefix
            prefix = FEATURE_PREFIX + ".grid_{}_{}__{}_".format(
                tile["type"],
                loc[0],
                loc[1]
            )

            # Check each pattern
            region = tile["region"]
            offset = tile["offset"]

            offset += self.database.regions[region]["offset"]

            for feature, data in segbits.items():
                width = len(data)

                for index, bits in data.items():

                    # Match
                    value = self.match_segbits(bits, offset)

                    # Emit
                    full_name = prefix + "." + feature
                    emit_feature(full_name, width, index, value)

        # Disassemble routing
        for loc, routing in self.database.routing.items():
            for sbox_type, sbox in routing.items():

                # Get segbits
                segbits_name = "{}_{}".format(sbox["type"], sbox["variant"])
                assert segbits_name in self.database.segbits
                segbits = self.database.segbits[segbits_name]

                # Format feature prefix
                prefix = FEATURE_PREFIX + ".{}_{}__{}_".format(
                    sbox["type"],
                    loc[0],
                    loc[1]
                )

                # Check each pattern
                region = sbox["region"]
                offset = sbox["offset"]

                offset += self.database.regions[region]["offset"]

                for feature, data in segbits.items():
                    width = len(data)
                    for index, bits in data.items():

                        # Match
                        value = self.match_segbits(bits, offset)

                        # Emit
                        full_name = prefix + "." + feature
                        emit_feature(full_name, width, index, value)


        # Convert to SetFasmFeatures
        features = convert_to_set_features(features)
        return features

# =============================================================================


def validate_crc(args, bitstream, database):
    """
    Validates bitstream CRC. A helper function.
    """

    # Validate checksum
    if not args.no_crc:

        # CRC mismatch
        if not bitstream.validate_checksums(database):

            # If the CRC check is disabled print a warning, otherwise an
            # error
            if args.no_check_crc:
                level = logging.WARNING
            else:
                level = logging.CRITICAL

            ref_checksums = bitstream.compute_checksums(database)
            logging.log(level, "Bitstream CRC mismatch!")
            logging.log(level, " head: {:08X}, should be {:08X}".format(
                        bitstream.head_crc, ref_checksums[0]))
            logging.log(level, " tail: {:08X}, should be {:08X}".format(
                        bitstream.tail_crc, ref_checksums[1]))

            # CRC check enabled and failed
            if not args.no_check_crc:
                exit(-1)

        # CRC ok
        else:
            logging.info("Bitstream CRC ok")
            logging.debug(" head: {:08X}".format(bitstream.head_crc))
            logging.debug(" tail: {:08X}".format(bitstream.tail_crc))


def fasm_to_bitstream(args, database):
    """
    Implements FASM to bitstream flow
    """

    # Determine if and where to load default bitstream from
    default_bitstream_file = None
    default_bitstream_format = None

    if not args.no_default_bitstream:

        # Use args
        if args.default_bitstream:
            default_bitstream_file = args.default_bitstream
            default_bitstream_format = args.default_bitstream_format

        # Use database
        elif database.default_bitstream_file:
            default_bitstream_file = database.default_bitstream_file
            default_bitstream_format = database.default_bitstream_format

    # Load the default binary bitstream
    if default_bitstream_file:
        logging.info("Reading default bitstream...")

        if default_bitstream_format == "txt":
            default_bitstream = TextBitstream.from_file(default_bitstream_file)

        elif default_bitstream_format == "4byte":
            default_bitstream = FourByteBitstream.from_file(
                default_bitstream_file)
            validate_crc(args, default_bitstream, database)

        default_bitstream = default_bitstream.to_bits(database)

    else:
        default_bitstream = None

    logging.info("Assembling bitstream from FASM...")

    # Load and parse FASM
    fasm_lines = fasm.parse_fasm_filename(args.i)

    # Assemble
    assembler = QlfFasmAssembler(database, default_bitstream)
    unknown_features = assembler.assemble_bitstream(fasm_lines)

    # Got unknown features
    if unknown_features:
        logging.critical("ERROR: Unknown FASM features encountered ({}):".format(
            len(unknown_features)
        ))
        for feature in unknown_features:
            logging.critical(" " + feature.set_feature.feature)
        exit(-1)

    # Build the binary bitstream
    logging.info("Writing bitstream...")
    if args.format == "txt":
        bitstream = TextBitstream.from_bits(assembler.bitstream, database)

    elif args.format == "4byte":
        bitstream = FourByteBitstream.from_bits(assembler.bitstream, database)
        if not args.no_crc:
            bitstream.compute_and_set_checksums(database)

    else:
        assert False, args.format

    bitstream.to_file(args.o)


def bitstream_to_fasm(args, database):
    """
    Implements bitstream to FASM flow
    """

    # Load the binary bitstream
    logging.info("Reading bitstream...")
    if args.format == "txt":
        bitstream = TextBitstream.from_file(args.i)

    elif args.format == "4byte":
        bitstream = FourByteBitstream.from_file(args.i, not args.no_crc)
        validate_crc(args, bitstream, database)

    else:
        assert False, args.format

    # Disassemble
    logging.info("Disassembling bitstream...")
    disassembler = QlfFasmDisassembler(database)
    features = disassembler.disassemble_bitstream(
        bitstream.to_bits(database))

    # Write FASM file
    logging.info("Writing FASM file...")
    with open(args.o, "w") as fp:
        for feature in features:

            if feature.value != 0 or args.unset_features:
                fp.write(fasm.set_feature_to_str(feature) + "\n")

    # Write Force bit file
    logging.info("Writing Force bit file...")
    split_file = os.path.splitext(args.o)
    force_bit_file = "{}.force_bit".format(split_file[0])
    with open(force_bit_file, "w") as fp:
        for feature in features:

            # Make single bit features
            for one_feature in canonical_features(feature):

                if not one_feature.value:
                    continue

                index = one_feature.start
                if index is None:
                    index = 0
                    
                address = "[{}]".format(index)
                fp.write("force {}{}=1'b{};\n".format(
                    one_feature.feature, address, int(one_feature.value)))


# =============================================================================


def main():

    # Parse arguments
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "i",
        type=str,
        help="Input file (FASM or bitstream)"
    )
    parser.add_argument(
        "o",
        type=str,
        help="Output file (FASM or bitstream)"
    )
    parser.add_argument(
        "-f", "--format",
        type=str,
        choices=["txt", "4byte"],
        default="4byte",
        help="Binary bitstream format (def. '4byte')"
    )
    parser.add_argument(
        "--no-default-bitstream",
        action="store_true",
        help="If FASM database provides a default bitstream, don't use it."
    )
    parser.add_argument(
        "--default-bitstream",
        type=str,
        default=None,
        help="Path to an external default binary bitstream to overlay FASM on"
    )
    parser.add_argument(
        "--default-bitstream-format",
        type=str,
        choices=["txt", "4byte"],
        default="4byte",
        help="External default binary bitstream format (def. '4byte')"
    )
    parser.add_argument(
        "-a", "--assemble",
        action="store_true",
        help="Force FASM to bitstream conversion regardless of file extensions"
    )
    parser.add_argument(
        "-d", "--disassemble",
        action="store_true",
        help="Force bitstream to FASM conversion regardless of file extensions"
    )
    parser.add_argument(
        "--db-root",
        type=str,
        required=True,
        help="FASM database root path"
    )
    parser.add_argument(
        "--unset-features",
        action="store_true",
        help="When disassembling write cleared FASM features as well"
    )
    parser.add_argument(
        "--no-crc",
        action="store_true",
        help="Disable reading and writing CRC for the 4-byte bitstream format",
    )
    parser.add_argument(
        "--no-check-crc",
        action="store_true",
        help="Disable CRC check when disassembling a bitstream in 4-byte format"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="WARNING",
        help="Log level (def. \"WARNING\")"
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, args.log_level.upper()),
    )

    # Check what to do
    if args.assemble and args.disassemble:
        logging.critical("Please specify either '-a' or '-d'")
        exit(1)

    inp_ext = os.path.splitext(args.i)[1].lower()
    out_ext = os.path.splitext(args.o)[1].lower()

    if args.assemble:
        action = "fasm2bit"

    elif args.disassemble:
        action = "bit2fasm"

    elif inp_ext == ".fasm" and out_ext in [".bit", ".bin"]:
        action = "fasm2bit"

    elif out_ext == ".fasm" and inp_ext in [".bit", ".bin"]:
        action = "bit2fasm"

    else:
        logging.critical("No known conversion between '{}' and '{}'".format(
            inp_ext,
            out_ext
        ))
        exit(-1)

    # Load the database
    database = Database(args.db_root)

    # Do the conversion
    try:
        if action == "fasm2bit":
            fasm_to_bitstream(args, database)
        elif action == "bit2fasm":
            bitstream_to_fasm(args, database)
        else:
            assert False, action

    except QlfFasmException as ex:
        logging.critical("ERROR: " + str(ex))
        exit(-1)

# =============================================================================

if __name__ == "__main__":
    main()
