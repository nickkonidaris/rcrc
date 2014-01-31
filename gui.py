
from traits.api import *

from threading import Thread
import ctypes
from httplib import CannotSendRequest
import numpy as np
import logging as log
import os
import pyfits as pf
import socket
import subprocess
from subprocess import check_output
import time
import winsound
import xmlrpclib




def ra_to_deg(ra):
    h,m,s = map(float,ra.split(":"))
    
    return 15 * h + 0.25*m + 0.0042*s

def dec_to_deg(dec):
    d,m,s = map(float,dec.split(":"))
    
    return d + m/60. + s/3600.
    
    

def ds9_image(xpa_class,  filename):
    
    if xpa_class is None:
        log.info("Can not autodisplay image")
        return
        
    retains = ["scale mode", "scale", "cmap",  "zoom", "pan to"]
    vals = []
    try:

            check_output("c:\\ds9\\xpaset -p %s frame 1" % (xpa_class), shell=True)
            for retain in retains:
                value = check_output("c:\\ds9\\xpaget %s %s" % (xpa_class, retain), shell=True)
                vals.append((retain, value))
                

            check_output("c:\\ds9\\xpaset -p %s file %s" % (xpa_class, filename), shell=True)
            check_output("c:\\ds9\\xpaset -p %s frame match wcs" % (xpa_class), shell=True)
            
            for key, val in vals:
                check_output("c:\\ds9\\xpaset -p %s %s %s" % (xpa_class, key, val), shell=True)
            
            if filename.find("rc") != -1:
                check_output("C:\\ds9\\xpaset -p %s regions load c:/sw/sedm/ds9.reg" % (xpa_class), shell=True)

    
    #check_output("c:\\ds9\\xpaset -p %s cmap invert yes" % (xpa_class), shell=True)
    except Exception as e:
        #FIXME
        
        
        pass

def play_sound(snd="SystemAsterix"):
    
    try:
        Play = Thread(target=winsound.PlaySound, args=(snd, 
            winsound.SND_ALIAS))
        Play.start()
    except:
        pass


class ExposureCommsProblem(Exception):
    def __init__(self, value):
        self.value = value
        log.error("Could not take exposure: %s" % value)
    
    def __str__(self):
        return str(self.value)
        
        
