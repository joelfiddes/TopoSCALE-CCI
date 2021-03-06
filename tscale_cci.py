"""
python 3

Description:
	Modified version of tscale3D.py specifically for CCI permafrost. 

Args:
	 coords = coordinates input file (see details)
	 eraDir = Directory containing ERA5 forcing files
	 outDir = Directory to write output to
	 startDT: start datetime YYYY-MM-DD HH:mm:ss
	 endDT:  end datetime YYYY-MM-DD HH:mm:ss
	 startIndex: Integer 0-46 indicating which annual 8day period to compute (given by tscale_cci_run.py)

Example:
	tscale_cci.py  
	"/home/joel/sim/cci_perm_final/coordinates.dat" 
	"/home/joel/sim/cci_perm_final/era5/"  
	"/home/joel/sim/cci_perm_final/era5/out/" 
	"1980-01-01 00:00:00" 
	"1980-01-10 00:00:00" 
	"0"

Details:
	- Accepts single timestep as argument.
	- Removes dependency on slp,asp,svf that are not avvailable in CCI. This effects LW (svf) and SWin (Horizon, selfshading)
	- accepts assci list "coords" lon,lat,ele (no header) eg:

			178.55413,16.062615,208.4555
			178.545797,16.051085,270.42717
			178.537463,16.039572,345.13469
			178.52913,16.028075,75.857465
			178.520797,16.016595,0.036243933

	- reads global single parameter files
	- writes 9 days netcdf results

"""

import sys
import os
import pandas as pd
import netCDF4 as nc
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from bisect import bisect_left
from bisect import bisect_right
import helper as hp
import solarGeom as sg


def calc_Pws(Tk):
	'''
	Water vapour saturation pressure, Pws in hPa
	
	Args:
		Air temp, K

	Details:
	constants valid for -20 - +50degC
	0.083% max error

	Ref:
	Eq.6 p5. HUMIDITY CONVERSION FORMULAS, Calculation formulas for humidity, Vaisala 2013
	'''

	m=7.591386
	A=6.116441
	Tn=240.7263
	Tc=Tk-273.15

	Pws = A* 10 **((m*Tc)/(Tc+Tn))
	return(Pws)

def calc_Pw(Pws, RH):
	'''
	Water vapour pressure. Pw in hPa
	
	Args:
		Pws, Water vapour saturation pressure hPa
		RH, rel humidity 0-100

	Ref:
	Eq.1 p3. HUMIDITY CONVERSION FORMULAS, Calculation formulas for humidity, Vaisala 2013
	'''
	#Check for RH scale it should be 0-100 not 0-1
	rhDividr=100
	if (np.max(RH)< 2): # range is 0-1
		rhDividr=1

	Pw = (RH/rhDividr) * Pws
	return(Pw)

def calc_AH(Pw, Tk):
	''' 
	Absolute humidity g/m3 

	C = Constant 2.16679 gK/J
	Pw =Vapour pressure in hPa 
	Tk = Temperature in K

	Ref:
	Eq.1 p3. HUMIDITY CONVERSION FORMULAS, Calculation formulas for humidity, Vaisala 2013
	'''

	C=2.16679
	Pw_pa=Pw*100
	AH = C * Pw_pa /Tk

	return (AH)


	# specific humidity calc
	temp = np.array(df.TA) *units('K')
	rh=np.array(df.RH) *units('percent')
	P=np.array(df.P) *units('Pa')

	dp = metpy.calc.dewpoint_from_relative_humidity(temp, rh*100)
	df["SH"] = metpy.calc.specific_humidity_from_dewpoint(dp, P)

def ah_gm3_To_ah_kgkg(ah_gm3,P_pa,Tk ):

	'''
	1.204kg is mass of m3 air parcel (density) under standard temperature and pressure 
	'''
	P0= 1013. #standard_pressure, hPa
	T0 = 293.15 #standard_pressure, K

	P_hpa = P_pa/100
	

	mass_of_m3_air = 1.204*(P_hpa/P0) * (T0/Tk) #calc density of air kg/m3 at given T/P

	# divide ah in g/m3 by new density to get AH in g/kg, 
	# divide by 1000 to get kg/kg
	AH_kgkg = (ah_gm3/mass_of_m3_air)/1000


	return(AH_kgkg)
	#https://hypertextbook.com/facts/2000/RachelChu.shtml

