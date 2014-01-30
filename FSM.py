#
#   Created by Nick Konidaris [c] 2014
#   Licensed under the GPL
#
#   npk@astro.caltech.edu
#
#   This module is a simple state machine
#

import time
from datetime import datetime, timedelta
import logging as log
import telnetlib
import smtplib
import GXN
import subprocess
import xmlrpclib
import gui
from threading import Thread

email_list = ["nick.konidaris@gmail.com"]


# Global Variables
Status = 0
rc_pid = 0
theSM =0
rc_gui=0

# create logger
log.basicConfig(filename="C:\\sedm\\logs\\rcrc.txt",
    format="%(asctime)s-%(filename)s:%(lineno)i-%(levelname)s-%(message)s",
    level = log.DEBUG)

log.info("?***************************** START ********")


mn = 60

Constants = {
    'config_flats_timeout': 10*mn,
    'hours_before_sunset_to_calibrate': 6,
    'lamp_flat_exposure_time_s': 7,
    'number_lamp_exposures': 1
    
}

Status = GXN.StatusThreads()
GXNCmd = GXN.Commands()

def classname(object):
    return object.__class__.__name__

def get_input():
    log.debug("Called get_input")
    status = {}
    
    status['OK'] = False
    for object in [Status.weather, Status.telescope, Status.status]:
        for trait in object.traits():
            
            cn = classname(object)
            try:
                if cn not in status:
                    status[cn] = {trait: object.__getattribute__(trait)}
                else:
                    status[cn][trait] = object.__getattribute__(trait)
            except AttributeError:
                pass
    
    if status['Status']['UTC'] == '': return status
    status['OK'] = True
    
    y,d,h,m,s = map(float, status['Status']['UTC'].split(":"))
    sunrise_h, sunrise_m = map(float, status['Telescope']['UTsnrs'].split(":"))
    sunset_h, sunset_m = map(float, status['Telescope']['UTSunset'].split(":"))
    
    hm = h+m/60.
    sunset_hm = sunset_h + sunset_m/60.
    sunrise_hm = sunrise_h + sunrise_m/60.

    sunup = (hm < sunset_hm) or (hm > sunrise_hm)
    
    status['Status']['Sun_Is_Up']= sunup
    if sunup: log.info("Sun is up")
    
    # Calibration time is 2 hours before sunrise
    calibration_h = sunset_h-Constants['hours_before_sunset_to_calibrate']
    calibration_m = sunset_m
    
    if calibration_h <= 0: calibration_h += 24
    
    a = h+m/60.
    b = (calibration_h+calibration_m/60.)
    calibration_hm = calibration_h + calibration_m/60.
    calibration_time = (hm >= calibration_hm) or (hm < sunset_hm)


    if calibration_time: 
        log.info("Time to calibrate")
        status['Status']['Calibration_Time'] = True
    else: 
        status['Status']['Calibration_Time'] = False
        log.info("Will begin calibrations at %2.2i:%2.2i UT" % (calibration_h,
        calibration_m))
    
    
    # Observe time
    status['Status']['Observe_Time'] =  hm > (sunset_hm + 0.5)
    if not status['Status']['Observe_Time']:
        log.info("Ready to observe at %2.2f" % (sunset_hm+0.5))
    
    
    return status        

def is_dome_open(status):
    
    return status['Status']['Dome_Shutter_Status'] == 'OPEN'

def is_ok_to_observe(status):
    '''Returns true if it's past 12 deg twilight'''
    
    return is_sun_ok(status) and status['Status']['Observe_Time']

def is_sun_ok(status):
    '''Returns true if sunlight status OK'''
    if not status['OK']: return False
    
    s = status['Status']['Sunlight_Status'] == 'OKAY'
    
    if s: log.info("Sunlight status is OK")
    else: log.info("Sunlight status is OK")
    
    # Double check
    s2 = not status['Status']['Sun_Is_Up']
    
    if s!= s2:
        log.info("Sunlight_Status and sunset/sunrise times do not agree. Assuming sun is up")
        return False
    
    return s

def is_lamp_off(status):
    '''Returns true if lamp is off'''
    
    s = status['Status']['Lamp_Status'] == 'OFF'
    
    if s: log.info("Lamps are off")
    else: log.info("Lamps are on")
    return s
    
def is_weather_safe(status):
    '''Returns true if weather status is OK'''
    
    s = status['Status']['Weather_Status'] == 'OKAY'
    
    if s: log.info("Weather status OK")
    else: log.info("Weather not safe")
    return s


