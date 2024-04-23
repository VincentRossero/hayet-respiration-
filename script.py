import numpy as np
from neo.io import CedIO
import glob
import xarray as xr
import os
import matplotlib as plt
import scipy

def read_smrx(file, channel_name='debit', rescaled=True):
    reader = CedIO(file)
    traces = reader.get_analogsignal_chunk(stream_index=0)
    all_names = reader.header['signal_channels']['name']
    inds, = np.nonzero(all_names == channel_name)
    if inds.size == 0:
        raise ValueError(f'{channel_name} does not exist in this file.\n Possible channels : {list(all_names)}')
    elif inds.size > 1:
        print(f'Multiple channels with name {channel_name} found. Choosing the first one.')
        ind = inds[0]
    else:
        ind = inds[0]
    # find the stream
    stream_id = reader.header['signal_channels']['stream_id'][ind]
    stream_index = np.nonzero(reader.header['signal_streams']['id'] == stream_id)[0][0]
    units = reader.header['signal_channels'][0][4]


    # find channel index in stream
    mask = reader.header['signal_channels']['stream_id'] == stream_id
    chans = reader.header['signal_channels'][mask]
    channel_indexes, = np.nonzero(chans['name'] == channel_name)

    if rescaled:
        traces = reader.rescale_signal_raw_to_float(traces, dtype = 'float32', stream_index=stream_index, channel_indexes=channel_indexes)
    srate = reader.header['signal_channels']['sampling_rate'][0]
    return traces[:,0], srate, units

def smrx_to_xarray(smrx_file):
    sig, srate, unit = read_smrx(smrx_file)
    time = np.arange(sig.size) / srate
    da = xr.DataArray(data = sig, dims = ['time'], coords = {'time':time}, attrs = {'srate':srate, 'unit':unit})
    return da

def save_all_to_nc():
    for file in glob.glob('data/*.smrx'):
        da = smrx_to_xarray(file)
        mouse = os.path.basename(file).split(' ')[0]
        day = os.path.basename(file).split(' ')[1]  # Récupère J1 ou J10 depuis le nom du fichier
        output_file = os.path.join('output', f'{mouse}_{day}.nc')  # Inclut J1 ou J10 dans le nom du fichier .nc
        da.to_netcdf(output_file)




def read_one_mouse_from_nc(num_mouse):
    load_file = f'output/souris{num_mouse}.nc'  # Utilise le dossier "output"
    da = xr.open_dataarray(load_file)
    raw_resp = da.values
    srate = da.attrs['srate']
    unit = da.attrs['unit']
    time_vector = da['time'].values
    return raw_resp, srate, unit, time_vector


'''
save_all_to_nc ()
print(read_one_mouse_from_nc('113_J1.smrx'))
'''


def iirfilt(sig, srate, lowcut=None, highcut=None, order = 4, ftype = 'butter', verbose = False, show = False, axis = 0):

    """
    IIR-Filter of signal

    -------------------
    Inputs : 
    - sig : nd array
    - srate : sampling rate of the signal
    - lowcut : lowcut of the filter. Lowpass filter if lowcut is None and highcut is not None
    - highcut : highcut of the filter. Highpass filter if highcut is None and low is not None
    - order : N-th order of the filter (the more the order the more the slope of the filter)
    - ftype : Type of the IIR filter, could be butter or bessel
    - verbose : if True, will print information of type of filter and order (default is False)
    - show : if True, will show plot of frequency response of the filter (default is False)
    """

    if lowcut is None and not highcut is None:
        btype = 'lowpass'
        cut = highcut

    if not lowcut is None and highcut is None:
        btype = 'highpass'
        cut = lowcut

    if not lowcut is None and not highcut is None:
        btype = 'bandpass'

    if btype in ('bandpass', 'bandstop'):
        band = [lowcut, highcut]
        assert len(band) == 2
        Wn = [e / srate * 2 for e in band]
    else:
        Wn = float(cut) / srate * 2

    filter_mode = 'sos'
    sos = scipy.signal.iirfilter(order, Wn, analog=False, btype=btype, ftype=ftype, output=filter_mode)

    filtered_sig = scipy.signal.sosfiltfilt(sos, sig, axis=axis)

    if verbose:
        print(f'{ftype} iirfilter of {order}th-order')
        print(f'btype : {btype}')


    if show:
        w, h = scipy.signal.sosfreqz(sos,fs=srate, worN = 2**18)
        fig, ax = plt.subplots()
        ax.plot(w, np.abs(h))
        ax.scatter(w, np.abs(h), color = 'k', alpha = 0.5)
        full_energy = w[np.abs(h) >= 0.99]
        ax.axvspan(xmin = full_energy[0], xmax = full_energy[-1], alpha = 0.1)
        ax.set_title('Frequency response')
        ax.set_xlabel('Frequency [Hz]')
        ax.set_ylabel('Amplitude')
        plt.show()

    return filtered_sig
