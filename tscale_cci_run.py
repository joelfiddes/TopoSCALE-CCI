"""
Description:
        TopoSCALE control script for CCI permafrost downscaling. 

Args:
         coords = coordinates input file (see details)
         eraDir = Directory containing ERA5 forcing files
         outDir = Directory to write output to
         startYear: start year YYYY
         endYear:  end year YYYY

Example:
        tscale_cci_run.py  "/cluster/home/fiddes/nn9606k/tscale/coordinates.dat" "/cluster/home/fiddes/nn9606k/era5" "/cluster/home/fiddes/nn9606k/tscale" 1980 2018
        python tscale_cci_run.py "/home/joel/sim/cci_perm_final/sebs_coords.txt"  "/home/joel/sim/cci_perm_final/era5" "/home/joel/sim/cci_perm_final/era5/out" 1980 1980

Details:
        - accepts assci list "coords" lon,lat,ele (no header) eg:

                        178.55413,16.062615,208.4555
                        178.545797,16.051085,270.42717
                        178.537463,16.039572,345.13469
                        178.52913,16.028075,75.857465
                        178.520797,16.016595,0.036243933

"""

# https://www.evernote.com/Home.action#n=cf913e83-0c04-469c-ae65-fab96083d751&s=s500&ses=4&sh=5&sds=2&x=addresses&

import sys
import tscale_cci
import datetime
import pandas as pd


def main(coords,eraDir, outDir,startYear, endYear):
        years= list(range(int(startYear),int(endYear)+1))

        for year in tqdm(years):
                print(year)
                startPeriods = pd.date_range(str(year)+'-01-01', periods=46, freq='8d')

                for startIndex in list(range(0,startPeriods.size)):

                        print(startIndex)
                        start=startPeriods[startIndex]
                        # always start last period at 23rd Dec to ensure 8 day period till 31 Dec
                        # python indexing (starts 0) so startIndex 45 == period 46
                        if startIndex==45:
                                start = str(year)+'-12-23'
                                t = pd.to_datetime(start)
                                end = t+datetime.timedelta(days=8)

                        if startIndex<45:
                                t = pd.to_datetime(start)
                                end = t+datetime.timedelta(days=9)



                        tscale_cci.main( coords,eraDir , outDir, str(start),  str(end), startIndex )



#===============================================================================
#       Calling Main
#===============================================================================
if __name__ == '__main__':
        coords = sys.argv[1]
        eraDir = sys.argv[2]
        outDir = sys.argv[3]
        startYear = sys.argv[4]
        endYear = sys.argv[5]
        
        main(coords, eraDir, outDir, startYear, endYear )
