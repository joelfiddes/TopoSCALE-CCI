# TopoSCALE-CCI
TopoSCALE downscaling for the ESA CCI global permafrost model

# Description:

# Example:
python tscale_cci_run.py "/home/joel/sim/cci_perm_final/sebs_coords.txt"  "/home/joel/sim/cci_perm_final/era5" "/home/joel/sim/cci_perm_final/era5/out" 1980 1980

# Deatails

## coordinates file format


## ERA5 input files

## Output format

The output is a set of single parameter 9 day NetCDF with the following naming convention:

> PARAMETER_TIMEPERIOD_YEAR.nc 

eg.

> lwin_1_1980.nc  prate_1_1980.nc  shum_1_1980.nc  swin_1_1980.nc  t_1_1980.nc  ws_1_1980.nc
> lwin_2_1980.nc  prate_2_1980.nc  shum_2_1980.nc  swin_2_1980.nc  t_2_1980.nc  ws_2_1980.nc



## NetCDF dimensions
- long amd lat are named but do not exist. 
- an index of 1: N points exists instead
- time is in hours since start of period
- time step is 6h

'''' 
ncdump -c swin_1_1980.nc 
netcdf swin_1_1980 {
dimensions:
	lon = 27 ;
	lat = 27 ;
	time = 36 ;
variables:
	float lon(lon) ;
	float lat(lat) ;
	int time(time) ;
		time:units = "hours since 1980-01-01 00:00:00" ;
	float swin(lon, time) ;

// global attributes:
		:history = "Created by toposcale on " ;
data:

 lon = _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, 
    _, _, _, _ ;

 lat = _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, 
    _, _, _, _ ;

 time = 0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72, 78, 84, 90, 96, 
    102, 108, 114, 120, 126, 132, 138, 144, 150, 156, 162, 168, 174, 180, 
    186, 192, 198, 204, 210 ;
}

''''
