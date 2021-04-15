#!/usr/bin/env python3
import os
import sys
import tempfile
import subprocess

# =============================================================================


def test_bitstream_roundtrip():
    """
    Bitstream -> FASM -> bitstream round-trip test
    """

    basedir = os.path.dirname(__file__)
    qlf_fasm = os.path.join(basedir, "..", "qlf_fasm", "qlf_fasm.py")

    with tempfile.TemporaryDirectory() as tempdir:

        # Disassemble the bitstream
        database = os.path.join(basedir, "..", "qlf_fasm", "database", "qlf_k4n8")
        bitstream1 = os.path.join(basedir, "data", "qlf_k4n8-counter.bit")
        fasm1 = os.path.join(tempdir, "fasm1.fasm")

        args = "{} --db-root {} {} {}".format(
            qlf_fasm,
            database,
            bitstream1,
            fasm1
        )
        subprocess.call(args, shell=True)

        # Assemble the FASM back to bitstream
        bitstream2 = os.path.join(tempdir, "bitstream2.bit")
        args = "{} --db-root {} {} {}".format(
            qlf_fasm,
            database,
            fasm1,
            bitstream2
        )
        subprocess.call(args, shell=True)

        # Disassemble to FASM again
        fasm2 = os.path.join(tempdir, "fasm2.fasm")
        args = "{} --db-root {} {} {}".format(
            qlf_fasm,
            database,
            bitstream2,
            fasm2
        )
        subprocess.call(args, shell=True)

        # Compare both FASM files
        with open(fasm1, "r") as fp:
            fasm_lines1 = fp.readlines().sort()
        with open(fasm2, "r") as fp:
            fasm_lines2 = fp.readlines().sort()

        assert fasm_lines1 == fasm_lines2
