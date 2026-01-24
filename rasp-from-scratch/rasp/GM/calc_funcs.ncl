;
; BLCLOUDPCT
;
function blcloudpct(qvapor, qcloud, tc, pmb, z, ter, pblh, cwbasecriteria, isize, jsize, ksize)
begin
        bparam = new( (/jsize,isize/), float)

        calc_subgrid_blcloudpct_grads( qvapor, qcloud, tc,pmb, z, ter, pblh, cwbasecriteria, isize,jsize,ksize, bparam  )

	; Bombs - Out of Memory - if running X (i.e. runlevel == 5)

	; This is the most *HORRIBLE* hack to reduce CUDA memory usage
	; With 6 large vars, it won't fit
	; So take only the lowest N levels of available 52 :-(
	; Value of N experimentally determined - YUK!
	; N = 33
	; print("*** WARNING: Only " + N + " levels")
        ; calc_subgrid_blcloudpct_grads( qvapor(0:N,:,:), qcloud(0:N,:,:), tc(0:N,:,:), pmb(0:N,:,:), z(0:N,:,:), ter, pblh, cwbasecriteria, isize,jsize,N+1, bparam  )

	return(bparam)
end

;;;;;;;;;;;;;;;;;
; blcwbase calc
;;;;;;;;;;;;;;;;;
function blcwbase(qcloud, z, ter, pblh, isize, jsize, ksize)
begin
	;;; laglcwbase can be either agl (=1) or msl (=0) (flag also changes titles below)
	;agl: laglcwbase = 1
	;msl: laglcwbase = 0
	laglcwbase = 1

	;;; set max cloudbase to allow reasonable contour intervals
	maxcwbasem = 5486.40   ; equals 18000ft
	maxcwbaseft = floattointeger( 3.28084*maxcwbasem )

	bparam = new( (/jsize,isize/), float)
	bparam@_FillValue = -999	; This is only required for V6, as the default is different!

	calc_blcloudbase( qcloud, z, ter, pblh, cwbasecriteria, maxcwbasem, laglcwbase, isize,jsize,ksize, bparam  )

	;4test print ( "POST-SUB: MIN,MAX="+min(bparam)+","+max(bparam) )

	return( bparam )
end

;
; BLICW
;
function blicw(qcloud, ppert, pb, psfc, z, pblh, ter, isize, jsize, ksize)
begin
        ptot = ppert + pb
        bparam = new( (/jsize,isize/), float)

        calc_blinteg_mixratio( qcloud, ptot, psfc, z, ter, pblh, isize,jsize,ksize, bparam )

	return( bparam )
end

;
; BLTOPVARIAB
;
function bltopvariab(thetac, z, pblh, ter, isize, jsize, ksize)
begin
        bparam = new( (/jsize,isize/), float)
        criteriondegc = 1.0
        calc_bltop_pottemp_variability( thetac, z, ter, pblh, isize,jsize,ksize, criteriondegc, bparam )

	return(bparam)
end

;
; BLWINDSHEAR
;
function blwindshear(ua, va, z, ter, pblh, isize, jsize, ksize)
begin
        bparam = new( (/jsize,isize/), float)
        calc_blwinddiff(ua,va,z,ter,pblh, isize,jsize,ksize, bparam )

	return(bparam)
end

;
; BSRATIO
;
function bsratio(blavgwindspeed, wstar)
begin
	;;; BUG: Calculation of bsratio in rasp.bparam_calc.ncl is done twice
	;;; If calculated on its own (and has not been done previously)
	;;; Then wstar is in m/s (wrf units) and blavgwindspeed is in Kt
	;;; BUT
	;;; When calculated as part of wstar_bsratio
	;;; blavgwindspeed is in Kts or m/s
	;;; wstar is in ft/min or cm/sec
	;;; WHO KNOWS which is correct?
	;;;
	;;; EITHER WAY, It contravenes the basic idea that
	;;; Units are a PLOTTING ISSUE
	;;; NOT a calculation issue!


	;;; at present use constant value for bl drag coefficient
	if(UNITS .ne. "metric") then
		tmp = wstar / sqrt( cdbl*((blavgwindspeed * 1.94386) ^ 2) )            ; wstar in m/s ; wind in Kt
		; OR
		; tmp = 196.85 * wstar / sqrt( cdbl*((blavgwindspeed * 1.94386) ^ 2) ) ; wstar in ft/min; wind in Kt 
	else
		tmp = wstar / sqrt( cdbl*(blavgwindspeed ^ 2) )                        ; wstar in m/s; wind in m/s 	
		; OR
		; tmp = 100.0 * wstar / sqrt( cdbl*(blavgwindspeed ^ 2) )              ; wstar in cm/s; wind in m/s 	
	end if

	return(tmp)
end

;
; CAPE
; Outside fortran routine since have ncl skewt functions available
; Very inefficient but leave for now
; Uses sfc humidity as reference, not 100mb avg
;
undef("cape")
function cape(pmb, tc, td, isize, jsize, ksize)
begin
        bparam = new( (/jsize,isize/), float)

	calc_cape2d(pmb,tc,td,isize,jsize,ksize,bparam)

        ; profilep = new( (/ksize/), float)
        ; profiletc = new( (/ksize/), float)
        ; do ii = 0,(isize-1)
        ;       do jj = 0,(jsize-1)
        ;               ;;; following taken from skewt_func.ncl
        ;               ;;; pmb,tc,td index is basis for calc (0=sfc)
        ;               plcl = -999.             ; p (hPa) Lifting Condensation Lvl (lcl)
        ;               tlcl = -999.             ; temperature (C) of lcl
        ;               kzhumidref = 0
        ;               ptlcl_skewt( pmb(kzhumidref,jj,ii),tc(kzhumidref,jj,ii),td(kzhumidref,jj,ii), plcl,tlcl )
        ;               profilepmb = pmb(:,jj,ii)
        ;               profiletc = tc(:,jj,ii)
        ;               bparam(jj,ii) = cape_thermo( profilepmb,profiletc, plcl, 0 )
        ;       end do
        ; end do
        ; delete ( profilepmb )
        ; delete ( profiletc )

	return(bparam)
end

;
; BL CLOUD-CONDENSATION EQUIV. HEAT FLUX
;
function cloudsuck(rqcblten, mu, mub, z, ter, pblh, isize, jsize, ksize) 
begin
	bparam = new( (/jsize, isize/), float)
        calc_qcblhf( rqcblten,mu, z, ter, pblh, isize,jsize,ksize, bparam  )

	return(bparam)
end

;
; DWCRIT
;
function dwcrit(wstar, ter, pblh, isize, jsize)
begin
	bparam = new( (/jsize,isize/), float)
	calc_hcrit( wstar, ter, pblh, isize,jsize, bparam )

	bparam = bparam - ter

	return(bparam)
end

;
; EXPERIMENTAL1
; Presently hcrit based on criteria=175fpm
;
function experimental1(wstar, ter, pblh, isize, jsize)
begin
        bparam = new( (/jsize,isize/), float)
        calc_hlift( 175., wstar, ter, pblh, isize, jsize, bparam )

	return(bparam)
end


;
; EXPERIMENTAL2 
; Presently max of CLDFRA within BL
;
function experimental2(cldfra, z, ter, pblh, isize, jsize, ksize)
begin
        ;;; CLDFRA NOT USED FOR ANY OTHER CALC SO DISCARD AFTER USE

        bparam = new( (/jsize,isize/), float)
        calc_blmax( cldfra, z, ter, pblh, isize,jsize,ksize, bparam  )

        bparam = 100.* bparam ;;; convert to percent
        return (bparam)
end

;
; HGLIDER
;
function hglider(hcrit, zsfclcl, zblcl, isize, jsize)
begin
	bparam = hcrit
	cparam = new( (/jsize,isize/), float)
	cparam = 0.0
	min_2darrays( bparam, cparam, zsfclcl, 1.0, isize, jsize )
	min_2darrays( bparam, cparam, zblcl, 2.0, isize, jsize )

	return(bparam)
end

;
; DGLIDER
;
function dglider(hcrit, zsfclcl, zblcl, ter, isize, jsize)
begin
	bparam = hcrit
	cparam = new( (/jsize,isize/), float)
	cparam = 0.0
	min_2darrays( bparam, cparam, zsfclcl, 1.0, isize, jsize )
	min_2darrays( bparam, cparam, zblcl, 2.0, isize, jsize )
	bparam = bparam - ter

	return(bparam)
end

;
; HWCRIT
;
function hwcrit( wstar, ter, pblh, isize, jsize)
begin
	bparam = new( (/jsize,isize/), float)
	calc_hcrit( wstar, ter, pblh, isize,jsize, bparam )

	return(bparam)
end

;
; WBLMAXMIN
;
function wblmaxmin(wa, z, ter, pblh, isize, jsize, ksize)
begin
	bparam = new( (/jsize,isize/), float )
	calc_wblmaxmin( 0, wa,z,ter,pblh, isize,jsize,ksize, bparam )

	return(bparam)
end

;
; ZWBLMAXMIN
;
function zwblmaxmin(wa, z, ter, pblh, isize, jsize, ksize)
begin
	bparam = new( (/jsize,isize/), float)
	calc_wblmaxmin( 1, wa,z,ter,pblh, isize,jsize,ksize, bparam )

	return(bparam)
end

;
; SWBLMAXMIN
;
function swblmaxmin(wa, z, ter, pblh, isize, jsize, ksize)
begin
	bparam = new( (/jsize,isize/), float)
	calc_wblmaxmin( 2, wa,z,ter,pblh, isize,jsize,ksize, bparam )

	return(bparam)
end

;
; PRESSNNN
;
function press(ter, name_chars, w_plane, u_plane, v_plane, w, ua, va, pmb )

begin
	;;; determine pressure level
 	char_str = stringtocharacter(name_chars)  
	pressure = stringtofloat(charactertostring(char_str(5:)))

	print( "    DOING PRESSURE PLOT of press for mb = "+pressure )

	;;;;;;;;;;
	; Vertically interpolate the selected 3d fields to this pressure surface.
	; Note that DrJack's wrf_user_intrp3d has different arguments (than NCL), which include "terrain"
	;;;;;;;;;;

	u_plane@_FillValue = -999
	v_plane@_FillValue = -999
	w_plane@_FillValue = -999

	u_plane  = wrf_user_intrp3d( ua, pmb, "h", pressure, 0., False)
	v_plane  = wrf_user_intrp3d( va, pmb, "h", pressure, 0., False)
	w_plane  = wrf_user_intrp3d( w,  pmb, "h", pressure, 0., False)

	print("    press" + pressure +": u_plane min = " + min(u_plane) + " max = " + max(u_plane))
	print("    press" + pressure +": v_plane min = " + min(v_plane) + " max = " + max(v_plane))
	print("    press" + pressure +": w_plane min = " + min(w_plane) + " max = " + max(w_plane))

	return(pressure)
end

;
; RAIN
;
function rain(filename, f, plot_param_chars, nx, ny)
begin
	;; Extract the accumulation time from the parameter name
	acctime = stringtointeger( chartostring( plot_param_chars(4:) ) )

	;; Get filename for the previous forecast. Needed to subtract earlier rain.
	filename_chars = stringtochar( filename )
	len_filename = dimsizes(filename_chars)-2

	; date of current file
	; sdate = string_target_replace(chartostring( filename_chars(len_filename-18:len_filename-6)), "_", "-" )
	sdate = str_sub_str(chartostring( filename_chars(len_filename-18:len_filename-6)), "_", "-" )

	; Allow for ".nc" on the end
	stime = filename_chars(len_filename-7:len_filename-3)

	; date  = stringtointeger(split_string_into_array( sdate,"-" ))
	date  = stringtointeger(str_split( sdate,"-" ))
	; date of previous file
	prevdate  = jul2greg( greg2jul(date(0),date(1),date(2),date(3)) - acctime/24. + 0.00001 )
	sprevdate = sprinti("%d-",prevdate(0)) + sprinti("%02d-",prevdate(1)) + sprinti("%02d_",prevdate(2)) + sprinti("%02d:", prevdate(3)) + stime 
	prevfilename = chartostring( filename_chars(0:len_filename-19)) + sprevdate

	rainc  = f->RAINC
	rainnc = f->RAINNC
	rainc  = rainc > 0.0
	rainnc = rainnc > 0.0

	rainTot = new ( (/ny, nx/), float)

	;; If the previous file exists -> load it, subtract earlier rain, plot it.
	if (isfilepresent(prevfilename)) then
		prevfile = addfile( prevfilename+".nc", "r" )

		prevrainc  = prevfile->RAINC
		prevrainnc = prevfile->RAINNC

		; Use NCL operator > to make sure all values >=0.0
		prevrainc  = prevrainc > 0.0
		prevrainnc = prevrainnc > 0.0

		rainTot = rainc + rainnc - prevrainc - prevrainnc
	else
		rainTot = rainc + rainnc
		print("    prevfilename = " + prevfilename )
		print("    WARNING: No previous file: showing total accumulated rain to " + date(3) + ":" + stime)
	end if
	return(rainTot)
end



;
; SOILMOIST - Enhanced Soil Moisture Content
; Uses weighted average of multiple soil layers for better detail
; Shows overall moisture distribution including drainage effects
; WRF SMOIS has 4 layers: 0-10cm, 10-40cm, 40-100cm, 100-200cm
;
function soilmoist(smois, isize, jsize)
local layer0, layer1, layer2, layer3, weighted_moist
begin
	; SMOIS is volumetric soil moisture content (m^3/m^3) with 4 vertical levels
	; Use weighted average emphasizing upper layers but including deeper moisture
	; This shows both surface wetness and subsurface moisture reserves
	
	bparam = new( (/jsize, isize/), float)
	
	; Extract all soil layers
	layer0 = smois(0,:,:)  ; 0-10cm (surface)
	layer1 = smois(1,:,:)  ; 10-40cm 
	layer2 = smois(2,:,:)  ; 40-100cm
	layer3 = smois(3,:,:)  ; 100-200cm (deep)
	
	; Weighted average: emphasize surface but include deeper layers
	; Surface moisture is most important, but deep moisture affects surface through capillary rise
	weighted_moist = (0.50 * layer0) + (0.30 * layer1) + (0.15 * layer2) + (0.05 * layer3)
	
	; Convert to percentage for easier interpretation
	bparam = weighted_moist * 100.0
	
	; Values typically range:
	; 0-10%:   Very dry soil (drought)
	; 10-20%:  Dry soil  
	; 20-30%:  Moderate moisture
	; 30-40%:  Moist soil (good for thermals)
	; 40-50%:  Saturated/very wet soil (recent rain, poor drainage)
	
	return(bparam)
end


; SFCMOIST - Surface Soil Moisture (Top Layer Only)
; Shows ONLY the top 0-10cm layer - most responsive to rain
; Use this to see rain shower effects and rapid surface drying
; Updates quickly with precipitation and evaporation
;
function sfcmoist(smois, isize, jsize)
begin
	; Focus entirely on surface layer for maximum rain sensitivity
	; This layer responds immediately to precipitation
	; and dries fastest through evaporation
	
	bparam = new( (/jsize, isize/), float)
	
	; Extract ONLY top soil layer (0-10cm depth)
	bparam = smois(0,:,:) * 100.0  ; Convert to percentage
	
	; This will show:
	; - Immediate wetting from rain showers
	; - Quick drying in sunny conditions
	; - Spatial variation from localized showers
	; - Runoff accumulation in low areas
	
	; Values typically range:
	; 0-15%:   Very dry surface
	; 15-25%:  Dry surface
	; 25-35%:  Moist surface
	; 35-45%:  Wet surface (recent rain or poor drainage)
	; 45-55%:  Saturated surface (active rain or flooding)
	
	return(bparam)
end


;
; SFCSUN
;
function sfcsun(swdown)
begin
	bparam = swdown
	bparam@_FillValue = -999
	return(swdown)
end

;
; SFCSUNPCT
;
function sfcsunpct(jday, gmthr, swdown, pmb, tc, qvapor, isize, jsize, ksize, ter, z, alat, alon)
begin
	bparam = swdown
	bparam@_FillValue = -999
	calc_sfcsunpct( jday, gmthr, alat, alon, ter, z, pmb, tc, qvapor, isize, jsize, ksize, bparam )


	; Another Horrible hack - see BLCLOUDPCT
	; N = 32
	; print("*** WARNING: Only " + N + " levels")
	; calc_sfcsunpct( jday, gmthr, alat, alon, ter, z(0:N,:,:), pmb(0:N,:,:), tc(0:N,:,:), qvapor(0:N,:,:), isize, jsize, N+1, bparam )

	return(bparam)
end

;
; PDFTOT
;
; function pfd_old2()
; begin
;     ; Uses only data files
;     ; Must select files with correct date and on full hours (i.e. minutes == 00lst)

;     filename_chars = stringtochar(getenv("ENV_NCL_FILENAME"))
;     len_filename = dimsizes(filename_chars)-2
;     datepart = chartostring(filename_chars(len_filename-18:len_filename-9))
;     dateStr = str_split(datepart, "-")
;     newdateStr = dateStr(0) + " " + toint(dateStr(1)) + " " + toint(dateStr(2))

;     cmd_wstar = "grep -l '" + newdateStr + "' " + BaseDir + "/" + Region + "/OUT/wstar.*lst.d2.data"
;     wstar_files = systemfunc(cmd_wstar)
;     cmd_dglider = "grep -l '" + newdateStr + "' " + BaseDir + "/" + Region + "/OUT/dglider.*lst.d2.data"
;     dglider_files = systemfunc(cmd_dglider)
;     cmd_zsfclcldif = "grep -l '" + newdateStr + "' " + BaseDir + "/" + Region + "/OUT/zsfclcldif.*lst.d2.data"
;     zsfclcldif_files = systemfunc(cmd_zsfclcldif)
;     cmd_bsratio = "grep -l '" + newdateStr + "' " + BaseDir + "/" + Region + "/OUT/bsratio.*lst.d2.data"
;     bsratio_files = systemfunc(cmd_bsratio)
;     nfiles = dimsizes(wstar_files)
;     delete(cmd_wstar)
;     delete(cmd_dglider)
;     delete(cmd_zsfclcldif)
;     delete(cmd_bsratio)

;     ; Read one file and extract nx & ny
;     ; Should be the same as in ENV_NCL_FILENAME but ...
;     f = wstar_files(0)
;     if(.not. fileexists(f) ) then
;         print(f + " does not exist!");
;         return(0)   ; pfdtot@valid is false!
;     end if
;     hdr = readAsciiHead(f, "Day")
;     nx = toint(extract_string_field(hdr(2), 11, " "))
;     ny = toint(extract_string_field(hdr(2), 13, " "))

;     pfdtot = new( (/ny,nx/), float)
;     pfdtot = 0.0
;     do i = 0, nfiles-2 ; Note: last file (i.e. for latest time) not included

;         ; Handle files
;         f_wstar = wstar_files(i)
;         ws = readAsciiTable(f_wstar, nx, "integer", 4)
;         f_dglider = dglider_files(i)
;         dg = readAsciiTable(f_dglider, nx, "integer", 4)
;         f_zsfclcldif = zsfclcldif_files(i)
;         cu = readAsciiTable(f_zsfclcldif, nx, "integer", 4)
;         f_bsratio = bsratio_files(i)
;         bs = readAsciiTable(f_bsratio, nx, "integer", 4)

;         ; Parameters
;         a = -0.000302016415111608
;         b = 0.0729181700942301
;         c = -5.21488508245734
;         dg_amp = 2.0
;         dg_fac = 200.0
;         dg_offx = 300.0
;         dg_offy = -1.0
;         cu_amp = 0.3
;         cu_fac = 50.0
;         cu_offx = -100.0
;         cu_offy = 0.7
;         bs_amp = 2.0
;         bs_fac = 1.5
;         bs_offx = 1.0
;         bs_offy = -1.0

;         ; Do calculation
;         w = ws / 100.0 - 1.0 ; Convert to m/s and subtract sinkrate
;         w = w > 0.0
;         dg_risk = dg_amp / (1.0 + exp(-(dg-dg_offx)/dg_fac)) + dg_offy
;         cu_risk = cu_amp / (1.0 + exp(-(cu-cu_offx)/cu_fac)) + cu_offy
;         bs_risk = bs_amp / (1.0 + exp(-(bs-bs_offx)/bs_fac)) + bs_offy
;         dg_risk = dg_risk > 0.0
;         cu_risk = cu_risk > 0.0
;         bs_risk = bs_risk > 0.0
;         w = w * dg_risk * cu_risk * bs_risk
;         v_cruise = sqrt((c-w)/a)
;         sink_cruise = a*v_cruise*v_cruise + b*v_cruise + c
;         v_avg = v_cruise * w / (w - sink_cruise)
;         pfdtot = pfdtot + v_avg
;         delete( (/ws, w, dg, cu, dg_risk, cu_risk, bs_risk, v_cruise, sink_cruise, v_avg/) )

;     end do

;     ; Smoothen
;     wgt = (/ 1., 1., 1., 1., 1., 1., 1. /)
;     wgt = wgt / sum(wgt)
;     pfdtot@_FillValue = -999999
;     pfdtot = wgt_runave_n_Wrap(pfdtot, wgt, 1, 0)
;     pfdtot = wgt_runave_n_Wrap(pfdtot, wgt, 1, 1)

;     pfdtot@valid = True
;     return(pfdtot)
; end

;
; PFDXC - Maximum achievable cross-country distance
; Calculates directly from WRF output files without relying on pre-computed data
;
; function pfd()
; local wrffiles, nfiles, pfd_result, nx_pfd, ny_pfd, nz_pfd, t, ff, \
;       vhf_pfd, pblh_pfd, hfx_pfd, tc_pfd, wstar_pfd, \
;       z_pfd, ter_pfd, ua_pfd, va_pfd, wa_pfd, pmb_pfd, td_pfd, qvapor_pfd, \
;       ppert_pfd, pb_pfd, ublavg_pfd, vblavg_pfd, windspeed_pfd, bsratio_pfd, \
;       zsfclcl_pfd, zblcl_pfd, qvaporblavg_pfd, hcrit_pfd, zsfclcldif_pfd, dglider_pfd, \
;       wconvergence_pfd, ws_pfd, w_pfd, v_cruise_pfd, sink_cruise_pfd, v_avg_pfd, \
;       soarable, max_distance, efficiency, wgt, max_distance_smooth
; begin
;     ; Find all WRF output files for the current domain
;     filename_env = getenv("ENV_NCL_FILENAME")
;     filename_chars = stringtochar(filename_env)
;     len_filename = dimsizes(filename_chars)-2
    
;     ; Extract domain ID from current filename (e.g., d01, d02)
;     jday_dummy = 0
;     gmthr_dummy = 0.0
;     domainid_local = ""
;     getfiledate(chartostring(filename_chars), jday_dummy, gmthr_dummy, domainid_local)
    
;     ; Find all wrfout files for this domain
;     cmd_wrffiles = "ls " + BaseDir + "/" + Region + "/wrfout_" + domainid_local + "_* 2>/dev/null | head -n -1"
;     wrffiles = systemfunc(cmd_wrffiles)
    
;     if(ismissing(wrffiles(0))) then
;         print("PFD: No WRF files found for domain " + domainid_local)
;         result = 0
;         result@valid = False
;         return(result)
;     end if
    
;     nfiles = dimsizes(wrffiles)
;     print("PFD: Found " + nfiles + " WRF files for domain " + domainid_local)
    
;     ; Open first file to get dimensions
;     ff = addfile(wrffiles(0) + ".nc", "r")
;     z_tmp = wrf_user_getvar(ff, "z", 0)
;     paramdims = dimsizes(z_tmp)
;     nz_pfd = paramdims(0)
;     ny_pfd = paramdims(1)
;     nx_pfd = paramdims(2)
;     delete(z_tmp)
;     delete(paramdims)
;     delete(ff)
    
;     ; Initialize accumulator arrays
;     max_distance = new((/ny_pfd, nx_pfd/), float)
;     max_distance = 0.0
;     soarable = new((/ny_pfd, nx_pfd/), float)
;     soarable = 0.0
    
;     ; Glider performance parameters
;     a = -0.000302016415111608
;     b = 0.0729181700942301
;     c = -5.21488508245734
    
;     ; Process each WRF file (excluding the last one as per original logic)
;     do t = 0, nfiles-2
;         print("PFD: Processing file " + (t+1) + " of " + (nfiles-1) + ": " + wrffiles(t))
        
;         ff = addfile(wrffiles(t) + ".nc", "r")
        
;         ; Load required variables
;         vhf_pfd = wrf_user_getvar(ff, "LH", 0)
;         hfx_pfd = wrf_user_getvar(ff, "HFX", 0)
;         pblh_pfd = wrf_user_getvar(ff, "PBLH", 0)
;         tc_pfd = wrf_user_getvar(ff, "tc", 0)
;         z_pfd = wrf_user_getvar(ff, "z", 0)
;         ter_pfd = wrf_user_getvar(ff, "HGT", 0)
;         ua_pfd = wrf_user_getvar(ff, "ua", 0)
;         va_pfd = wrf_user_getvar(ff, "va", 0)
;         wa_pfd = wrf_user_getvar(ff, "wa", 0)
;         pmb_pfd = wrf_user_getvar(ff, "pressure", 0)
;         td_pfd = wrf_user_getvar(ff, "td", 0)
;         qvapor_pfd = wrf_user_getvar(ff, "QVAPOR", 0)
        
;         ; Ensure terrain >= 1
;         ter_pfd = ter_pfd > 1.0
        
;         ; Calculate virtual heat flux
;         vhf_pfd = where(vhf_pfd .lt. 0.0, 0.0, vhf_pfd)
;         vhf_pfd = hfx_pfd + 0.000245268*(tc_pfd(0,:,:)+273.16)*vhf_pfd
        
;         ; Calculate wstar
;         wstar_pfd = new((/ny_pfd, nx_pfd/), float)
;         calc_wstar(vhf_pfd, pblh_pfd, nx_pfd, ny_pfd, nz_pfd, wstar_pfd)
        
;         ; Calculate BL average wind
;         ublavg_pfd = new((/ny_pfd, nx_pfd/), float)
;         vblavg_pfd = new((/ny_pfd, nx_pfd/), float)
;         calc_blavg(ua_pfd, z_pfd, ter_pfd, pblh_pfd, nx_pfd, ny_pfd, nz_pfd, ublavg_pfd)
;         calc_blavg(va_pfd, z_pfd, ter_pfd, pblh_pfd, nx_pfd, ny_pfd, nz_pfd, vblavg_pfd)
;         windspeed_pfd = sqrt(ublavg_pfd * ublavg_pfd + vblavg_pfd * vblavg_pfd)
        
;         ; Calculate bsratio
;         bsratio_pfd = wstar_pfd / sqrt(cdbl * (windspeed_pfd ^ 2))
;         bsratio_pfd = where(ismissing(bsratio_pfd) .or. bsratio_pfd .lt. 0.0, 0.0, bsratio_pfd)
;         bsratio_pfd = where(bsratio_pfd .gt. 10.0, 10.0, bsratio_pfd)
        
;         ; Calculate zsfclcl
;         zsfclcl_pfd = new((/ny_pfd, nx_pfd/), float)
;         calc_sfclclheight(pmb_pfd, tc_pfd, td_pfd, z_pfd, ter_pfd, pblh_pfd, nx_pfd, ny_pfd, nz_pfd, zsfclcl_pfd)
        
;         ; Calculate zblcl
;         qvaporblavg_pfd = new((/ny_pfd, nx_pfd/), float)
;         calc_blavg(qvapor_pfd, z_pfd, ter_pfd, pblh_pfd, nx_pfd, ny_pfd, nz_pfd, qvaporblavg_pfd)
;         zblcl_pfd = new((/ny_pfd, nx_pfd/), float)
;         calc_blclheight(pmb_pfd, tc_pfd, qvaporblavg_pfd, z_pfd, ter_pfd, pblh_pfd, nx_pfd, ny_pfd, nz_pfd, zblcl_pfd)
        
;         ; Calculate hcrit
;         hcrit_pfd = new((/ny_pfd, nx_pfd/), float)
;         calc_hcrit(wstar_pfd, ter_pfd, pblh_pfd, nx_pfd, ny_pfd, hcrit_pfd)
        
;         ; Calculate dglider (hglider - terrain)
;         dglider_pfd = hcrit_pfd
;         cparam_tmp = new((/ny_pfd, nx_pfd/), float)
;         cparam_tmp = 0.0
;         min_2darrays(dglider_pfd, cparam_tmp, zsfclcl_pfd, 1.0, nx_pfd, ny_pfd)
;         min_2darrays(dglider_pfd, cparam_tmp, zblcl_pfd, 2.0, nx_pfd, ny_pfd)
;         dglider_pfd = dglider_pfd - ter_pfd
;         delete(cparam_tmp)
        
;         ; Calculate zsfclcldif
;         zsfclcldif_pfd = pblh_pfd + ter_pfd - zsfclcl_pfd
        
;         ; Calculate wind convergence
;         wconvergence_pfd = new((/ny_pfd, nx_pfd/), float)
;         calc_wblmaxmin(0, wa_pfd, z_pfd, ter_pfd, pblh_pfd, nx_pfd, ny_pfd, nz_pfd, wconvergence_pfd)
        
;         ; Calculate xcspeed inline
;         ws_pfd = (wstar_pfd * 100.0) + wconvergence_pfd
;         w_pfd = ws_pfd / 100.0 - 1.0
;         w_pfd = w_pfd > 0.0
        
;         ; Apply risk factors (simplified)
;         dg_risk = 2.0 / (1.0 + exp(-(dglider_pfd-300.0)/200.0)) - 1.0
;         cu_risk = 0.3 / (1.0 + exp(-(zsfclcldif_pfd+100.0)/50.0)) + 0.7
;         bs_risk = 2.0 / (1.0 + exp(-(bsratio_pfd-1.0)/1.5)) - 1.0
;         dg_risk = dg_risk > 0.0
;         cu_risk = cu_risk > 0.0
;         bs_risk = bs_risk > 0.0
        
;         w_pfd = w_pfd * dg_risk * cu_risk * bs_risk
        
;         ; Calculate average cross-country speed
;         v_cruise_pfd = sqrt((c - w_pfd) / a)
;         sink_cruise_pfd = a * v_cruise_pfd * v_cruise_pfd + b * v_cruise_pfd + c
;         v_avg_pfd = v_cruise_pfd * w_pfd / (w_pfd - sink_cruise_pfd)
;         v_avg_pfd = where(ismissing(v_avg_pfd) .or. v_avg_pfd .lt. 0.0, 0.0, v_avg_pfd)
;         v_avg_pfd = where(v_avg_pfd .gt. 200.0, 200.0, v_avg_pfd)
        
;         ; Update soarability map
;         soarable = where(v_avg_pfd .gt. 0.0, 1.0, soarable)
        
;         ; Accumulate distance
;         efficiency = 0.85
;         max_distance = max_distance + (v_avg_pfd * efficiency)
        
;         ; Cleanup
;         delete([/vhf_pfd, hfx_pfd, pblh_pfd, tc_pfd, z_pfd, ter_pfd, ua_pfd, va_pfd, wa_pfd, \
;                  pmb_pfd, td_pfd, qvapor_pfd, wstar_pfd, ublavg_pfd, vblavg_pfd, windspeed_pfd, \
;                  bsratio_pfd, zsfclcl_pfd, zblcl_pfd, qvaporblavg_pfd, hcrit_pfd, dglider_pfd, \
;                  zsfclcldif_pfd, wconvergence_pfd, ws_pfd, w_pfd, dg_risk, cu_risk, bs_risk, \
;                  v_cruise_pfd, sink_cruise_pfd, v_avg_pfd/])
;         delete(ff)
;     end do
    
;     ; Apply conditional smoothing
;     wgt = (/ 0.05, 0.1, 0.15, 0.4, 0.15, 0.1, 0.05 /)
;     wgt = wgt / sum(wgt)
;     max_distance@_FillValue = -999999
    
;     do smooth_pass = 0, 2
;         max_distance_smooth = wgt_runave_n_Wrap(max_distance, wgt, 1, 0)
;         max_distance_smooth = wgt_runave_n_Wrap(max_distance_smooth, wgt, 1, 1)
;         max_distance = where(soarable .eq. 1.0, max_distance_smooth, 0.0)
;     end do
    
;     delete(soarable)
;     delete(wrffiles)
    
;     max_distance@valid = True
;     return(max_distance)
; end


;
; PDFTOT OLD
;
; function pfd_old()
; begin
;     ; Uses only data files
;     ; Must select files with correct date and on full hours (i.e. minutes == 00lst)

;     filename_chars = stringtochar(getenv("ENV_NCL_FILENAME"))
;     len_filename = dimsizes(filename_chars)-2
;     datepart = chartostring(filename_chars(len_filename-18:len_filename-9))
;     dateStr = str_split(datepart, "-")
;     newdateStr = dateStr(0) + " " + toint(dateStr(1)) + " " + toint(dateStr(2))

;     cmd = "grep -l '" + newdateStr + "' " + BaseDir + "/" + Region + "/OUT/wstar.*lst.d2.data"
;     wstar_files = systemfunc(cmd)
;     nfiles = dimsizes(wstar_files)
;     delete(cmd)

;     ; Read one file and extract nx & ny
;     ; Should be the same as in ENV_NCL_FILENAME but ...
;     f = wstar_files(0)
;     if(.not. fileexists(f) ) then
;         print(f + " does not exist!");
;         return(0)   ; pfdtot@valid is false!
;     end if
;     hdr = readAsciiHead(f, "Day")
;     nx = toint(extract_string_field(hdr(2), 11, " "))
;     ny = toint(extract_string_field(hdr(2), 13, " "))

;     pfdtot = new( (/ny,nx/), float)
;     pfdtot = 0.0
;     do i = 0, nfiles-2 ; Note: last file (i.e. for latest time) not included
;         f = wstar_files(i)
;         ; print("i = " + i + " f = " + f)

;         wstar = readAsciiTable(f, nx, "integer", 4)
;         if(UNITS .eq. "metric")
;             wssel = wstar / 100.0 - 1.15 ; Convert from cm/sec & Deduct sink rate
;         else
;             wssel = (wstar / 196.85039) - 1.15 ; But first convert to m/sec
;         end if
;         wssel = wssel > 0.0
;         dist = ((wssel*(sqrt((-5.21488508245734-wssel)/-0.000302016415111608))) \
;                /(2*wssel-2*-5.21488508245734-0.0729181700942301*(sqrt((-5.21488508245734-wssel)\
;                /-0.000302016415111608))))/2
;         pfdtot = pfdtot + dist
;         delete( (/wstar, wssel/) )
;     end do  

;     pfdtot@valid = True
;     return(pfdtot)
; end

; ;
; ; AVGSTARS
; ;
; function avgstars()
; begin
;     ; Note uses only data files
;     ; Must select files with correct date and on full hours (i.e. minutes == 00lst)

;     cmd = "ls -l --time-style=+%F " + BaseDir + "/" + Region + "/OUT/stars.*lst.d2.data"
;     star_files = systemfunc(cmd)
;     nfiles = dimsizes(star_files)
;     delete(cmd)

;     ; Read one file to extract date and nx, ny
;     ; Assume that a file in the middle has date of interest
;     ; May old files from change of DST may exist

;     n = string_pattern_grep(star_files(0), " ")
;     f = extract_string_field(star_files(nfiles/2), n+1, " ") ; filename only for a file in the middle - note "ls -l" 
;     hdr = readAsciiHead(f, "Day")

;     yr  = stringtointeger(extract_string_field(hdr(3), 2,  " "))
;     mon = stringtointeger(extract_string_field(hdr(3), 3,  " "))
;     dom = stringtointeger(extract_string_field(hdr(3), 4,  " "))
;     nx  = stringtointeger(extract_string_field(hdr(2), 11, " "))
;     ny  = stringtointeger(extract_string_field(hdr(2), 13, " "))

;     stars_tot = new( (/ny,nx/), float)
;     stars_tot = 0.0
;     do i = 0, nfiles-2 ; Note: last file (i.e. for latest time) not included
;         F = star_files(i)
;         n = string_pattern_grep(F, " ")
;         f = extract_string_field(F, n+1, " ") ; full filename only - note "ls -l" above!
;         ; print("i = " + i + " f = " + f)

;         ; Check date is correct
;         hdr = readAsciiHead(f, "Day")
;         yr1  = stringtointeger(extract_string_field(hdr(3), 2,  " "))
;         mon1 = stringtointeger(extract_string_field(hdr(3), 3,  " "))
;         dom1 = stringtointeger(extract_string_field(hdr(3), 4,  " "))
;         if(yr1 .ne. yr .or. mon1 .ne. mon .or. dom1 .ne. dom)
;             print(f + " has wrong date")
;             continue;
;         end if

;         stars = readAsciiTable(f, nx, "float", 4)
;         stars_tot = stars_tot + stars
;         delete( stars )
;         ; print(max(stars_tot))
;     end do  

;     stars_tot = stars_tot / (nfiles-1)
;     stars_tot@valid = True
;     return(stars_tot)
; end

;
; STARS
;
; Note that wind is sfcwind (10m) if HGflag==True else blavgwind
function stars(hglider_mag, ter, cu_pot, wind, bsratio_mag, slvl, HGflag) 
local hglider, stars
begin
	; WARNING: params here are in feet & Knots
	; hglider, ter, blavgwind & cu_pot need conversion

	hglider = 3.28084 * hglider_mag ; Convert to feet
	cupot  = 3.28084 * cu_pot      ; Convert to feet
	if(HGflag) then
		wind_local = 2.2369363 * wind	; Convert to mph(!?)
	else
		wind_local = 1.9438445 * wind	; Convert to Kts
	end if

	; Start with hglider
	stars = hglider
	stars = where(hglider .gt. 4000.0, 5000, stars)
	stars = where(hglider .le. 4000.0, 4000, stars)
	stars = where(hglider .le. 3500.0, 3000, stars)
	stars = where(hglider .le. 3000.0, 2000, stars)
	stars = where(hglider .le. 2500.0, 1000, stars)
	stars = where(hglider .lt. 1500.0, 0000, stars)
	; print("stars(hglider): Min = " + min(stars) + " Max = " + max(stars) )

	; If it's the same as the Terrain, rating must be 0
	stars = where(stars .eq. ter * 3.28084, 0, stars)
	; print("stars(ter): Min = " + min(stars) + " Max = " + max(stars) )

	; Apply modification for "small puffy clouds"
	; Criterion is small(ish) clouds if 500 < cu_pot < 5000
	; If cu_pot < 0 => blue
	; print("stars - cupot: Min = " + min(cupot) + " Max = " + max(cupot) )
	stars = where(cupot .gt. 500.0 .and. cupot.lt.5000.0, stars + 500.0, stars)
	stars = where(cupot .lt. 0.0                        , stars - 500.0, stars)
	; print("stars(cu_pot): Min = " + min(stars) + " Max = " + max(stars) )

	; Wind Reduction and bsratio adjustment

	MAXWIND = 15.0	; Winds (Kt) less than this do not reduce rating

	; NB Star ratings are 0 - 5000
	if(HGflag) then
		; updated 16/5/2014 sreduction = 1000.0 * (0.043 * (wind_local ^ 2.0) - 0.71 * wind_local + 3)
		sreduction = where( wind_local .gt. 8.0 , 1000.0 * (0.047 * (wind_local ^ 2.0) - 0.74 * wind_local + 2.9), 0)
	else
		sreduction = where( wind_local .lt. MAXWIND, MAXWIND, wind_local)
		sreduction = 200 * ((sreduction - MAXWIND)^2.0) / sreduction
	end if
	; print ( " stars No Wind "+min(stars)+","+max(stars) ) 
	stars = stars - sreduction
	stars = stars > 0
	; print("stars(wind_local): Min = " + min(stars) + " Max = " + max(stars) )

	;;;;; bsratio Adjustment ;;;;;;
	; stars += (bsratio - 3) * 300
	; 3 is No Adjustment; +/-300 for each integer away from this
	; Max bsratio is 6
	; Min adjustment -900 @ bsratio = 0
	; Max adjustment +900 @ bsratio = 6
	; Note bsratio cannot be < 0!

	MAXBSRATIO = 5.0  ; Very seldom better than this in the UK :-)
	bsadjust = where(bsratio_mag .gt. MAXBSRATIO, MAXBSRATIO, bsratio_mag)
	stars = stars + ((bsadjust - 3.0) * 300)
	stars = stars > 0
	; print("stars(bsratio): Min = " + min(stars) + " Max = " + max(stars) )

	;;; End bsratio adjustment				

	; Pentreath's adjustment
	if( HGflag ) then
		; updated 16 May 2014 sreduction = 0.0077*(slvl-1001)^2 - 0.323*(slvl-1001) + 3.4
		sreduction = 0.0062*(slvl-1002)^2 - 0.29*(slvl-1002) + 3.4
		stars = stars - 1000 * sreduction
		stars = stars > 0
		; print("pentreath: min = "+min(sreduction)+" max = "+max(sreduction))
	end if
	; end Pentreath

	; Spatially filter the Rating
	; Here you can choose your filter :-)
	; Only FIR filters supported
	; N_coeffs should be odd, to avoid shift

	; The coeffs should probably be selected by gridspacingkm,
	; To give similar results for each resolution (??)

	; wgt = (/ 1., 1, 1, 1, 1/) ; Simple (1/n, 1/n, ... ) filter

	; wgt = (/                                  1.,       1.                                      /)	; Don't use N_coeffs is even
	; wgt = (/                              1.,      2.,       1.                                 /)
	; wgt = (/                          1.,     3.,       3.,      1.                             /)	; Don't use N_coeffs is even
	; wgt = (/                      1.,     4.,       6.,      4.,      1.                        /)
	  wgt = (/                  1.,     5.,      10.,     10.,      5.,      1.                   /)	; Don't use N_coeffs is even
	; wgt = (/              1.,     6.,     15.,      20.,     15.,      6.,     1.               /)
	; wgt = (/          1.,    7.,     21.,      35.,      35.,      21.,    7.,      1.          /)	; Don't use N_coeffs is even
	; wgt = (/       1.,    8.,    28.,     56.,      70.,      56.,     28.,     8.,     1.      /)
	; wgt = (/   1.,    9.,    36.,     84.,     126.,     126.,     84.,     36.,    9.,    1.   /)	; Don't use N_coeffs is even
	; wgt = (/1.,   10.,   45.,    120.,    210.,     252.,     210.,    120.,    45.,   10.,   1./)

	; Ensure coeffs sum to 1.0 to avoid scale change
	wgt = wgt / sum(wgt)

	; Filter Horizontally
	; stars = wgt_runave(stars, wgt, -1)	; Cyclic conditions
	stars = wgt_runave(stars, wgt, 0)       ; Unsmoothed beginning and end pts to _FillValue
	; stars = wgt_runave(stars, wgt, 1)	; Reflective (symmetric) conditions
	; print ( " stars Filtered " + min(stars) + "," + max(stars) ) 

	; Transpose array
	stars!0 = "x"
	stars!1 = "y"
	stars_T = stars(y|:, x|:)

	; Filter transposed array (i.e. vertically)
	stars_T = wgt_runave(stars_T, wgt, 0)

	; Transpose back again
	stars_T!0 = "x_T"
	stars_T!1 = "y_T"
	stars_U = stars_T(y_T|:, x_T|:)

	; Normalize to 0 - 5
	stars_U = stars_U / 1000.0 

	; print ( " stars_U Filtered " + min(stars_U) + "," + max(stars_U) ) 

	stars_U@_FillValue = 0.0001

	return(stars_U)
