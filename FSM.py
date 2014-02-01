#
#   Created by Nick Konidaris [c] 2014
#   Licensed under the GPL
#
#   npk@astro.caltech.edu
#
#   This module is a simple state machine
#

from astropy.table import Table
from astropy.coordinates import Angle

import ctypes
from datetime import datetime, timedelta
import ExposureSet
import Focus
import gui
import GXN
import logging as log
import numpy
import smtplib
import SimpleQueue
from threading import Thread
import time


email_list = ["nick.konidaris@gmail.com"]


# Global Variables

Status = GXN.StatusThreads()

theSM =0

rc_camera = None
next_target = []
target_plan = []
#last_focus = [datetime(2010, 1, 1, 1, 1, 1) , 14.3]
last_focus = [datetime.now() , 14.38]
stop_loop = False

force_focus = True


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
    'number_lamp_exposures': 15,
    'Hours_between_focus': 3,
    'number_bias_exposures': 10,
    'number_dark_exposures': 3,    
    'dark_exposure_time': 180
}



def classname(object):
    return object.__class__.__name__

def get_input():

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
    if sunup: log.debug("Sun is up")
    
    # Calibration time is 2 hours before sunrise
    calibration_h = sunset_h-Constants['hours_before_sunset_to_calibrate']
    calibration_m = sunset_m
    
    if calibration_h <= 0: calibration_h += 24
    
    calibration_hm = calibration_h + calibration_m/60.
    calibration_time = (hm >= calibration_hm) or (hm < sunset_hm)


    if calibration_time: 
        log.debug("Time to calibrate")
        status['Status']['Calibration_Time'] = True
    else: 
        status['Status']['Calibration_Time'] = False
    
    
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
    
    if s: log.debug("Sunlight status is OK")
    else: log.debug("Sunlight status is OK")
    
    # Double check
    s2 = not status['Status']['Sun_Is_Up']
    
    if s!= s2:
        log.info("Sunlight_Status and sunset/sunrise times do not agree. Assuming sun is up")
        return False
    
    return s


def is_telescope_tracking(status):
    '''Returns true if telescope is tracking'''
    
    return status['Telescope']['Status'] == 'TRACKING'
    
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
        log.debug("Telescope is not initialized")
        return False
    else:
        log.debug("Telescope is initialized")
        return True
        
def is_telescope_in_instrument_mode(status):
    '''Returns true if telescope is in instrument (not manual) mode'''
    
    s = status['Status']['Telescope_Control_Status']
    
    if s == 'REMOTE':
        log.debug("Telescope is available")
        return True
    else:
        log.debug("Telescope in manual mode")
        return False
    
    
def is_telescope_powered(status):
    ''' Returns true if telescope is powered on'''
    
    s = status['Status']
    if  (s['Oil_Pad_Status'] == 'READY') and \
        (s['Telescope_Power_Status'] == 'READY'):
            log.debug("Telescope is powered")
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
        
        log.info("Is Weather safe? %s" % is_weather_safe(inputs))
        if not is_weather_safe(inputs):
            log.info("[%s] is in weather safe mode" % self.__class__.__name__)
            return "weather_safe"
        
        if not is_sun_ok(inputs):
            log.info ("[%s] sun is not ok" % self.__class__.__name__)
            return "close"
        
        log.info("[%s].execute()" % self.__class__.__name__)            
        return ""

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
        
        try: 
            cmd = GXN.Commands()
            cmd.telinit()
            cmd.close()
        except: 
            cmd.close()
            return "telinit_failed"
        
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
        
        try: 
            log.info("Turning on lamps..")
            GXNCmd = GXN.Commands()
            GXNCmd.lamps_on()
            GXNCmd.close()
        except: 
            return "lampson_failed"
        
        try: 
            GXNCmd = GXN.Commands()
            GXNCmd.stow_flats()
            GXNCmd.close()
        except:
            GXNCmd.close()
            return "stow_failed"
        
        return "take_flats"

