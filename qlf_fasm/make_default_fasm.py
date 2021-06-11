#!/usr/bin/env python3
"""
This is a utility script used for preparation of default bitstreams. Give a
set of segbit feature names writes a FASM files with their full names
(instances).

Current limitations
 - Works only for tile features, not with switchbox (routing) features
 - Features can only be set to 1 (in case of multi-bit features).

"""
import argparse
import logging

from .database import Database
from .qlf_fasm import FEATURE_PREFIX

# =============================================================================


def main():

    # Parse arguments
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--features",
        type=str,
        required=True,
        help="A comma-separated list of segbits to be instanced"
    )
    parser.add_argument(
        "-o",
        type=str,
        default="default_bitstream.fasm",
        help="Output default FASM file"
    )
    parser.add_argument(
        "--db-root",
        type=str,
        required=True,
        help="FASM database root path"
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

    # Load the database
    database = Database(args.db_root)
    
    # Instantiate each segbit feature
    features = args.features.split(",")
    fasm_lines = []

    for feature in features:

        # Find the feature in available segbits
        feature = feature.strip()
        found = False

        for segbits_name, segbits in database.segbits.items():
            if feature in segbits:
                found = True
                logging.debug("Feature '{}' found in '{}'".format(feature, segbits_name))

                # Look for tiles that refer to this segbit set.
                for loc, tile in database.tiles.items():
                    if tile["type"] == segbits_name:

                        # Emit
                        prefix = "grid_{}_{}__{}_".format(tile["type"], *loc)
                        line = "{}.{}.{}".format(FEATURE_PREFIX, prefix, feature)
                        fasm_lines.append(line) 

        # An unknown feature
        if not found:
            logging.critical("Unknown FASM feature '{}'".format(feature))
            exit(-1)

    # Write out the FASM file
    with open(args.o, "w") as fp:
        for line in fasm_lines:
            fp.write(line + "\n")

# =============================================================================


if __name__ == "__main__":
    main()
