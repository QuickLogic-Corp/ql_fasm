# FASM to/from bitstream converter for QuickLogic qlf FPGA device family

Currently done:
 * FASM database generation

Work in progress:
 * FASM to bitstream conversion
 * Bitstream to FASM disassembly

## Database generation

To generate a FASM database for a QuickLogic qlf device a fabric-dependent bitstream in XML format is required. The `qlf_fasm_db_builder.py` scipt identifies all the bits contained within it and converts them to a compact representation that can be stored and used by the `qlf_fasm` utility. Please refer to the help for the script for more details.