end

;
; BLWIND
;
procedure blwind(z, ter, pblh, nx, ny, nz, ua, va, windspeed, ublavg, vblavg )
begin
	;;; calc bl avg winds for plotting
	ublavg = new( (/ny,nx/), float)
	calc_blavg(ua,z,ter,pblh, nx,ny,nz, ublavg )

	vblavg = new( (/ny,nx/), float)
	calc_blavg(va,z,ter,pblh, nx,ny,nz, vblavg )

	windspeed = sqrt(ublavg * ublavg + vblavg * vblavg)
end

;
; SFCWIND0 (2m wind)
;
procedure sfcwind0(ua, va, uplot, vplot, mag)
begin
	uplot = ua(0,:,:)
	vplot = va(0,:,:)
	; mag = (uplot ^ 2.0 + vplot ^ 2.0) ^ 0.5
	mag = sqrt(uplot * uplot + vplot * vplot)
end

;
; SFCWIND (10m wind)
;
procedure sfcwind(ua, va, uplot, vplot, mag)
begin
	uplot = ua(1,:,:)
	vplot = va(1,:,:)
	; mag = (uplot ^ 2.0 + vplot ^ 2.0) ^ 0.5
	mag = sqrt(uplot * uplot + vplot * vplot)
end

;
; SFCWIND2 (30m wind)
;
procedure sfcwind2(ua, va, uplot, vplot, mag)
begin
	uplot = ua(2,:,:)
	vplot = va(2,:,:)
	; mag = (uplot ^ 2.0 + vplot ^ 2.0) ^ 0.5
	mag = sqrt(uplot * uplot + vplot * vplot)
