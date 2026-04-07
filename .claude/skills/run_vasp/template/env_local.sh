#!/bin/bash
# Local Environment Setup Template
# module purge
# module load intel/2021.4.0 mpi/2021.4.0 vasp/6.3.2
export OMP_NUM_THREADS=1
export I_MPI_FABRICS=shm:ofi