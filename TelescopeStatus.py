

class CommsThread(Thread):
    abort = False

    
    def run(self):       
        T = self.telescope 
        while not self.abort:
            self.telescope.telnet.write("?POS\n")
            while True:

                r= self.telescope.telnet.read_until("\n", .1)
                if r == "":
                    break               

                try:lhs,rhs = r.rstrip().split("=")
                except: continue


                if lhs == 'UTC': T.UTC = rhs
                if lhs == 'Dome_Azimuth': T.domeaz = float(rhs)
                if lhs == 'LST': T.LST = rhs
                if lhs == 'Julian_Date': T.JD = float(rhs)
                if lhs == 'Apparent_Equinox': T.appeq = float(rhs)
                if lhs == 'Telescope_HA': T.HA = rhs
                if lhs == 'Telescope_RA': T.RA = rhs
                if lhs == 'Telescope_Dec': T.Dec = rhs
                if lhs == 'Telescope_RA_Rate': T.RArate = rhs
                if lhs == 'Telescope_Dec_Rate': T.DECrate = rhs
                if lhs == 'Telescope_RA_Offset': T.RAoff = float(rhs)
                if lhs == 'Telescope_Dec_Offset': T.Decoff = float(rhs)
                if lhs == 'Telescope_Azimuth': T.Az = float(rhs)
                if lhs == 'Telescope_Elevation': T.El = float(rhs)
                if lhs == 'Telescope_Parallactic': T.prlltc = float(rhs)
                if lhs == 'Telescope_HA_Speed': T.HAspeed = float(rhs)
                if lhs == 'Telescope_Dec_Speed': T.Decspeed = float(rhs)
                if lhs == 'Telescope_HA_Refr(arcsec)': T.HArefr = float(rhs)
                if lhs == 'Telescope_Dec_Refr(arcsec)': T.Dec_refr = float(rhs)
                if lhs == 'Telescope_Motion_Status': T.Status = rhs
                if lhs == 'Telescope_Airmass': T.airmass = float(rhs)
                if lhs == 'Object_Name': T.Name = rhs.lstrip('"').rstrip('"')

                if lhs == 'Telescope_Equinox': T.equinox = rhs
                if lhs == 'Object_RA': T.obRA = rhs
                if lhs == 'Object_Dec': T.obDEC = rhs
                if lhs == 'Object_RA_Rate': T.obRArt = float(rhs)
                if lhs == 'Object_DEC_Rate': T.obDECrt = float(rhs)
                if lhs == 'Object_RA_Proper_Motion': T.obRApm = float(rhs)
                if lhs == 'Object_Dec_Proper_Motion': T.obDECpm = float(rhs)
                if lhs == 'Focus_Position': T.secfocus = float(rhs)
                if lhs == 'Dome_Gap(inch)': T.domegap = float(rhs)
                if lhs == 'Dome_Azimuth': T.domeaz = float(rhs)
                if lhs == 'Windscreen_Elevation': T.windsc = float(rhs)
                if lhs == 'UTSunset': T.UTSunset = rhs
                if lhs == 'UTSunrise': T.UTsnrs = rhs 

            time.sleep(0.7)