def rh2sh(Pw,P ):

	#' @title calculate specific humidity
	#' @description calculate specific humidity \eqn{q} based on partial water vapor pressure \eqn{e} under given atmospheric pressure \eqn{p}
	#' @param e partial water vapor pressure in Pascal (Pa)
	#' @param p atmospheric pressure in Pascal (Pa). The default is standard atmospheric pressure of 101325Pa.
	#' @return numeric specific humidity \eqn{q} (\eqn{kg/kg})
	#' @seealso \code{\link{WVP2}}, \code{\link{WVP2}}, \code{\link{AH}}, \code{\link{RH}}, \code{\link{MR}}.
	#' @author Jun Cai (\email{cai-j12@@mails.tsinghua.edu.cn}), PhD candidate from
	#' Department of Earth System Science, Tsinghua University
	#' @export
	#' @examples
	#' t <- 273.15
	#' Es <- SVP(t)
	#' e <- WVP2(70, Es)
	#' SH(e, p = 101325)
	Pw=Pw.transpose()
	Mw = 18.01528 # Molecular weight of water vapor g/mol
	Md = 28.9634 # Molecular weight of dry air g/mol
	k = Mw / Md
	q = k * Pw / (P - (1 - k) * Pw)
	return(q)

def main(coords,eraDir, outDir,startDT, endDT, startIndex):
	print(startDT)
	print(endDT)
	g=9.81 # geopotential constant
	tz=0 # timezone always utc0 for era5 data
	myyear = startDT.split('-')[0] 

	zp_file=eraDir+"/PLEV_geopotential_"+myyear+".nc"

	plevDict={
	eraDir+"/PLEV_temperature_"+myyear+".nc" : "t",
	eraDir+"/PLEV_u_component_of_wind_"+myyear+".nc": "u",
	eraDir+"/PLEV_v_component_of_wind_"+myyear+".nc": "v",
	eraDir+"/PLEV_relative_humidity_"+myyear+".nc" : "r"
	}

	surfDict={
	eraDir+"/SURF_2m_temperature_"+myyear+".nc" : "t2m",
	eraDir+"/SURF_2m_dewpoint_temperature_"+myyear+".nc": "d2m",
	eraDir+"/SURF_geopotential_"+myyear+".nc": "z",
	eraDir+"/SURF_surface_solar_radiation_downwards_"+myyear+".nc" : "ssrd",
	eraDir+"/SURF_surface_thermal_radiation_downwards_"+myyear+".nc" :"strd",
	eraDir+"/SURF_Total precipitation_"+myyear+".nc" : "tp",	# removed _
	eraDir+"/SURF_TOA incident solar radiation_"+myyear+".nc": "tisr"
	}

	# read in lispoints
	lpin=pd.read_csv(coords, header=None)

	# make out path for results
	out = outDir
	if not os.path.exists(out):
		os.makedirs(out)

	# time stuff
	f = nc.Dataset(zp_file)
	nctime = f.variables['time']
	dtime = pd.to_datetime(nc.num2date(nctime[:],nctime.units, calendar="standard", only_use_cftime_datetimes=False,
                         only_use_python_datetimes=True))

	if (np.array(np.where(dtime==startDT)).size==0):
		sys.exit( "SYSTEMEXIT:Start date not in netcdf, end of timeseries")

	starti = np.where(dtime==startDT)[0].item() # so can run on a single timestep
	print(endDT)
	if (np.array(np.where(dtime==endDT)).size==0):
		sys.exit( "SYSTEMEXIT: End date not in netcdf, end of timeseries")
		
	endi = np.where(dtime==endDT)[0].item()
	year = dtime.year[0] 

	# compute timestep before we cut timeseries
	a=dtime[2]-dtime[1]
	step = a.seconds
	stephr=step/(60*60)
	# extract timestep
	dtime= dtime[starti:endi,] 

	print(("Running timestep "+ str(startDT)))

	#===============================================================================
	# tscale3d - 3D interpolation of pressure level fields
	#===============================================================================
	ele= lpin.iloc[:,2]#[:,3]
	lats = lpin.iloc[:,0]#[:,2] #[s['lat'] for s in stations]
	lons = lpin.iloc[:,1] +180 #[:,1] #[s['lon'] for s in stations] convert -180-180 to 0-360 

	lp = hp.Bunch(ele=ele, lat=lats, lon=lons)
	
	out_xyz_dem = np.asarray([lats,lons,ele*g],order="F" ).transpose()

	# init gtob object
	gtob = hp.Bunch(time=dtime)

	for plev in plevDict:

		t= nc.Dataset(plev) # key is filename
		varname=plevDict[plev] # value of key is par shortname
		z=nc.Dataset(zp_file) 

		# init grid stack
		xdim=out_xyz_dem.shape[0]
		sa_vec = np.zeros(xdim)
		#names=1:n

		for timestep in range(starti, endi):

			"""
	        Return original grid temperatures and geopotential of differnet
	        pressure levels. The function are called by inLevelInterp() to
	        get the input ERA5 values.
	        
	        Args: 
	            variable: Given interpolated climate variable
	            timestep: Time need to be interpolated. Time is in interger (e.g.
	            0, 1, 2)
	            
	        Returns:
	            gridT: Grid temperatures of different pressure levels. Retruned 
	            temperature are formated in [level, lat, lon]
	            gridZ: Grid geopotential of different pressure levels. Retruned 
	            temperature are formated in [level, lat, lon]
	            gridLon: Grid longitude of pressure level variables
	            gridLat: Grid latitude of pressure level variables
	        
	        Example:
	            gridT,gridZ,gridLat,gridLon=downscaling.gridValue('Temperature',0)
	            
			"""

			gridT = t.variables[varname][timestep,:,:,:]
			gridZ = z.variables['z'][timestep,:,:,:]
			gridLat = t['latitude'][:] # coords of grid centre https://confluence.ecmwf.int/display/CKB/ERA5%3A+What+is+the+spatial+reference
			gridLat = gridLat[::-1] # reverse to deal with ERA5 order
			gridLon = t['longitude'][:] # coords of grid centre https://confluence.ecmwf.int/display/CKB/ERA5%3A+What+is+the+spatial+reference
			gridLev = t.variables['level'][::-1] 
	        #return gridT,gridZ,gridLat,gridLon

			"""
			This is a 2D interpolatation, and returns interpolated temperatures
			of different pressure levels.

			Interpolated domain is smaller than original domain - original (ERA5) domain
			should be one cell larger than expected point or grid domain.

			Args:
			    gridT: Grid temperatures of different pressure levels. Retruned 
			        temperature are formated in [level, lat, lon]
			    gridZ: Grid geopotential of different pressure levels. Retruned 
			        temperature are formated in [level, lat, lon]
			    gridLat: Grid longitude of pressure level variables
			    gridLon: Grid latitude of pressure level variables
			    out_xyz: Given sites, which will be interpolated.
			    
			Returns:
			    t_interp: Interpolated temperatre of different pressure levels. 
			        The returned values are fomrated in [level, lat, lon]
			    z_interp: Interpolated geopotential of different pressure levels. 
			        The returned values are fomrated in [level, lat, lon]

			Examples:
			    downscaling = downscaling(dem, geop, sa, pl)

			    out_xyz_dem, lats, lons, shape = downscaling.demGrid()
			    out_xyz_sur = downscaling.surGrid(lats, lons, None)

			    #interpolate 2-meter temperature
			    surTa = downscaling.surTa(0, out_xyz_sur)
			    #original ERA-I values
			    gridT,gridZ,gridLat,gridLon = downscaling.gridValue(variable,0)
			    #interpolate temperatures and geopotential of different 
			    pressure levels.

			    t_interp, z_interp = downscaling.inLevelInterp(gridT,gridZ,
			                                                   gridLat,gridLon,
			                                                   out_xyz_dem)
			"""



			shape = gridT.shape
			#create array to hold interpolation resultes
			t_interp = np.zeros([shape[0], len(out_xyz_dem)])
			z_interp = np.zeros([shape[0], len(out_xyz_dem)]) # HOW MANY TIMES DO WE REALLY NEED TO COMPUTE THIS?

			#temperatue and elevation interpolation 2d
			for i in range(shape[0]):
				ft = RegularGridInterpolator((gridLat,gridLon), 
			                                  gridT[i,::-1,:], 'linear', bounds_error=False)
				fz = RegularGridInterpolator((gridLat,gridLon), 
			                                  gridZ[i,::-1,:], 'linear', bounds_error=False)
				t_interp[i,:] = ft(out_xyz_dem[:,:2] )#temperature

				z_interp[i,:] = fz(out_xyz_dem[:,:2])#elevation

				# invert pressure levels
				#t_interp = t_interp[::-1,:]
				#z_interp = z_interp[::-1,:]

				"""This is a 1D interpoation. The function return interpolated 
				upper air temperature at the given sites by 
				interpolation between different pressure levels.
				"""
			ele = out_xyz_dem[:,2]
			size = np.arange(out_xyz_dem.shape[0])
			n = [bisect_left(z_interp[:,i], ele[i]) for i in size]
			n = [x+1 if x == 0 else x for x in n]

			lowN = [l-1 for l in n]

			upperT = t_interp[n,size]
			upperZ = z_interp[n,size]
			dG  = upperT-t_interp[lowN,size]#<0
			dG /= upperZ-z_interp[lowN,size]#<0
			dG *= out_xyz_dem[:,2] - upperZ#>0
			dG += upperT
			     
			pl_obs=dG


			sa_vec=np.column_stack((sa_vec,pl_obs))
		
		# drop init row
		sa_vec =sa_vec[:,1:]
		# rename to variable
		setattr( gtob, varname, sa_vec)
	print("t,r,u,v done")
	#===============================================================================
	# tscale2d - Generates 2D interpolations from coarse (ERA5) to fine (1km) grid
	#===============================================================================
	gsob = hp.Bunch(dtime=dtime)
	# init grid stack
	xdim=shape[0]
	sa_vec = np.zeros((xdim))

	for surf in surfDict:
		
		t= nc.Dataset(surf) # key is filename
		varname=surfDict[surf] # value of key is par shortname
		z=nc.Dataset(zp_file) # could be outside loop

		# init grid stack
		xdim=out_xyz_dem.shape[0]
		sa_vec = np.zeros(xdim)
		
		#names=1:n
		for timestep in range(starti, endi):

			"""
			2D interpolated of surface firelds.
				Args:
					timestep: Timestep of interpolation as an interger (index)
					stations: pandas dataframe of input station csv file (id,lon,lat,ele)
					var: surface variarble eg "ssrd"
				Returns:
					t_sp: 2D interpolation of ERA surface field to stations points

				Example:
					surTa = ds.surTaPoint(0, mystations, 't2m')
			"""
			# read in data from variable 'varname'
			in_v = t[varname][timestep,:,:]#geopotential
			in_v=in_v[::-1,:] # reverse latitude dimension to agree with ascending 'lat'
			lat = t.variables['latitude'][:]
			lat=lat[::-1] # must be ascending for RegularGridInterpolator
			lon = t.variables['longitude'][:]

			# 2d interpolation
			f_sa = RegularGridInterpolator((lat,lon), in_v, 'linear', bounds_error=False)
			out_xy = np.asarray([lats,lons]).T
			sa_t = f_sa(out_xy) 

			# stack timepoint to existing
			sa_vec=np.column_stack((sa_vec,sa_t))

		# drop init row
		sa_vec =sa_vec[:,1:]

		# Add to gsob
		setattr( gsob, varname, sa_vec)



	print("Made a sob")
	#===============================================================================
	# Conversions
	#===============================================================================


	""" convert tp from m/timestep (total accumulation over timestep) to rate in mm/h 

				Args:
					step: timstep in seconds (era5=3600, ensemble=10800)

				Note: both EDA (ensemble 3h) and HRES (1h) are accumulated over the timestep
				and therefore treated here the same.
			https://confluence.ecmwf.int/display/CKB/ERA5+data+documentation
	"""
	tphrm = gsob.tp #/step*60*60 # convert metres per timestep (in secs) -> m/hour 
	gsob.pmmhr = tphrm	*1000 # m/hour-> mm/hour

	""" Convert SWin from accumulated quantities in J/m2 to 
	instantaneous W/m2 see: 
	https://confluence.ecmwf.int/pages/viewpage.action?pageId=104241513

	Args:
		step: timstep in seconds (era5=3600, ensemble=10800)

	Note: both EDA (ensemble 3h) and HRES (1h) are accumulated over the timestep
	and therefore treated here the same ie step=3600s (1h)
	https://confluence.ecmwf.int/display/CKB/ERA5+data+documentation
	"""
	gsob.strd = gsob.strd/3600  
	gsob.ssrd = gsob.ssrd/3600
	gsob.tisr = gsob.tisr/3600 

	gsob.gridEle=gsob.z[:,0]/g
	gtob.prate=gsob.pmmhr #*pcf # mm/hour
	gtob.psum=gsob.tp*1000*stephr #pcf mm/timestep
	print("conversions done")
	#===============================================================================
	# TopoSCALE
	#=============================================================================


	#===============================================================================
	# Precip
	#===============================================================================

	'''
	Args:
	fineEle:ele vector from station dataframe
	sob: contains gridEle, tp and dtime
	'''
	# convert TP to mm/hr

	# lookups = {
	# 	   1:0.35,
	# 	   2:0.35,
	# 	   3:0.35,
	# 	   4:0.3,
	# 	   5:0.25,
	# 	   6:0.2,
	# 	   7:0.2,
	# 	   8:0.2,
	# 	   9:0.2,
	# 	   10:0.25,
	# 	   11:0.3,
	# 	   12:0.35
	# }

	# # Precipitation lapse rate, varies by month (Liston and Elder, 2006).
	# pfis = gsob.dtime.month.map(lookups)
	# pfis = np.repeat(pfis.values[:,None], lp.ele.size, axis=1)

	# dz=(lp.ele-gsob.gridEle)/1e3  # Elevation difference in kilometers between the fine and coarse surface.

		   
	# pcf=(1+pfis.T*dz[:,None])/(1-pfis.T*dz[:,None])# Precipitation correction factor.
	#Pf=sob.pmmhr.T*lp



	#===============================================================================
	# Longwave
	#===============================================================================




	"""Convert to RH (should be in a function). Following MG Lawrence 
	DOI 10.1175/BAMS-86-2-225 """
	A1=7.625 
	B1=243.04 
	C1=610.94
	tc=gsob.t2m-273.15
	tdc=gsob.d2m-273.15
	tf=gtob.t-273.15 # fout.T
	c=(A1*tc)/(B1+tc)
	RHc=100*np.exp((tdc*A1-tdc*c-B1*c)/(B1+tdc)) # Inverting eq. 8 in Lawrence.

	""" Calculate saturation vapor pressure at grid and "subgrid" [also
	through function] using the Magnus formula."""

	svpf=C1*np.exp(A1*tf/(B1+tf))
	svpc=C1*np.exp(A1*tc/(B1+tc))

	"""
	Calculate the vapor pressure at grid (c) and subgrid (f).
	"""
	vpf=gtob.r*svpf/1e2 # RHf
	vpc=RHc*svpc/1e2

	"""
	Use the vapor pressure and temperature to calculate clear sky
	# emssivity at grid and subgrid. [also function]
	Konzelmann et al. 1994
	Ta in kelvin
	"""
	x1=0.43 
	x2=5.7
	cef=0.23+x1*(vpf/gtob.t)**(1/x2) #Pretty sure the use of Kelvin is correct.
	cec=0.23+x1*(vpc/gsob.t2m)**(1/x2)

	"""Diagnose the all sky emissivity at grid."""
	sbc=5.67e-8
	aec=gsob.strd/(sbc*gsob.t2m**4)
	# need to constrain to 1 as original code?

	""" 
	Calculate the "cloud" emissivity at grid, assume this is the same at
	subgrid.
	"""
	deltae=aec-cec

	""" 
	Use the former cloud emissivity to compute the all sky emissivity at 
	subgrid. 
	"""
	aef=cef+deltae
	gtob.lwin=aef*sbc*gtob.t**4


	print("Lwin done")
	#===============================================================================
	# make a pob - required as input to swin routine. This object is data on each 
	# pressure level interpolated to the fine grid ie has dimensions xy (finegrid) x plev
	#===============================================================================

	f = nc.Dataset(zp_file)
	lev = f.variables['level'][:]
	var='t'
	#	ds = rc.t3d( pl=plevfile, dem =demfile)
	#	out_xyz_dem, lats, lons, shape= ds.demGrid()
	xdim=lev.shape[0]
	ydim=out_xyz_dem.shape[0]  
	t_interp_out = np.zeros((xdim,ydim))
	z_interp_out = np.zeros((xdim,ydim))
		
	# for timestep in range(starti,endi):
	# 	gridT,gridZ,gridLat,gridLon=ds.gridValue(var,timestep)
	# 	t_interp, z_interp = ds.inLevelInterp(gridT,gridZ, gridLat,gridLon,out_xyz_dem)
	# 	t_interp_out = np.dstack((t_interp_out, t_interp))
	# 	z_interp_out = np.dstack((z_interp_out, z_interp))


	#======================= all this can be done in first instance need to gen t/z_interp_out additionally
	tfile = list(plevDict.keys())[list(plevDict.values()).index('t')] 
	t= nc.Dataset(tfile) # key is filename
	z=nc.Dataset(zp_file) # could be outside loop

	for timestep in range(starti, endi):

		gridT = t.variables['t'][timestep,:,:,:]
		gridZ = z.variables['z'][timestep,:,:,:]
		gridLat = t['latitude'][:]
		gridLat = gridLat[::-1] # reverse to deal with ERA5 order
		gridLon = t['longitude'][:]
		gridLev = t.variables['level'][::-1] 
		#return gridT,gridZ,gridLat,gridLon


		shape = gridT.shape
		#create array to hold interpolation resultes
		t_interp = np.zeros([shape[0], len(out_xyz_dem)])
		z_interp = np.zeros([shape[0], len(out_xyz_dem)]) # HOW MANY TIMES DO WE REALLY NEED TO COMPUTE THIS?

		#temperatue and elevation interpolation 2d
		for i in range(shape[0]):
			ft = RegularGridInterpolator((gridLat,gridLon), 
		                                  gridT[i,::-1,:], 'linear', bounds_error=False)
			fz = RegularGridInterpolator((gridLat,gridLon), 
		                                  gridZ[i,::-1,:], 'linear', bounds_error=False)
			t_interp[i,:] = ft(out_xyz_dem[:,:2] )#temperature
			z_interp[i,:] = fz(out_xyz_dem[:,:2])#elevation

		t_interp_out = np.dstack((t_interp_out, t_interp))
		z_interp_out = np.dstack((z_interp_out, z_interp))

		# invert pressure levels
		#t_interp = t_interp[::-1,:]
		#z_interp = z_interp[::-1,:]


	# drop init blank layer
	tinterp =t_interp_out[:,:,1:]
	zinterp =z_interp_out[:,:,1:]

	gpob= hp.Bunch(t=tinterp,z=zinterp, levels=lev)

	# dem  = nc.Dataset(demfile)
	# lon = dem.variables['longitude'][:]
	# lat = dem.variables['latitude'][:]
	# demv = dem.variables['ele'][:]
	# demlon1 = dem.variables['longitude'][:]
	# demlat1 = dem.variables['latitude'][:]
	# demlon = np.tile(demlon1,demlat1.size)
	# demlat = np.repeat(demlat1,demlon1.size)
	# demv=np.reshape(demv,demv.size)

	# # why are these masked values generated?
	# demv =np.ma.filled(demv, fill_value=1)
	# tz = np.repeat(tz,demv.size)

	# stat = pd.DataFrame({	"ele":demv, 
	# 				"lon":demlon,
	# 				"lat":demlat,
	# 				"tz":tz					
	# 				})
	#===============================================================================
	# Compute Shortwave
	#===============================================================================	

	#def swin2D(pob,sob,tob, stat, dates): 
	'''
	main edit over standard function for points:
	- 3d tob,sob reduce to 2D (reshape)
	'''


	""" toposcale surface pressure using hypsometric equation - move to own 
	class """
	g=9.81
	R=287.05  # Gas constant for dry air.
	#ztemp = pob.z # geopotential height b = np.transpose(a, (2, 0, 1))
	ztemp = np.transpose(gpob.z, (2, 0, 1)) # pob is originally ordered levels,stations/cells,time
	#Ttemp = pob.t
	Ttemp = np.transpose(gpob.t, (2, 0, 1))# pob is originally ordered levels,stations/cells,time
	statz = np.array(lp.ele)*g
	#dz=ztemp.transpose()-statz[None,:,None] # transpose not needed but now consistent with CGC surface pressure equations
	dz=ztemp-statz # dimensions of dz : time, levels, stations

	# set all levels below surface to very big number so they canot be found by min
	newdz=dz
	newdz[newdz<0]=999999

	psf =np.zeros( (gsob.dtime.size , statz.shape[0]) )

	# reshape tob.t here
	#gtob.tr=gtob.t.reshape(gtob.t.shape[0]*gtob.t.shape[1], gtob.t.shape[2], order='F')
	#tob.trT=tob.tr.T # transpose to get right order


	# loop through timesteps
	for i in range(0,gsob.dtime.size ):
		
		# find overlying layer
		thisp = dz[i,:,:]==np.min(newdz[i,:,:],axis=0) # thisp is a booleen matrix of levels x stations with true indicating overlying plevel over station surface ele

		# flatten to 1 dimension order='Fortran' or row major
		thispVec =thisp.reshape(thisp.size,order='F')
		TtempVec = Ttemp.reshape(Ttemp.shape[0], Ttemp.shape[1]*Ttemp.shape[2], order='F')
		ztempVec = ztemp.reshape(ztemp.shape[0], ztemp.shape[1]*ztemp.shape[2], order='F')
		
		# booleen indexing to find temp and geopotential that correspond to lowesest overlying layer
		T1=TtempVec[i,thispVec]
		z1=ztempVec[i,thispVec]


		p1=np.tile(gpob.levels[::-1],statz.shape[0])[thispVec]*1e2 #Convert to Pa. Reverse levels to ensure low ele (hig pressure) to high elel (low pressure)
		Tbar=np.mean([T1, gtob.t[:, i]],axis=0) # temperature midway between surface (toposcale T) and loweset overlying level (T1)
		""" Hypsometric equation.""" #P1 is above surface is this correct? Yes!
		psf[i,:]=p1*np.exp(   ((z1/g)-(statz/g))*(g/(Tbar*R))  ) # exponent is positive ie increases pressure as surface is lower than pressure level


	""" Maybe follow Dubayah's approach (as in Rittger and Girotto) instead
	for the shortwave downscaling, other than terrain effects. """

	""" Height of the "grid" (coarse scale)"""
	Zc=gsob.z.T #.reshape(gsob.z.shape[0]*gsob.z.shape[1], gsob.z.shape[2]).T # reshape and transpose to remove dimension and make broadcastable

	""" toa """
	SWtoa = gsob.tisr#.reshape(gsob.tisr.shape[0]*gsob.tisr.shape[1], gsob.tisr.shape[2]).T  

	""" Downwelling shortwave flux of the "grid" using nearest neighbor."""
	SWc=gsob.ssrd#.reshape(sob.ssrd.shape[0]*sob.ssrd.shape[1], sob.ssrd.shape[2]).T 

	"""Calculate the clearness index."""
	kt=SWc/SWtoa

	#kt[is.na(kt)==T]<-0 # make sure 0/0 =0
	#kt[is.infinite(kt)==T]<-0 # make sure 0/0 =0
	kt[kt<0]=0
	kt[kt>1]=0.8 #upper limit of kt
	kt=kt


	"""
	Calculate the diffuse fraction following the regression of Ruiz-Arias 2010 

	"""
	kd=0.952-1.041*np.exp(-1*np.exp(2.3-4.702*kt))


	""" Use this to calculate the downwelling diffuse and direct shortwave radiation at grid. """
	SWcdiff=kd*SWc
	SWcdir=(1-kd)*SWc
	SWcdiff=SWcdiff
	SWcdir=SWcdir

	""" Use the above with the sky-view fraction to calculate the 
	downwelling diffuse shortwave radiation at subgrid. """
	SWfdiff=SWcdiff
	SWfdiff = np.nan_to_num(SWfdiff) # convert nans (night) to 0

	""" Direct shortwave routine, modified from Joel. 
	Get surface pressure at "grid" (coarse scale). Can remove this
	part once surface pressure field is downloaded, or just check
	for existance. """

	ztemp = np.transpose(gpob.z, (0, 2, 1))
	Ttemp = np.transpose(gpob.t, (0, 2, 1))
	dz=ztemp-Zc # dimensions of dz : levels, time, stations

	# set all levels below surface to very big number so they canot be found by min
	newdz=dz
	newdz[newdz<0]=999999

	psc =np.zeros( (gsob.dtime.size, statz.shape[0]) )
	for i in range(0,gsob.dtime.size):

		#thisp.append(np.argmin(dz[:,i][dz[:,i]>0]))
		# find overlying layer
		thisp = dz[:,i,:]==np.min(newdz[:,i,:],axis=0) # thisp is a booleen matrix of levels x stations with true indicating overlying plevel over station surface ele !! time index in middle this time!!!
		z0 = Zc[i,:]
		T0 = gsob.t2m.T[i,:]

		# flatten to 1 dimension order='Fortran' or row major
		thispVec =thisp.reshape(thisp.size,order='F')
		TtempVec = Ttemp.reshape(Ttemp.shape[1], Ttemp.shape[0]*Ttemp.shape[2], order='F') # !! order of permutations is different from pressure at finegrid routine (time is middle dimension)
		ztempVec = ztemp.reshape(ztemp.shape[1], ztemp.shape[0]*ztemp.shape[2], order='F')# !! order of permutations is different from pressure at finegrid routine (time is middle dimension)
		
		# booleen indexing to find temp and geopotential that correspond to lowesest overlying layer
		T1=TtempVec[i,thispVec]
		z1=ztempVec[i,thispVec]

		p1=np.tile(gpob.levels[::-1],statz.shape[0])[thispVec]*1e2 #Convert to Pa.
		Tbar=np.mean([T0, T1],axis=0)
		""" Hypsometric equation."""
		psc[i,:] = p1*np.exp(      ( (z1/g)-(z0/g) )* (g/(Tbar*R))   )



	"""compute julian dates"""
	jd= sg.to_jd(gsob.dtime)

	"""
	Calculates a unit vector in the direction of the sun from the observer 
	position.
	"""
	svx,svy,svz =	sg.sunvectorMD(jd, lp.lat, lp.lon, tz,lp.ele.size,gsob.dtime.size )
	sp=sg.sunposMD(svx,svy,svz)


	# Cosine of the zenith angle.
	#sp.zen=sp.zen*(sp.zen>0) # Sun might be below the horizon.
	muz=np.cos(sp.zen) 
	muz = muz
	# NB! psc must be in Pa (NOT hPA!).

	# Calculate the "broadband" absorption coefficient. Elevation correction
	ka=(g*muz/(psc))*np.log(SWtoa.T/SWcdir.T)	
	ka = np.nan_to_num(ka) 

	# Now you can (finally) find the direct component at subgrid. 
	SWfdir=SWtoa.T*np.exp(-ka*psf/(g*muz))
	SWfdirCor=SWfdir #*dprod

	gtob.swin  =  SWfdiff+ SWfdirCor.T
	gtob.psf = psf
	print("Swin done")


	#gtob.swin = swin2D(gpob,gsob,gtob, stat, dtime)
	#gtob.swin =gtob.swin.reshape(gtob.swin.shape[0], gsob.ssrd.shape[0], gsob.ssrd.shape[1])

	ntime = len(gsob.dtime)
	stephr =a.seconds/60/60
	rtime=np.array(list(range(len(gsob.dtime))))*stephr


	#===============================================================================
	# write results
	#===============================================================================	
	## conversuions
	T = np.single(gtob.t -273.15)
	gtob.r[gtob.r>100]=100
	RH = np.single(gtob.r)
	ws = np.single( np.sqrt(gtob.u**2+gtob.v**2) )
	prate = np.single(gtob.prate)

	#===========================================================================
	# Calculate absolute humidity kg/kg
	#===========================================================================
	# Tk=273.15+20
	# RH=80.
	# ah = 13.82g/m3
	pws = calc_Pws(gtob.t)
	pw =calc_Pw(pws,RH)
	ah_gm3 = calc_AH(pw, gtob.t) # ah in g/m3
	#AH_kgkg = ah_gm3_To_ah_kgkg(ah_gm3,gtob.psf,gtob.t )
	SH = rh2sh(pw,gtob.psf )





	# Dictionary to loop over
	varDict={
	"t":T,
	"ws"   : ws,
	"shum" : SH.transpose(),  
	"swin" : gtob.swin,
	"lwin" : gtob.lwin, 
	"prate": prate, 
	"P" : gtob.psf.transpose()
	}



	for var in varDict:

		#open
		f = nc.Dataset(outDir+"/"+var+"_"+str(startIndex+1)+"_"+str(year)+".nc",'w', format='NETCDF4')

		# Implement cf H.2.1 http://cfconventions.org/Data/cf-conventions/cf-conventions-1.7/build/cf-conventions.html#idp9763584
		
		# #make dimensions
		# f.createDimension('time', ntime)
		# f.createDimension('lon', len(lp.lon))
		# f.createDimension('lat', len(lp.lat))
		

		# #make dimension variables
		# mytime = f.createVariable('time', 'i', ('time',))
		# longitude = f.createVariable('lon',    'f4',('lon',))
		# latitude  = f.createVariable('lat',    'f4',('lat',))
		
		# myvar = f.createVariable(var,    'f4',('time','lon'))

		# #assign dimensions
		# mytime[:] = rtime
		# longitude = lp.lon
		# latitude  = lp.lat
		
		# myvar[:] = varDict[var].T
		
		# #metadata
		# from time import ctime
		# mytime=ctime()
		# f.history = 'Created by toposcale on '+mytime
		# mytime.units = 'hours since '+str(gsob.dtime[0])
		# f.close()

		#make dimensions
		f.createDimension('time', ntime)
		f.createDimension('station', len(lp.ele))

		

		#make dimension variables
		mytime = f.createVariable('time', 'i', ('time',))
		station = f.createVariable('station',    'i',('station',))

		#make variables
		myvar = f.createVariable(var,    'f4',('time','station'))
		longitude = f.createVariable('longitude',    'f4',('station'))
		latitude = f.createVariable('latitude',    'f4',('station'))

		#assign dimensions
		mytime[:] = rtime
		longitude[:] = np.array(lp.lon)
		latitude[:]  = np.array(lp.lat)
		station[:] = range(len(lp.ele))
		myvar[:] = varDict[var].T
		
		#metadata
		from time import ctime
		mycomptime=ctime()
		f.history = 'Created by tscale-cci on '+mycomptime
		mytime.units = 'hours since '+str(gsob.dtime[0])
		f.close()


	print("Toposcale complete!")





#===============================================================================
#	Calling Main
#===============================================================================
if __name__ == '__main__':
	coords = sys.argv[1]
	eraDir = sys.argv[2]
	outDir = sys.argv[3]
	startDT = sys.argv[4]
	endDT = sys.argv[5]
	startIndex = sys.argv[6]
	
	main(coords, eraDir, outDir, startDT, endDT, startIndex )
