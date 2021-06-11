import sys
import os
import tempfile

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from qlf_fasm.qlf_fasm import main as qlf_main

# =============================================================================


def test_feature_conflict(monkeypatch):

    basedir = os.path.dirname(__file__)
    db_root = os.path.join(basedir, "data", "testdb")

    with tempfile.TemporaryDirectory() as tempdir:

        # Prepare a FASM file
        fasm_file = os.path.join(tempdir, "input.fasm")
        with open(fasm_file, "w") as fp:
            fp.write("fpga_top.grid_clb_0__0_.LUT_INIT[1:0]=2'b01\n")
            fp.write("fpga_top.grid_clb_0__0_.LUT_INIT[0]=1'b0\n")

        # Invoke fasm to bitstream conversion
        bit_file = os.path.join(tempdir, "output.bit")
        monkeypatch.setattr(
            "sys.argv",
            [
                "qlf_fasm.py",
                "--db-root", db_root,
                "-a",
                "-f", "txt",
                fasm_file,
                bit_file
            ]
        )

        # Expect failure
        with pytest.raises(SystemExit) as ex:
            qlf_main()
        assert ex.value.code == -1


def test_bit_conflict(monkeypatch):

    basedir = os.path.dirname(__file__)
    db_root = os.path.join(basedir, "data", "testdb")

    with tempfile.TemporaryDirectory() as tempdir:

        # Prepare a FASM file
        fasm_file = os.path.join(tempdir, "input.fasm")
        with open(fasm_file, "w") as fp:
            fp.write("fpga_top.sb_0__0_.ROUTING.SEL0\n")
            fp.write("fpga_top.sb_0__0_.ROUTING.NOT_SEL0\n")

        # Invoke fasm to bitstream conversion
        bit_file = os.path.join(tempdir, "output.bit")
        monkeypatch.setattr(
            "sys.argv",
            [
                "qlf_fasm.py",
                "--db-root", db_root,
                "-a",
                "-f", "txt",
                fasm_file,
                bit_file
            ]
        )

        # Expect failure
        with pytest.raises(SystemExit) as ex:
            qlf_main()
        assert ex.value.code == -1
