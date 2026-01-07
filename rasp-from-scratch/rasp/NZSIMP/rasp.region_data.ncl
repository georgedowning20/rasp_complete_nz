#############################################################################################
#############  RASP PLOT INFORMATION - to be read by rasp.ncl  ##############################
#############################################################################################
### FORMAT FOR EACH REGION:
###   1st line: ===MY_REGION_NAME (matching that used in rasp.pl, spaces not allowed)
###   2nd line: units (american/celsius/metric)
###   then (optional) sounding location(s) of 4 lines each: (1) "sounding#" (where # is an integer) (2) sounding id (spaces allowed) (3) latitude (decimal degrees,S=negative) (4) longitude (decimal degrees, W=negative)
###   ( sounding integers normally increase sequentially but need not - numbers must not contain a "+" sign )
### IF RUN REGION IS NOT IN THIS FILE, THEN DEFAULT UNITS USED AND NO SOUNDINGS ARE PLOTTED
#############################################################################################
===NZSIMP
celsius
sounding1
~F34~7~F21~Te Aroha
-37.5333
175.7000
sounding2
~F34~7~F21~Matamata GC
-37.8100
175.7700
sounding3
~F34~7~F21~Paeroa
-37.3700
175.6700
