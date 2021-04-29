import sys
import os
import tempfile
import tarfile

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from qlf_fasm.qlf_fasm import main as qlf_main

# =============================================================================


@pytest.mark.skipif("QLF_FASM_DB_ROOT" not in os.environ, reason="QLF_FASM_DB_ROOT not set")
def test_force_bit(monkeypatch):

    basedir = os.path.dirname(__file__)
    db_root = os.environ.get("QLF_FASM_DB_ROOT", None)

    bitstream_tar = "qlf_k4n8-counter8.hex.tar.gz"
    force_bit_tar = "qlf_k4n8-counter8.force_bit.tar.gz"

    with tempfile.TemporaryDirectory() as tempdir:

        # Unpack the bitstream
        bitstream_tar = os.path.join(basedir, "data", bitstream_tar)
        tar = tarfile.open(name=bitstream_tar, mode="r:gz")
        tar.extractall(path=tempdir)

        # Disassemble the bitstream
        bitstream = os.path.join(tempdir, os.path.basename(bitstream_tar).replace(".tar.gz", ""))
        fasm_out = os.path.join(tempdir, "out.fasm")
        force_bit_out = os.path.join(tempdir, "out.force_bit")

        monkeypatch.setattr(
            "sys.argv",
            [
                "qlf_fasm.py",
                "--db-root", db_root,
                "-d",
                "-f", "4byte",
                bitstream,
                fasm_out
            ]
        )
        qlf_main()

        # Unpack the reference force_bit file
        force_bit_tar = os.path.join(basedir, "data", force_bit_tar)
        tar = tarfile.open(name=force_bit_tar, mode="r:gz")
        tar.extractall(path=tempdir)

        # Compare
        force_bit_ref = os.path.join(tempdir, os.path.basename(force_bit_tar).replace(".tar.gz", ""))

        with open(force_bit_out, "r") as fp:
            lines_out = sorted(list(fp.readlines()))
        with open(force_bit_ref, "r") as fp:
            lines_ref = sorted(list(fp.readlines()))

        assert len(lines_out) == len(lines_ref)
        for out, ref in zip(lines_out, lines_ref):
            assert out == ref
