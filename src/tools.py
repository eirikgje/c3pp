import numba
import numpy as np
#######################
# HELPFUL TOOLS BELOW #
#######################


@numba.njit(cache=True, fastmath=True)  # Speeding up by a lot!
def unpack_alms(maps, lmax):
    #print("Unpacking alms")
    mmax = lmax
    nmaps = len(maps)
    # Nalms is length of target alms
    Nalms = int(mmax * (2 * lmax + 1 - mmax) / 2 + lmax + 1)
    alms = np.zeros((nmaps, Nalms), dtype=np.complex128)

    # Unpack alms as output by commander
    for sig in range(nmaps):
        i = 0
        for l in range(lmax + 1):
            j_real = l ** 2 + l
            alms[sig, i] = complex(maps[sig, j_real], 0.0)
            i += 1

        for m in range(1, lmax + 1):
            for l in range(m, lmax + 1):
                j_real = l ** 2 + l + m
                j_comp = l ** 2 + l - m

                alms[sig, i] = complex(maps[sig, j_real], maps[sig, j_comp],) / np.sqrt(2.0)

                i += 1
    return alms


def alm2fits_tool(input, dataset, nside, lmax, fwhm, save=True):
    import h5py
    import healpy as hp

    with h5py.File(input, "r") as f:
        alms = f[dataset][()]
        lmax_h5 = f[f"{dataset[:-3]}lmax"][()]  # Get lmax from h5

    if lmax:
        # Check if chosen lmax is compatible with data
        if lmax > lmax_h5:
            print(
                "lmax larger than data allows: ", lmax_h5,
            )
            print("Please chose a value smaller than this")
    else:
        # Set lmax to default value
        lmax = lmax_h5
    mmax = lmax

    alms_unpacked = unpack_alms(alms, lmax)  # Unpack alms

    print("Making map from alms")
    pol=False if alms_unpacked.shape[0] == 1 else True
    maps = hp.sphtfunc.alm2map(alms_unpacked, nside, lmax=lmax, mmax=mmax, fwhm=arcmin2rad(fwhm),pol=pol, pixwin=True,)

    outfile = dataset.replace("/", "_")
    outfile = outfile.replace("_alm", "")
    if save:
        outfile += f"_{str(int(fwhm))}arcmin" if fwhm > 0.0 else ""
        hp.write_map(outfile + f"_n{str(nside)}_lmax{lmax}.fits", maps, overwrite=True, dtype=None)
    return maps, nside, lmax, fwhm, outfile


