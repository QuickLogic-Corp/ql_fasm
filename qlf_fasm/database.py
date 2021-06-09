#!/usr/bin/env python3
"""
Classes for representing QLF device databases
"""
import os
import logging
import json
import re

# =============================================================================


class Bit():
    """
    A single bit / segbit. Has an index and a value.
    """

    def __init__(self, index, value):
        self.idx = index
        self.val = value

    @staticmethod
    def from_string(s):
        """
        Parses a string with a bit specification. This should be "[!]<index>".
        For example:
          - "!123"
          - "768"
        """

        s = s.strip()
        if s[0] == "!":
            value = False
            s = s[1:]
        else:
            value = True

        index = int(s)

        return Bit(index, value)

    def __str__(self):
        if self.val:
            return str(self.idx)
        else:
            return "!" + str(self.idx)

    def __repr__(self):
        return str(self)


class Database():
    """
    FASM database representation.
    """

    FEATURE_RE = re.compile(
        r"^(?P<feature>[^\[\]\s]+)(\[(?P<index>[0-9]+)\])?$"
    )

    def __init__(self, root=None):

        # Tiles indexed by grid location
        self.tiles = {}
        # Routing resources indexed by grid location and type
        self.routing = {}

        # Segbits (repeating bit patterns) per block type
        self.segbits = {}
        # Total bitstream length (in bits)
        self.bitstream_size = 0

        # Bit regions
        self.regions = {}

        # Default bitstream file name and format
        self.default_bitstream_file = None
        self.default_bitstream_format = None

        # Load the database
        if root is not None:
            self.load(root)

    def load(self, path):
        """
        Loads the database given its root directory
        """

        logging.info("Loading FASM database from '{}'".format(path))

        # Load the device file
        device_file = os.path.join(path, "device.json")
        logging.info(" " + device_file)
        with open(device_file, "r") as fp:
            json_root = json.load(fp)

        # Get the basic info
        configuration = json_root["configuration"]
        assert configuration["type"] == "scan_chain", configuration["type"]

        self.bitstream_size = int(configuration["length"])
        self.regions = {
            int(region["id"]): region for region in configuration["regions"]
        }

        # Get default bitstream file and format if any
        if "default_bitstream" in json_root:
            self.default_bitstream_file = os.path.join(path,
                json_root["default_bitstream"]["file"])
            self.default_bitstream_format = \
                json_root["default_bitstream"]["format"]

        # Sort tiles by their locations, load segbits
        for data in json_root["tiles"]:
            loc = (data["x"], data["y"])

            keys = ["type", "region", "offset"]
            tile = {k:v for k, v in data.items() if k in keys}

            assert loc not in self.tiles, (loc, self.tiles[loc], tile)
            self.tiles[loc] = tile

            segbits_name = tile["type"]
            if segbits_name not in self.segbits:

                segbits_file = os.path.join(
                    path, "segbits_{}.db".format(segbits_name)
                )
                self.segbits[segbits_name] = self.load_segbits(segbits_file)

        # Sort routing blocks by their locations, load segbits
        for data in json_root["routing"]:
            loc = (data["x"], data["y"])

            keys = ["type", "variant", "region", "offset"]
            sbox = {k:v for k, v in data.items() if k in keys}

            if loc not in self.routing:
                self.routing[loc] = {}

            assert sbox["type"] not in self.routing[loc], (loc, sbox["type"])
            self.routing[loc][sbox["type"]] = sbox

            segbits_name = "{}_{}".format(sbox["type"], sbox["variant"])
            if segbits_name not in self.segbits:

                segbits_file = os.path.join(
                    path, "segbits_{}.db".format(segbits_name)
                )
                self.segbits[segbits_name] = self.load_segbits(segbits_file)

    @staticmethod
    def load_segbits(file_name):
        """
        Loads segbits. Returns a dict indexed by FASM feature names containing
        segbit sets.
        """

        # Load the file
        logging.info(" " + file_name)
        with open(file_name, "r") as fp:
            lines = fp.readlines()

        # Parse segbits
        segbits = {}
        for line in lines:

            line = line.strip().split()
            if not line:
                continue

            assert len(line) >= 2, line

            feature = line[0]
            bits = [Bit.from_string(s) for s in line[1:]]

            assert feature not in segbits, feature
            segbits[feature] = tuple(bits)

        # Group multi-bit features together
        grouped_segbits = {}
        for tag, bits in segbits.items():

            # Get the base name and index
            match = Database.FEATURE_RE.fullmatch(tag)
            assert match is not None, tag

            feature = match.group("feature")
            index = match.group("index")

            if index is not None:
                index = int(index)

            # Group accordingly
            if feature not in grouped_segbits:
                grouped_segbits[feature] = {}

            grouped_segbits[feature][index] = bits

        return grouped_segbits