def is_telescope_initialized(status):
    '''Returns true if the teelscope is initialized'''
    
    s = status['Status']['Telescope_Ready_Status']
    if s == 'NOT_READY':
        log.info("Telescope is not initialized")
        return False
    else:
        log.info("Telescope is initialized")
        return True
        
def is_telescope_in_instrument_mode(status):
    '''Returns true if telescope is in instrument (not manual) mode'''
    
    s = status['Status']['Telescope_Control_Status']
    
    if s == 'REMOTE':
        log.info("Telescope is available")
        return True
    else:
        log.info("Telescope in manual mode")
        return False
    
    
def is_telescope_powered(status):
    ''' Returns true if telescope is powered on'''
    
    s = status['Status']
    if  (s['Oil_Pad_Status'] == 'READY') and \
        (s['Telescope_Power_Status'] == 'READY'):
            log.info("Telescope is powered")
            return True
    else:
        log.info("Telescope is not powered")
        return False




def email(to, message):
    FROM = "palomar.sed.machine@gmail.com"
    SUBJECT = "SEDM News"
    
    header = "\r\n".join(
        ["from: %s" % FROM,
        "subject: %s" % SUBJECT,
        "to: %s" % ", ".join(to),
        "mime-version: 1.0",
        "content-type: text/html"])
    
    email = header + "\r\n\r\n" + message
    
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.login("palomar.sed.machine", "palomar rules")
    
    log.info("Emailing") 
    log.info(email)
    server.sendmail("palomar.sed.machine", to, email)
    server.quit()

class State(object):
    elapsed = timedelta(0) # length of time in the state
    n_times = 0 # Number of times executed
    
    def __init__(self):
        log.info("Initialized state '%s'" % self.__class__.__name__)

    
    def execute(self, prev_state_name, inputs):
        log.info("[%s].execute()" % self.__class__.__name__)


class DomeOpenState(object):
    '''Similar to State. Checks to see if it's safe to observe '''
    
    elapsed = timedelta(0) # length of time in the state
    n_times = 0 # Number of times executed
    
    def __init__(self):
        log.info("Initialized dome open state '%s'" % self.__class__.__name__)
        
    def execute(self, prev_state_name, inputs):
        
        if not is_weather_safe(inputs):
            return "weather_safe"
        
        if not is_sun_ok(inputs):
            return "close"
        
        log.info("[%s].execute()" % self.__class__.__name__)            


def check_basics(inputs):
    ''' Check to see if the telescope is ready for basic observations'''
    if not is_telescope_powered(inputs):
        return "telescope_not_powered"
    elif not is_telescope_in_instrument_mode(inputs):
        return "telescope_not_in_instrument_mode"
    elif not is_telescope_initialized(inputs):
        if (not inputs['Status']['Sun_Is_Up']) or (inputs['Status']['Calibration_Time']):
            return "telinit"

    
    return ""
    

class startup(State):
    '''Entry point state'''
    
    def __init__(self):
        State.__init__(self)
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
    
        new_state = check_basics(inputs)

        if new_state != '':
            return new_state
        
        if inputs['Status']['Calibration_Time']:
            return "configure_flats"
        
        if not inputs['Status']['Sun_Is_Up']:
            return "open_dome"
            
        time.sleep(10)
        return "startup"
        
class telinit(State):
    def __init__(self):
        State.__init__(self)
            
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        cmd = GXNCmd
        try: cmd.telinit()
        except: return "telinit_failed"
        
        return "startup"
        
class telinit_failed(State):
    def __init__(self):
        State.__init__(self)
            
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        
        if prev_state_name != 'telinit_failed':
            log.error("Telinit failed, likely because the dome is in manual mode. Emailing people.")
            log.error("Sleeping for 10 m and trying again")
        
        time.sleep(600)
        return "telinit"