def h5handler_old(input, dataset, min, max, maxchain, output, fwhm, nside, command,):
    # Check if you want to output a map
    import h5py
    import healpy as hp
    from tqdm import tqdm

    print()
    print("{:-^48}".format(f" {dataset} calculating {command.__name__} "))
    print("{:-^48}".format(f" nside {nside}, {fwhm} arcmin smoothing "))

    if dataset.endswith("map"):
        type = "map"
    elif dataset.endswith("alm"):
        type = "alm"
    elif dataset.endswith("sigma"):
        type = "sigma"
    else:
        print(f"Type {type} not recognized")
        sys.exit()

    dats = []
    maxnone = True if max == None else False  # set length of keys for maxchains>1
    for c in range(1, maxchain + 1):
        filename = input.replace("c0001", "c" + str(c).zfill(4))
        with h5py.File(filename, "r") as f:
            if maxnone:
                # If no max is specified, chose last sample
                max = len(f.keys()) - 1

            print("{:-^48}".format(f" Samples {min} to {max} in {filename}"))

            for sample in tqdm(range(min, max + 1), ncols=80):
                # Identify dataset
                # alm, map or (sigma_l, which is recognized as l)

                # Unless output is ".fits" or "map", don't convert alms to map.
                alm2map = True if output.endswith((".fits", "map")) else False

                # HDF dataset path formatting
                s = str(sample).zfill(6)

                # Sets tag with type
                tag = f"{s}/{dataset}"
                #print(f"Reading c{str(c).zfill(4)} {tag}")

                # Check if map is available, if not, use alms.
                # If alms is already chosen, no problem
                try:
                    data = f[tag][()]
                    if len(data[0]) == 0:
                        tag = f"{tag[:-3]}map"
                        print(f"WARNING! No {type} data found, switching to map.")
                        data = f[tag][()]
                        type = "map"
                except:
                    print(f"Found no dataset called {dataset}")
                    print(f"Trying alms instead {tag}")
                    try:
                        # Use alms instead (This takes longer and is not preferred)
                        tag = f"{tag[:-3]}alm"
                        type = "alm"
                        data = f[tag][()]
                    except:
                        print("Dataset not found.")

                # If data is alm, unpack.
                if type == "alm":
                    lmax_h5 = f[f"{tag[:-3]}lmax"][()]
                    data = unpack_alms(data, lmax_h5)  # Unpack alms

                if data.shape[0] == 1:
                    # Make sure its interprated as I by healpy
                    # For non-polarization data, (1,npix) is not accepted by healpy
                    data = data.ravel()

                # If data is alm and calculating std. Bin to map and smooth first.
                if type == "alm" and command == np.std and alm2map:
                    #print(f"#{sample} --- alm2map with {fwhm} arcmin, lmax {lmax_h5} ---")
                    data = hp.alm2map(data, nside=nside, lmax=lmax_h5, fwhm=arcmin2rad(fwhm), pixwin=True,verbose=False,)

                # If data is map, smooth first.
                elif type == "map" and fwhm > 0.0 and command == np.std:
                    #print(f"#{sample} --- Smoothing map ---")
                    data = hp.sphtfunc.smoothing(data, fwhm=arcmin2rad(fwhm),verbose=False,)

                # Append sample to list
                dats.append(data)

    # Convert list to array
    dats = np.array(dats)
    # Calculate std or mean
    outdata = command(dats, axis=0)

    # Smoothing afterwards when calculating mean
    if type == "alm" and command == np.mean and alm2map:
        #print(f"# --- alm2map mean with {fwhm} arcmin, lmax {lmax_h5} ---")
        outdata = hp.alm2map(outdata, nside=nside, lmax=lmax_h5, fwhm=arcmin2rad(fwhm), pixwin=True,verbose=False,)

    # Smoothing can be done after for np.mean
    if type == "map" and fwhm > 0.0 and command == np.mean:
        #print(f"--- Smoothing mean map with {fwhm} arcmin,---")
        outdata = hp.sphtfunc.smoothing(outdata, fwhm=arcmin2rad(fwhm), verbose=False,)

    # Outputs fits map if output name is .fits
    if output.endswith(".fits"):
        hp.write_map(output, outdata, overwrite=True)
    elif output.endswith(".dat"):
        np.savetxt(output, outdata)
    else:
        return outdata