end

;
; BLTOPWIND
;
procedure bltopwind(ua, va, z, ter, pblh, isize, jsize, ksize, uplot, vplot, mag)	; Wind at BL top
begin
	calc_bltopwind(ua,va,z,ter,pblh, isize,jsize,ksize, uplot,vplot )

	mag = sqrt(uplot * uplot + vplot * vplot)
end


;
; WRF=<param>
; Plot an arbitrary 2d/3d parameter name
;  2D paramname = "wrf=FILEparameterNAME" where FILEparamNAME is name used for NetCDF WRF output file
;  3D paramname = "wrf=FILEparameterNAME=level#" where level#=0 for lowest atm (highest soil) level
;     (note that 3D level is at constant model level, NOT constant MSL, AGL, or pressure)
;
function wrf(a, plot_param)
begin
	; param_array = split_string_into_array( plot_param, "=" )
	param_array = str_split( plot_param, "=" )
	dims = dimsizes(param_array)
        data = wrf_user_getvar(a, param_array(1), time)
        if( dims .eq. 2 ) then        ; 2D array
                bparam = data
        else ;;; **** NOT TESTED **** ;;; 3D array
                ;;; *NB* WARNING TOP-MOST LEVEL IN SOME ARRAYS HAS MISSING VALUES THERE ! eg qcloud
                ;;; 3D SIZES CHECKED SAME FOR Z,T,uz,wa,qcloud,
                datadims = dimsizes(data)
                kkdata = datadims(0)
                jjsize = datadims(1)
                iisize = datadims(2)
                if ( ismissing(iisize) ) then
                        print( "*** REQUESTED ARRAY "+plot_param+" IS NOT 3D - DIMS="+datadims )
                        exit
                else
                        level=  stringtointeger( param_array(2) )
                        bparam = data(level,:,:)
                end if
        end if
        delete ( data )

	return(bparam)
