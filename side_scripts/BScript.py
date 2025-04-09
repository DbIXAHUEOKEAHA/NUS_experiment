from devices import sr860, Waverunner9000, opticool
import matplotlib.pyplot as plt
from scipy import optimize
import numpy as np
from scipy.fft import fft, fftfreq
import pandas as pd
import os
from scipy.signal import butter, lfilter, freqz

lockin = sr860.sr860('GPIB0::1::INSTR')
opticool = opticool.opticool('192.168.0.181:5000')
device = Waverunner9000.Waverunner9000('192.168.0.196')
print('Devices initialised')

device.sparcing = 1
device._npoints = int(30e6)
device.set_config()
device.window_div = 5000e-6 / 10
device.set_TDIV(device.window_div)

rep = 1
num = 500000
plt_time = 1e-5

folder = r'D:\Program_sweep\App\46. Connected p-bits\test'
filename = 'test3_n.csv'

f = lockin.frequency()
dc = lockin.dc_bias()
ac = lockin.amplitude()
T = opticool.T_finger()

d = {}

d['AC'] = [ac]
d['DC'] = [dc]
d['T'] = [T]

d['std'] = []
d['clk'] = []

num_clicks = 0

def butter_lowpass(cutoff, fs, order=5):
    return butter(order, cutoff, fs=fs, btype='low', analog=False)

def butter_lowpass_filter(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = lfilter(b, a, data)
    return y

for i in range(rep):

    _ampl = device._ampl1()#[:num]
    _time = device._time1()
    n = _time.shape[0]
    nbins = max(1, device.window_div * 10 * f)
    npoints = n / nbins
    
    delta = ac
    
    mean = np.mean(_ampl)

    filtered_data = butter_lowpass_filter(_ampl, cutoff = 3*f, fs = 1000*f, order=1)

    if dc > 0:
        start = np.argmin(filtered_data) % npoints
    else:
        start = np.argmax(filtered_data) % npoints
    
    start = int(start)
    
    print(f'Start position is {start}')
    
    plt.plot(_time[:num], _ampl[:num], color = 'darkblue', label = 'Raw data')
    plt.plot(_time[:num], filtered_data[:num], color = 'darkgreen', label = 'Filtered data')
    plt.plot(_time[start], filtered_data[start], 'o', color = 'red')
    plt.xlim((0, plt_time))
    plt.legend()
    plt.xlabel('_time, t (s)')
    plt.ylabel('_amplitude, V (V)')
    plt.show()
    
    _time = _time[start:] - _time[start]
    _ampl = _ampl[start:]
    
    edges = []
    cur_std = []
    for j in range(int(nbins) - 2):
        
        left_edge = int(npoints * j + 4 * npoints // 8)
        right_edge = int(npoints * j + 5* npoints // 8)
        
        cur_ampls = _ampl[left_edge:right_edge]
        std = np.std(cur_ampls) * np.sqrt(cur_ampls.shape[0])
        
        d['std'].append(std)
        cur_std.append(std)
        
        edges.append(_time[left_edge])
        edges.append(_time[right_edge])
        
    nth = 2#int(nbins // 10)
    nth_max = np.partition(d['std'], -nth)[-nth]  
    nth_min = np.partition(d['std'], nth-1)[nth-1]
    
    d_trashold = nth_max - nth_min
    
    trashold = 0.003
    
    for j in range(int(nbins) - 2):
        
        if cur_std[j] < trashold:
            d['clk'].append(0)
        else:
            d['clk'].append(1)
            num_clicks += 1
    
    plt.plot(_time[:num], _ampl[:num], color = 'darkblue', label = 'Ranges')
    plt.vlines(edges, ymin = np.min(_ampl * 1.5), ymax = np.max(_ampl * 1.5), colors = 'red', linestyles='dashed')
    plt.xlim((0, plt_time))
    plt.legend()
    plt.xlabel('_time, t (us)')
    plt.ylabel('_amplitude, V (V)')
    plt.show()
    
    plt.plot(d['std'], 'o', color = 'darkblue', label = 'Standard deviation')
    plt.plot([0, nbins], [trashold, trashold], '--', color = 'crimson', label = r'Trashold')
    #plt.plot([0, nbins], [std_glob, std_glob], '--', color = 'darkgreen', label = 'Global std')
    plt.legend()
    plt.xlabel('Bin number')
    plt.ylabel('Standard deviation, V')
    plt.show()


print(f'Probability of clicks is {num_clicks / nbins}')

d['P'] = [num_clicks / nbins / rep]

df = pd.DataFrame.from_dict(d, orient='index')
df = df.transpose()
df.to_csv(os.path.join(folder, filename), index = False)