FASM to/from bitstream converter for QuickLogic qlf FPGA device family
======================================================================

Installation
------------

Both the utility and device database(s) is enclosed in a Python module namd ``qlf_fasm``. To install it directly from the GitHub repository run::

    pip3 install git+https://github.com/QuickLogic-Corp/ql_fasm.git

FASM to/from bitstream conversion
---------------------------------

Invoke the ``qlf_fasm.py`` utility script, provide it with a path to a device database along with input and output file name. The tool automatically determines the conversion direction basing on file name extensions. A FASM file name must end with ``.fasm`` while a bitstream file on ``.bit`` or ``.bin``.

For example::

   qlf_fasm --device qlf_k4n8 design.fasm bitstream.bit
   qlf_fasm --device qlf_k4n8 bitstream.bit disassembled.fasm

Database generation
-------------------

To generate a FASM database for a QuickLogic qlf device, a fabric-dependent bitstream in XML format is required.

The ``qlf_fasm_db_builder.py`` script identifies all the bits contained within it and converts them to a compact representation that can be stored and used by the ``qlf_fasm`` utility.

Please refer to the help for the script's helper for more details.