class configure_flats(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        #cmd = GXN.Commands()
        #cmd.takecontrol()
        try: GXNCmd.lamps_on()
        except: return "lampson_failed"
        
        try: GXNCmd.stow_flats()
        except: return "stow_failed"
        
        return "take_flats"

class take_flats(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        global rc_gui
        State.execute(self, prev_state_name, inputs)
        
        cmd = GXNCmd

        rc_gui.object = "Flat"
        for i in range(Constants['number_lamp_exposures']):
            expose(Constants['lamp_flat_exposure_time_s'])
            time.sleep(1)
                        
        return "check_take_flats"

class check_take_flats(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        return "waitfor_sunset"

class waitfor_sunset(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        if inputs['Status']['Sun_Is_Up']:
            time.sleep(10)
            return "waitfor_sunset"    
        
        return "open_dome"
        
class open_dome(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        new_state = check_basics(inputs)
        if new_state != '': return new_state
        
        if not is_weather_safe(inputs):
            return "weather_safe"
        
        if not is_sun_ok(inputs):
            return "waitfor_sunset"
        
        
        if not is_dome_open(inputs):
            try: GXNCmd.open_dome()
            except:
                return "open_dome_failed"
        
        return "observe"


## DOME Open States

class observe(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        DomeOpenState.execute(self, prev_state_name, inputs)
            
        if is_ok_to_observe(inputs):
            return "select_target"

        
        time.sleep(10)
        return "observe"
        
class telescope_not_powered(State):
    def __init__(self):
        State.__init__(self)
    
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        if prev_state_name != 'telescope_not_powered':
            log.error("Telescope is not powered. Emailing people")
        
        return check_basics(inputs)



class telescope_not_powered(State):
    def __init__(self):
        State.__init__(self)
    
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        if prev_state_name != 'telescope_not_powered':
            log.error("Telescope is not powered. Emailing people")
        
        return check_basics(inputs)

class telescope_not_in_instrument_mode(State):
    def __init__(self):
        State.__init__(self)
    
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        if prev_state_name != 'telescope_not_in_instrument_mode':
            log.error("Telescope is not in instrument mode. Emailing people")
        
        return check_basics(inputs)

class StateMachine:
    # statetable is initialized dynamically by programatically
    # identifying sub classes of class State/
    statetable = {}
    prev_state_name = None
    next_state_name = None
    
    def __init__(self):
        log.info("Initializing StateMachine and all states...")
        states = State.__subclasses__()
        for state in states:
            self.statetable[state.__name__] = state()
        
        states = DomeOpenState.__subclasses__()
        for state in states:
            self.statetable[state.__name__] = state()
            
        log.info("All states initialized.")
        
        self.prev_state_name = None
        self.next_state_name = "startup"
    
    def execute(self, inputs):
        
        now = datetime.now()
        ns = self.statetable[self.next_state_name]
        
        log.info("Executing %s" % self.next_state_name)
        print self.next_state_name
        self.prev_state_name = self.next_state_name
        self.next_state_name = ns.execute(self.prev_state_name, inputs)
        
        if self.prev_state_name != self.next_state_name:
            log.info("Transitioning %s->%s" % (self.prev_state_name, 
                self.next_state_name))
        
        elapsed = datetime.now() - now
        ns.elapsed += elapsed
        ns.n_times += 1

def expose(itime):
    global rc_gui
    
    rc_gui.exposure = itime
    log.info("Exposing for %3.1f s" % (itime))
    print "Exposing for %3.1f s" % itime
    rc_gui._go_button_fired()
    time.sleep(1)
        
    while rc_gui.int_time < (rc_gui.exposure + 3):
        time.sleep(0.5)
    
    time.sleep(2)
    rc_gui.int_time = 0
        
def main():
    global Status, rc_pid, rc_gui, theSM
    
    Status.start()
    time.sleep(1)
    
    curr_state = None
    next_state = "startup"
    
    theSM = StateMachine()
    sedmpy = "C:/Users/sedm/Dropbox/Python-3.3.0/PCbuild/amd64/python.exe"

    rc_pid = subprocess.Popen([sedmpy, "c:/sw/sedm/camera.py", "-rc"])
    time.sleep(0.5),
    rc_con = xmlrpclib.ServerProxy("http://127.0.0.1:8001")
    time.sleep(2)
    
    rc_gui, rc_view = gui.gui_connection(rc_con, 'rc', get_input)
    rc_gui.configure_traits(view=rc_view)

    rc_gui._shutter_changed()
    rc_gui.update_settings()
    rc_gui.xpa_class = 'c6ca7de8:18387'

def fsm_loop():
    global Status, rc_pid, theSM
    i = 0
    GXNCmd.takecontrol()
    while i < 100:
        try:
            inputs = get_input()
            theSM.execute(inputs)
            time.sleep(.5)
        except GXN.TCSConnectionError:
            log.info("Caught a communication error. Rebooting computer.")
            return
            import os
            email(email_list, """Sed machine cannot communicate with TCS. The
            instrument will attempt to reboot and continue. Sorry for the spam.""")
            log.info("executing shutdown -r")
            #os.system("shutdown -r")

        i += 1


if __name__ == '__main__':
    main()
    Thread(target=fsm_loop).start()