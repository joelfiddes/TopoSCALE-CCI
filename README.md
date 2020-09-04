# TopoSCALE-CCI
TopoSCALE downscaling for the ESA CCI global permafrost model

# Description:

# Example:

```
python tscale_cci_run.py "/home/joel/sim/cci_perm_final/sebs_coords.txt"  "/home/joel/sim/cci_perm_final/era5" "/home/joel/sim/cci_perm_final/era5/out" 1980 1980
```
# Details

## coordinates file format

A comma separted ascii file with 3 columns "longitude,latitude,elevation" in that order (nb: no header) eg:

> 178.55413,16.062615,208.4555
> 178.545797,16.051085,270.42717
> 178.537463,16.039572,345.13469
> 178.52913,16.028075,75.857465
> 178.520797,16.016595,0.036243933



## ERA5 input files
- Single parameter annuanl global files produced by "era5_request_CCI.py ", naming convention: 
	- PLEV_ERA5PARNAME_YEAR.nc
	- SURF_ERA5PARNAME_YEAR.nc


> PLEV_geopotential_1980.nc         SURF_2m_dewpoint_temperature_1980.nc      SURF_instantaneous_surface_sensible_heat_flux_1980.nc
> PLEV_relative_humidity_1980.nc    SURF_2m_temperature_1980.nc               SURF_surface_solar_radiation_downwards_1980.nc
> PLEV_temperature_1980.nc          SURF_friction_velocity_1980.nc            SURF_surface_thermal_radiation_downwards_1980.nc
> PLEV_u_component_of_wind_1980.nc  SURF_geopotential_1980.nc                 SURF_TOA_incident_solar_radiation_1980.nc
> PLEV_v_component_of_wind_1980.nc  SURF_instantaneous_moisture_flux_1980.nc  SURF_Total_precipitation_1980.nc



## Input NetCDF format

Standard ERA5 NetCDF format

```
[fiddes@login-3.SAGA ~/nn9606k/era5]$ ncdump -h SURF_2m_temperature_1980.nc 
netcdf SURF_2m_temperature_1980 {
dimensions:
	longitude = 1440 ;
	latitude = 721 ;
	time = 1464 ;
variables:
	float longitude(longitude) ;
		longitude:units = "degrees_east" ;
		longitude:long_name = "longitude" ;
	float latitude(latitude) ;
		latitude:units = "degrees_north" ;
		latitude:long_name = "latitude" ;
	int time(time) ;
		time:units = "hours since 1900-01-01 00:00:00.0" ;
		time:long_name = "time" ;
		time:calendar = "gregorian" ;
	short t2m(time, latitude, longitude) ;
		t2m:scale_factor = 0.0019369995756104 ;
		t2m:add_offset = 260.62106366574 ;
		t2m:_FillValue = -32767s ;
		t2m:missing_value = -32767s ;
		t2m:units = "K" ;
		t2m:long_name = "2 metre temperature" ;

// global attributes:
		:Conventions = "CF-1.6" ;
		:history = "2019-11-15 02:52:33 GMT by grib_to_netcdf-2.14.0: /opt/ecmwf/eccodes/bin/grib_to_netcdf -o /cache/data0/adaptor.mars.internal-1573786171.4555001-10939-16-686e4b7d-fce8-4399-a243-f8135543b018.nc /cache/tmp/686e4b7d-fce8-4399-a243-f8135543b018-adaptor.mars.internal-1573786171.4562213-10939-8-tmp.grib" ;
}
```

## Output NetCDF format

The output is a set of single parameter 9 day NetCDF with the following naming convention:

> PARAMETER_TIMEPERIOD_YEAR.nc 

eg.

> lwin_1_1980.nc  prate_1_1980.nc  shum_1_1980.nc  swin_1_1980.nc  t_1_1980.nc  ws_1_1980.nc
> lwin_2_1980.nc  prate_2_1980.nc  shum_2_1980.nc  swin_2_1980.nc  t_2_1980.nc  ws_2_1980.nc



## NetCDF dimensions
- long amd lat are named as dimensions but do not exist. 
- Each point is indexed as 1:Npoints corresponding to order in coordinates file
- time is in hours since start of period
- time step is 6h

```
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


```