def h5handler(input, dataset, min, max, maxchain, output, fwhm, nside, command, pixweight=None, zerospin=False, lowmem=True,):

    # Check if you want to output a map
    import h5py
    import healpy as hp
    from tqdm import tqdm

    if (lowmem and command == np.std): #need to compute mean first
        mean_data = h5handler(input, dataset, min, max, maxchain, output, fwhm, nside, np.mean, pixweight, zerospin, lowmem,)

    print()
    print("{:-^50}".format(f" {dataset} calculating {command.__name__} "))
    print("{:-^50}".format(f" nside {nside}, {fwhm} arcmin smoothing "))

    if dataset.endswith("map"):
        type = "map"
    elif dataset.endswith("rms"):
        type = "map"
    elif dataset.endswith("alm"):
        type = "alm"
    elif dataset.endswith("sigma"):
        type = "sigma"
    else:
        print(f"Type {type} not recognized")
        sys.exit()

    if (lowmem):
        nsamp = 0 #track number of samples
        first_samp = True #flag for first sample
    else:
        dats = []

    use_pixweights = False if pixweight == None else True
    maxnone = True if max == None else False  # set length of keys for maxchains>1
    pol = True if zerospin == False else False  # treat maps as TQU maps (polarization)
    for c in range(1, maxchain + 1):
        filename = input.replace("c0001", "c" + str(c).zfill(4))
        with h5py.File(filename, "r") as f:
            if maxnone:
                # If no max is specified, chose last sample
                max = len(f.keys()) - 1

            print("{:-^48}".format(f" Samples {min} to {max} in {filename}"))

            for sample in tqdm(range(min, max + 1), ncols=80):
                # Identify dataset
                # alm, map or (sigma_l, which is recognized as l)

                # Unless output is ".fits" or "map", don't convert alms to map.
                alm2map = True if output.endswith((".fits", "map")) else False

                # HDF dataset path formatting
                s = str(sample).zfill(6)

                # Sets tag with type
                tag = f"{s}/{dataset}"
                #print(f"Reading c{str(c).zfill(4)} {tag}")

                # Check if map is available, if not, use alms.
                # If alms is already chosen, no problem
                try:
                    data = f[tag][()]
                    if len(data[0]) == 0:
                        tag = f"{tag[:-3]}map"
                        print(f"WARNING! No {type} data found, switching to map.")
                        data = f[tag][()]
                        type = "map"
                except:
                    print(f"Found no dataset called {dataset}")
                    print(f"Trying alms instead {tag}")
                    try:
                        # Use alms instead (This takes longer and is not preferred)
                        tag = f"{tag[:-3]}alm"
                        type = "alm"
                        data = f[tag][()]
                    except:
                        print("Dataset not found.")

                # If data is alm, unpack.
                if type == "alm":
                    lmax_h5 = f[f"{tag[:-3]}lmax"][()]
                    data = unpack_alms(data, lmax_h5)  # Unpack alms

                if data.shape[0] == 1:
                    # Make sure its interprated as I by healpy
                    # For non-polarization data, (1,npix) is not accepted by healpy
                    data = data.ravel()

                # If data is alm and calculating std. Bin to map and smooth first.
                if type == "alm" and command == np.std and alm2map:
                    #print(f"#{sample} --- alm2map with {fwhm} arcmin, lmax {lmax_h5} ---")
                    data = hp.alm2map(data, nside=nside, lmax=lmax_h5, fwhm=arcmin2rad(fwhm), pixwin=True,verbose=False,pol=pol,)

                # If data is map, smooth first.
                elif type == "map" and fwhm > 0.0 and command == np.std:
                    #print(f"#{sample} --- Smoothing map ---")
                    if use_pixweights:
                        data = hp.sphtfunc.smoothing(data, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_pixel_weights=True,datapath=pixweight)
                    else: #use ring weights
                        data = hp.sphtfunc.smoothing(data, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_weights=True)

                if (lowmem):
                    if (first_samp):
                        first_samp=False
                        if (command==np.mean):
                            dats=data.copy()
                        elif (command==np.std):
                            dats=(mean_data - data)**2
                        else:
                            print('     Unknown command {command}. Exiting')
                            exit()
                    else:
                        if (command==np.mean):
                            dats=dats+data
                        elif (command==np.std):
                            dats=dats+(mean_data - data)**2
                    nsamp+=1
                else:
                    # Append sample to list
                    dats.append(data)

    if (lowmem):
        if (command == np.mean):
            outdata = dats/nsamp
        elif (command == np.std):
            outdata = np.sqrt(dats/nsamp)
    else:
        # Convert list to array
        dats = np.array(dats)
        # Calculate std or mean
        outdata = command(dats, axis=0)

    # Smoothing afterwards when calculating mean
    if type == "alm" and command == np.mean and alm2map:
        print(f"# --- alm2map mean with {fwhm} arcmin, lmax {lmax_h5} ---")
        outdata = hp.alm2map(
            outdata, nside=nside, lmax=lmax_h5, fwhm=arcmin2rad(fwhm), pixwin=True, pol=pol
        )

    if type == "map" and fwhm > 0.0 and command == np.mean:
        print(f"--- Smoothing mean map with {fwhm} arcmin,---")
        if use_pixweights:
            outdata = hp.sphtfunc.smoothing(outdata, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_pixel_weights=True,datapath=pixweight)
        else: #use ring weights
            outdata = hp.sphtfunc.smoothing(outdata, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_weights=True)

    # Outputs fits map if output name is .fits
    if output.endswith(".fits"):
        hp.write_map(output, outdata, overwrite=True)
    elif output.endswith(".dat"):
        np.savetxt(output, outdata)
    return outdata

def arcmin2rad(arcmin):
    return arcmin * (2 * np.pi) / 21600

