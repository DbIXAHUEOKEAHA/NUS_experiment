from devices import sr860, Waverunner9000, opticool
import matplotlib.pyplot as plt
from scipy import optimize
import numpy as np
from scipy.signal import find_peaks
import pandas as pd
import os

lockin = sr860.sr860('GPIB0::1::INSTR')
opticool = opticool.opticool('192.168.0.181:5000')
device = Waverunner9000.Waverunner9000('192.168.0.196')
print('Devices initialised')

device.sparcing = 1
device._npoints = int(2e6)
device.set_config()
device.window_div = 50e-6 / 10
device.set_TDIV(device.window_div)

rep = 1
num = 500000
trashold = 0.002
width = 20

folder = r'D:\Program_sweep\App\46. Connected p-bits\test'
filename = 'test1.csv'

f = lockin.frequency()
dc = lockin.dc_bias()
ac = lockin.amplitude()
T = opticool.T_finger()

d = {}

d['AC'] = [ac]
d['DC'] = [dc]
d['T'] = [T]

d['N'] = []
d['dt'] = []

for i in range(rep):

    _ampl = device._ampl1()#[:num]
    _time = device._time1()
    n = _time.shape[0]
    #_time = _time[:num]
    
    
    
    delta = ac
    
    mean = np.mean(_ampl)
    
    
    def _sin(x, phi):
        return delta / 2 * np.sin(2*np.pi*device.sparcing*f*x + phi) + mean
    
    try:
        opt, _ = optimize.curve_fit(_sin, _time, _ampl, p0 = [0])
    except:
        opt = [0]
        
    phi = opt[0]
    if phi < 0:
        phi += 2 * np.pi
        
    nbins = max(1, device.window_div * 10 * f)
    npoints = n / nbins
    
    distance = 100
        
    fit = _sin(_time, phi)
    
    delta = 0.0001
    mask = np.abs(fit - mean) <= delta
    try:
        start = np.where(mask)[0][0]
    except IndexError:
        start = 0
    print(f'Start position is {start}')
    
    plt.plot(_time[:num], _ampl[:num], color = 'darkblue', label = 'Raw data')
    plt.plot(_time[:num], fit[:num], color = 'crimson', label = 'Fit')
    plt.plot(_time[start], fit[start], 'o', color = 'red')
    plt.legend()
    plt.xlabel('_time, t (s)')
    plt.ylabel('_amplitude, V (V)')
    plt.show()
    
    
    if fit[int(start + npoints // 4)] < 0:
        start += npoints // 2
        
    start = int(start + npoints // 6)
    
    if dc >= 0:
        _ampl = fit - _ampl
    else:
        _ampl -= fit
        
    _time = _time[start:] - _time[start]
    _ampl = _ampl[start:]
    
    
    peaks, _ = find_peaks(_ampl, height = trashold, distance = distance, width = width) #index of peaks
    
    plt.plot(_time[:num], _ampl[:num], color = 'darkblue', label = 'Deviation from sinus')
    plt.plot(_time[peaks], _ampl[peaks], 'o', color = 'red')
    plt.xlim((0, 2e-5))
    plt.legend()
    plt.xlabel('_time, t (us)')
    plt.ylabel('_amplitude, V (V)')
    plt.show()
    
    
    for i in range(int(nbins)-1):
        cur_peaks = peaks[(np.where((peaks > i*npoints) & (peaks < (i+1)*npoints)))]
        d['N'] = np.concatenate((d['N'], [cur_peaks.shape[0]]))
        
        dt = []
        
        for j in range(cur_peaks.shape[0] - 1):
            dt.append(_time[cur_peaks[j+1]] - _time[cur_peaks[j]])
        
        d['dt'] = np.concatenate((d['dt'], dt))
        
        '''
        if i == 0:
            try:
                t0 = _time[cur_peaks[0]]
            except IndexError:
                t0 = 0
        
        if cur_peaks.shape[0] != 0:
            d[f'{i+1}'] = np.concatenate(([cur_peaks.shape[0]], _time[cur_peaks] - t0))
        else:
            d[f'{i+1}'] = [0]
        '''



df = pd.DataFrame.from_dict(d, orient='index')
df = df.transpose()
df.to_csv(os.path.join(folder, filename), index = False)