end

;
; WSTAR
;
function wstar(xsiz, ysiz, zsiz, vhf, pblh, hfx, tc)
local wstar
begin
	wstar = new( (/ysiz, xsiz/), float)

	calc_wstar( vhf, pblh, xsiz, ysiz, zsiz, wstar )

	return(wstar)
end

;
; ZBLCL
;
function zblcl(qvapor, z, ter, pblh, pmb, tc, isize, jsize, ksize)
begin
	qvaporblavg = new( (/jsize,isize/), float)
	calc_blavg(qvapor,z,ter,pblh, isize,jsize,ksize, qvaporblavg )

        bparam = new( (/jsize,isize/), float)
        calc_blclheight( pmb, tc, qvaporblavg, z, ter, pblh, isize,jsize,ksize, bparam )

	return(bparam)
end

;
; ZBLCLDIF
;
function zblcldif(ter, pblh, zblcl_mag)
begin
	return(pblh + ter - zblcl_mag)
end

;
; ZSFCLCL
;
function zsfclcl(pmb, tc, td, z, ter, pblh, isize, jsize, ksize)
begin
        bparam = new( (/jsize,isize/), float)
        calc_sfclclheight( pmb, tc, td, z, ter, pblh, isize,jsize,ksize, bparam )
	; Bombs - Out of CUDA Memory

	; Another Horrible hack - see BLCLOUDPCT
	; N = 41
	; print("*** WARNING: Only " + N + " levels")
        ; calc_sfclclheight( pmb(0:N,:,:), tc(0:N,:,:), td(0:N,:,:), z(0:N,:,:), ter, pblh, isize,jsize,N+1, bparam )

	return(bparam)
