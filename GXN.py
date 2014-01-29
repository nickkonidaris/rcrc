'''
Devices to control the P60 GXN interface.

Written by Nick Konidaris [c] 2014

Released under GPLv2
'''

from threading import Thread
import telnetlib
from traits.api import *
from threading import Thread
import telnetlib
import re
import time
import numpy as np
import logging as log

PELE = "198.202.125.194"
PELEPORT = 49300

log.basicConfig(filename="C:\\sedm\\logs\\rcrc.txt",
    format="%(asctime)s-%(filename)s:%(lineno)i-%(levelname)s-%(message)s",
    level = log.DEBUG)





class TCSConnectionError(Exception):
    def __init__(self, value):
        self.value = value
        log.error("Could not connect to TCS. Fatal error.")
    
    def __str__(self):
        return str(self.value)
        
class TCSReadError(Exception):
    def __init__(self, value):
        self.value = value
        
        log.error("Could not read response from TCS.")
    
    def __str__(self):
        return str(self.value)


class SlowCommandFailed(Exception):
    def __init__(self, value):
        self.value = value
        log.error("Slow command returned failure")
    
    def __str__(self):
        return str(self.value)

class Commands:
    '''Wrapper around the GXN/Telnet interface'''
    
    T = None
    gxn_res = {0: "Success", -1: "Unknown command", -2: "Bad parameter", 
        -3: "Aborted", -6: "Do not have control"}
    
    def __init__(self):
        log.info("GXN Interface initalizing")
        try:
            self.T = telnetlib.Telnet(PELE, PELEPORT)
        except Exception as e:
            raise TCSConnectionError(e)
            
        log.info("Connection to %s made" % PELE)
        
        
    def __del__(self):
        self.T.close()
        
        
    def read_until(self, s,timeout):
        T = self.T
        try:
            T.read_until(s, timeout)
        except:
            raise TCSReadError(e)
    
    def slow(self, timeout):
        '''Handle a slow command but waiting for a number to return'''
        T = self.T
        try:
            r = T.expect(["-?\d"], timeout)
        except Exception as e:
            return
        
        try: res = int(r)
        except:
            log.error("Command timed out")
            return
        
        if res == 0:
            log.info("Executed command")
        else:
            log.error("Command failed: %s" % gxn_res[res])
            raise SlowCommandFailed(res)

        
    def pt(self, dRA, dDec):
        '''PT (Slow) offsets the telescope by requested amount at MRATES rates.
        Telescope_Motion_Status must be TRACKING or IN_POSITION and changes to
        MOVING during move.'''
        log.info("GXN: pt %f %f" % (dRA, dDec))
        
        T = self.T
        
        T.write("pt %f %f\n" % (dRA, dDec))
        T.slow(60)
    
    def takecontrol(self):
        T = self.T
        T.write("takecontrol\n")
        self.read_until("\n", .1)

class CommsThread(Thread):
    abort = False

    telescope = None
            
    def run(self):       
        T = self.telescope 
        while not self.abort:
            try:
                self.telescope.telnet.write("?POS\n")
            except Exception as e:
                raise TCSReadError(e)
                
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

class Telescope(HasTraits):
    comms_thread = Instance(CommsThread)
    
    telnet = Instance(telnetlib.Telnet)
    UTC = String()
    LST = String()
    JD = Float()
    appeq = Float()
    HA = String()
    RA = String()
    Dec = String()
    RArate = String()
    DECrate = String()
    RAoff = Float()
    Decoff = Float()
    Az = Float()
    El = Float()
    prlltc = Float()
    HAspeed = Float()
    Decspeed = Float()
    HArefr = Float()
    Dec_refr = Float()
    Status = String()
    airmass = Float()
    Name = String()
    equinox=String()
    obRA = String()
    obDEC = String()
    obRArt = Float()
    obDECrt = Float()
    obRApm = Float()
    obDECpm = Float()
    secfocus = Float()
    domegap = Float()
    domeaz = Float()
    windsc = Float()
    UTSunset = String()
    UTsnrs = String()
    
    
    def __init__(self):
        log.info("Telescope status thread initialized")
        
        
        try:
            self.telnet = telnetlib.Telnet(PELE, PELEPORT)
        except Exception as e:
            raise TCSConnectionError(e)

        self.comms_thread.telescope = self            
        self.comms_thread = CommsThread()




