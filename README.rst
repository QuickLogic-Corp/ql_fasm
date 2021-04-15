FASM to/from bitstream converter for QuickLogic qlf FPGA device family
======================================================================

FASM to/from bitstream conversion
---------------------------------

Invoke the ``qlf_fasm.py`` utility script, provide it with a path to a device database along with input and output file name. The tool automatically determines the conversion direction basing on file name extensions. A FASM file name must end with ``.fasm`` while a bitstream file on ``.bit`` or ``.bin``.

For example:
 - ``qlf_fasm.py --db-root qlf_fasm/database/qlf_k4n8 design.fasm bitstream.bit``
 - ``qlf_fasm.py --db-root qlf_fasm/database/qlf_k4n8 bitstream.bit disassembled.fasm``

Database generation
-------------------

To generate a FASM database for a QuickLogic qlf device a fabric-dependent bitstream in XML format is required. The ``qlf_fasm_db_builder.py`` scipt identifies all the bits contained within it and converts them to a compact representation that can be stored and used by the ``qlf_fasm`` utility. Please refer to the help for the script for more details.
