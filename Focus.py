
import os
import numpy as np
import scipy.signal as signal
import pyfits as pf


def rc_focus_check(files):
    

    fpos = []
    metrics = []
    for fn in files:
        F = pf.open(fn)
        
        dat,hdr = F[0].data, F[0].header
        dat = dat[1200:1900,1200:1900]
        dat -= np.median(dat)
        
        md = signal.medfilt2d(dat)
        bad = (dat-md)/md > 5
        dat[bad]=md[bad]
        
        sort = np.sort(dat.flatten())
        a,b = np.floor(len(sort)*.03), np.ceil(len(sort)*.97)
        metric = (sort[b]-sort[a])/sort[b]
        metric = np.max(dat) - np.min(dat)
        fpos.append(hdr["secfocus"])
        metrics.append(metric)
        
        print fn, hdr["secfocus"], hdr["EXPTIME"], metric
        

    x = np.argmax(metrics)
    return fpos[x], fpos, metrics