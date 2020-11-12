#!/bin/bash
#SBATCH --account=nn9606k
#SBATCH --job-name=tscale
#SBATCH --time=1:00:0
#SBATCH --ntasks=1
#SBATCH --mem-per-cpu=4G

module purge
module load netcdf4-python/1.5.3-intel-2019b-Python-3.7.4
pip install --user numpy
pip install --user pandas


python tscale_cci_run.py  "/cluster/home/fiddes/coords.txt" "/cluster/home/fiddes/nn9606k/era5" "/cluster/home/fiddes/sebs_points/" 1980 1981
