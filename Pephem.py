#
#   Created by Nick Konidaris [c] 2014
#   Licensed under the GPL
#
#   npk@astro.caltech.edu
#
#   This module is a simple wrapper around PyEphem
#


import ephem as Ep
from datetime import datetime

Palomar = Ep.Observer()
Palomar.lat  =   '33:21:21.6'
Palomar.long = Ep.hours('-7:47:27')

def sun_now(time_now=None):
    ''' Return the sun's altitude relative to the local time on the clock '''
    
    if time_now is not None:
        Palomar.date = time_now
        
    sun = Ep.Sun()
    sun.compute(Palomar)

    return sun


if __name__ == '__main__':
    s= sun_now()
    print s.alt 
    s=sun_now(time_now='2014/01/28 01:21')
    print s.alt
    s=sun_now(time_now='2014/01/28 14:39')
    print s.alt
