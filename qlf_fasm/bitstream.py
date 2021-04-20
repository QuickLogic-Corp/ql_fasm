#!/usr/bin/env python3
"""
Utility classes responsible for binary bitstream reading and writing from/to
various formats.
"""
import logging

# =============================================================================


class Bitstream():
    """
    A base class for reading/writing/storing binary bitstream
    """

    def __init__(self, init=0):
        self.bitstream = bytearray(init)

    @staticmethod
    def from_bits(raw_bitstream, database):
        """
        Encodes a raw bitstream
        """
        return Bitstream(raw_bits)

    @staticmethod
    def from_file(file_name):
        """
        Reads raw binary data from a file
        """

        with open(file_name, "rb") as fp:
            data = fp.read()

        bitstream = Bitstream()
        bitstream.bitstream = bytearray(data)

        return bitstream

    def to_bits(self, database):
        """
        Decodes a raw bitstream
        """
        return self.bitstream

    def to_file(self, file_name):
        """
        Writes data to a raw binary file
        """

        with open(file_name, "wb") as fp:
            fp.write(self.bitstream)


# =============================================================================


class TextBitstream(Bitstream):
    """
    Supports bitstreams represented as text consisting of "0" and "1" chars.
    """

    @staticmethod
    def from_bits(raw_bitstream, database):
        """
        Converts a raw bitstream to its encoded form
        """

        # Compute the expected total length with padding bits
        max_region = max(
            [region["length"] for region in database.regions.values()]
        )
        padded_length = max_region * len(database.regions)
    
        # Pad the bitstream - add trailing zeros to each chain (region) that is
        # shorter than the longest one.
        bitstream = bytearray(padded_length)
        for region_id, region in database.regions.items():
    
            dst_address = region_id * max_region
            src_address = region["offset"]
            length = region["length"]
    
            bitstream[dst_address:dst_address+length] = \
                raw_bitstream[src_address:src_address+length]

        # Return the object
        return TextBitstream(bitstream)

    @staticmethod
    def from_file(file_name):
        """
        Parses a textual bitstream file
        """

        # Read
        with open(file_name, "r") as fp:
            text = fp.read()
            text = text.strip()

        # Strip
        text = [c for c in text if not c.isspace()]

        # Parse
        bitstream = TextBitstream(len(text))
        for i in range(len(text)):

            if text[i] == "0":
                bitstream.bitstream[i] = 0
            elif text[i] == "1":
                bitstream.bitstream[i] = 1
            else:
                assert False, text[i]

        return bitstream

    def to_bits(self, database):
        """
        Decodes the bitstream and returns it as raw bits
        """

        # Compute the expected total length with padding bits
        max_region = max(
            [region["length"] for region in database.regions.values()]
        )
        padded_length = max_region * len(database.regions)
    
        # Verify length
        if len(self.bitstream) < padded_length:
            logging.error("ERROR: The bistream is too short ({} / {})".format(
                len(self.bitstream),
                padded_length
            ))
            # TODO: pad
    
        if len(self.bitstream) > padded_length:
            logging.warning("WARNING: {} extra trailing bits found ({} / {})".format(
                len(self.bitstream) - padded_length,
                len(self.bitstream),
                padded_length
            ))
            # TODO: trim
    
        # Remove padding bits
        bitstream = bytearray(database.bitstream_size)
        for region_id, region in database.regions.items():
    
            src_address = region_id * max_region
            dst_address = region["offset"]
            length = region["length"]
    
            bitstream[dst_address:dst_address+length] = \
                self.bitstream[src_address:src_address+length]

        # Return the raw bits
        return bitstream

    def to_file(self, file_name):
        """
        Writes a textual bitstram file
        """

        text = ""
        for bit in self.bitstream:
            if bit == 0:
                text += "0"
            else:
                text += "1"        

        with open(file_name, "w") as fp:
            fp.write(text + "\n")

# =============================================================================


class FourByteBitstream(Bitstream):
    """
    The "Four byte format" by QuickLogic.
    """

    def __init__(self, init):
        assert isinstance(init, list)
        assert len(init) == 32

        self.bit_planes = init

    @staticmethod
    def from_bits(raw_bitstream, database):
        """
        Converts a raw bitstream to its encoded form
        """

        # Compute the expected total length with padding bits
        total_length = max(
            [region["length"] for region in database.regions.values()]
        )

        # Separate chains into bit planes
        bit_planes = [bytearray(total_length) for i in range(32)]
        for region_id, region in database.regions.items():
    
            src_address = region["offset"]
            length = region["length"]
    
            bit_planes[region_id][:length] = \
                raw_bitstream[src_address:src_address+length]

        # Return the object
        return FourByteBitstream(bit_planes)

    @staticmethod
    def from_file(file_name):
        """
        Parses a textual bitstream file
        """

        # Read
        with open(file_name, "r") as fp:
            lines = fp.readlines()

        # Convert lines to a list of 32-bit words
        words = []
        for line in lines:

            line = line.strip()
            if not line:
                continue

            assert len(line) == 8, line
            words.append(int(line, 16))

        # Separate bit planes
        bit_planes = [bytearray(len(words)) for i in range(32)]
        for i, w in enumerate(words):
            for b in range(32):
                bit_planes[b][i] = (w & (1 << b)) != 0

        # Return the object
        return FourByteBitstream(bit_planes)

    def to_bits(self, database):
        """
        Decodes the bitstream and returns it as raw bits
        """

        # Compute the expected total length with padding bits
        max_region = max(
            [region["length"] for region in database.regions.values()]
        )
        padded_length = max_region
    
        # Verify length
        total_length = max([len(plane) for plane in self.bit_planes])

        if total_length < padded_length:
            logging.error("ERROR: The bistream is too short ({} / {})".format(
                total_length,
                padded_length
            ))
            # TODO: pad
    
        if total_length > padded_length:
            logging.warning("WARNING: {} extra trailing bits found ({} / {})".format(
                total_length - padded_length,
                total_length,
                padded_length
            ))
            # TODO: trim

        # Extract chains from bit planes
        bitstream = bytearray(database.bitstream_size)
        for region_id, region in database.regions.items():
    
            dst_address = region["offset"]
            length = region["length"]
    
            bitstream[dst_address:dst_address+length] = \
                self.bit_planes[region_id][:length]

        # Return bits
        return bitstream

    def to_file(self, file_name):
        """
        Writes a textual bitstram file
        """
        assert len(self.bit_planes) <= 32, len(self.bit_planes)

        # Initialize 4-byte words to be written
        total_length = max([len(plane) for plane in self.bit_planes])
        words = [0] * total_length

        # Assemble the bit planes into words
        for i in range(total_length):
            word = 0
            for b in range(len(self.bit_planes)):
                if self.bit_planes[b][i]:
                    word |= (1 << b)

            words[i] = word

        # Convert words to text
        text = "\n".join(["{:08X}".format(w) for w in words])
        with open(file_name, "w") as fp:
            fp.write(text + "\n")
