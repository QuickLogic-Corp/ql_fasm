FASM to/from bitstream converter for QuickLogic qlf FPGA device family
======================================================================

Installation
------------

The utility and is enclosed in a Python module namd ``qlf_fasm``. To install it directly from the GitHub repository run::

    pip3 install git+https://github.com/QuickLogic-Corp/ql_fasm.git

The tool can be invoked directly from a cloned repository without installation. For that one may run::

    cd <path_to_the_cloned_repository>
    python3 -m qlf_fasm <options>

FASM to/from bitstream conversion
---------------------------------

Invoke the ``qlf_fasm`` utility, provide it with a path to a device database along with input and output file name. The tool automatically determines the conversion direction basing on file name extensions. A FASM file name must end with ``.fasm`` while a bitstream file on ``.bit`` or ``.bin``.

For example::

   qlf_fasm --db-root <path_to_device_database> design.fasm bitstream.bit
   qlf_fasm --db-root <path_to_device_database> bitstream.bit disassembled.fasm

More options are documented in the utility help available by running it with ``-h`` option::

   usage: qlf_fasm [-h] [-f {txt,4byte}] [-a] [-d] --db-root DB_ROOT
                   [--unset-features]
                   [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                   i o
   
   QuickLogic qlf-series FPGA FASM to bitstream and bitstream to FASM conversion
   utility.
   
   positional arguments:
     i                     Input file (FASM or bitstream)
     o                     Output file (FASM or bitstream)
   
   optional arguments:
     -h, --help            show this help message and exit
     -f {txt,4byte}, --format {txt,4byte}
                           Binary bitstream format (def. '4byte')
     -a, --assemble        Force FASM to bitstream conversion regardless of file
                           extensions
     -d, --disassemble     Force bitstream to FASM conversion regardless of file
                           extensions
     --db-root DB_ROOT     FASM database root path
     --unset-features      When disassembling write cleared FASM features as well
     --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                           Log level (def. "WARNING")
