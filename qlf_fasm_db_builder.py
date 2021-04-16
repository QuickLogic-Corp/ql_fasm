#!/usr/bin/env python3
"""
QLF FASM database builder. This script builds a FASM database from the
given QLF device fabric dependent bitstream file.
"""
import argparse
import os
import re
import json
import logging

from collections import OrderedDict

import lxml.etree as ET

# =============================================================================


def make_segbit_sets(bits_by_loc):
    """
    This functions identifies and creates segbits sets given a dict of tile
    bits present at specific grid locations.

    The assumption here is that identical items (tiles, switchboxtes etc.) have
    identical configuration bit patterns. These patterns exhibit offsets
    dependent on their positions in the bitstream.

    This function identifies repeating patterns that conform to this assumption
    and emits common bit patterns (a.k.a. segbits) and their offsets that
    correspond to grid locations
    """

    # First sort all bits by their names
    for loc in bits_by_loc.keys():
        bits_by_loc[loc] = sorted(bits_by_loc[loc], key=lambda bit: bit[2])

    locs = set(bits_by_loc.keys())
    segbit_sets = []

    while locs:

        # Pick a seed tile to be used for segbit pattern
        seed_loc = next(iter(locs))
        seed_bits = bits_by_loc[seed_loc]

        # Find bit offset of the seed tile
        seed_offset = min([bit[1] for bit in seed_bits])
        seed_segbits = [(bit[1] - seed_offset, bit[2]) for bit in seed_bits]

        # Verify the segbits pattern against all tiles in the grid that do
        # not have segbits assigned yet
        offsets = {}
        for loc in set(locs):
            bits = bits_by_loc[loc]

            # Compute offset and segbits
            regions = set([bit[0] for bit in bits])
            assert len(regions) == 1, (loc, regions)

            region = next(iter(regions))
            offset = min([bit[1] for bit in bits])
            segbits = [(bit[1] - offset, bit[2]) for bit in bits]

            # Check match and store
            if segbits == seed_segbits:
                offsets[loc] = (region, offset)

        # Must have at least 1 location
        assert offsets

        # Remove the locations with assigned segbits and add a new segbit set
        locs -= set(offsets.keys())

        # Make the segbit set
        segbit_sets.append((seed_segbits, offsets))
        

    return segbit_sets


def parse_fabric_bitstream(xml_root):
    """
    Parses fabric bitstream XML. Returns two dictionaries. The first one holds
    bits as (region_id, bit_id, name) grouped by tile / switchbox types and
    grid locations. The second one contains regions as (offset, length) indexed
    by their ids.
    """

    LOC_RE = re.compile(r"(?P<name>.+)_(?P<x>[0-9]+)__(?P<y>[0-9]+)_$")

    grouped_bits = {}
    regions = {}

    for xml_region in xml_root.findall("region"):
        region_id = int(xml_region.attrib["id"])

        region_min = None
        region_max = None

        for xml_bit in xml_region.findall("bit"):

            # FIXME: For now only "scan_chain" configuration is supported. Check
            # if the bitstream conforms to that
            assert not xml_bit.find("wl") and not xml_bit.find("bl") \
                   and not xml_bit.find("frame"), "Only \"scan_chain\" configuration is supported"

            # Get bit info
            bit_id = int(xml_bit.attrib["id"])
            feature = xml_bit.attrib["path"]

            # Parse the feature name to get tile type and grid coordinates
            parts = feature.split(".")
            assert parts[0] == "fpga_top", feature

            # Get grid location
            match = LOC_RE.fullmatch(parts[1])
            assert match is not None, feature

            loc = (int(match.group("x")), int(match.group("y")))
            name = match.group("name")

            # This bit refers to a block (tile)
            if name.startswith("grid_"):
                name = name.replace("grid_", "")

            # This bit refers to a routing interconnect
            else:
                name = name.split("_", maxsplit=1)[0]
                assert name in ["sb", "cbx", "cby"], feature

            # Store the bit
            if name not in grouped_bits:
                grouped_bits[name] = {}

            if loc not in grouped_bits[name]:
                grouped_bits[name][loc] = set()

            grouped_bits[name][loc].add((region_id, bit_id, ".".join(parts[2:])))

            # Determine bit region extent
            if region_min is None:
                region_min = bit_id
            else:
                region_min = min(region_min, bit_id)

            if region_max is None:
                region_max = bit_id
            else:
                region_max = max(region_max, bit_id)

        # Add region
        assert region_id not in regions, region_id
        regions[region_id] = (region_min, region_max - region_min + 1)

    return grouped_bits, regions

# =============================================================================


