import time
import sys
import os
import numpy as np
import healpy as hp
from src.tools import *


def format_fits(chain, extname, types, units, nside, burnin, maxchain, polar, component, fwhm, nu_ref_t, nu_ref_p, procver, filename, bndctr, restfreq, bndwid,):
    print()
    print("{:#^80}".format(""))
    print("{:#^80}".format(f" Formatting and outputting {filename} "))
    print("{:#^80}".format(""))

    header = get_header(extname, types, units, nside, polar, component, fwhm, nu_ref_t, nu_ref_p, procver, filename, bndctr, restfreq, bndwid,)
    dset = get_data(chain, extname, component, burnin, maxchain, fwhm, nside, types,)

    print(f"{procver}/{filename}", dset.shape)
    hp.write_map(f"{procver}/{filename}", dset, column_names=types, column_units=units, coord="G", overwrite=True, extra_header=header,)


def get_data(chain, extname, component, burnin, maxchain, fwhm, nside, types,):
    print("Formatting", extname)
    if extname.endswith("CMB"):
        print("CMB")
        # Mean data
        amp_mean = h5handler(input=chain, dataset="cmb/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.mean,)

        # stddev data
        amp_stddev = h5handler(input=chain, dataset="cmb/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.std,)

        # Masks
        mask1 = np.zeros((hp.nside2npix(nside)))
        mask2 = np.zeros((hp.nside2npix(nside)))

        dset = np.zeros((len(types), hp.nside2npix(nside)))
        dset[0] = amp_mean[0, :]
        dset[1] = amp_mean[1, :]
        dset[2] = amp_mean[2, :]
        dset[3] = np.sqrt(amp_mean[1, :]**2 + amp_mean[2, :]**2)

        dset[4] = amp_stddev[0, :]
        dset[5] = amp_stddev[1, :]
        dset[6] = amp_stddev[2, :]
        dset[7] = np.sqrt(amp_stddev[1, :]**2 + amp_stddev[2, :]**2)

        dset[8] = mask1
        dset[9] = mask2

    if extname.endswith("RESAMP"):
        print("CMB-RESAMP")
        # Mean data
        amp_mean = h5handler(input=chain, dataset="cmb/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.mean,)

        # stddev data
        amp_stddev = h5handler(input=chain, dataset="cmb/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.std,)

        dset = np.zeros((len(types), hp.nside2npix(nside)))
        dset[0] = amp_mean
        dset[1] = amp_stddev

    elif extname.endswith("SYNCHROTRON"):
        # Mean data
        amp_mean = h5handler(input=chain, dataset="synch/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.mean,)
        beta_mean = h5handler(input=chain, dataset="synch/beta_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.mean,)

        # stddev data
        amp_stddev = h5handler(input=chain, dataset="synch/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.std,)
        beta_stddev = h5handler(input=chain, dataset="synch/beta_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.std,)

        dset = np.zeros((len(types), hp.nside2npix(nside)))

        dset[0] = amp_mean[0, :]
        dset[1] = amp_mean[1, :]
        dset[2] = amp_mean[2, :]
        dset[3] = np.sqrt(amp_mean[1, :]**2 + amp_mean[2, :]**2)

        dset[4] = beta_mean[0, :]
        dset[5] = beta_mean[1, :]

        dset[6] = amp_stddev[0, :]
        dset[7] = amp_stddev[1, :]
        dset[8] = amp_stddev[2, :]
        dset[9] = np.sqrt(amp_stddev[1, :]**2 + amp_stddev[2, :]**2)

        dset[10] = beta_stddev[0, :]
        dset[11] = beta_stddev[1, :]

    elif extname.endswith("DUST"):
        # Mean data
        amp_mean = h5handler(input=chain, dataset="dust/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.mean,)
        beta_mean = h5handler(input=chain, dataset="dust/beta_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.mean,)
        T_mean = h5handler(input=chain, dataset="dust/T_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.mean,)

        # stddev data
        amp_stddev = h5handler(input=chain, dataset="dust/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.std,)
        beta_stddev = h5handler(input=chain, dataset="dust/beta_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.std,)
        T_stddev = h5handler(input=chain, dataset="dust/T_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.std,)

        dset = np.zeros((len(types), hp.nside2npix(nside)))

        dset[0] = amp_mean[0, :]
        dset[1] = amp_mean[1, :]
        dset[2] = amp_mean[2, :]
        dset[3] = np.sqrt(amp_mean[1, :]**2 + amp_mean[2, :]**2)

        dset[4] = beta_mean[0, :]
        dset[5] = beta_mean[1, :]

        dset[6] = T_mean[0, :]
        dset[7] = T_mean[1, :]

        dset[8] = amp_stddev[0, :]
        dset[9] = amp_stddev[1, :]
        dset[10] = amp_stddev[2, :]
        dset[11] = np.sqrt(amp_stddev[1, :]**2 + amp_stddev[2, :]**2)

        dset[12] = beta_stddev[0, :]
        dset[13] = beta_stddev[1, :]

        dset[14] = T_stddev[0, :]
        dset[15] = T_stddev[1, :]

    elif extname.endswith("FREE-FREE"):
        # Mean data
        amp_mean = h5handler(input=chain, dataset="ff/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.mean,)
        Te_mean = h5handler(input=chain, dataset="ff/Te_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.mean,)

        # stddev data
        amp_stddev = h5handler(input=chain, dataset="ff/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.std,)
        Te_stddev = h5handler(input=chain, dataset="ff/Te_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.std,)

        dset = np.zeros((len(types), hp.nside2npix(nside)))

        dset[0] = amp_mean
        dset[1] = Te_mean

        dset[2] = amp_stddev
        dset[3] = Te_stddev

    elif extname.endswith("AME"):
        # Mean data
        amp_mean = h5handler(input=chain, dataset="ame/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.mean,)
        nu_p_mean = h5handler(input=chain, dataset="ame/nu_p_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.mean,)

        # stddev data
        amp_stddev = h5handler(input=chain, dataset="ame/amp_alm", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.std,)
        nu_p_stddev = h5handler(input=chain, dataset="ame/nu_p_map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=0.0, nside=nside, command=np.std,)

        dset = np.zeros((len(types), hp.nside2npix(nside)))

        dset[0] = amp_mean
        dset[1] = nu_p_mean

        dset[2] = amp_stddev
        dset[3] = nu_p_stddev

    if extname.endswith("FREQMAP"):
        # Mean data
        amp_mean = h5handler(input=chain, dataset=f"tod/{component}/map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.mean,)

        # stddev data
        amp_stddev = h5handler(input=chain, dataset=f"tod/{component}/map", min=burnin, max=None, maxchain=maxchain, output="map", fwhm=fwhm, nside=nside, command=np.std,)

        # Masks

        dset = np.zeros((len(types), hp.nside2npix(nside)))

        dset[0] = amp_mean[0, :]
        dset[1] = amp_mean[1, :]
        dset[2] = amp_mean[2, :]
        dset[3] = np.sqrt(amp_mean[1, :]**2 + amp_mean[2, :]**2)
        
        dset[4] = amp_stddev[0, :]
        dset[5] = amp_stddev[1, :]
        dset[6] = amp_stddev[2, :]
        dset[7] = np.sqrt(amp_stddev[1, :]**2 + amp_stddev[2, :]**2)

    #print(f"Shape of dset {dset.shape}")
    return dset


def get_header(extname, types, units, nside, polar, component, fwhm, nu_ref_t, nu_ref_p, procver, filename, bndctr, restfreq, bndwid,):
    stamp = f'Written {time.strftime("%c")}'

    header = []
    header.append(("DATE", stamp, "Time and date of creation.",))
    header.append(("PIXTYPE", "HEALPIX", "HEALPIX pixelisation.",))
    header.append(("COORDSYS", "GALACTIC"))
    header.append(("POLAR", polar))
    header.append(("BAD_DATA", hp.UNSEEN, "HEALPIX UNSEEN value.",))
    header.append(("METHOD", "COMMANDER", "COMMANDER sampling framework",))
    header.append(("AST-COMP", component))
    if extname == "FREQMAP":
        header.append(("FREQ", nu_ref_t))
    else:
        header.append(("FWHM", fwhm))
        header.append(("NU_REF_T", nu_ref_t))
        header.append(("NU_REF_P", nu_ref_p))

    header.append(("PROCVER", procver, "Release version"))
    header.append(("FILENAME", filename))
    if extname == "FREQMAP":
        # TODO are these correct?
        header.append(("BNDCTR", bndctr, "Formal Band Center",))
        header.append(("RESTFREQ", restfreq, "Effective Central Frequency",))
        header.append(("BNDWID", bndwid, "Effective Bandwidth",))
    return header
