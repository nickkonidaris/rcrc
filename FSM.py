#
#   Created by Nick Konidaris [c] 2014
#   Licensed under the GPL
#
#   npk@astro.caltech.edu
#
#   This module is a simple state machine
#

from datetime import datetime, timedelta
import logging 
import logging.config



logging.config.fileConfig('/Users/npk/Dropbox/SED Machine/Project/RC Robotic Control/logging.conf')

# create logger
logger = logging.getLogger('sedm')

# 'application' code
logger.debug('debug message')
logger.info('info message')
logger.warn('warn message')
logger.error('error message')
logger.critical('critical message')


mn = 60

Constants = {
    'config_flats_timeout': 10*mn
}


def go():
    
    curr_state = None
    next_state = Startup()
    
    theSM = StateMachine()
    now = datetime.now()
    
    i = 0
    while i < 100:
        
        inputs = get_inputs()
        theSM.execute(inputs)
        i += 1

class State(object):
    def __init__(self):
        logger.info("Initialized state '%s'" % self.__class__.__name__)
        print "Hi"
    elapsed = timedelta(0)

class startup(State):
    def __init__(self):
        State.__init__(self)

class StateMacine:
    statetable = []
    curr_state = None
    next_state = None
    
    def __init__(self):
        statetable
    
    def execute(self):
        
        now = datetime.now()
        self.next_state = self.curr_state.execute()
        elapsed = datetime.now() - now
        self.curr_state.elapsed += elapsed 
        
            
        