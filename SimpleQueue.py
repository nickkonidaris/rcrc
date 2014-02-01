# Simple observing queue


import astropy
from astropy.table import Table
from astropy.coordinates import Angle
import numpy as np

TO_OBSERVE = "s://to_observe.txt"
OBSERVED = "s://observed.txt"

force_focus = False

no_target =[None, 0, 0, 0, 0, 0, 0, 0]

def abs_diff(a, b):
    '''Angular separation between two angles'''
    
    d = np.abs(a-b)
    if d>180:
        d -= 360
    
    return np.abs(d)

def select_next_target(lst):
    
    h,m,s = map(float, lst.split(":"))
    lstf = h*15 + m*15/60. + s*15/3600.
    
    try:
        to_observe=Table.read("S:/to_observe.txt", format="ascii.fixed_width_two_line")
    except Exception as e:
        print "Couldn't read file: %s" % e
        return no_target
        
    
    oks = []
    
    for i in xrange(len(to_observe)):
        try:
            RA = Angle(to_observe['ra'][i])
        except astropy.units.UnitsError:
            # Assume that the default value is decimal degrees
            RA = float(to_observe['ra'][i])

        D = abs_diff(RA, lstf)

        if np.abs(D) < 60:
            oks.append(i)
    
    if len(oks) == 0: return no_target
    
    row = to_observe[[oks[0]]]
    return np.array(row)
    

if __name__ == '__main__':
    targ= select_next_target("2:30:00")
    print targ
    
    