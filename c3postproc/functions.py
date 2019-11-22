import math
import sys
import os
import time
import healpy as hp
import numpy as np



#######################
# ACTUAL MODULES HERE #
#######################

def h5handler(flags, command):
    filename = str(flags[0])
    signal = str(flags[1])
    min = int(flags[2])
    max = int(flags[3])
    outname = flags[-1]
    l = max-min
    
    import h5py     
    dats = []
    with h5py.File(filename, 'r') as f:
        for i in range(min,max+1):
            s = str(i).zfill(6)
            dats.append(f[s+"/"+signal][()])
    dats = np.array(dats)

    outdata = command(dats, axis=0)
    if "fits" in outname[-4:]: 
        hp.write_map(outname, outdata, overwrite=True)
    else:
        np.savetxt(outname, outdata)

def mean(flags):
    h5handler(flags, np.mean)

def stddev(flags):
    h5handler(flags, np.std)


def plot(flags):
    from c3postproc.plotter import Plotter
    Plotter(flags)

def sigma_l2fits(flags):
    filename = str(flags[0])
    path     = "cmb/sigma_l"
    burnin  = int(flags[-2])
    outname  = str(flags[-1])
    if len(flags)==4:
        path = str(flags[1])

    import h5py
    with h5py.File(filename, 'r') as f:
        print("Reading HDF5 file: "+filename+" ...")
        groups = list(f.keys())
        print()
        print("Reading "+str(len(groups))+" samples from file.")

        dset = np.zeros((len(groups)+1,1,len(f[groups[0]+'/'+path]),len(f[groups[0]+'/'+path][0])))
        nspec = len(f[groups[0]+'/'+path])
        lmax  = len(f[groups[0]+'/'+path][0])-1

        print('Found: \
        \npath in the HDF5 file : '+path+' \
        \nnumber of spectra :'+str(nspec)+\
        '\nlmax: '+str(lmax) )

        for i in range(len(groups)):
            for j in range(nspec):
                dset[i+1,0,j,:] = np.asarray(f[groups[i]+'/'+path][j][:])

    ell = np.arange(lmax+1)
    for i in range(1,len(groups)+1):
        for j in range(nspec):
            dset[i,0,j,:] = dset[i,0,j,:]*ell[:]*(ell[:]+1.)/2./np.pi
    dset[0,:,:,:] = len(groups) - burnin

    if save:
        import fitsio
        print("Dumping fits file: "+outname+" ...")
        dset = np.asarray(dset, dtype='f4')
        fits = fitsio.FITS(outname,mode='rw',clobber=True, verbose=True)
        h_dict = [{'name':'FUNCNAME','value':'Gibbs sampled power spectra','comment':'Full function name'}, \
                {'name':'LMAX','value':lmax,'comment':'Maximum multipole moment'}, \
                {'name':'NUMSAMP','value':len(groups),'comment':'Number of samples'}, \
                {'name':'NUMCHAIN','value':1,'comment':'Number of independent chains'}, \
                {'name':'NUMSPEC','value':nspec,'comment':'Number of power spectra'}]
        fits.write(dset[:,:,:,:],header=h_dict,clobber=True)
        fits.close()
    return dset

def h5map2fits(flags, save=True):
    import h5py
    h5file = str(flags[0])
    dataset = str(flags[1])
    with h5py.File(h5file, 'r') as f:
        maps = f[dataset][()]
        lmax = f[dataset[:-4]+"_lmax"][()] # Get lmax from h5

    nside = hp.npix2nside(maps.shape[-1])
    outfile =  dataset.replace("/", "_")
    outfile = outfile.replace("_map","")
    if save:
        hp.write_map(outfile+"_n"+str(nside)+".fits", maps, overwrite=True)
    return maps, nside, lmax, outfile