def legend_positions(df, y, scaling):
    """ Calculate position of labels to the right in plot... """
    positions = {}
    for column in y:
        positions[column] = df[column].values[-1] - 0.005

    def push():
        """
        ...by puting them to the last y value and
        pushing until no overlap
        """
        collisions = 0
        for column1, value1 in positions.items():
            for column2, value2 in positions.items():
                if column1 != column2:
                    dist = abs(value1-value2)
                    if dist < scaling:# 0.075: #0.075: #0.023:
                        collisions += 1
                        if value1 < value2:
                            positions[column1] -= .001
                            positions[column2] += .001
                        else:
                            positions[column1] += .001
                            positions[column2] -= .001
                            return True
    while True:
        pushed = push()
        if not pushed:
            break

    return positions

def forward(x):
    return x/100
def inverse(x):
    return x*100



def cmb(nu, A):
    h = 6.62607e-34 # Planck's konstant
    k_b  = 1.38065e-23 # Boltzmanns konstant
    Tcmb = 2.7255      # K CMB Temperature

    x = h*nu/(k_b*Tcmb)
    g = (np.exp(x)-1)**2/(x**2*np.exp(x))
    s_cmb = A/g
    return s_cmb

def sync(nu, As, alpha, nuref=0.408):
    #alpha = 1., As = 30 K (30*1e6 muK)
    nu_0 = nuref*1e9 # 408 MHz
    from pathlib import Path
    synch_template = Path(__file__).parent / "Synchrotron_template_GHz_extended.txt"
    fnu, f = np.loadtxt(synch_template, unpack=True)
    f = np.interp(nu, fnu*1e9, f)
    f0 = np.interp(nu_0, nu, f) # Value of s at nu_0
    s_s = As*(nu_0/nu)**2*f/f0
    return s_s


def ffEM(nu,EM,Te):
    #EM = 1 cm-3pc, Te= 500 #K
    T4 = Te*1e-4
    nu9 = nu/1e9 #Hz
    g_ff = np.log(np.exp(5.960-np.sqrt(3)/np.pi*np.log(nu9*T4**(-3./2.)))+np.e)
    tau = 0.05468*Te**(-3./2.)*nu9**(-2)*EM*g_ff
    s_ff = 1e6*Te*(1-np.exp(-tau))
    return s_ff

def ff(nu,A,Te, nuref=40.):
    h = 6.62607e-34 # Planck's konstant
    k_b  = 1.38065e-23 # Boltzmanns konstant

    nu_ref = nuref*1e9
    S =     np.log(np.exp(5.960 - np.sqrt(3.0)/np.pi * np.log(    nu/1e9*(Te/1e4)**-1.5))+2.71828)
    S_ref = np.log(np.exp(5.960 - np.sqrt(3.0)/np.pi * np.log(nu_ref/1e9*(Te/1e4)**-1.5))+2.71828)
    s_ff = A*S/S_ref*np.exp(-h*(nu-nu_ref)/k_b/Te)*(nu/nu_ref)**-2
    return s_ff

def sdust(nu, Asd, nu_p, fnu = None, f_ = None, nuref=22.,):
    nuref = nuref*1e9 
    scale = 30./nu_p

    try:
        f = np.interp(scale*nu, fnu, f_)
        f0 = np.interp(scale*nuref, fnu, f_) # Value of s at nu_0
        
    except:
        from pathlib import Path
        ame_template = Path(__file__).parent / "spdust2_cnm.dat"
        fnu, f_ = np.loadtxt(ame_template, unpack=True)
        fnu *= 1e9
        f = np.interp(scale*nu, fnu, f_)
        f0 = np.interp(scale*nuref, fnu, f_) # Value of s at nu_0
        
    s_sd = Asd*(nuref/nu)**2*f/f0
    return s_sd


def tdust(nu,Ad,betad,Td,nuref=545.):
    h = 6.62607e-34 # Planck's konstant
    k_b  = 1.38065e-23 # Boltzmanns konstant
    nu0=nuref*1e9
    gamma = h/(k_b*Td)
    s_d=Ad*(nu/nu0)**(betad+1)*(np.exp(gamma*nu0)-1)/(np.exp(gamma*nu)-1)
    return s_d

def lf(nu,Alf,betalf,nuref=30e9):
    return Alf*(nu/nuref)**(betalf)

