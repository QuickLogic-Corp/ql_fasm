#!/usr/bin/env python3
"""
QuickLogic qlf-series FPGA FASM to bitstream and bitstream to FASM conversion
utility.
"""
import argparse
import os
import re
import logging
import pkg_resources

import fasm

from .database import Bit, Database
from .bitstream import TextBitstream, FourByteBitstream

# =============================================================================

# Known databases
DATABASES = {
    "qlf_k4n8": pkg_resources.resource_filename("qlf_fasm", "database/qlf_k4n8")
}

# Common FASM feature prefix
FEATURE_PREFIX = "fpga_top"

# =============================================================================


class QlfFasmAssembler():
    """
    FASM assembler for QuickLogic QLF devices.
    """

    # A regular expression for FASM feature grid location tags. For example:
    # - "grid_clb_1__4_"
    # - "sb_20__2_"
    # - "cbx_2__5_"
    LOC_RE = re.compile(r"(?P<name>.+)_(?P<x>[0-9]+)__(?P<y>[0-9]+)_$")

    class LookupError(Exception):
        """
        FASM database lookup error exception
        """
        pass

    class FeatureConflict(Exception):
        """
        FASM feature conflict exception
        """
        pass

    def __init__(self, database):
        self.bitstream = bytearray(database.bitstream_size)
        self.database = database

        self.features_by_bits = {}

    def process_fasm_line(self, line):
        """
        Assembles and updates a part of the bistream described by the given
        single FASM line object.
        """

        set_feature = line.set_feature
        if not set_feature:
            return

        # Ignore features that are not set
        if set_feature.value == 0:
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

        # Canonicalize - split to single-bit features and process them
        # individually
        for one_feature in fasm.canonical_features(set_feature):

            # Skip cleared features
            assert one_feature.value in [0, 1], one_feature
            if one_feature.value == 0:
                continue

            base_name = one_feature.feature.split(".")
            base_name = ".".join(base_name[2:])

            # Lookup segbits, For 1-bit features try without the index suffix
            # first.
            bits = None
            if one_feature.start in [0, None]:
                key = base_name
                bits = segbits.get(key, None)

            # Try with index
            if bits is None:
                idx = 0 if one_feature.start is None else one_feature.start
                key = "{}[{}]".format(base_name, idx)
                bits = segbits.get(key, None)

            if bits is None:
                logging.debug(one_feature)
                logging.debug(base_name)
                raise self.LookupError

            if not len(bits):
                logging.error(
                    "ERROR: The feature '{}' didn't set/clear any bits!".format(
                    one_feature.feature
                ))

            # Apply them to the bitstream
            for bit in bits:
                address = bit.idx + offset

                # Check for conflict
                if address in self.features_by_bits:
                    if key in self.features_by_bits[address] and \
                       bit.val != self.bitstream[address]:

                        new_bit_act = "set" if bit.val else "clear"
                        org_bit_act = "set" if self.bitstream[address] else "cleared"

                        # Format the error message
                        msg = "The line '{}' wants to {} bit {} already {} by the line '{}'".format(
                            set_feature.feature,
                            new_bit_act,
                            bit.id,
                            org_bit_act,
                            key
                        )
                        raise self.FeatureConflict(msg)
                else:
                    self.features_by_bits[address] = set()

                # Set/clear the bit
                self.bitstream[address] = bit.val
                self.features_by_bits[address].add(key)


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

    def disassemble_bitstream(self, bitstream, emit_unset=False):
        """
        Disassembles a bistream.
        """
        features = []

        def emit_feature(feature):
            if emit_unset:
                features.append(full_name + "=1'b{}".format(int(value)))
            else:
                features.append(full_name)

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

            for feature, bits in segbits.items():

                # Match
                value = self.match_segbits(bits, offset)
                if not value and not emit_unset:
                    continue

                # Emit
                full_name = prefix + "." + feature
                emit_feature(full_name)

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

                for feature, bits in segbits.items():

                    # Match
                    value = self.match_segbits(bits, offset)
                    if not value and not emit_unset:
                        continue

                    # Emit
                    full_name = prefix + "." + feature
                    emit_feature(full_name)

        return features

# =============================================================================


def fasm_to_bitstream(args, database):
    """
    Implements FASM to bitstream flow
    """

    logging.info("Assembling bitstream from FASM...")

    # Load and parse FASM
    fasm_lines = fasm.parse_fasm_filename(args.i)

    # Assemble
    assembler = QlfFasmAssembler(database)
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
        bitstream = FourByteBitstream.from_file(args.i)
    else:
        assert False, args.format

    # Disassemble
    logging.info("Disassembling bitstream...")
    disassembler = QlfFasmDisassembler(database)
    features = disassembler.disassemble_bitstream(
        bitstream.to_bits(database),
        args.unset_features
    )

    # Write FASM file
    logging.info("Writing FASM file...")
    with open(args.o, "w") as fp:
        for feature in features:
            fp.write(feature + "\n")

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
        "--device",
        type=str,
        choices=["qlf_k4n8"],
        default=None,
        help="Device name"
    )
    parser.add_argument(
        "--db-root",
        type=str,
        default=None,
        help="FASM database root path, required when --device is not given"
    )
    parser.add_argument(
        "--unset-features",
        action="store_true",
        help="When disassembling write cleared FASM features as well"
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

    # Determine device database path
    if args.db_root is not None:
        db_root = args.db_root
    elif args.device is not None:
        db_root = DATABASES[args.device]
    else:
        logging.critical("Please provide either '--device' or '--db-root' option")
        exit(1)

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
    database = Database(db_root)

    if action == "fasm2bit":
        fasm_to_bitstream(args, database)

    elif action == "bit2fasm":
        bitstream_to_fasm(args, database)

    else:
        assert False, action

# =============================================================================


if __name__ == "__main__":
    main()