def alm2fits(flags, save=True):
    import h5py
    h5file = str(flags[0])
    dataset = str(flags[1])
    nside = int(flags[2]) # Output nside

    with h5py.File(h5file, 'r') as f:
        alms = f[dataset][()]
        lmax = f[dataset[:-4]+"_lmax"][()] # Get lmax from h5
    
    if "-lmax" in flags:
        lmax_ = int(get_key(flags, "-lmax"))
        if lmax_ > lmax:
            print("lmax larger than data allows: ", lmax)
            print("Please chose a value smaller than this")
        else:
            lmax =  lmax_
        mmax = lmax
    else:
        mmax = lmax

    if "-fwhm" in flags:
        fwhm = float(get_key(flags, "-fwhm"))
    else:
        fwhm = 0.0

    hehe = int(mmax * (2 * lmax + 1 - mmax) / 2 + lmax + 1) 
    print("Setting lmax to ", lmax, "hehe: ", hehe, "datashape: ", alms.shape)
    
    alms_unpacked = unpack_alms(alms,lmax) # Unpack alms
    maps = hp.sphtfunc.alm2map(alms_unpacked, nside, lmax=lmax, mmax= mmax, fwhm=arcmin2rad(fwhm))

    outfile =  dataset.replace("/", "_")
    outfile = outfile.replace("_alm","")
    if save:
        outfile += '_{}arcmin'.format(str(int(fwhm))) if "-fwhm" in flags else ""
        hp.write_map(outfile+"_n"+str(nside)+"_lmax{}".format(lmax) + ".fits", maps, overwrite=True)
    return maps, nside, lmax, fwhm, outfile



#######################
# HELPFUL TOOLS BELOW #
#######################



def unpack_alms(maps,lmax):
    """
    Create lm pairs here (same as commander)
    """
    mind = []
    lm = []
    idx = 0
    # lm pairs where m = 0
    mind.append(idx)
    for l in range(0, lmax+1):
        lm.append((l,0))
        idx += 1
    # rest of lm pairs
    for m in range(1,lmax+1):
        mind.append(idx)
        for l in range(m,lmax+1):
            lm.append((l,m))              
            lm.append((l,-m))
            idx +=2

    """
    unpack data here per l,m pair
    """
    alms =[[],[],[]] 
    for l, m in lm:
        if m < 0:
            continue
        if m == 0:
            idx = mind[m] + l 
            for pol in range(3):
                alms[pol].append(complex( maps[pol, idx], 0.0 ))
        else:
            idx = mind[abs(m)] + 2*(l-abs(m))
            for pol in range(3):
                alms[pol].append( complex(maps[pol,idx], maps[pol, idx+1])/np.sqrt(2) )


    alms_unpacked = np.array(alms, dtype=np.complex128)
    return alms_unpacked


def get_key(flags, keyword):
    return flags[flags.index(keyword) + 1]

def arcmin2rad(arcmin):
    return arcmin*(2*np.pi)/21600

"""

lm2 = lm
mind = []
lm = []
idx = 0
for m in range(lmax+1):
    mind.append(idx)
    if m == 0:
        for l in range(m, lmax+1):
            lm.append((l,m))
            idx += 1
    else:
        for l in range(m,lmax+1):
            lm.append((l,m))
            idx +=1
            
            lm.append((l,-m))
            idx +=1

lm = np.zeros((2,22801))
mind = np.zeros(lmax+1)
ind = 0
for m in range(lmax+1):
    mind[m] = ind
    if m == 0:
        for l in range(m, lmax+1):
            lm[:,ind] = (l,m)
            ind                           = ind+1
    else:
        for l in range(m, lmax+1):
        lm[:,ind] = (l,m)
        ind                           = ind+1
        lm[:,ind] = (l,-m)
        ind                           = ind+1
print(lm.shape)


  alms1 =[[],[],[]] 
    for l, m in lm:
        if m<0:
            continue
        idx = lm2i(l, m,mind)
        if m == 0:
            for pol in range(3):
                alms1[pol].append( complex( maps[pol,idx], 0.0 ) )
        else:
            idx2 = lm2i(l,-m,mind)
            for pol in range(3):
                alms1[pol].append( 1/np.sqrt(2)*complex(maps[pol,idx], maps[pol,idx2]) )




def lm2i(l,m,mind):
    if m == 0:
        i = mind[int(m)] + l
    else:
        i = mind[int(abs(m))] + 2*(l-abs(m))
        if (m < 0):
           i = i+1
    return int(i)
"""