class take_flats(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        global rc_gui
        State.execute(self, prev_state_name, inputs)
        

        rc_camera.object = "Flat"
        rc_camera.shutter = "normal"
        for i in range(Constants['number_lamp_exposures']):
            try:
                expose(Constants['lamp_flat_exposure_time_s'])
            except gui.ExposureCommsProblem:
                return "detector_problem"
            time.sleep(1)
          
        try: 
            GXNCmd = GXN.Commands()
            GXNCmd.lamps_off()
            GXNCmd.close()
        except:
            GXNCmd.close()
            
        return "check_take_flats"

class detector_problem(State):
    def __init__(self):
        State.__init__(self)
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        cmd = GXN.Commands()
        cmd.stop()
        cmd.close_dome()
        cmd.close()
        log.error("Major detector problem identified. Could be unplugged or system may require reboot")
        # email people here
        
        time.sleep(2000)
        return "detector_problem"
        
class check_take_flats(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        return "take_darks"

class take_darks(State):
    def __init__(self):
        State.__init__(self)
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        rc_camera.object = "bias"
        rc_camera.shutter = "closed"
        for i in range(Constants['number_bias_exposures']):
            try:
                expose(0)
            except gui.ExposureCommsProblem:
                return "detector_problem"
            time.sleep(1)
        
        rc_camera.object = "dark"

        for i in range(Constants['number_dark_exposures']):
            try:
                expose(Constants['dark_exposure_time'])
            except gui.ExposureCommsProblem:
                return "detector_problem"
            
            time.sleep(1)
        
        rc_camera.shutter = "normal"

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
            try: 
                cmd = GXN.Commands()
                cmd.open_dome()
                cmd.close()
            except:
                cmd.close()
                return "open_dome_failed"
        
        return "observe"
        
        
class open_dome_failed(State):
    '''Deals with failure to open dome.
    Untested as of 31 Jan 2014'''
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        if not is_weather_safe(inputs):
            return "weather_safe"
        
        if not is_sun_ok(inputs):
            return "waitfor_sunset"
        
        if prev_state_name != 'open_dome_failed':
            log.error("Dome open failure. Will try again")
            # Email everyone

        
        if not is_dome_open(inputs):
            try: 
                cmd = GXN.Commands()
                cmd.open_dome()
                cmd.close()
            except:
                cmd.close()
                return "open_dome_failed"
        
        return "observe"

class weather_safe(State):
    def __init__(self):
        State.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        new_state = check_basics(inputs)
        if new_state != '': return new_state
        
        if is_telescope_tracking(inputs):
            try:
                cmd = GXN.Commands()
                cmd.stop()
                cmd.close()
            except:
                cmd.close()
                
        if not is_weather_safe(inputs):
            time.sleep(30)
            return "weather_safe"
        
        return "observe"

## DOME Open States

class observe(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        ns = DomeOpenState.execute(self, prev_state_name, inputs)
        if ns != '': return ns
            
        if is_ok_to_observe(inputs):
            if not is_dome_open(inputs):
                return "open_dome"

            return "select_target"

        time.sleep(10)
        return "observe"

        
class select_target(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        ns=DomeOpenState.execute(self, prev_state_name, inputs)
        if ns != '': return ns
        
        global next_target, target_plan
        

        lst = inputs['Telescope']['LST']
        log.debug("SimpleQueue.select_next_target at %s" % lst)
        next_target = SimpleQueue.select_next_target(lst)
        
        log.info("Next Target: %s" % next_target)

    
        if next_target[0] is None:
            log.debug("No target found")
            time.sleep(20)
            return "select_target"
        
        times = {"u": next_target['u'],
                    "g": next_target['g'],
                    "r": next_target['r'],
                    "i": next_target['i']}
        target_plan = ExposureSet.create_target_plan(times)
        log.info("Created new plan: %s" % target_plan)
        
        return "slew_to_target"

class slew_to_target(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
    

        ns=DomeOpenState.execute(self, prev_state_name, inputs)
        if ns != '': return ns
        global next_target, last_focus, force_focus
        

        try:
            cmd = GXN.Commands()
            cmd.coords( next_target['ra'], 
                        next_target['dec'],
                        next_target['epoch'],
                        0, 0, 0)
            cmd.go()
            cmd.close()
        except Exception as e:
            log.error("Failed to slew: %s" % e)
            cmd.close()
            time.sleep(1)
            return "slew_failed"
                
        time_since_last_focus = datetime.now() - last_focus[0]
        log.info("Time since last focus %i s" % time_since_last_focus.seconds)
        if time_since_last_focus.seconds > Constants['Hours_between_focus']*60*60:
            return "secfocus_loop"
        
        if force_focus:
            force_focus = False
            log.info("Forced to focus")
            return "secfocus_loop"
        
        return "exposure_handler"
        


class exposure_handler(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        global next_target, target_plan
        ns=DomeOpenState.execute(self, prev_state_name, inputs)
        if ns != '': return ns
        
        log.info("Remaining plan is: %s" % str(target_plan))
        
        if len(target_plan) == 0:
            return 'observe'
            
        return target_plan[0][0]
        
class expose_target(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        global next_target, target_plan
        ns=DomeOpenState.execute(self, prev_state_name, inputs)
        if ns != '': return ns
        
        plan = target_plan[0]
        del target_plan[0]
        
        target_name=next_target[0]
        fltr = plan[2]
        itime = plan[1]
        rc_camera.object = "%s: %s" % (target_name, fltr)
        log.info("Exposing on %s in filter %s for %i s" % (target_name,
            fltr, itime))
        
        rc_camera.shutter = "normal"
        try:
            expose(itime[0])
        except gui.ExposureCommsProblem:
            return "detector_problem"
            
        log.info("Exposure complete")
        
        return "exposure_handler"

class filter_move(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        global next_target, target_plan
        ns=DomeOpenState.execute(self, prev_state_name, inputs)
        if ns != '': return ns

        plan = target_plan[0]
        del target_plan[0]
        
        dRA, dDec = plan[1]
        log.info("Moving %i %i" % (dRA, dDec))
                
        try:
            cmds = GXN.Commands()
            cmds.pt(dRA, dDec)
            cmds.close()
        except:
            log.info
        
        return "exposure_handler"

class secfocus_loop(DomeOpenState):
    def __init__(self):
        DomeOpenState.__init__(self)
        
    def execute(self, prev_state_name, inputs):
        global last_focus
        ns=DomeOpenState.execute(self, prev_state_name, inputs)
        if ns != '': return ns
            

        try:
            cmd = GXN.Commands()
            
            positions = numpy.arange(14.0, 14.8, 0.1)
            filenames = []
            
            rc_camera.object = "Focus Loop"        
            cmd.gofocus(13)
            rc_camera.shutter = "normal"
            for position in positions:
                cmd.gofocus(position)
                try:
                    expose(15)
                except:
                    return "restart_detector_software"
                filenames.append(rc_camera.filename)
            
            log.info("FN: %s" % str(filenames))
            fpos, fposs, metrics = Focus.rc_focus_check(filenames)
            
            log.info("In the range of: %s" % positions)
            log.info("Metrics: %s" % metrics)
            log.info("Best focus is %f" % fpos)
            last_focus = [datetime.now(), fpos]
            cmd.gofocus(fpos)
            cmd.close()
        except:
            cmd.close()
            return "focus_failed"
        
        return "exposure_handler"
        

class telescope_not_powered(State):
    def __init__(self):
        State.__init__(self)
    
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        if prev_state_name != 'telescope_not_powered':
            log.error("Telescope is not powered. Emailing people")
        
        time.sleep(20)
        ns = check_basics(inputs)
        if ns == "":
            return "startup"
        return ns

class telescope_not_in_instrument_mode(State):
    def __init__(self):
        State.__init__(self)
    
    
    def execute(self, prev_state_name, inputs):
        State.execute(self, prev_state_name, inputs)
        
        if prev_state_name != 'telescope_not_in_instrument_mode':
            log.error("Telescope is not in instrument mode. Emailing people")
        
        time.sleep(20)
        ns = check_basics(inputs)
        if ns == "":
            return "startup"
        return ns

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
        self.next_state_name = "configure_flats"
    
    def execute(self, inputs):
        
        now = datetime.now()
        ns = self.statetable[self.next_state_name]
        
        log.info("Executing %s" % self.next_state_name)
        self.prev_state_name = self.next_state_name
        self.next_state_name = ns.execute(self.prev_state_name, inputs)
        
        if self.prev_state_name != self.next_state_name:
            log.info("Transitioning %s->%s" % (self.prev_state_name, 
                self.next_state_name))
        
        elapsed = datetime.now() - now
        ns.elapsed += elapsed
        ns.n_times += 1
        
        dt = datetime.now()
        fn = "%4.4i_%2.2i_%2.2i.txt" % (dt.year, dt.month, dt.day)
        names = []
        times = []
        elapsed = []
        for statename, state in self.statetable.items():
            names.append(statename)
            times.append(state.n_times)
            elapsed.append(state.elapsed.seconds)
        
        table = Table([names, times, elapsed], 
            names=("State", "# times", "# sec"))
        table.write("s:/logs/states/%s" % fn, format="ascii.fixed_width_two_line")
            

def expose(itime):
    global rc_camera
    
    rc_camera.exposure = itime
    log.info("Exposing for %3.1f s" % (itime))
    rc_camera.run()

        
def start_software():
    global Status, theSM, rc_camera

    rc_camera = gui.Camera()
    rc_camera.status_function = get_input
    rc_camera.xpa_class = 'c6ca7de8:18639'
    rc_camera.readout=2.0
        
    rc_camera.make_connection()


    
    
def main():
    global Status, rc_camera, theSM
    
    Status.start()
    time.sleep(1)
    
    theSM = StateMachine()
    start_software()

def fsm_loop():
    global Status, rc_pid, theSM, stop_loop
    cmd = GXN.Commands()
    cmd.takecontrol()
    cmd.close()
    while stop_loop == False:
        try:
            inputs = get_input()
            theSM.execute(inputs)
        except GXN.TCSConnectionError:
            log.info("Caught a communication error. Rebooting computer.")
            return
            import os
            email(email_list, """Sed machine cannot communicate with TCS. The
            instrument will attempt to reboot and continue. Sorry for the spam.""")
            log.info("executing shutdown -r")
            #os.system("shutdown -r")
    
    log.info("Received and accepted a stop request")


if __name__ == '__main__':
    main()
    #fsm_loop()
    #Thread(target=fsm_loop).start()