end

;
; ZSFCLCLDIF
;
function zsfclcldif(ter, pblh, zsfclcl_mag)
begin

	tmp = (pblh + ter - zsfclcl_mag)
	return(tmp)
end

;
; ABOVEBLWICW
;
function aboveblicw(qcloud, ppert, pb, z, ter, pblh, isize, jsize, ksize)
begin
        ptot = ppert + pb
	bparam = new( (/jsize,isize/), float)
	calc_aboveblinteg_mixratio( qcloud, ptot, z, ter, pblh, isize,jsize,ksize, bparam )

	return(bparam)
end

;
; SIMPLETEST - Simple test parameter that returns value of 2 everywhere
;
function simpletest(isize, jsize)
begin
	bparam = new( (/jsize,isize/), float)
	bparam = 2.0
	return(bparam)
end


;
; RIDGELIFT - Vertical velocity at approximately 300ft AGL
; Extracts the model-computed vertical velocity at a level close to 300ft (91m) AGL
; This includes all lift sources: ridge lift, convergence, wave, etc.
;
function ridgelift(wa, isize, jsize)
begin
	; Model level 3 is approximately 100m AGL, close to 300ft (91m)
	; This extracts the actual WRF-computed vertical velocity at that level
	bparam = wa(5,:,:)
	
	return(bparam)
