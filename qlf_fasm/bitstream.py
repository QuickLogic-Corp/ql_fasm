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

    def __init__(self, init, checksums=None):
        assert isinstance(init, list)
        assert len(init) == 32

        self.bit_planes = init

        if checksums is not None:
            assert isinstance(checksums, tuple)
            self.head_crc = checksums[0]
            self.tail_crc = checksums[1]

        else:
            self.head_crc = None
            self.tail_crc = None

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
    def from_file(file_name, with_crc=True):
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

        # Extract checksums
        if with_crc:
            checksums = (words[0], words[1])
            words = words[2:]

        else:
            checksums = None

        # Reverse word order
        words = words[::-1]

        # Separate bit planes
        bit_planes = [bytearray(len(words)) for i in range(32)]
        for i, w in enumerate(words):
            for b in range(32):
                bit_planes[b][i] = (w & (1 << b)) != 0

        # Return the object
        return FourByteBitstream(bit_planes, checksums)

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

        # Reverse the word order
        words = words[::-1]

        # Append checksums if present
        if self.head_crc is not None and self.tail_crc is not None:
            words = [self.head_crc, self.tail_crc] + words

        # Convert words to text
        text = "\n".join(["{:08X}".format(w) for w in words])
        with open(file_name, "w") as fp:
            fp.write(text + "\n")

    @staticmethod
    def checksum(words, init=0):
        """
        Computes a checksum of a list of data words. Returns a tuple with the
        checksum complement and last state of the checksum accumulator.
        """

        # Initialize
        c0 = init & 0xFFFF
        c1 = init >> 16

        # Compute the checksum
        for w in words:
            hi = w >> 16
            lo = w & 0xFFFF

            c0 = (c0 + lo) & 0xFFFF
            c1 = (c0 + c1) & 0xFFFF

            c0 = (c0 + hi) & 0xFFFF
            c1 = (c0 + c1) & 0xFFFF

        # Compute the complement
        cb0 = 0x10000 - ((c0 + c1 ) & 0xFFFF)
        cb1 = 0x10000 - ((c0 + cb0) & 0xFFFF)

        return (cb1 << 16) | cb0, (c1 << 16) | c0

    def compute_checksums(self, database):
        """
        Computes pre-checksum (a.k.a. head checksum) and post-checksum (a.k.a.
        tail checksum. The database object is needed to get individual chain
        lengths.
        """

        total_length = max([len(plane) for plane in self.bit_planes])
        words = [0] * total_length

        # Assemble the bitstream into words for the head checksum
        for i in range(total_length):
            word = 0
            for b in range(len(self.bit_planes)):
                if self.bit_planes[b][i]:
                    word |= (1 << b)
            words[i] = word
        words = words[::-1]

        # Compute the head checksum
        head_crc, _ = FourByteBitstream.checksum(words)

        # Compute chain pad lengths
        pad_length = {region_id: total_length - region["length"] \
                      for region_id, region in database.regions.items()}

        # Assemble the bitstream into words for the tail checksum. This has
        # to encounter for the padding bits. In other words: chains are padded
        # from the other end.
        num_regions = len(database.regions)
        for i in range(total_length):
            word = 0
            for b in range(num_regions):
                ii = i - pad_length[b]
                if ii >= 0:
                    if self.bit_planes[b][ii]:
                        word |= (1 << b)
            words[i] = word
        words = words[::-1]

        # Compute the tail checksum.
        # FIXME: Apparently the first word is ignored and there is one
        # additional 0 at the end.
        crc_words = words[1:] + [0]
        tail_crc, _ = FourByteBitstream.checksum(crc_words)

        return head_crc, tail_crc

    def compute_and_set_checksums(self, database):
        """
        Computes checksums for the bitstream and stores them within the object
        """
        checksums = self.compute_checksums(database)

        self.head_crc = checksums[0]
        self.tail_crc = checksums[1]

    def validate_checksums(self, database):
        """
        Computes and validates checksums. Returns True/False depending on the
        validation status
        """
        assert self.head_crc is not None and self.tail_crc is not None

        checksums = self.compute_checksums(database)
        return checksums == (self.head_crc, self.tail_crc)
