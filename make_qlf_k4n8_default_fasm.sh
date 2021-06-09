#!/bin/bash
if [ -z "${QLF_FASM_DB_ROOT}" ]; then
    echo "ERROR: Please set the env. var. QLF_FASM_DB_ROOT to point to FASM database"
    exit -1
fi

set -e

# Build a set of IO mode features for one tile. Each tile contains 16 IOs
FEATURES=""
for i in {0..15}; do
  FEATURES+="logical_tile_io_mode_io__$i.logical_tile_io_mode_physical__iopad_0.logical_tile_io_mode_physical__iopad_mode_default__pad_0.IO_QL_CCFF_mem.mem_out"
  if [ "$i" -ne 15 ]; then
    FEATURES+=","
  fi
done

python3 -m qlf_fasm.make_default_fasm --log-level DEBUG --db-root ~/Repos/qlfpga-symbiflow-plugins/qlf_k4n8/fasm_database --features $FEATURES
python3 -m qlf_fasm --log-level DEBUG --db-root ~/Repos/qlfpga-symbiflow-plugins/qlf_k4n8/fasm_database -a default_bitstream.fasm default_bitstream.hex