class Camera(HasTraits):
    '''Exposure Control'''  
    name = String("rc")  
    target_name = String()
    object = String
    connection = None #xmlrpclib object to connect to PIXIS camera
    connection_pid = None

    state = String("Idle")
    filename = String("")
    
    gain = Enum(2,1,3,
        desc="the gain index of the camera",
        label='gain')
    
    num_exposures = Int(1)
    
    int_time = Int(0)
    
    readout = Enum([0.1, 2.0],
        desc="Readout speed in MHz",
        label="readout")
        
    amplifier = Enum(1,2,
        desc="the amplifier index",
        label = 'amp')
    
    shutter = Enum('normal', 'closed')
    
    xpa_class = String()
    
    exposure = Float(10, desc="the exposure time in s",
        label = "Exposure")
        
    def run(self):
        nexp = self.num_exposures
        while self.num_exposures > 0:
            
            hdrvalues_to_update = []
            
            stats = self.status_function()
            header_vals = {}
            
            #flatten variables for header
            for stat, stat_item in stats.items():
                if type(stat_item) == dict:
                    for k,v in stat_item.items():
                        header_vals[k] = v
            
            for k,v in header_vals.items():
                if type(v) in [float, int, str]:
                    hdrvalues_to_update.append((k,v))


            socket.setdefaulttimeout(self.exposure + 60)
            number_acq_attempts = 2
            while number_acq_attempts > 0:
                try:
                    filename = self.connection.acquire().data
                    number_acq_attempts = 0
                except Exception as e:
                    log.info("Received exception %s" % e)
                    self.make_connection()
                        
                    number_acq_attempts -= 1
                    filename = ''
                    
            socket.setdefaulttimeout(None)
            
            if filename == '':
                raise ExposureCommsProblem("Could not read camera, server keeps failing. Likely a hardware issue")
            
            if not os.path.exists(filename):
                raise ExposureCommsProblem("Camera timed out. Likely a reconnect or reboot is needed.")
                
            self.filename = filename
            self.state = "Updating Fits %s" % filename
            try:
                hdus = pf.open(filename)
                hdr = hdus[0].header
                hdr.update("OBJECT",self.object)
            except:
                self.state = "Could not open raw fits"
                return
            

            for el in hdrvalues_to_update:
                trait, val = el

                try: hdr.update(trait, val)
                except: pass
            
            if self.name == 'ifu':
                if self.amplifier == 1:
                    if self.readout == 0.1:
                        if self.gain == 1: gain = 3.29
                        if self.gain == 2: gain = 1.78
                        if self.gain == 3: gain = 0.89
                    if self.readout == 2:
                        if self.gain == 1: gain = 3.49
                        if self.gain == 2: gain = 1.82
                        if self.gain == 3: gain = 0.90
                if self.amplifier == 2:
                    if self.readout == 0.1:
                        if self.gain == 1: gain = 14.72
                        if self.gain == 2: gain = 7.03
                        if self.gain == 3: gain = 3.49
                    if self.readout == 2:
                        if self.gain == 1: gain = 13.92
                        if self.gain == 2: gain = 6.88
                        if self.gain == 3: gain = 3.43
            elif self.name == 'rc':
                if self.amplifier == 1:
                    if self.readout == 0.1:
                        if self.gain == 1: gain = 3.56
                        if self.gain == 2: gain = 1.77
                        if self.gain == 3: gain = 0.90
                    if self.readout == 2:
                        if self.gain == 1: gain = 3.53
                        if self.gain == 2: gain = 1.78
                        if self.gain == 3: gain = 0.88
                if self.amplifier == 2:
                    if self.readout == 0.1:
                        if self.gain == 1: gain = 14.15
                        if self.gain == 2: gain = 7.27
                        if self.gain == 3: gain = 3.79
                    if self.readout == 2:
                        if self.gain == 1: gain = 14.09
                        if self.gain == 2: gain = 7.02
                        if self.gain == 3: gain = 3.52
                        
            hdr.update("GAIN", gain, 'gain in e-/ADU')
            hdr.update("CHANNEL", self.name, "Instrument channel")
            hdr.update("TNAME", self.target_name, "Target name")
            
            if self.name == 'rc':
                hdr.update("CRPIX1", 1293, "Center pixel position")
                hdr.update("CRPIX2", 1280, "")
                hdr.update("CDELT1", -0.00010944, "0.394 as")
                hdr.update("CDELT2" ,-0.00010944, "0.394 as")
                hdr.update("CTYPE1", "RA---TAN")
                hdr.update("CTYPE2", "DEC--TAN")
                hdr.update("CRVAL1", ra_to_deg(hdr["RA"]), "from tcs")
                hdr.update("CRVAL2", dec_to_deg(hdr["Dec"]), "from tcs")
            elif self.name == 'ifu':
                hdr.update("CRPIX1", 1075, "Center pixel position")
                hdr.update("CRPIX2", 974, "Center pixel position")
                hdr.update("CDELT1", -0.0000025767, "0.00093 as")
                hdr.update("CDELT2", -0.0000025767, "0.00093 as")
                hdr.update("CTYPE1", "RA---TAN")
                hdr.update("CTYPE2", "DEC--TAN")
                as120 = 0.03333
                hdr.update("CRVAL1", ra_to_deg(hdr["ra"]) - as120, "from tcs")
                hdr.update("CRVAL2", dec_to_deg(hdr["dec"]) - as120, "from tcs")

            new_hdu = pf.PrimaryHDU(np.uint16(hdus[0].data), header=hdr)
            hdus.close()

            tempname = "c:/users/sedm/appdata/local/temp/sedm_temp.fits"
            origname = filename

            
            try: os.remove(tempname)
            except WindowsError: pass
            
            try:
                os.rename(origname, tempname)
            except Exception as e:
                log.error("Rename %s to %s failed" % (filename, tempname))
                self.state = "Rename %s to %s failed" % (filename, tempname)
                play_sound("SystemExclamation")
                return
            
            try:
                new_hdu.writeto(filename)
            except:
                os.rename(tempname, filename)
                self.state = "Could not write extension [2]"
                play_sound("SystemExclamation")
                return
                

            play_sound("SystemAsterix")    
            
            ds9_image(self.xpa_class,  filename)
            self.num_exposures -= 1
        self.num_exposures = 1
        self.state = "Idle"
        if nexp > 1: play_sound("SystemExclamation")

    def make_connection(self):
        sedmpy = "C:/Users/sedm/Dropbox/Python-3.3.0/PCbuild/amd64/python.exe"
        
        if self.connection_pid is not None:
            ctypes.windll.kernel32.TerminateProcess(int(self.connection_pid._handle))
        
        try:    
            self.connection_pid = subprocess.Popen([sedmpy, "c:/sw/sedm/camera.py", "-rc"])
            time.sleep(0.5)
            self.connection = xmlrpclib.ServerProxy("http://127.0.0.1:8001")
        except:
            raise ExposureCommsProblem("Could not make a detector connection.")

        self.update_settings()
        self.connection.set_shutter(self.shutter)

    
    def _gain_changed(self): self.update_settings()
    def _readout_changed(self): self.update_settings()
    def _amplifier_changed(self): self.update_settings()
    def _exposure_changed(self): self.update_settings()
    def _shutter_changed(self): 
        self.connection.set_shutter(self.shutter)
        
        
    def update_settings(self):
        try:
            self.connection.set([self.exposure, self.gain, self.amplifier, 
                self.readout])
        except CannotSendRequest:
            self.state = "DID NOT UPDATE. RETRY"
        except: 
            self.state = "DID NOT UPDATE. Retry"



if __name__ == '__main__':
    c = Camera()
    c.make_connection()


    