def line(nu, A, freq, conversion=1.0):
    if isinstance(nu, np.ndarray):
        return np.where(np.isclose(nu, 1e9*freq), A*conversion, 0.0)
    else:
        if np.isclose(nu, 1e9*freq[0]):
            return A*conversion
        else:
            return 0.0

def rspectrum(nu, r, sig, scaling=1.0):
    import camb
    from camb import model, initialpower
    import healpy as hp
    #Set up a new set of parameters for CAMB
    pars = camb.CAMBparams()
    #This function sets up CosmoMC-like settings, with one massive neutrino and helium set using BBN consistency
    pars.set_cosmology(H0=67.5, ombh2=0.022, omch2=0.122, mnu=0.06, omk=0, tau=0.06)
    pars.InitPower.set_params(As=2e-9, ns=0.965, r=r)
    lmax=6000
    pars.set_for_lmax(lmax,  lens_potential_accuracy=0)
    pars.WantTensors = True
    results = camb.get_results(pars)
    powers = results.get_cmb_power_spectra(params=pars, lmax=lmax, CMB_unit='muK', raw_cl=True,)


    l = np.arange(2,lmax+1)

    if sig == "TT":
        cl = powers['unlensed_scalar']
        signal = 0
    elif sig == "EE":
        cl = powers['unlensed_scalar']
        signal = 1
    elif sig == "BB":
        cl = powers['tensor']
        signal = 2

    bl = hp.gauss_beam(40/(180/np.pi*60), lmax,pol=True)
    A = np.sqrt(sum( 4*np.pi * cl[2:,signal]*bl[2:,signal]**2/(2*l+1) ))
    return cmb(nu, A*scaling)



