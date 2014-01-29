#
#   Created by Nick Konidaris [c] 2014
#   Licensed under the GPL
#
#   npk@astro.caltech.edu
#
#   This module is a simple state machine
#

from datetime import datetime, timedelta
import logging as log
import telnetlib
import smtplib
import GXN

email_list = ["nick.konidaris@gmail.com"]

# create logger
log.basicConfig(filename="C:\\sedm\\logs\\rcrc.txt",
    format="%(asctime)s-%(filename)s:%(lineno)i-%(levelname)s-%(message)s",
    level = log.DEBUG)

log.info("?***************************** START ********")


mn = 60

Constants = {
    'config_flats_timeout': 10*mn
}

Status = GXN.StatusThreads()


def classname(object):
    return object.__class__.__name__

def get_input():
    log.debug("Called get_input")
    status = {}
    
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
    
    return status        


def is_sun_ok(status):
    '''Returns true if sunlight status OK'''
    
    s = status['Status']['Sunlight_Status'] == 'OKAY'
    
    if s: log.info("Sunlight status is OK")
    else: log.info("Sunlight status is OK")
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

def is_telescope_in_instrument_mode(status):
    '''Returns true if telescope is in instrument (not manual) mode'''
    
    s = status['Status']['Telescope_Control_Status']
    
    if s == 'AVAILABLE':
        log.info("Telescope is available")
        return True
    else:
        log.info("Telescope in manual mode")
        return False
    
    
def is_telescope_powered(status):
    ''' Returns true if telescope is powered on'''
    if  (s['Oil_Pad_Status'] == 'READY') and \
        (s['Telescope_Power_Status'] == 'READY'):
            log.info("Telescope is powered")
            return True
    else:
        log.info("Telescope is not powered")
        return False

def go():
    global Status
    
    Status.start()
    
    curr_state = None
    next_state = "startup"
    
    theSM = StateMachine()
    
    i = 0
    while i < 5:
        
        try:
            inputs = 0
            theSM.execute(inputs)
        except TCSConnectionError:
            log.info("Caught a communication error. Rebooting computer.")
            return
            import os
            email(email_list, """Sed machine cannot communicate with TCS. The
            instrument will attempt to reboot and continue. Sorry for the spam.""")
            log.info("executing shutdown -r")
            os.system("shutdown -r")

        i += 1
    
    return theSM


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

    
    def execute(self, inputs):
        log.info("[%s].execute()" % self.__class__.__name__)

class startup(State):
    '''Entry point state'''
    
    def __init__(self):
        State.__init__(self)
    
    
    def execute(self, inputs):
        State.execute(self, inputs)
        d = datetime.now()
        
        h,m = d.hour, d.minute
        
        return "startup"
        
        if inputs['telinit_needed']:
            return "telinit"
        elif h < 3:
            return "startup"
        elif (h < 5) and (m < 30):
            return "configure_flats"
        else:
            return "focus"
        

class telinit(State):
    def __init__(self):
        State.__init__(self)
            
    def execute(self, inputs):
        
        pass

class configure_flats(State):
    def __init__(self):
        State.__init__(self)

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
        
        log.info("All states initialized.")
        
        self.prev_state_name = None
        self.next_state_name = "startup"
    
    def execute(self, inputs):
        
        now = datetime.now()
        ns = self.statetable[self.next_state_name]
        
        self.prev_state_name = self.next_state_name
        self.next_state_name = ns.execute(inputs)
        
        elapsed = datetime.now() - now
        ns.elapsed += elapsed
        ns.n_times += 1
        
        
        
            

if __name__ == '__main__':
    sm=go()    