end

;
; XCSPEED - Cross-country speed based on hourly performance calculation
;
function xcspeed(wstar_mag, dglider_mag, zsfclcldif_mag, bsratio_mag, wa, z, ter, pblh, isize, jsize, ksize)
begin
; Calculate wind convergence effect using wblmaxmin approach
wconvergence = new( (/jsize,isize/), float )
; calc_wblmaxmin( 0, wa, z, ter, pblh, isize, jsize, ksize, wconvergence )
calc_wblmaxmin( 0, wa,z,ter,pblh, isize,jsize,ksize, wconvergence )
; Add convergence effect to wstar for enhanced climb rates

; Convert enhanced wstar from m/s to cm/s for calculation
ws = (wstar_mag * 100.0) + wconvergence

; Use current hour values directly (not accumulated)
dg = dglider_mag
cu = zsfclcldif_mag
bs = bsratio_mag

; Glider performance parameters (same as PFD)
a = -0.000302016415111608
b = 0.0729181700942301
c = -5.21488508245734

; Risk factor parameters
dg_amp = 2.0
dg_fac = 200.0
dg_offx = 300.0
dg_offy = -1.0
cu_amp = 0.3
cu_fac = 50.0
cu_offx = -100.0
cu_offy = 0.7
bs_amp = 2.0
bs_fac = 1.5
bs_offx = 1.0
bs_offy = -1.0