def main():

    # Parse arguments
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--fabric-bitstream",
        type=str,
        required=True,
        help="Fabric bitstream XML file"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="database",
        help="Output FASM database directory"
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

    # Read and parse the fabric bitstream XML techfile
    logging.info("Loading fabric-dependent bitstream ...")
    xml_tree = ET.parse(args.fabric_bitstream, ET.XMLParser(remove_blank_text=True))
    xml_bitstream = xml_tree.getroot()
    assert xml_bitstream is not None and xml_bitstream.tag == "fabric_bitstream"

    # Parse the bitstream, group bits and features
    grouped_bits, regions = parse_fabric_bitstream(xml_bitstream)

    # Count bits
    logging.info("Counting bits...")
    total_bits = 0

    logging.info(" {} regions:".format(len(regions)))
    for region_id, (offset, count) in regions.items():
        total_bits += count
        logging.debug("  region {:2d}: {} bits ({}-{})".format(
            region_id,
            count,
            offset,
            offset + count - 1
        ))

    logging.info(" {} bits in total".format(total_bits))

    # No bits
    if not total_bits:
        logging.critical("The bitstream contains no bits")
        exit(1)

    # Verify that all bits of a tile / switchbox belong to the same region.
    for tile_name, bits_at_loc in grouped_bits.items():
        for loc, bits in bits_at_loc.items():
            regs = set([bit[0] for bit in bits])
            assert len(regs) == 1, (tile_name, loc, regs)

    # Build segbits for each tile type
    logging.info("Building segbits database...")
    os.makedirs(args.output_dir, exist_ok=True)

    item_at_loc = {}
    total_bits_unflattened = 0

    for tile_type, bits_at_loc in grouped_bits.items():
        logging.debug(" " + tile_type)

        # Check if we have a tile or a switchbox / connection box
        if tile_type in ["sb", "cbx", "cby"]:
            item_type = tile_type
        else:
            item_type = "tile"

        # Build segbit sets
        segbit_sets = make_segbit_sets(bits_at_loc)

        logging.debug("  {} segbit sets:".format(len(segbit_sets)))
        for segbits, offsets in segbit_sets:
            logging.debug("   {} segbits, {} locations".format(len(segbits), len(offsets)))

        # A tile must not have more than one segbits set - tiles should be
        # identical independent of their location in the grid
        if item_type == "tile":
            assert len(segbit_sets) == 1, tile_type

        # Write segbit sets
        for i, (segbits, offsets) in enumerate(segbit_sets):

            # Segbits set suffix
            if len(segbit_sets) > 1:
                suffix = "_{}".format(i)
            else:
                suffix = ""

            # Store data to be written to the main device file
            if item_type not in item_at_loc:
                item_at_loc[item_type] = {}

            type = tile_type if item_type == "tile" else i
            for loc, (region, offset) in offsets.items():                
                assert loc not in item_at_loc[item_type], (type, loc)

                # Subtract region offset
                assert region in regions, region
                offset = offset - regions[region][0]
                assert offset >= 0, offset

                item_at_loc[item_type][loc] = (type, region, offset)

            # Write segbits file
            fname = os.path.join(args.output_dir, "segbits_{}{}.db".format(tile_type, suffix))
            with open(fname, "w") as fp:
                for offset, name in sorted(segbits, key=lambda s: s[0]):
                    fp.write("{} {}\n".format(name, offset))

            # Count bits
            total_bits_unflattened += len(segbits) * len(offsets)    

    # Check if we haven't lost any bits
    assert total_bits == total_bits_unflattened, (total_bits, total_bits_unflattened)

    # Format the device data
    logging.info("Formatting the device file...")
    device = OrderedDict()
    device["configuration"] = {
        "length": int(total_bits),
        "type": "scan_chain", # FIXME: For now only "scan_chain" is supported
        "regions": []
    }
    
    for region_id, (offset, count) in regions.items():
        device["configuration"]["regions"].append({
            "id": region_id,
            "offset": int(offset),
            "length": int(count),
        })

    device["tiles"] = []
    device["routing"] = []

    # Append tiles and routing
    for item_type in sorted(item_at_loc.keys()):
        items = item_at_loc[item_type]

        if item_type == "tile":
            for loc in sorted(items.keys(), key=lambda x:x[::-1]):
                (tile_type, region, offset) = items[loc]
                device["tiles"].append({
                    "type": tile_type,
                    "x": int(loc[0]),
                    "y": int(loc[1]),
                    "region": int(region),
                    "offset": int(offset),
                })

        else:
            for loc in sorted(items.keys(), key=lambda x:x[::-1]):
                (variant, region, offset) = items[loc]
                device["routing"].append({
                    "type": item_type,
                    "variant": int(variant),
                    "x": int(loc[0]),
                    "y": int(loc[1]),
                    "region": int(region),
                    "offset": int(offset),
                })

    # Write device data
    fname = os.path.join(args.output_dir, "device.json")
    with open(fname, "w") as fp:
        json.dump(device, fp, indent=2)

    logging.info("Done.")

if __name__ == "__main__":
    main()