def fits_handler(input, min, max, minchain, maxchain, chdir, output, fwhm, nside, zerospin, drop_missing, pixweight, return_mean, command, lowmem=True):
    # Check if you want to output a map
    import healpy as hp
    from tqdm import tqdm
    import os

    if (not input.endswith(".fits")):
        print("Input file must be a '.fits'-file")
        exit()

    if (lowmem and command == np.std): #need to compute mean first
        mean_data = fits_handler(input, min, max, minchain, maxchain, chdir, output, fwhm, nside, zerospin, drop_missing, pixweight, True, np.mean)

    if (minchain > maxchain):
        print('Minimum chain number larger that maximum chain number. Exiting')
        exit()
    aline=input.split('/')
    dataset=aline[-1]
    print()
    print("{:-^50}".format(f" {dataset} calculating {command.__name__} "))
    if (nside == None):
        print("{:-^50}".format(f" {fwhm} arcmin smoothing "))
    else:
        print("{:-^50}".format(f" nside {nside}, {fwhm} arcmin smoothing "))

    type = 'map'

    if (not lowmem):
        dats = []

    nsamp = 0 #track number of samples
    first_samp = True #flag for first sample

    use_pixweights = False if pixweight == None else True
    maxnone = True if max == None else False  # set length of keys for maxchains>1
    pol = True if zerospin == False else False  # treat maps as TQU maps (polarization)
    for c in range(minchain, maxchain + 1):
        if (chdir==None):
            filename = input.replace("c0001", "c" + str(c).zfill(4))
        else:
            filename = chdir+'_c%i/'%(c)+input
        basefile = filename.split("k000001")

        if maxnone:
            # If no max is specified, find last sample of chain
            # Assume residual file of convention res_label_c0001_k000234.fits, 
            # i.e. final numbers of file are sample number
            max_found = False
            siter=min
            while (not max_found):
                filename = basefile[0]+'k'+str(siter).zfill(6)+basefile[1]

                if (os.path.isfile(filename)):
                    siter += 1
                else:
                    max_found = True
                    max = siter - 1

        else:
            if (first_samp):
                for chiter in range(minchain,maxchain + 1):
                    if (chdir==None):
                        tempname = input.replace("c0001", "c" + str(c).zfill(4))
                    else:
                        tempname = chdir+'_c%i/'%(c)+input
                        temp = tempname.split("k000001")

                    for siter in range(min,max+1):
                        tempf = temp[0]+'k'+str(siter).zfill(6)+temp[1]

                        if (not os.path.isfile(tempf)):
                            print('chain %i, sample %i missing'%(c,siter))
                            print(tempf)
                            if (not drop_missing):
                                exit()


        print("{:-^48}".format(f" Samples {min} to {max} in {filename}"))

        for sample in tqdm(range(min, max + 1), ncols=80):
                # dataset sample formatting
                filename = basefile[0]+'k'+str(sample).zfill(6)+basefile[1]                
                if (first_samp):
                    # Check which fields the input maps have
                    if (not os.path.isfile(filename)):
                        if (not drop_missing):
                            exit()
                        else:
                            continue

                    data, header = hp.fitsfunc.read_map(filename,verbose=False,h=True,dtype=np.float64)
                    nfields = 0
                    for par in header:
                        if (par[0] == 'TFIELDS'):
                            nfields = par[1]
                            break
                    if (nfields == 0):
                        print('No fields/maps in input file')
                        exit()
                    elif (nfields == 1):
                        fields=(0)
                    elif (nfields == 2):
                        fields=(0,1)
                    elif (nfields == 3):
                        fields=(0,1,2)

                    print('   Reading fields ',fields)

                    nest = False
                    for par in header:
                        if (par[0] == 'ORDERING'):
                            if (not par[1] == 'RING'):
                                nest = True
                            break

                    nest = False
                    for par in header:
                        if (par[0] == 'NSIDE'):
                            nside_map = par[1]
                            break


                    if (not nside == None):
                        if (nside > nside_map):
                            print('   Specified nside larger than that of the input maps')
                            print('   Not up-grading the maps')
                            print('')

                if (not os.path.isfile(filename)):
                    if (not drop_missing):
                        exit()
                    else:
                        continue

                data = hp.fitsfunc.read_map(filename,field=fields,verbose=False,h=False, nest=nest, dtype=np.float64)
                
                if (nest): #need to reorder to ring-ordering
                    data = hp.pixelfunc.reorder(data,n2r=True)

                # degrading if relevant
                if (not nside == None):
                    if (nside < nside_map):
                        data=hp.pixelfunc.ud_grade(data,nside) #ordering=ring by default

                if data.shape[0] == 1:
                    # Make sure its interprated as I by healpy
                    # For non-polarization data, (1,npix) is not accepted by healpy
                    data = data.ravel()

                # If smoothing applied and calculating stddev, smooth first.
                if fwhm > 0.0 and command == np.std:
                    #print(f"#{sample} --- Smoothing map ---")
                    if use_pixweights:
                        data = hp.sphtfunc.smoothing(data, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_pixel_weights=True,datapath=pixweight)
                    else: #use ring weights
                        data = hp.sphtfunc.smoothing(data, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_weights=True)
                    
                if (lowmem):
                    if (first_samp):
                        if (command==np.mean):
                            dats=data.copy()
                        elif (command==np.std):
                            dats=(mean_data - data)**2
                        else:
                            print('     Unknown command {command}. Exiting')
                            exit()
                    else:
                        if (command==np.mean):
                            dats=dats+data
                        elif (command==np.std):
                            dats=dats+(mean_data - data)**2
                    nsamp+=1
                else:
                    # Append sample to list
                    dats.append(data)
                first_samp=False

    if (lowmem):
        if (command == np.mean):
            outdata = dats/nsamp
        elif (command == np.std):
            outdata = np.sqrt(dats/nsamp)
    else:
        # Convert list to array
        dats = np.array(dats)
        # Calculate std or mean
        outdata = command(dats, axis=0)

    # Smoothing afterwards when calculating mean
    if fwhm > 0.0 and command == np.mean:
        print(f"--- Smoothing mean map with {fwhm} arcmin,---")
        if use_pixweights:
            outdata = hp.sphtfunc.smoothing(outdata, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_pixel_weights=True,datapath=pixweight)
        else: #use ring weights
            outdata = hp.sphtfunc.smoothing(outdata, fwhm=arcmin2rad(fwhm),verbose=False,pol=pol,use_weights=True)

    # Outputs fits map if output name is .fits
    if (return_mean and command == np.mean):
        return outdata
    elif output.endswith(".fits"):
        hp.write_map(output, outdata, overwrite=True)
    elif output.endswith(".dat"):
        np.savetxt(output, outdata)
    else:
        return outdata