; Calculate effective lift rate
w = ws / 100.0 - 1.0 ; Convert to m/s and subtract sink rate
w = w > 0.0

; Apply risk factors
dg_risk = dg_amp / (1.0 + exp(-(dg-dg_offx)/dg_fac)) + dg_offy
cu_risk = cu_amp / (1.0 + exp(-(cu-cu_offx)/cu_fac)) + cu_offy
bs_risk = bs_amp / (1.0 + exp(-(bs-bs_offx)/bs_fac)) + bs_offy
dg_risk = dg_risk > 0.0
cu_risk = cu_risk > 0.0
bs_risk = bs_risk > 0.0

; Apply risk adjustments to lift
w = w * dg_risk * cu_risk * bs_risk

; Calculate optimal cruise speed and average speed
v_cruise = sqrt((c-w)/a)
sink_cruise = a*v_cruise*v_cruise + b*v_cruise + c
v_avg = v_cruise * w / (w - sink_cruise)

; Ensure reasonable values and handle edge cases
v_avg = where(v_avg .lt. 0.0 .or. ismissing(v_avg), 0.0, v_avg)
v_avg = where(v_avg .gt. 200.0, 200.0, v_avg)  ; Cap at 200 km/h

; Convert to km/h for output
bparam = v_avg 

return(bparam)
end