class Weather(HasTraits):
    UTC = String()
    Windspeed_Avg_Threshold = Float()
    Gust_Speed_Threshold = Float()
    Gust_Hold_Time = Float()
    Outside_DewPt_Threshold = Float()
    Inside_DewPt_Threshold = Float()
    Wetness_Threshold = Float()
    Wind_Dir_Current = Float()
    Windspeed_Current = Float()
    Windspeed_Average = Float()
    Outside_Air_Temp = Float()
    Outside_Rel_Hum = Float()
    Outside_DewPt = Float()
    Inside_Air_Temp = Float()
    Inside_Rel_Hum = Float()
    Inside_DewPt = Float()
    Mirror_Temp = Float()
    Floor_Temp = Float()
    Bot_Tube_Temp = Float()
    Mid_Tube_Temp = Float()
    Top_Tube_Temp = Float()
    Top_Air_Temp = Float()
    Primary_Cell_Temp = Float()
    Secondary_Cell_Temp = Float()
    Wetness = Int()
    Weather_Status = String()
    
    def __init__(self):
        log.info("Weather status thread initalized")
        try:
            self.telnet = telnetlib.Telnet(PELE, PELEPORT)
        except Exception as e:
            raise TCSConnectionError(e)
        self.comms_thread = WeatherCommsThread()
        self.comms_thread.weather = self
    
        
class WeatherCommsThread(Thread):
    abort = False

        
    def run(self):       
        W = self.weather 
        while not self.abort:
            try:
                W.telnet.write("?WEATHER\n")
            except Exception as e:
                raise TCSReadError(e)
                
            while True:

                r= W.telnet.read_until("\n", .1)

                if r == "":
                    break               

                try:lhs,rhs = r.rstrip().split("=")
                except: continue
                
                type_fun = type(getattr(W, lhs))
                setattr(W, lhs, type_fun(rhs))
            time.sleep(1)





class Status(HasTraits):
    Telescope_ID = Int()
    Telescope_Control_Status = String()
    Lamp_Status = String()
    Lamp_Curent = Float()
    Dome_Shutter_Status = String()
    WS_Motion_Mode = String()
    Dome_Motion_Mode = String()
    Telescope_Power_Status = String()
    Oil_Pad_Status = String()
    Weather_Status = String()
    Sunlight_Status = String()
    Remote_Close_Status = String()
    Telescope_Ready_Status = String()
    HA_Axis_Hard_Limit_Status = String()
    Dec_Axis_Hard_Limit_Status = String()
    Focus_Hard_Limit_Status = String()
    Focus_Soft_Up_Limit_Value = Float()
    Focus_Soft_Down_Limit_Value = Float()
    Focus_Soft_Limit_Status = String()
    Focus_Motion_Status = String()
    East_Soft_Limit_Value = Float()
    West_Soft_Limit_Value = Float()
    North_Soft_Limit_Value = Float()
    South_Soft_Limit_Value = Float()
    Horizon_Soft_Limit_Value = Float()
    HA_Axis_Soft_Limit_Status = String()
    Dec_Axis_Soft_Limit_Status = String()
    Horizon_Soft_Limit_Status = String()
    
    def __init__(self):
        log.info("Status thread initalized")
        
        try:
            self.telnet = telnetlib.Telnet(PELE, PELEPORT)
        except Exception as e:
            raise TCSConnectionError(e)
            
        self.comms_thread = StatusCommsThread()
        self.comms_thread.weather = self
    
        
class StatusCommsThread(Thread):
    abort = False

        
    def run(self):       
        W = self.weather 
        while not self.abort:
            try:
                W.telnet.write("?WEATHER\n")
            except Exception as e:
                raise TCSReadError(e)
                
            while True:

                r= W.telnet.read_until("\n", .1)

                if r == "":
                    break               

                try:lhs,rhs = r.rstrip().split("=")
                except: continue
                
                type_fun = type(getattr(W, lhs))
                setattr(W, lhs, type_fun(rhs))
            time.sleep(1)


class StatusThreads():
    '''
    Maintains the status watching threads and provides convenience wrappers
    around them.
    '''
    telescope  = None
    weather = None
    status = None
    
    def __init__(self):
        log.info("StatusThreads initialized")
        self.telescope = Telescope()
        self.weather = Weather()
        self.status = Status()
    
        self.telescope.run()

