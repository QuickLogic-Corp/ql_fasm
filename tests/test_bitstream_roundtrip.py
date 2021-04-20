#!/usr/bin/env python3
import os
import sys
import tempfile
import subprocess
import tarfile

# =============================================================================


def bitstream_roundtrip(bitstream_file, bitstream_format):
    """
    Bitstream -> FASM -> bitstream round-trip test
    """

    basedir = os.path.dirname(__file__)
    qlf_fasm = "python3 -m qlf_fasm"

    with tempfile.TemporaryDirectory() as tempdir:

        # Unpack the bitstream
        bitstream = os.path.join(basedir, "data", bitstream_file)
        tar = tarfile.open(name=bitstream, mode="r:gz")
        tar.extractall(path=tempdir)

        # Disassemble the bitstream
        database = os.path.join(basedir, "..", "qlf_fasm", "database", "qlf_k4n8")
        bitstream1 = os.path.join(tempdir, os.path.basename(bitstream).replace(".tar.gz", ""))
        fasm1 = os.path.join(tempdir, "fasm1.fasm")

        args = "{} --db-root {} {} {} -d -f {}".format(
            qlf_fasm,
            database,
            bitstream1,
            fasm1,
            bitstream_format
        )
        subprocess.call(args, shell=True)

        # Assemble the FASM back to bitstream
        bitstream2 = os.path.join(tempdir, "bitstream2.bit")
        args = "{} --db-root {} {} {} -a -f {}".format(
            qlf_fasm,
            database,
            fasm1,
            bitstream2,
            bitstream_format
        )
        subprocess.call(args, shell=True)

        # Disassemble to FASM again
        fasm2 = os.path.join(tempdir, "fasm2.fasm")
        args = "{} --db-root {} {} {} -d -f {}".format(
            qlf_fasm,
            database,
            bitstream2,
            fasm2,
            bitstream_format
        )
        subprocess.call(args, shell=True)

        # Compare both FASM files
        with open(fasm1, "r") as fp:
            fasm_lines1 = fp.readlines().sort()
        with open(fasm2, "r") as fp:
            fasm_lines2 = fp.readlines().sort()

        assert fasm_lines1 == fasm_lines2


def test_txt_bitstream_roundtrip():
    bitstream_roundtrip("qlf_k4n8-counter.bit.tar.gz", "txt")

def test_4byte_bitstream_roundtrip():
    bitstream_roundtrip("qlf_k4n8-and.hex.tar.gz", "4byte")
