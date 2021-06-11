import sys
import os
import tempfile
import tarfile

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from qlf_fasm.qlf_fasm import main as qlf_main

# =============================================================================


def test_default_bitstream(monkeypatch):

    basedir = os.path.dirname(__file__)
    db_root = os.path.join(basedir, "data", "testdb")

    fasm_in = os.path.join(basedir, "data", "test-overlay.fasm")
    hex_ref = os.path.join(basedir, "data", "test-overlay.hex")

    with tempfile.TemporaryDirectory() as tempdir:

        # Assemble
        hex_out = os.path.join(tempdir, "out.fasm")
        monkeypatch.setattr(
            "sys.argv",
            [
                "qlf_fasm.py",
                "--db-root", db_root,
                "-a",
                "-f", "4byte",
                fasm_in,
                hex_out
            ]
        )
        qlf_main()

        # Compare
        with open(hex_out, "r") as fp:
            lines_out = list(fp.readlines())
        with open(hex_ref, "r") as fp:
            lines_ref = list(fp.readlines())

        assert len(lines_out) == len(lines_ref)
        for out, ref in zip(lines_out, lines_ref):
            assert out == ref
