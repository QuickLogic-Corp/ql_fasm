#!/usr/bin/env python3
"""
Utility classes responsible for binary bitstream reading and writing from/to
various formats.
"""

# =============================================================================


class Bitstream():
    """
    A base class for reading/writing/storing binary bitstream
    """

    def __init__(self, init=0):
        self.bits = bytearray(init)

    @staticmethod
    def from_file(file_name):
        """
        Reads raw binary data from a file
        """

        with open(file_name, "rb") as fp:
            data = fp.read()

        bitstream = Bitstream()
        bitstream.bits = bytearray(data)

        return bitstream

    def to_file(self, file_name):
        """
        Writes data to a raw binary file
        """

        with open(file_name, "wb") as fp:
            fp.write(self.bits)


# =============================================================================


class TextBitstream(Bitstream):
    """
    Supports bitstreams represented as text consisting of "0" and "1" chars.
    """

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
                bitstream.bits[i] = 0
            elif text[i] == "1":
                bitstream.bits[i] = 1
            else:
                assert False, text[i]

        return bitstream

    def to_file(self, file_name):
        """
        Writes a textual bitstram file
        """

        text = ""
        for bit in self.bits:
            if bit == 0:
                text += "0"
            else:
                text += "1"        

        with open(file_name, "w") as fp:
            fp.write(text + "\n")
