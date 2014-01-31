# Exposure Helper
# Nick Konidaris [c] 2014

import numpy as np


def create_target_plan(the_request):
    ''' the_request is a hash of {filter: exptime} '''
    plan = []
    dist = 6.5 * 60 # arcsecond
    positions = {"r": (0,0), "g": (-dist, 0),
        "i": (-dist, -dist), "u": (0, -dist)}
    
    # Starting at r
    prev_filter = 'r'
    if ("r" in the_request) and (the_request["r"] > 0):
        plan.append(('expose_target', the_request["r"], 'r'))
    
    for fltr, itime in the_request.items():
        if itime <= 0: continue
        if fltr == 'r': continue
        
        prev_pos = positions[prev_filter]
        next_pos = positions[fltr]

        move = (next_pos[0] - prev_pos[0],
            next_pos[1] - prev_pos[1])
        
        plan.append(('filter_move', move))
        plan.append(('expose_target', itime, fltr))
        prev_filter = fltr
    
    
    return plan