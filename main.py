import os
from os.path import exists
core_dir = os.getcwd() 
import sys
import json
import csv
csv.field_size_limit(int(1e9))
from csv import writer
import threading
from tkinter import ttk
import tkinter as tk
from tkinter import messagebox
from addons.ToolTip import CreateToolTip
from mapper.mapper2D import mapper2D
from mapper.mapper3D import mapper3D
from mapper.add_ticks import add_ticks
from mapper.string_utils import rm_all, condition_2_func
from mapper.filename_utils import cut, basename, unify_filename, fix_unicode, get_filename_index
import matplotlib.animation as animation
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
from matplotlib import style
import pyvisa as visa
import time
from datetime import datetime
import pandas as pd
import matplotlib
import numpy as np
from scipy import optimize, signal
from scipy.signal import butter, lfilter, freqz
import numpy.ma as ma
import glob
import serial
from IPy import IP
from PIL import Image, ImageTk
from itertools import count, cycle

def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = [f'COM{i+1}' for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

if not exists(os.path.join(core_dir, 'devices')):
    os.mkdir(os.path.join(core_dir, 'devices'))
      
sys.path.insert(0, os.path.join(core_dir, 'devices'))

def str_to_class(classname):
    return getattr(sys.modules[__name__], classname)

device_classes = os.listdir(os.path.join(core_dir, 'devices'))
_device_classes = []
for i in device_classes:
    if i[-3:] == '.py':
        _device_classes.append(i)
device_classes = _device_classes.copy()
    
for ind, device in enumerate(device_classes):
    try:
        exec(f'from {device[:-3]} import {device[:-3]}')
        device_classes[ind] = str_to_class(device[:-3])
    except Exception as e:
        print(f'Device import faced problem: {e}')
              
print('Devices import succes')

matplotlib.use("Agg")
plt.rcParams['animation.html'] = 'jshtml'
LARGE_FONT = ('Verdana', 12)
SUPER_LARGE = ('Verdana', 16)
style.use('seaborn-v0_8-whitegrid')

# Check if everything connected properly
rm = visa.ResourceManager()
list_of_devices = list(rm.list_resources())

for i in serial_ports():
    list_of_devices.append(i)

# Write command to a device and get it's output
def get(device, command):
    # return np.round(np.random.random(1), 1)
    return device.query(command)

print(f'Instruments: {list_of_devices} \n')

def var2str(var, vars_data=locals()):
    return [var_name for var_name in vars_data if id(var) == id(vars_data[var_name])][0]

# assigning variables for sweeping

parameter_to_sweep1 = ''
parameter_to_sweep2 = ''
parameter_to_sweep3 = ''
parameters_to_read_dict = {}
step_counter = 0
from_sweep1 = 0
to_sweep1 = 1
ratio_sweep1 = 1
back_ratio_sweep1 = 1
delay_factor1 = 1
back_delay_factor1 = 1
from_sweep2 = 0
to_sweep2 = 1
ratio_sweep2 = 1
back_ratio_sweep2 = 1
delay_factor2 = 1
back_delay_factor2 = 1
from_sweep3 = 0
to_sweep3 = 1
ratio_sweep3 = 1
back_ratio_sweep3 = 1
delay_factor3 = 1
back_delay_factor3 = 1
setget_delay_factor = 1
stepper_flag = False
#fastmode_slave_flag = False
#fastmode_master_flag = False
snakemode_slave_flag = False
snakemode_master_flag = False
interpolated2D = True
interpolated3D = True
uniform2D = True
uniform3D = True

plot_flag = 'Plot'
plot_err_msg = ''

deli = ','

#month_dictionary = {'01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun', 
#                    '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'}
DAY = datetime.today().strftime('%d')
MONTH = datetime.today().strftime('%m')
YEAR = datetime.today().strftime('%Y')[-2:]

if not exists(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')):
    os.mkdir(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}'))
    
cur_dir = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')

if not exists(os.path.join(cur_dir, 'data_files')):
    os.mkdir(os.path.join(cur_dir, 'data_files'))

filename_sweep = os.path.join(cur_dir, 'data_files', f'{YEAR}{MONTH}{DAY}.csv')

ind_setget = [0]
path = os.path.join(cur_dir, 'data_files')
path = fix_unicode(path)

for file in os.listdir(path):
    if f'setget_{YEAR}{MONTH}{DAY}' in file: 
        try:
            ind_setget.append(int(file[len(file) - file[::-1].find('-') : -4]))
        except ValueError:
            pass
        finally:
            pass
        
filename_setget = os.path.join(cur_dir, 'data_files', f'setget_{YEAR}{MONTH}{DAY}-{np.max(ind_setget) + 1}.csv')
filename_setget = fix_unicode(filename_setget)

sweeper_flag1 = False
sweeper_flag2 = False
sweeper_flag3 = False
setget_flag = False

pause_flag = False
stop_flag = False
tozero_flag = False

condition = ''

if not exists(os.path.join(core_dir, 'config')):
    os.mkdir(os.path.join(core_dir, 'config'))

manual_sweep_flags = [0]
manual_filenames = [os.path.join(cur_dir, 'data_files', 'manual' + datetime.today().strftime(
    '%H_%M_%d_%m_%Y') + '.csv')]

master_lock = False

back_and_forth_master = 1
back_and_forth_slave = 1
back_and_forth_slave_slave = 1

columns = []

# variables for plotting

cur_animation_num = 1

#creating config files if they were deleted

address_dictionary_path = os.path.join(core_dir, 'config', 'address_dictionary.txt')
if not exists(address_dictionary_path):
    with open(address_dictionary_path, 'w') as file:
        try:
            file.write('{}')
            file.close()
        except:
            file.close()
        finally:
            file.close()  
            
def create_preset(dimension):
    global cur_dir
    global filename_sweep
    dimension = str(dimension)
    globals()['sweeper' + dimension + 'd_path'] = os.path.join(core_dir, 'config', f'sweeper{dimension}d_preset.csv')
    if not exists(globals()[f'sweeper{dimension}d_path']):
        dic = {}
        for i in range(int(dimension)):
             dic['combo_to_sweep' + str(i+1)] = [0]
             dic['sweep_options' + str(i+1)] = [0]
             dic['from' + str(i+1)] = ['']
             dic['to' + str(i+1)] = ['']
             dic['count_option' + str(i+1)] = ['ratio']
             dic['ratio' + str(i+1)] = ['']
             dic['back_ratio' + str(i+1)] = ['']
             dic['delay_factor' + str(i+1)] = ['']
             dic['back_delay_factor' + str(i+1)] = ['']
             dic['status_back_and_forth' + str(i+1)] = [0]
             dic['status_manual' + str(i+1)] = [0]
             dic['manual_filename' + str(i+1)] = ''
             if i == 1 or i == 2:
                 #dic['status_fastmode' + str(i+1)] = [0]
                 dic['status_snakemode' + str(i+1)] = [0]
        dic['condition'] = ''
        dic['filename_sweep'] = filename_sweep
        dic['interpolated'] = [1]
        dic['uniform'] = [1]
        dataframe = pd.DataFrame(dic)
        dataframe.to_csv(globals()[f'sweeper{dimension}d_path'], index = False)

for i in range(3):
    create_preset(i+1)

setget_path = os.path.join(core_dir, 'config', 'setget_preset.csv')
if not exists(setget_path):
    dic = {}
    dic['num_widgets'] = [1]
    dic['combo_to_sweep1'] = [0]
    dic['sweep_options1'] = [0]
    dic['set1'] = ['']
    dic['combo_to_sweep2'] = [0]
    dic['sweep_options2'] = [0]
    dic['set2'] = ['']
    dic['combo_to_sweep3'] = [0]
    dic['sweep_options3'] = [0]
    dic['set3'] = ['']
    dic['combo_to_sweep4'] = [0]
    dic['sweep_options4'] = [0]
    dic['set4'] = ['']
    dic['combo_to_sweep5'] = [0]
    dic['sweep_options5'] = [0]
    dic['set5'] = ['']
    dic['combo_to_sweep6'] = [0]
    dic['sweep_options6'] = [0]
    dic['set6'] = ['']
    dataframe = pd.DataFrame(dic)
    dataframe.to_csv(setget_path, index = False)

graph_preset_path = os.path.join(core_dir, 'config', 'graph_preset.csv')
if not exists(graph_preset_path):
    dic = {}
    dic['num_plots'] = [1]
    for i in range(1, 100):
        dic[f'title{i}'] = [f'Plot {i}']
        dic[f'x{i}_current'] = [0]
        dic[f'x{i}_log'] = [0]
        dic[f'y{i}_current'] = [0]
        dic[f'y{i}_log'] = [0]
        dic[f'z{i}_current'] = [0]
        dic[f'x{i}_lim_left'] = ['']
        dic[f'x{i}_lim_right'] = ['']
        dic[f'x{i}_autoscale'] = [1]
        dic[f'y{i}_lim_left'] = ['']
        dic[f'y{i}_lim_right'] = ['']
        dic[f'y{i}_autoscale'] = [1]
        dic[f'x{i}_label'] = ['x']
        dic[f'y{i}_label'] = ['y']
        dic[f'z{i}_label'] = ['z']
        dic[f'cmap{i}'] = ['viridis']
        dic[f'x{i}_transform'] = ['x']
        dic[f'y{i}_transform'] = ['y']
        dic[f'z{i}_transform'] = ['z']
        if i % 3 == 1:
            dic[f'title_map{i}'] = [f'Map {i}']
            dic[f'x{i}_label_map'] = ['x']
            dic[f'y{i}_label_map'] = ['y']
            dic[f'z{i}_label_map'] = ['z']
            dic[f'x{i}_transform_map'] = ['x']
            dic[f'y{i}_transform_map'] = ['y']
            dic[f'z{i}_transform_map'] = ['z']
    dataframe = pd.DataFrame(dic)
    dataframe.to_csv(graph_preset_path, index = False)

if len(list_of_devices) == 0:
    list_of_devices = ['']
    
types_of_devices = []
for i in range (len(list_of_devices)):
    types_of_devices.append('Not a class')
        
list_of_devices.insert(0, 'Time')
types_of_devices.insert(0, 'Time')

with open(os.path.join(core_dir, 'config', 'address_dictionary.txt'), 'r') as file:
    address_dict = file.read()
address_dict = json.loads(address_dict)

for address in list(address_dict.keys()):
    if ':' in address and not '::' in address:
        try:
            ip = IP(address.split(':')[0])
            list_of_devices.append(address)
            types_of_devices.append('Not a class')
        except ValueError:
            pass
    elif not ':' in address:
        try:
            ip = IP(address)
            list_of_devices.append(address)
            types_of_devices.append('Not a class')
        except ValueError:
            pass
    if address.startswith('cDAQ'):
        list_of_devices.append(address)
        types_of_devices.append('Not a class')
        
for ind_, type_ in enumerate(types_of_devices):
    if type_ == 'Not a class':
        if list_of_devices[ind_] in list(address_dict.keys()):
            types_of_devices[ind_] = address_dict[list_of_devices[ind_]]

list_of_devices_addresses = list_of_devices.copy()
for ind, device in enumerate(list_of_devices_addresses):
    if types_of_devices[ind] != 'Not a class':
        try:
            list_of_devices[ind] = str_to_class(types_of_devices[ind])(adress =  list_of_devices_addresses[ind])
        except Exception as e:
            print(f'Exception happened in initialising {list_of_devices[ind]}: {e}')

device_to_sweep1 = list_of_devices[0]
device_to_sweep2 = list_of_devices[0]
device_to_sweep3 = list_of_devices[0]

def new_parameters_to_read():
    global list_of_devices
    global list_of_devices_addresses
    
    parameters_to_read = []
    for ind, device in enumerate(list_of_devices):
        if not isinstance(device, str): #if device is object of a class but not a string object
            get_options = getattr(device, 'get_options')
            adress = list_of_devices_addresses[ind]
            for option in get_options:
                parameters_to_read.append(adress + '.' + option)
    return parameters_to_read

parameters_to_read = new_parameters_to_read()

parameters_to_read_copy = parameters_to_read.copy()

zero_time = time.perf_counter()

def plot_animation(i, n, filename):
    
    def axes_settings(i, pad = 0, tick_size = 4, label_size = 6, x_pad =0, y_pad = 1, title_size = 8, title_pad = -5):
        globals()[f'ax{i}'].tick_params(axis='y', which='both', length = 0, pad=pad, labelsize=tick_size)
        globals()[f'ax{i}'].tick_params(axis='x', which='both', length = 0, pad=pad + 1, labelsize=tick_size)
        globals()[f'ax{i}'].yaxis.offsetText.set_fontsize(tick_size)
        globals()[f'ax{i}'].xaxis.offsetText.set_fontsize(tick_size)
        globals()[f'ax{i}'].set_xlabel('x', fontsize = label_size, labelpad = x_pad)
        globals()[f'ax{i}'].set_ylabel('y', fontsize = label_size, labelpad = y_pad)
        globals()[f'ax{i}'].set_title(f'Plot {i}', fontsize = title_size, pad = title_pad)
    
    global columns
    global x_transformation
    global y_transformation
    
    import numpy as np
    log = lambda x: np.log(x)
    exp = lambda x: np.exp(x)
    sqrt = lambda x: x ** 0.5
    
    if n%3 == 1:
        color = 'darkblue'
    elif n%3 == 2:
        color = 'darkgreen'
    elif n%3 == 0:
        color = 'crimson'
    else:
        color = 'black'
        
    if not 'setget' in filename:
        filename = globals()['filename_sweep']
        
    
        
    try:
        data = pd.read_csv(filename, sep = deli)
        globals()[f'x{n}'] = data[columns[globals()[f'x{n}_status']]].values
        globals()[f'y{n}'] = data[columns[globals()[f'y{n}_status']]].values
    except Exception as e:
        if str(e) != globals()['plot_err_msg']:
            globals()['plot_err_msg'] = str(e)
            print(f'Exception happened in graph plot extracting data: {e}')
    x = np.array(globals()[f'x{n}'])
    y = np.array(globals()[f'y{n}'])
    
    if not y.shape[0] == 0 and not x.shape[0] == 0:
        if type(y[0]) == str and ',' in y[0] and type(x[0]) == str and ',' in x[0]:
            try:
                y = np.array([float(i) for i in y[-1].split(',')])
                x = np.array([float(i) for i in x[-1].split(',')])
            except:
                pass
            
        elif type(y[0]) == str and ',' in y[0]:
            return
        elif type(x[0]) == str and ',' in x[0]:
            return
    try:
        x = eval(globals()[f'x_transformation{n}'], locals())
    except:
        pass
    
    try:
        y = eval(globals()[f'y_transformation{n}'], locals())
    except:
        pass
    
    ax = globals()[f'ax{n}']
    
    xscale_status = ax.get_xscale()
    yscale_status = ax.get_yscale()
    autoscale_x = ax.get_autoscalex_on()
    autoscale_y = ax.get_autoscaley_on()
    title = ax.get_title()
    xlabel = ax.get_xlabel()
    ylabel = ax.get_ylabel()
    xlims = ax.get_xlim()
    ylims = ax.get_ylim()
    ax.clear()
    ax.set_xscale(xscale_status)
    ax.set_yscale(yscale_status)
    axes_settings(n)
    ax.set_title(title, fontsize = 8, pad = -5)
    ax.set_xlim(xlims)
    ax.set_ylim(ylims)
    ax.set_xlabel(xlabel, fontsize = 8)
    ax.set_ylabel(ylabel, fontsize = 8)
    
    ax.autoscale(enable = autoscale_x, axis = 'x')
    ax.autoscale(enable = autoscale_y, axis = 'y')
    
    plt.rcParams['axes.grid'] = False
    ax.plot(x, y, '-', lw=1, color=color)
    
    #globals()[f'graph_object{globals()["cur_animation_num"] - 3}'].update()
    globals()[f'graph_object{globals()["cur_animation_num"] - 3}'].update_idletasks()
    
    return [ax]


def map_animation(i, n, filename):
    
    global sweeper_write
    global parameters_to_read
    global manual_sweep_flags
    
    import numpy as np
    log = lambda x: np.log(x)
    exp = lambda x: np.exp(x)
    sqrt = lambda x: x ** 0.5
    
    ax = globals()[f'ax{n}']
    
    if len(manual_sweep_flags) == 2 or (len(manual_sweep_flags) == 3 and (sweeper_write.condition_status == 'yz' or sweeper_write.condition_status == 'yx')):
        if hasattr(sweeper_write.mapper2D, 'map_slave'):
            _pass = True
        else:
            _pass = False
    elif len(manual_sweep_flags) == 3:
        if hasattr(sweeper_write.mapper3D, 'map_slave_slave'):
            _pass = True
        else:
            if hasattr(sweeper_write.mapper3D, 'map_slave_slave0'):
                _pass = True
            else:
                _pass = False
    else:
        _pass = False
        
    if _pass:
        
        if len(manual_sweep_flags) == 2 or (len(manual_sweep_flags) == 3 and (sweeper_write.condition_status == 'yz' or sweeper_write.condition_status == 'yx')):
            x = sweeper_write.mapper2D.map_slave
            y = sweeper_write.mapper2D.map_master
            parameter = parameters_to_read[globals()[f'z{n}_status']]
            z = getattr(sweeper_write.mapper2D, f'map_{parameter}')
            
            if x.shape[0] == 1:
                x = np.vstack([x, x])
                y = np.vstack([y, [i + 1 for i in y]])
                z = np.vstack([z, np.nan * np.ones(x.shape[1])])
              
            z = ma.masked_invalid(z)  
              
            mapper = sweeper_write.mapper2D
        
        elif len(manual_sweep_flags) == 3:
            master = sweeper_write.mapper3D.master
            
            try:
                parameter = parameters_to_read[globals()[f'z{n}_status']]
            except IndexError:
                parameter = parameters_to_read[0]
            
            cur_graph = globals()[f'graph_object{globals()["cur_animation_num"] - 3}']
            if master.shape[0] > cur_graph.master_shape:
                cur_graph.slider.config(to = master.shape[0])
                cur_graph.master_shape = master.shape[0]
                cur_graph.master = master
                
            if cur_graph.last:
                if hasattr(sweeper_write.mapper3D, f'map_{parameter}'):
                    x = sweeper_write.mapper3D.map_slave_slave
                    y = sweeper_write.mapper3D.map_slave
                    z = getattr(sweeper_write.mapper3D, f'map_{parameter}')
                    cur_graph.slider.set(master.shape[0])
                    cur_graph.change_label(event = None)
                else:
                    iterator = round(cur_graph.slider.get()) - 1
                    try:
                        x = getattr(sweeper_write.mapper3D, f'map_slave_slave{iterator}')
                        y = getattr(sweeper_write.mapper3D, f'map_slave{iterator}')
                        z = getattr(sweeper_write.mapper3D, f'map_{parameter}{iterator}')
                    except AttributeError:
                        try:
                            x = getattr(sweeper_write.mapper3D, 'map_slave_slave0')
                            y = getattr(sweeper_write.mapper3D, 'map_slave0')
                            z = getattr(sweeper_write.mapper3D, f'map_{parameter}0')
                        except:
                            return
                            
            else:
                iterator = round(cur_graph.slider.get()) - 1
                x = getattr(sweeper_write.mapper3D, f'map_slave_slave{iterator}')
                y = getattr(sweeper_write.mapper3D, f'map_slave{iterator}')
                z = getattr(sweeper_write.mapper3D, f'map_{parameter}{iterator}')
            
            if x.shape[0] == 1:
                x = np.vstack([x, x])
                y = np.vstack([y, [i + 1 for i in y]])
                z = np.vstack([z, np.nan * np.ones(x.shape[1])]) 
              
            z = ma.masked_invalid(z)  
              
            mapper = sweeper_write.mapper3D
    
        try:
            x = eval(globals()[f'x_transformation{n}'], locals())
        except Exception as e:
            print(e)
        
        try:
            y = eval(globals()[f'y_transformation{n}'], locals())
        except Exception as e:
            print(e)
        
        try:
            z = eval(globals()[f'z_transformation{n}'], locals())
        except Exception as e:
            print(e)
        
        try:
            globals()[f'colorbar{n}'].remove()
        except Exception as e:
            print(e)

        title = ax.get_title()
        xlabel = ax.get_xlabel()
        ylabel = ax.get_ylabel()
        ax.clear()
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        
        plt.rcParams['axes.grid'] = False
        if len(manual_sweep_flags) == 3:
            try:
                parameter = parameters_to_read[globals()[f'z{n}_status']]
            except IndexError:
                parameter = parameters_to_read[0]
            if hasattr(sweeper_write.mapper3D, f'max_{parameter}'):
                max_z = getattr(sweeper_write.mapper3D, f'max_{parameter}')
                min_z = getattr(sweeper_write.mapper3D, f'min_{parameter}')
                z_transformation = globals()[f'z_transformation{n}']
                if '[' in z_transformation and ']' in z_transformation:
                    ind1 = z_transformation.index('[')
                    ind2 = len(z_transformation) - z_transformation[::-1].index(']')
                    z_transformation = z_transformation[:ind1] + z_transformation[ind2:]
                try:
                    max_z = eval(z_transformation.replace('z', 'max_z'), locals())
                    min_z = eval(z_transformation.replace('z', 'min_z'), locals())
                except Exception as e:
                    print(f'Exception in max_z min_z z_transformation - {e}')
                    max_z = np.nanmax(z)
                    min_z = np.nanmin(z)

            else:
                max_z = np.nanmax(z)
                min_z = np.nanmin(z)
        else:
            max_z = np.nanmax(z)
            min_z = np.nanmin(z)
        colormap = ax.pcolormesh(z, cmap = globals()[f'cmap_{n}'], vmin=min_z, vmax=max_z, shading = 'flat')
        globals()[f'colorbar{n}'] = ax.get_figure().colorbar(colormap, ax = ax)
        globals()[f'colorbar{n}'].ax.tick_params(labelsize=5, which = 'both')
        
        try:
            globals()[f'colorbar{n}'].set_label(globals()[f'colorbar{n}_label'])
        except:
            pass
        
        add_ticks(ax, x[0, :], y[:, 0])

def my_animate(i, n, filename):
    # function to animate graph on each step

    global plot_flag
    
    
    
    if plot_flag == 'Plot' or n % 3 != 1:
        plot_animation(i, n, filename)
    elif plot_flag == 'Map' and n % 3 == 1:
        map_animation(i, n, filename)
    else:
        raise Exception(f'Plot flag can only be "plot" or "map", not {plot_flag}')

zero_time = time.perf_counter()

class Universal_frontend(tk.Tk):

    def __init__(self, classes, start, size = '1920x1080', title = 'Unisweep', *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        tk.Tk.iconbitmap(self)
        tk.Tk.geometry(self, newGeometry = size)
        tk.Tk.wm_title(self, title)

        container = tk.Frame(self)
        container.pack(side='top', fill='both', expand='True')
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        for F in classes:
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky='nsew')

        self.show_frame(start)

    def show_frame(self, cont):
        global settings_flag
        frame = self.frames[cont]
        frame.tkraise()
        globals()['Sweeper_object'] = frame

class StartPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        label = tk.Label(self, text='Start Page', font=LARGE_FONT)
        label.pack(pady=10, padx=10)
        
        devices_button = tk.Button(self, text = 'Devices', command = lambda: self.devices_show(), 
                                   font = LARGE_FONT)
        devices_button.place(relx = 0.1, rely = 0.1)
        
        setget_button = tk.Button(self, text = 'Set/Get', 
                                  command = lambda: self.setget_show(), font = LARGE_FONT)
        setget_button.place(relx = 0.1, rely = 0.25)

        sweeper1d_button = tk.Button(
            self, text='1D - sweeper', command=lambda: self.sweeper1d_show(), font = LARGE_FONT)
        sweeper1d_button.place(relx=0.1, rely=0.4)

        sweeper2d_button = tk.Button(
            self, text='2D - sweeper', command=lambda: self.sweeper2d_show(), font = LARGE_FONT)
        sweeper2d_button.place(relx=0.2, rely=0.4)

        sweeper3d_button = tk.Button(
            self, text='3D - sweeper', command=lambda: self.sweeper3d_show(), font = LARGE_FONT)
        sweeper3d_button.place(relx=0.3, rely=0.4)
    
    def setget_show(self):
        self.controller.show_frame(SetGet)
    
    def sweeper1d_show(self):
        global settings_flag
        settings_flag = True
        self.controller.show_frame(Sweeper1d)
        
    def sweeper2d_show(self):
        global settings_flag
        settings_flag = True
        self.controller.show_frame(Sweeper2d)
        
    def sweeper3d_show(self):
        global settings_flag
        settings_flag = True
        self.controller.show_frame(Sweeper3d)
        
    def devices_show(self):
        self.controller.show_frame(Devices)

class Devices(tk.Frame):
    
    def __init__(self, parent, controller):       

        tk.Frame.__init__(self, parent)
        
        button_home = tk.Button(self, text='Back to Home',
                                 command=lambda: controller.show_frame(StartPage))
        button_home.pack()
        
        label_adress = tk.Label(self, text = 'Set device type:', font = LARGE_FONT)
        label_adress.place(relx = 0.05, rely = 0.05)
        
        self.combo_adresses = ttk.Combobox(self, value = list_of_devices_addresses)
        self.combo_adresses.current(0)
        self.combo_adresses.place(relx = 0.05, rely = 0.1)
        
        self.device_classes = []
        for class_ in device_classes:
            self.device_classes.append(var2str(class_))
            
        self.combo_types = ttk.Combobox(self, value = self.device_classes)    
        self.combo_types.bind("<<ComboboxSelected>>", self.set_type_to_adress)
        self.combo_types.place(relx = 0.2, rely = 0.1)
        
    def set_type_to_adress(self, interval = 100):
        global address_dict
        global types_of_devices
        global parameters_to_read
        global parameters_to_read_copy
        global new_parameters_to_read
        
        if list(self.combo_adresses['values'])[self.combo_adresses.current()] != '':
        
            types_of_devices[self.combo_adresses.current()] = list(self.combo_types['values'])[self.combo_types.current()]
            
            address_dict[list(self.combo_adresses['values'])[self.combo_adresses.current()]] = list(self.combo_types['values'])[self.combo_types.current()]
            
            with open(os.path.join(core_dir, 'config', 'address_dictionary.txt'), "w") as outfile:
                json.dump(address_dict, outfile)
                
            parameters_to_read = new_parameters_to_read()
            parameters_to_read_copy = parameters_to_read.copy()

class SetGet(tk.Frame):
    
    def __init__(self, parent, controller):       

        tk.Frame.__init__(self, parent)
        
        self.preset = pd.read_csv(globals()['setget_path'], sep = ',')
        self.preset = self.preset.fillna('')
        self.num_widgets = int(self.preset['num_widgets'].values[0])
        if self.num_widgets > 6:
            self.num_widgets = 6
        self.combo_to_sweep1_current = int(self.preset['combo_to_sweep1'].values[0])
        self.sweep_options1_current = int(self.preset['sweep_options1'].values[0])
        self.set1_current = str(self.preset['set1'].values[0])
        self.combo_to_sweep2_current = int(self.preset['combo_to_sweep2'].values[0])
        self.sweep_options2_current = int(self.preset['sweep_options2'].values[0])
        self.set2_current = str(self.preset['set2'].values[0])
        self.combo_to_sweep3_current = int(self.preset['combo_to_sweep3'].values[0])
        self.sweep_options3_current = int(self.preset['sweep_options3'].values[0])
        self.set3_current = str(self.preset['set3'].values[0])
        self.combo_to_sweep4_current = int(self.preset['combo_to_sweep4'].values[0])
        self.sweep_options4_current = int(self.preset['sweep_options4'].values[0])
        self.set4_current = str(self.preset['set4'].values[0])
        self.combo_to_sweep5_current = int(self.preset['combo_to_sweep5'].values[0])
        self.sweep_options5_current = int(self.preset['sweep_options5'].values[0])
        self.set5_current = str(self.preset['set5'].values[0])
        self.combo_to_sweep6_current = int(self.preset['combo_to_sweep6'].values[0])
        self.sweep_options6_current = int(self.preset['sweep_options6'].values[0])
        self.set6_current = str(self.preset['set6'].values[0])
        
        self.dict_num_heading = {}
        
        button_home = tk.Button(self, text='Back to Home',
                                 command=lambda: self.go_home(controller))
        button_home.pack()
        
        button_set_all = tk.Button(self, text = 'Set all', command = self.set_all)
        button_set_all.pack()
        
        for i in range (1, self.num_widgets + 1):
        
            self.__dict__[f'label_devices{i}'] = tk.Label(self, text = 'Devices:', font=LARGE_FONT)
            self.__dict__[f'label_devices{i}'].place(relx = 0.05 + (i - int(i / 5) * 4 - 1) * 7/30, rely = 0.21 + int(i / 5) * 0.35)
    
            self.__dict__[f'combo_to_sweep{i}'] = ttk.Combobox(self, value=list_of_devices_addresses)
            self.__dict__[f'combo_to_sweep{i}'].bind(
                "<<ComboboxSelected>>", getattr(self, f'update_sweep_parameters{i}'))
            self.__dict__[f'combo_to_sweep{i}'].place(relx=0.15 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.21 + int(i / 5) * 0.35)
            
            self.__dict__[f'label_options{i}'] = tk.Label(self, text = 'Options:', font = LARGE_FONT)
            self.__dict__[f'label_options{i}'].place(relx = 0.05 + (i - int(i / 5) * 4 - 1) * 7/30, rely = 0.25 + int(i / 5) * 0.35)
            
            self.__dict__[f'sweep_options{i}'] = ttk.Combobox(self)
            self.__dict__[f'sweep_options{i}'].bind(
                "<<ComboboxSelected>>", getattr(self, f'update_sweep_options{i}'))
            self.__dict__[f'sweep_options{i}'].place(relx=0.15 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.25 + int(i / 5) * 0.35)
            
            try:
                self.__dict__[f'combo_to_sweep{i}'].current(getattr(self, f'combo_to_sweep{i}_current'))
                getattr(self, f'update_sweep_parameters{i}')(event = None)
            except:
                self.__dict__[f'combo_to_sweep{i}'].current(0)
                
                if self.__dict__[f'combo_to_sweep{i}']['values'][0] != '':
                    getattr(self, f'update_sweep_parameters{i}')(event = None)
                
            
            self.__dict__[f'label_set{i}'] = tk.Label(self, text = 'Set', font = LARGE_FONT)
            self.__dict__[f'label_set{i}'].place(relx=0.05 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.29 + int(i / 5) * 0.35)
            
            self.__dict__[f'entry_set{i}'] = tk.Entry(self, width = 16)
            self.__dict__[f'entry_set{i}'].insert(0, getattr(self, f'set{i}_current'))
            self.__dict__[f'entry_set{i}'].place(relx=0.15 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.29 + int(i / 5) * 0.35)
            
            self.__dict__[f'button_set{i}'] = tk.Button(self, text = 'Set', command = getattr(self, f'set_device{i}'))
            self.__dict__[f'button_set{i}'].place(relx=0.235 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.285 + int(i / 5) * 0.35)
            
        i = self.num_widgets
        
        if i >= 2:
            self.__dict__[f'button_destroy{i}'] = tk.Button(self, text = r'🗙', command = lambda: self.destroy_block(i))
            self.__dict__[f'button_destroy{i}'].place(relx = 0.28 + (i - int(i / 5) * 4 - 1) * 7/30, rely = 0.17 + int(i / 5) * 0.35)
        
        if i >= 1 and i <= 5:
            self.__dict__[f'button_add{i}'] = tk.Button(self, text = 'Add', font = LARGE_FONT, command = lambda: self.add_block(i + 1))
            self.__dict__[f'button_add{i}'].place(relx=0.15 + (i - int((i + 1) / 5) * 4) * 7/30, rely=0.25 + int((i+1) / 5) * 0.35)
            
        label_get = tk.Label(self, text = 'Get', font = LARGE_FONT)
        label_get.place(relx = 0.7, rely = 0.4)
            
        self.devices = tk.StringVar()
        self.devices.set(value=parameters_to_read)
        if len(parameters_to_read) <= 10:
            height = len(parameters_to_read)
        else:
            height = 10
        self.lstbox_to_read = tk.Listbox(self, listvariable = self.devices,
                                         selectmode='multiple', exportselection=False,
                                         width=50,
                                         height=height)
        self.lstbox_to_read.place(relx=0.6, rely=0.45)
        
        self.dict_lstbox = {}
        
        for parameter in parameters_to_read:
            self.dict_lstbox[parameter] = parameter
            
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.place(relx = 0.85, rely = 0.45)
        
        self.scrollbar.config(command=self.lstbox_to_read.yview)
        self.lstbox_to_read.config(yscrollcommand=self.scrollbar.set)
        
        button_open_graph = tk.Button(
            self, text='📊', font = SUPER_LARGE, command = self.open_graph)
        button_open_graph.place(relx = 0.85, rely = 0.6)
        
        self.button_get = tk.Button(self, text = 'Get!', command = self.check_get_mode)
        self.button_get.bind('<Button-3>', self.change_button_get)
        self.button_get.place(relx = 0.9, rely = 0.45)
        CreateToolTip(self.button_get, 'Right click to switch modes')
        
        self.entry_filename = tk.Entry(self)
        self.entry_filename.insert(0, filename_setget)
        self.entry_filename.place(relx = 0.65, rely = 0.7, width = 600)
        self.entry_filename.config(state=tk.DISABLED)
        
        idx = len(filename_setget) - filename_setget[::-1].index('-') - 1
        self.ind_setget = int(filename_setget[idx + 1:-4])
        
        self.thread_n = 0
        
    def pause(self):
        global pause_flag
        
        pause_flag = not pause_flag
        
    def go_home(self, controller):
        global setget_flag
        
        setget_flag = False
        
        controller.show_frame(StartPage)
            
    def change_button_get(self, event):
        global setget_flag
        global pause_flag
        global ind_setget
        global filename_setget
        
        if self.button_get['text'] == 'Get!' and not setget_flag and not pause_flag:
            answer = messagebox.askyesnocancel('Mode change', 'Are you sure you want to change the measurement mode to "Append"?\n This would change the current datafile.')
            if answer:
                self.button_get['text'] = 'Append line!'
                self.entry_filename.config(state='normal')
                self.ind_setget += 1
                ind_setget.append(self.ind_setget)
                filename_setget = os.path.join(cur_dir, 'data_files', f'setget_{YEAR}{MONTH}{DAY}-{self.ind_setget}.csv')
                self.entry_filename.delete(0, tk.END)
                self.entry_filename.insert(0, filename_setget)
        elif self.button_get['text'] == 'Append line!':
            answer = messagebox.askyesnocancel('Mode change', 'Are you sure you want to change the measurement mode to "Get"?\n This would change the current datafile.')
            if answer:
                self.button_get['text'] = 'Get!'
                self.ind_setget += 1
                ind_setget.append(self.ind_setget)
                filename_setget = os.path.join(cur_dir, 'data_files', f'setget_{YEAR}{MONTH}{DAY}-{self.ind_setget}.csv')
                self.entry_filename.delete(0, tk.END)
                self.entry_filename.insert(0, filename_setget)
                self.entry_filename.config(state=tk.DISABLED)
        
    def update_sweep_parameters1(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        i = 1
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        if class_of_sweeper_device != 'Not a class':
            try:
                self.__dict__[f'sweep_options{i}']['value'] = getattr(
                    device_to_sweep, 'set_options')
                self.__dict__[f'sweep_options{i}'].current(getattr(self, f'sweep_options{i}_current'))
                self.__dict__[f'sweep_options{i}'].after(interval)
            except:
                self.__dict__[f'sweep_options{i}'].current(0)
                self.__dict__[f'sweep_options{i}'].after(interval)
                
        else:
            self.__dict__[f'sweep_options{i}']['value'] = ['']
            self.__dict__[f'sweep_options{i}'].current(0)
            self.__dict__[f'sweep_options{i}'].after(interval)
            
        if self.__dict__[f'combo_to_sweep{i}'].current() != getattr(self, f'combo_to_sweep{i}_current'):
            self.preset.loc[0, f'combo_to_sweep{i}'] = self.__dict__[f'combo_to_sweep{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def update_sweep_options1(self, event):
        i = 1
        if self.__dict__[f'sweep_options{i}'].current() != getattr(self, f'sweep_options{i}_current'):
            self.preset.loc[0, f'sweep_options{i}'] = self.__dict__[f'sweep_options{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def set_device1(self):
        global types_of_devices
        global list_of_devices
        
        i = 1
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        parameters = device_to_sweep.set_options
        parameter_to_sweep = parameters[self.__dict__[f'sweep_options{i}'].current()]
        value = float(self.__dict__[f'entry_set{i}'].get())
        
        self.preset.loc[0, f'set{i}'] = value
        self.preset.to_csv(globals()['setget_path'], index = False)
        
        if class_of_sweeper_device != 'Not a class':
            try:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = 'SetGet')
            except TypeError:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
            
    def update_sweep_parameters2(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        i = 2
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        if class_of_sweeper_device != 'Not a class':
            try:
                self.__dict__[f'sweep_options{i}']['value'] = getattr(
                    device_to_sweep, 'set_options')
                self.__dict__[f'sweep_options{i}'].current(getattr(self, f'sweep_options{i}_current'))
                self.__dict__[f'sweep_options{i}'].after(interval)
            except:
                self.__dict__[f'sweep_options{i}'].current(0)
                self.__dict__[f'sweep_options{i}'].after(interval)
                
        else:
            self.__dict__[f'sweep_options{i}']['value'] = ['']
            self.__dict__[f'sweep_options{i}'].current(0)
            self.__dict__[f'sweep_options{i}'].after(interval)
            
        if self.__dict__[f'combo_to_sweep{i}'].current() != getattr(self, f'combo_to_sweep{i}_current'):
            self.preset.loc[0, f'combo_to_sweep{i}'] = self.__dict__[f'combo_to_sweep{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def update_sweep_options2(self, event):
        i = 2
        if self.__dict__[f'sweep_options{i}'].current() != getattr(self, f'sweep_options{i}_current'):
            self.preset.loc[0, f'sweep_options{i}'] = self.__dict__[f'sweep_options{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def set_device2(self):
        global types_of_devices
        global list_of_devices
        
        i = 2
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        parameters = device_to_sweep.set_options
        parameter_to_sweep = parameters[self.__dict__[f'sweep_options{i}'].current()]
        value = float(self.__dict__[f'entry_set{i}'].get())
        
        self.preset.loc[0, f'set{i}'] = value
        self.preset.to_csv(globals()['setget_path'], index = False)
        
        if class_of_sweeper_device != 'Not a class':
            try:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = 'SetGet')
            except TypeError:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
            
    def update_sweep_parameters3(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        i = 3
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        if class_of_sweeper_device != 'Not a class':
            try:
                self.__dict__[f'sweep_options{i}']['value'] = getattr(
                    device_to_sweep, 'set_options')
                self.__dict__[f'sweep_options{i}'].current(getattr(self, f'sweep_options{i}_current'))
                self.__dict__[f'sweep_options{i}'].after(interval)
            except:
                self.__dict__[f'sweep_options{i}'].current(0)
                self.__dict__[f'sweep_options{i}'].after(interval)
                
        else:
            self.__dict__[f'sweep_options{i}']['value'] = ['']
            self.__dict__[f'sweep_options{i}'].current(0)
            self.__dict__[f'sweep_options{i}'].after(interval)
            
        if self.__dict__[f'combo_to_sweep{i}'].current() != getattr(self, f'combo_to_sweep{i}_current'):
            self.preset.loc[0, f'combo_to_sweep{i}'] = self.__dict__[f'combo_to_sweep{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def update_sweep_options3(self, event):
        i = 3
        if self.__dict__[f'sweep_options{i}'].current() != getattr(self, f'sweep_options{i}_current'):
            self.preset.loc[0, f'sweep_options{i}'] = self.__dict__[f'sweep_options{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def set_device3(self):
        global types_of_devices
        global list_of_devices
        
        i = 3
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        parameters = device_to_sweep.set_options
        parameter_to_sweep = parameters[self.__dict__[f'sweep_options{i}'].current()]
        value = float(self.__dict__[f'entry_set{i}'].get())
        
        self.preset.loc[0, f'set{i}'] = value
        self.preset.to_csv(globals()['setget_path'], index = False)
        
        if class_of_sweeper_device != 'Not a class':
            try:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = 'SetGet')
            except TypeError:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
            
    def update_sweep_parameters4(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        i = 4
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        if class_of_sweeper_device != 'Not a class':
            try:
                self.__dict__[f'sweep_options{i}']['value'] = getattr(
                    device_to_sweep, 'set_options')
                self.__dict__[f'sweep_options{i}'].current(getattr(self, f'sweep_options{i}_current'))
                self.__dict__[f'sweep_options{i}'].after(interval)
            except:
                self.__dict__[f'sweep_options{i}'].current(0)
                self.__dict__[f'sweep_options{i}'].after(interval)
                
        else:
            self.__dict__[f'sweep_options{i}']['value'] = ['']
            self.__dict__[f'sweep_options{i}'].current(0)
            self.__dict__[f'sweep_options{i}'].after(interval)
            
        if self.__dict__[f'combo_to_sweep{i}'].current() != getattr(self, f'combo_to_sweep{i}_current'):
            self.preset.loc[0, f'combo_to_sweep{i}'] = self.__dict__[f'combo_to_sweep{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def update_sweep_options4(self, event):
        i = 4
        if self.__dict__[f'sweep_options{i}'].current() != getattr(self, f'sweep_options{i}_current'):
            self.preset.loc[0, f'sweep_options{i}'] = self.__dict__[f'sweep_options{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def set_device4(self):
        global types_of_devices
        global list_of_devices
        
        i = 4
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        parameters = device_to_sweep.set_options
        parameter_to_sweep = parameters[self.__dict__[f'sweep_options{i}'].current()]
        value = float(self.__dict__[f'entry_set{i}'].get())
        
        self.preset.loc[0, f'set{i}'] = value
        self.preset.to_csv(globals()['setget_path'], index = False)
        
        if class_of_sweeper_device != 'Not a class':
            try:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = 'SetGet')
            except TypeError:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
            
    def update_sweep_parameters5(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        i = 5
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        if class_of_sweeper_device != 'Not a class':
            try:
                self.__dict__[f'sweep_options{i}']['value'] = getattr(
                    device_to_sweep, 'set_options')
                self.__dict__[f'sweep_options{i}'].current(getattr(self, f'sweep_options{i}_current'))
                self.__dict__[f'sweep_options{i}'].after(interval)
            except:
                self.__dict__[f'sweep_options{i}'].current(0)
                self.__dict__[f'sweep_options{i}'].after(interval)
                
        else:
            self.__dict__[f'sweep_options{i}']['value'] = ['']
            self.__dict__[f'sweep_options{i}'].current(0)
            self.__dict__[f'sweep_options{i}'].after(interval)
            
        if self.__dict__[f'combo_to_sweep{i}'].current() != getattr(self, f'combo_to_sweep{i}_current'):
            self.preset.loc[0, f'combo_to_sweep{i}'] = self.__dict__[f'combo_to_sweep{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def update_sweep_options5(self, event):
        i = 5
        if self.__dict__[f'sweep_options{i}'].current() != getattr(self, f'sweep_options{i}_current'):
            self.preset.loc[0, f'sweep_options{i}'] = self.__dict__[f'sweep_options{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def set_device5(self):
        global types_of_devices
        global list_of_devices
        
        i = 5
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        parameters = device_to_sweep.set_options
        parameter_to_sweep = parameters[self.__dict__[f'sweep_options{i}'].current()]
        value = float(self.__dict__[f'entry_set{i}'].get())
        
        self.preset.loc[0, f'set{i}'] = value
        self.preset.to_csv(globals()['setget_path'], index = False)
        
        if class_of_sweeper_device != 'Not a class':
            try:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = 'SetGet')
            except TypeError:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
            
    def update_sweep_parameters6(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        i = 6
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        if class_of_sweeper_device != 'Not a class':
            try:
                self.__dict__[f'sweep_options{i}']['value'] = getattr(
                    device_to_sweep, 'set_options')
                self.__dict__[f'sweep_options{i}'].current(getattr(self, f'sweep_options{i}_current'))
                self.__dict__[f'sweep_options{i}'].after(interval)
            except:
                self.__dict__[f'sweep_options{i}'].current(0)
                self.__dict__[f'sweep_options{i}'].after(interval)
                
        else:
            self.__dict__[f'sweep_options{i}']['value'] = ['']
            self.__dict__[f'sweep_options{i}'].current(0)
            self.__dict__[f'sweep_options{i}'].after(interval)
            
        if self.__dict__[f'combo_to_sweep{i}'].current() != getattr(self, f'combo_to_sweep{i}_current'):
            self.preset.loc[0, f'combo_to_sweep{i}'] = self.__dict__[f'combo_to_sweep{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def update_sweep_options6(self, event):
        i = 6
        if self.__dict__[f'sweep_options{i}'].current() != getattr(self, f'sweep_options{i}_current'):
            self.preset.loc[0, f'sweep_options{i}'] = self.__dict__[f'sweep_options{i}'].current()
            self.preset.to_csv(globals()['setget_path'], index = False)
            
    def set_device6(self):
        global types_of_devices
        global list_of_devices
        
        i = 6
        #which type of device did I chose
        ind = self.__dict__[f'combo_to_sweep{i}'].current()
        class_of_sweeper_device = types_of_devices[ind]
        device_to_sweep = list_of_devices[ind]
        parameters = device_to_sweep.set_options
        parameter_to_sweep = parameters[self.__dict__[f'sweep_options{i}'].current()]
        value = float(self.__dict__[f'entry_set{i}'].get())
        
        self.preset.loc[0, f'set{i}'] = value
        self.preset.to_csv(globals()['setget_path'], index = False)
        
        if class_of_sweeper_device != 'Not a class':
            try:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = 'SetGet')
            except TypeError:
                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
            
    def set_all(self):
        for i in range(1, self.num_widgets):
            try:
                self.__dict__[f'set_device{i}']()
            except Exception as e:
                print(e)
            
    def add_block(self, i):
        
        try:
            self.__dict__[f'button_destroy{i - 1}'].destroy()
        except KeyError:
            pass
        self.__dict__[f'button_add{i - 1}'].destroy()
        
        self.__dict__[f'label_devices{i}'] = tk.Label(self, text = 'Devices:', font=LARGE_FONT)
        self.__dict__[f'label_devices{i}'].place(relx = 0.05 + (i - int(i / 5) * 4 - 1) * 7/30, rely = 0.21 + int(i / 5) * 0.35)

        self.__dict__[f'combo_to_sweep{i}'] = ttk.Combobox(self, value=list_of_devices_addresses)
        self.__dict__[f'combo_to_sweep{i}'].bind(
            "<<ComboboxSelected>>", getattr(self, f'update_sweep_parameters{i}'))
        self.__dict__[f'combo_to_sweep{i}'].place(relx=0.15 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.21 + int(i / 5) * 0.35)
        
        self.__dict__[f'label_options{i}'] = tk.Label(self, text = 'Options:', font = LARGE_FONT)
        self.__dict__[f'label_options{i}'].place(relx = 0.05 + (i - int(i / 5) * 4 - 1) * 7/30, rely = 0.25 + int(i / 5) * 0.35)
        
        self.__dict__[f'sweep_options{i}'] = ttk.Combobox(self)
        self.__dict__[f'sweep_options{i}'].bind(
            "<<ComboboxSelected>>", getattr(self, f'update_sweep_options{i}'))
        self.__dict__[f'sweep_options{i}'].place(relx=0.15 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.25 + int(i / 5) * 0.35)
        
        try:
            self.__dict__[f'combo_to_sweep{i}'].current(getattr(self, f'combo_to_sweep{i}_current'))
            getattr(self, f'update_sweep_parameters{i}')(event = None)
        except:
            self.__dict__[f'combo_to_sweep{i}'].current(0)
            if self.__dict__[f'combo_to_sweep{i}']['values'][0] != '':
                getattr(self, f'update_sweep_parameters{i}')(event = None)
        
        self.__dict__[f'label_set{i}'] = tk.Label(self, text = 'Set', font = LARGE_FONT)
        self.__dict__[f'label_set{i}'].place(relx=0.05 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.29 + int(i / 5) * 0.35)
        
        self.__dict__[f'entry_set{i}'] = tk.Entry(self, width = 16)
        self.__dict__[f'entry_set{i}'].insert(0, getattr(self, f'set{i}_current'))
        self.__dict__[f'entry_set{i}'].place(relx=0.15 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.29 + int(i / 5) * 0.35)
        
        self.__dict__[f'button_set{i}'] = tk.Button(self, text = 'Set', command = getattr(self, f'set_device{i}'))
        self.__dict__[f'button_set{i}'].place(relx=0.235 + (i - int(i / 5) * 4 - 1) * 7/30, rely=0.285 + int(i / 5) * 0.35)

        if i >= 2:
            self.__dict__[f'button_destroy{i}'] = tk.Button(self, text = r'🗙', command = lambda: self.destroy_block(i))
            self.__dict__[f'button_destroy{i}'].place(relx = 0.28 + (i - int(i / 5) * 4 - 1) * 7/30, rely = 0.17 + int(i / 5) * 0.35)
        
        if i <= 5:
            self.__dict__[f'button_add{i}'] = tk.Button(self, text = 'Add', font = LARGE_FONT, command = lambda: self.add_block(i + 1))
            self.__dict__[f'button_add{i}'].place(relx=0.15 + (i - int((i + 1) / 5) * 4) * 7/30, rely=0.25 + int((i+1) / 5) * 0.35)
            
        self.num_widgets += 1
        
        self.preset.loc[0, 'num_widgets'] = self.num_widgets
        self.preset.to_csv(globals()['setget_path'], index = False)
        
    def destroy_block(self, i):
        
        if i != 1:
        
            self.__dict__[f'button_destroy{i}'].destroy()
            try:
                self.__dict__[f'button_add{i}'].destroy()
            except KeyError:
                pass
            self.__dict__[f'label_devices{i}'].destroy()
            self.__dict__[f'combo_to_sweep{i}'].destroy()
            self.__dict__[f'label_options{i}'].destroy()
            self.__dict__[f'sweep_options{i}'].destroy()
            self.__dict__[f'label_set{i}'].destroy()
            self.__dict__[f'entry_set{i}'].destroy()
            self.__dict__[f'button_set{i}'].destroy()
            
            i -= 1
            
            if i > 1:
                self.__dict__[f'button_destroy{i}'] = tk.Button(self, text = r'🗙', command = lambda: self.destroy_block(i))
                self.__dict__[f'button_destroy{i}'].place(relx = 0.28 + (i - int(i / 5) * 4 - 1) * 7/30, rely = 0.17 + int(i / 5) * 0.35)
            
            if i <= 6:
                self.__dict__[f'button_add{i}'] = tk.Button(self, text = 'Add', font = LARGE_FONT, command = lambda: self.add_block(i + 1))
                self.__dict__[f'button_add{i}'].place(relx=0.15 + (i - int((i + 1) / 5) * 4) * 7/30, rely=0.25 + int((i+1) / 5) * 0.35)
                
            self.num_widgets -= 1
            
            self.preset.loc[0, 'num_widgets'] = self.num_widgets
            self.preset.to_csv(globals()['setget_path'], index = False)
          
    def open_graph(self):
        
        global cur_animation_num
        global x_current
        global y_current
        
        def return_range(x, n):
            if x % n == 0:
                return [x + p for p in range(n)]
            elif x % n == n - 1:
                return [x - p for p in range(n)][::-1]
            else:
                return return_range(x + 1, n)
        
        globals()[f'graph_object{globals()["cur_animation_num"]}'] = Graph(globals()['filename_setget'])
        for i in return_range(cur_animation_num, 3):
            preset = pd.read_csv(globals()['graph_preset_path'], sep = ',')
            preset = preset.fillna('')
            x_current = int(preset[f'x{i + 1}_current'].values[0])
            y_current = int(preset[f'y{i + 1}_current'].values[0])
            globals()[f'x{i + 1}'] = []
            if x_current < len(columns):
                globals()[f'x{i + 1}_status'] = x_current
            else:
                globals()[f'x{i + 1}_status'] = 0
            globals()[f'y{i + 1}'] = []
            if y_current < len(columns):
                globals()[f'y{i + 1}_status'] = y_current
            else:
                globals()[f'y{i + 1}_status'] = 0
            globals()[f'ani{i+1}'] = StartAnimation
            globals()[f'ani{i+1}'].start(globals()['filename_setget'])

          
    def heading_chosed(self, event):
        global parameters_to_read 
        
        try:
            self.current_heading = parameters_to_read[int(self.table_dataframe.identify_column(event.x)[1:]) - 2]
        except IndexError:
            self.current_heading = 'Time'
        
        
        globals()[f'self.tw{self.num_tw}'] = tw = tk.Toplevel(self)
        
        tw.geometry("800x400")
        tw.title("Graph")
        
        self.__dict__[f'fig_setget{self.num_tw}'] = Figure((2.4, 1.4), dpi=300)
        self.__dict__[f'ax_setget{self.num_tw}'] = globals()[f'fig_setget{self.num_tw}'].add_subplot(111)
        self.__dict__[f'fig_setget{self.num_tw}'].subplots_adjust(left = 0.25, bottom = 0.3)
        self.__dict__[f'ax_setget{self.num_tw}'].set_xlabel('t, s')
        self.__dict__[f'ax_setget{self.num_tw}'].set_title(self.current_heading)
        
        self.__dict__[f'plot_setget{self.num_tw}'] = FigureCanvasTkAgg(globals()[f'fig_setget{self.num_tw}'], tw)
        self.__dict__[f'plot_setget{self.num_tw}'].draw()
        self.__dict__[f'plot_setget{self.num_tw}'].get_tk_widget().place(relx=0, rely=0)
        
        self.__dict__[f'ani_setget{self.num_tw}'] = animation.FuncAnimation(
            fig = self.__dict__[f'fig_setget{self.num_tw}'], func = lambda x: self.animate(x, self.current_heading), 
            interval=100, blit = False)
        
        self.dict_num_heading[self.current_heading] = self.num_tw
        self.num_tw += 1
          
    def check_get_mode(self):
        if self.button_get['text'] == 'Get!':
            self.get_read_parameters()
        elif self.button_get['text'] == 'Append line!':
            self.append_read_parameters()
        
    def get_read_parameters(self):
        global setget_flag
        global filename_setget
        global ind_setget
        global columns
        global deli
        
        filename_setget = self.entry_filename.get()

        def get_key(val, my_dict):
            for key, value in my_dict.items():
                if val == value:
                    return key
        
        self.list_to_read = []
        # asking multichoise to get parameters to read
        selection = self.lstbox_to_read.curselection()
        for i in selection:
            entrada = self.lstbox_to_read.get(i)
            self.list_to_read.append(get_key(entrada, self.dict_lstbox))
        globals()['parameters_to_read'] = self.list_to_read
        
        columns = ['Time']
        for parameter in self.list_to_read:
            columns.append(parameter)
        setget_data = pd.DataFrame(columns=columns)
        setget_data.to_csv(filename_setget, index=False, sep = deli)
        
        setget_flag = True
        
        if self.thread_n == 0:
            self.__dict__[f'thread{self.thread_n}'] = Sweeper_write()
        else:
            setget_flag = False
            time.sleep(0.25)
            del self.__dict__[f'thread{self.thread_n - 1}']
            setget_flag = True
            self.__dict__[f'thread{self.thread_n}'] = Sweeper_write()
        self.thread_n += 1
        
        if not hasattr(self, 'table_dataframe'):
            self.table_dataframe = ttk.Treeview(self, columns = columns, show = 'headings', height = 1)
            self.table_dataframe.place(relx = 0.28, rely = 0.76, relwidth = 0.65)
            
            self.initial_value = []
            
            for ind, heading in enumerate(columns):
                self.table_dataframe.heading(ind, text = heading)
                self.table_dataframe.column(ind, anchor=tk.CENTER, stretch=tk.YES, width=120)
                self.initial_value.append(heading)
                    
            self.table_dataframe.insert('', tk.END, 'Current dataframe', text = 'Current dataframe', values = self.initial_value)
            
            self.update_item('Current dataframe')
            
            self.scrollbar_table = tk.Scrollbar(self, orient = 'horizontal')
            self.scrollbar_table.place(relx = 0.28, rely = 0.82, relwidth = 0.65)
            
            self.scrollbar_table.config(command=self.table_dataframe.xview)
            self.table_dataframe.config(xscrollcommand=self.scrollbar_table.set)
            
            self.num_tw = 1
        
        else:
            self.table_dataframe.destroy()
            self.scrollbar_table.destroy()
            setget_flag = False
            time.sleep(0.11)
            setget_flag = True
            self.table_dataframe = ttk.Treeview(self, columns = columns, show = 'headings', height = 1)
            self.table_dataframe.place(relx = 0.28, rely = 0.76, relwidth = 0.65)
            
            self.initial_value = []
            
            for ind, heading in enumerate(columns):
                self.table_dataframe.heading(ind, text = heading)
                self.table_dataframe.column(ind,anchor=tk.CENTER, stretch=tk.YES, width=120)
                self.initial_value.append(heading)
                    
            self.table_dataframe.insert('', tk.END, 'Current dataframe', text = 'Current dataframe', values = self.initial_value)
            
            self.update_item('Current dataframe')
            
            self.scrollbar_table = tk.Scrollbar(self, orient = 'horizontal')
            self.scrollbar_table.place(relx = 0.28, rely = 0.82, relwidth = 0.65)
            
            self.scrollbar_table.config(command=self.table_dataframe.xview)
            self.table_dataframe.config(xscrollcommand=self.scrollbar_table.set)
            
    def append_read_parameters(self):
        
        global setget_flag
        global filename_setget
        global ind_setget
        global columns
        global deli
        
        filename_setget = self.entry_filename.get()
        
        def get_key(val, my_dict):
            for key, value in my_dict.items():
                if val == value:
                    return key
        
        self.list_to_read = []
        # asking multichoise to get parameters to read
        selection = self.lstbox_to_read.curselection()
        for i in selection:
            entrada = self.lstbox_to_read.get(i)
            self.list_to_read.append(get_key(entrada, self.dict_lstbox))
        globals()['parameters_to_read'] = self.list_to_read
        
        if not exists(filename_setget):
            columns = ['Time']
            for parameter in self.list_to_read:
                columns.append(parameter)
            setget_data = pd.DataFrame(columns=columns)
            setget_data.to_csv(filename_setget, index=False, sep = deli)
        else:
            existing_columns = list(pd.read_csv(filename_setget).columns)
            columns = ['Time']
            for parameter in self.list_to_read:
                columns.append(parameter)
            if existing_columns != columns:
                answer = messagebox.askyesnocancel('Coulmns matching conflict', f'The file you trying to append contains the following columns\n {list(existing_columns)}\n The current selection is\n {columns}\n Append to a separate file?')
                if answer:
                    self.ind_setget += 1
                    ind_setget.append(self.ind_setget)
                    self.ind_setget = np.max(ind_setget)
                    filename_setget = os.path.join(cur_dir, 'data_files', f'setget_{YEAR}{MONTH}{DAY}-{self.ind_setget}.csv')
                    self.entry_filename.delete(0, tk.END)
                    self.entry_filename.insert(0, filename_setget)
                    setget_data = pd.DataFrame(columns=columns)
                    setget_data.to_csv(filename_setget, index=False, sep = deli)
                    
        dataframe = []
        dataframe.append(round(time.perf_counter() - zero_time, 2))
        
        for parameter in globals()['parameters_to_read']:
            index_dot = len(parameter) - parameter[::-1].find('.') - 1
            adress = parameter[:index_dot]
            option = parameter[index_dot + 1:]
            try:
                parameter_value = getattr(list_of_devices[list_of_devices_addresses.index(adress)],
                                          option)()
                dataframe.append(parameter_value)
            except Exception as e:
                print(f'Exception happened in setget_write: {e}')
                dataframe.append(None)
                return
        time.sleep(0.2)
            
        with open(filename_setget, 'a', newline='') as f_object:
            try:
                writer_object = writer(f_object, delimiter = deli)
                writer_object.writerow(dataframe)
                f_object.close()
            except KeyboardInterrupt:
                f_object.close()
            except Exception as e:
                print(f'Exception happened in setget_write append: {e}')
            finally:
                f_object.close()
        
        if not hasattr(self, 'table_dataframe'):
            self.table_dataframe = ttk.Treeview(self, columns = columns, show = 'headings', height = 1)
            self.table_dataframe.place(relx = 0.28, rely = 0.76, relwidth = 0.65)
            
            self.initial_value = []
            
            for ind, heading in enumerate(columns):
                self.table_dataframe.heading(ind, text = heading)
                self.table_dataframe.column(ind, anchor=tk.CENTER, stretch=tk.YES, width=120)
                self.initial_value.append(heading)
                    
            self.table_dataframe.insert('', tk.END, 'Current dataframe', text = 'Current dataframe', values = self.initial_value)
            
            self.update_item('Current dataframe')
            
            self.scrollbar_table = tk.Scrollbar(self, orient = 'horizontal')
            self.scrollbar_table.place(relx = 0.28, rely = 0.82, relwidth = 0.65)
            
            self.scrollbar_table.config(command=self.table_dataframe.xview)
            self.table_dataframe.config(xscrollcommand=self.scrollbar_table.set)
            
            self.num_tw = 1
        
        else:
            self.table_dataframe.destroy()
            self.scrollbar_table.destroy()
            setget_flag = False
            time.sleep(0.11)
            setget_flag = True
            self.table_dataframe = ttk.Treeview(self, columns = columns, show = 'headings', height = 1)
            self.table_dataframe.place(relx = 0.28, rely = 0.76, relwidth = 0.65)
            
            self.initial_value = []
            
            for ind, heading in enumerate(columns):
                self.table_dataframe.heading(ind, text = heading)
                self.table_dataframe.column(ind,anchor=tk.CENTER, stretch=tk.YES, width=120)
                self.initial_value.append(heading)
                    
            self.table_dataframe.insert('', tk.END, 'Current dataframe', text = 'Current dataframe', values = self.initial_value)
            
            self.update_item('Current dataframe')
            
            self.scrollbar_table = tk.Scrollbar(self, orient = 'horizontal')
            self.scrollbar_table.place(relx = 0.28, rely = 0.82, relwidth = 0.65)
            
            self.scrollbar_table.config(command=self.table_dataframe.xview)
            self.table_dataframe.config(xscrollcommand=self.scrollbar_table.set)
        
    def update_item(self, item):
        
        global filename_setget
        global deli
        
        try:
            dataframe = pd.read_csv(filename_setget, sep = deli, engine = 'python').tail(1).values.flatten()
            self.table_dataframe.item(item, values=tuple(dataframe))
            self.table_dataframe.after(250, self.update_item, item)
        except FileNotFoundError:
            self.table_dataframe.after(250, self.update_item, item)
            

class Sweeper1d(tk.Frame):

    def __init__(self, parent, controller):       

        tk.Frame.__init__(self, parent)
        
        self.preset = pd.read_csv(globals()['sweeper1d_path'], sep = ',', dtype = str)
        self.preset = self.preset.fillna('')
        self.combo_to_sweep1_current = int(self.preset['combo_to_sweep1'].values[0])
        self.sweep_options1_current = int(self.preset['sweep_options1'].values[0])
        self.from1_init = self.preset['from1'].values[0]
        self.to1_init = self.preset['to1'].values[0]
        self.ratio1_init = self.preset['ratio1'].values[0]
        self.back_ratio1_init = self.preset['back_ratio1'].values[0]
        self.count_option1 = self.preset['count_option1'][0]
        self.delay_factor1_init = self.preset['delay_factor1'].values[0]
        self.back_delay_factor1_init = self.preset['back_delay_factor1'].values[0]
        self.status_back_and_forth_master = tk.IntVar(value = int(self.preset['status_back_and_forth1'].values[0]))
        self.status_manual = tk.IntVar(value = int(self.preset['status_manual1'].values[0]))
        self.manual_filenames = [self.preset['manual_filename1'].values[0]]
        self.filename_sweep = self.preset['filename_sweep'][0]
        self.condition = str(self.preset['condition'].values[0])

        self.filename_index = get_filename_index(filename = self.filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')

        #updates filename with respect to date and current index
        try:
            path = os.path.normpath(self.filename_sweep)
            path = path.split(os.sep)
            name = path[-1]
            if '.csv' in name or '.txt' in name: #if name has the extension, remove it
                name = name[:len(name) - name[::-1].index('.') - 1]
            if int(name[:2]) in np.linspace(0, 99, 100, dtype = int) \
                and int(name[2:4]) in np.linspace(1, 12, 12, dtype = int) \
                    and int(name[4:6]) in np.linspace(1, 32, 32, dtype = int): #If filename is in yy.mm.dd format, make it current day
                self.filename_sweep = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}-{self.filename_index}.csv')
                self.filename_sweep = fix_unicode(self.filename_sweep)
                if ':' in self.filename_sweep and ':\\' not in self.filename_sweep:
                    i = self.filename_sweep.index(':')
                    self.filename_sweep = self.filename_sweep[:i+1] + '\\' + self.filename_sweep[i+1:]
        except:
            path = os.path.normpath(self.filename_sweep)
            path = path.split(os.sep)
            name = path[-1]
            if '.csv' in name or '.txt' in name: #if name has the extension, remove it
                name = name[:len(name) - name[::-1].index('.') - 1] 
            self.filename_sweep = os.path.join(*path[:-1], f'{name}-{self.filename_index}.csv')
            self.filename_sweep = fix_unicode(self.filename_sweep)
            if ':' in self.filename_sweep and ':\\' not in self.filename_sweep:
                i = self.filename_sweep.index(':')
                self.filename_sweep = self.filename_sweep[:i+1] + '\\' + self.filename_sweep[i+1:]
        
        globals()['setget_flag'] = False
        #globals()['parameters_to_read'] = globals()['parameters_to_read_copy']

        label = tk.Label(self, text='1dSweeper', font=LARGE_FONT)
        label.pack(pady=10, padx=10)

        button_home = tk.Button(self, text='Back to Home',
                                 command=lambda: controller.show_frame(StartPage))
        button_home.pack()

        label_to_sweep = tk.Label(self, text='To sweep:', font=LARGE_FONT)
        label_to_sweep.place(relx=0.15, rely=0.12)

        label_to_read = tk.Label(self, text='To read:', font=LARGE_FONT)
        label_to_read.place(relx=0.3, rely=0.12)

        label_devices = tk.Label(self, text = 'Devices:', font = LARGE_FONT)
        label_devices.place(relx = 0.05, rely = 0.16)

        self.combo_to_sweep1 = ttk.Combobox(
            self, value=list_of_devices_addresses)
        self.combo_to_sweep1.bind(
            "<<ComboboxSelected>>", self.update_sweep_parameters)
        self.combo_to_sweep1.place(relx=0.15, rely=0.16)
        
        global back_and_forth_master
        
        back_and_forth_master = 1
        
        self.back_and_forth_master_count = 2
        
        self.save_back_and_forth_master_status()
    
        class BackAndForthMaster(object):
            
            def __init__(self, widget, parent):
                self.master_toplevel = None
                self.master_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.master_widget.bbox('all')
                x = x + self.master_widget.winfo_rootx()
                y = y + self.master_widget.winfo_rooty()
                self.master_toplevel = tw = tk.Toplevel(self.master_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                label_back_and_forth_slave = tk.Label(tw, text = 'Set number of back and forth\n walks for slave axis', font = LARGE_FONT)
                label_back_and_forth_slave.grid(row = 0, column = 0, pady = 2)
                
                self.combo_back_and_forth_master = ttk.Combobox(tw, value = [2, 'custom', 'continious'])
                if self.parent.status_back_and_forth_master.get() == 0:
                    self.combo_back_and_forth_master.current(0)
                else:
                    self.combo_back_and_forth_master.current(1)
                    self.combo_back_and_forth_master.delete(0, tk.END)
                    self.combo_back_and_forth_master.insert(0, self.parent.back_and_forth_master_count)
                self.combo_back_and_forth_master.grid(row = 1, column = 0, pady = 2)
                
                def update_back_and_forth_master_count():
                    if self.combo_back_and_forth_master.current() == 0:
                        self.parent.back_and_forth_master_count = 2
                    elif self.combo_back_and_forth_master.current() == -1:
                        self.parent.back_and_forth_master_count = int(self.combo_back_and_forth_master.get())
                    elif self.combo_back_and_forth_master.current() == 2:
                        self.parent.back_and_forth_master_count = int(1e5)
                    else:
                        raise Exception(f'Insert proper back_and_forth_master. Should be int, but given {type(self.combo_back_and_forth_master.get())}')
                    
                    self.parent.entry_ratio.delete(0, tk.END)
                    self.parent.entry_ratio.insert(0, self.entry_ratio1.get())
                    self.parent.back_ratio1_init = self.entry_back_ratio1.get()
                    
                    self.parent.entry_delay_factor.delete(0, tk.END)
                    self.parent.entry_delay_factor.insert(0, self.entry_delay_factor1.get())
                    self.parent.back_delay_factor1_init = self.entry_back_delay_factor1.get()
                
                button_set_back_and_forth_master = tk.Button(tw, text = 'Set', command = update_back_and_forth_master_count)
                button_set_back_and_forth_master.grid(row = 1, column = 1, pady = 2)
                
                def hide_toplevel():
                    tw = self.master_toplevel
                    self.master_toplevel = None
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
            def update_ratio1(self):
                tw = self.master_toplevel
                
                count_option1 = self.parent.count_option1
                
                self.entry_ratio_label = tk.Label(tw, text = f'Forward {count_option1}')
                self.entry_ratio_label.grid(row = 2, column = 0, pady = 2)
                
                self.entry_back_ratio_label = tk.Label(tw, text = f'Back {count_option1}')
                self.entry_back_ratio_label.grid(row = 2, column = 1, pady = 2)
                
                self.entry_ratio1 = tk.Entry(tw)
                self.entry_ratio1.insert(0, self.parent.entry_ratio.get())
                self.entry_ratio1.grid(row = 3, column = 0, pady = 2)
                
                self.entry_back_ratio1 = tk.Entry(tw)
                self.entry_back_ratio1.insert(0, self.parent.back_ratio1_init)
                self.entry_back_ratio1.grid(row = 3, column = 1, pady = 2)
                
                self.entry_delay_factor_label = tk.Label(tw, text = 'Forward delay factor')
                self.entry_delay_factor_label.grid(row = 4, column = 0, pady = 2)
                
                self.entry_back_delay_factor_label = tk.Label(tw, text = 'Back delay factor')
                self.entry_back_delay_factor_label.grid(row = 4, column = 1, pady = 2)
                
                self.entry_delay_factor1 = tk.Entry(tw)
                self.entry_delay_factor1.insert(0, self.parent.entry_delay_factor.get())
                self.entry_delay_factor1.grid(row = 5, column = 0, pady = 2)
                
                self.entry_back_delay_factor1 = tk.Entry(tw)
                self.entry_back_delay_factor1.insert(0, self.parent.back_delay_factor1_init)
                self.entry_back_delay_factor1.grid(row = 5, column = 1, pady = 2)
            
        def CreateMasterToplevel(widget, parent):
            
            toplevel = BackAndForthMaster(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                toplevel.update_ratio1()
                
            widget.bind('<Button-3>', show)    
    
        self.checkbox_back_and_forth_master = ttk.Checkbutton(self,
                                           variable=self.status_back_and_forth_master, onvalue=1,
                                           offvalue=0, command=lambda: self.save_back_and_forth_master_status())
        self.checkbox_back_and_forth_master.place(relx=0.23, rely=0.56)
        CreateMasterToplevel(self.checkbox_back_and_forth_master, self)
        
        self.label_back_and_forth_master = tk.Label(self, text = '🔁', font = SUPER_LARGE)
        self.label_back_and_forth_master.place(relx = 0.2435, rely = 0.55)
        CreateToolTip(self.label_back_and_forth_master, 'Back and forth sweep for this axis \nRight click to configure')
        CreateMasterToplevel(self.label_back_and_forth_master, self)

        def stepper_mode():
            global stepper_flag
            
            if stepper_flag == True:
                stepper_flag = False
            elif stepper_flag == False:
                stepper_flag = True

        self.checkbox_stepper = tk.Checkbutton(self, text = r'🦶', font = LARGE_FONT, command = stepper_mode)
        if stepper_flag == True:
            self.checkbox_stepper.select()
        self.checkbox_stepper.place(relx = 0.275, rely = 0.555)
        CreateToolTip(self.checkbox_stepper, 'Stepper mode')

        self.devices = tk.StringVar()
        self.devices.set(value=parameters_to_read)
        self.lstbox_to_read = tk.Listbox(self, listvariable = self.devices,
                                         selectmode='multiple', exportselection=False,
                                         width=50, height=len(parameters_to_read) * 1)
        
        self.dict_lstbox = {}
        
        for parameter in parameters_to_read:
            self.dict_lstbox[parameter] = parameter
            
        self.lstbox_height = len(parameters_to_read) / 47
        
        self.button_update_sweep = tk.Button(self, text = 'Update sweep', command = lambda: self.update_sweep_configuration())
        self.button_update_sweep.place(relx = 0.3, rely = 0.21 + self.lstbox_height)

        self.button_pause = tk.Button(self, text = '⏸️', font = LARGE_FONT, command = lambda: self.pause())
        self.button_pause.place(relx = 0.3, rely = 0.25 + self.lstbox_height)
        CreateToolTip(self.button_pause, 'Pause\continue sweep')
        
        self.button_stop = tk.Button(self, text = '⏹️', font = LARGE_FONT, command = lambda: self.stop())
        self.button_stop.place(relx = 0.3375, rely = 0.25 + self.lstbox_height)
        CreateToolTip(self.button_stop, 'Stop sweep')
        
        self.button_start_sweeping = tk.Button(
            self, text="▶", command=lambda: self.start_sweeping(), font = LARGE_FONT)
        self.button_start_sweeping.place(relx=0.375, rely=0.21 + self.lstbox_height, height= 90, width=30)
        CreateToolTip(self.button_start_sweeping, 'Start sweeping')
        
        self.button_tozero = tk.Button(self, text = 'To zero', width = 11, command = lambda: self.tozero())
        self.button_tozero.place(relx = 0.3, rely = 0.3 + self.lstbox_height)
        
        if len(parameters_to_read) < 10:
            self.lstbox_to_read.place(relx=0.3, rely=0.16)
        else:
            self.lstbox_height = 18 / 47
            self.lstbox_to_read.place(relx=0.3, rely=0.16, height = 300)
            self.button_pause.place(relx = 0.3, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.3375, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.375, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.3, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.3, rely = 0.21 + self.lstbox_height)
            
        self.lstbox_to_read.bind('<Button-3>', self.update_listbox)
        
        scrollbar= ttk.Scrollbar(self, orient = 'vertical')
        scrollbar.place(relx = 0.5, rely = 0.16, height = 75)
        
        self.lstbox_to_read.config(yscrollcommand= scrollbar.set)
        scrollbar.config(command= self.lstbox_to_read.yview)

        label_options = tk.Label(self, text = 'Options:', font = LARGE_FONT)
        label_options.place(relx = 0.05, rely = 0.2)
        

        self.sweep_options1 = ttk.Combobox(self)
        self.sweep_options1.bind(
            "<<ComboboxSelected>>", self.update_sweep_options)
        self.sweep_options1.place(relx=0.15, rely=0.2)
        
        try:
            self.combo_to_sweep1.current(self.combo_to_sweep1_current)
            self.update_sweep_parameters(event = None)
        except:
            self.combo_to_sweep1.current(0)
            if self.combo_to_sweep1['values'][0] != '':
                self.update_sweep_parameters(event = None)

        class ChangeName(object):
            
            def __init__(self, widget, parent):
                self.name_toplevel = None
                self.name_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x = y = 0
                x = x + self.name_widget.winfo_rootx()
                y = y + self.name_widget.winfo_rooty()
                self.name_toplevel = tw = tk.Toplevel(self.name_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_names = tk.Label(tw, text = 'Change names:', font = LARGE_FONT)
                label_names.grid(row = 0, column = 0, pady = 2)
                    
                def update_combo_set_parameters(event, interval = 100):
                    global types_of_devices
                    global list_of_devices
                    ind = self.combo_devices.current()
                    class_of_sweeper_device = types_of_devices[ind]
                    device = list_of_devices[ind]
                    
                    if self.combo_devices.current() != -1:
                        self.selected_device = ind
                    if class_of_sweeper_device != 'Not a class':
                        self.combo_set_parameters['values'] = getattr(device, 'set_options')
                        self.combo_set_parameters.after(interval)
                    else:
                        self.combo_set_parameters['values'] = ['']
                        self.combo_set_parameters.current(0)
                        self.combo_set_parameters.after(interval)

                def update_names_devices():
                    new_device_name = self.combo_devices.get()
                    new_device_values = list(self.combo_devices['values'])
                    new_device_values[self.selected_device] = new_device_name
                    self.combo_devices['values'] = new_device_values
                    self.combo_devices.after(1)
                    
                    try:
                        self.parent.combo_to_sweep1['values'] = new_device_values
                        self.parent.combo_to_sweep1.current(self.selected_device)
                    except:
                        pass
                    
                    self.parent.after(1)
                    
                def update_names_set_parameters():
                    new_set_parameter_name = self.combo_set_parameters.get()
                    new_set_parameters_values = list(self.combo_set_parameters['values'])
                    new_set_parameters_values[self.selected_set_option] = new_set_parameter_name
                    self.combo_set_parameters['values'] = new_set_parameters_values
                    try:
                        self.parent.sweep_options1['values'] = new_set_parameters_values
                        self.parent.sweep_options1.current(self.selected_set_options)
                    except:
                        pass
                    self.parent.after(1)
                    
                def update_names_get_parameters(interval = 1000):
                    new_get_parameter_name = self.get_current.get()
                    new_get_parameters_values = list(self.combo_get_parameters['values'])
                    new_get_parameters_values[self.selected_get_option] = new_get_parameter_name
                    
                    self.parent.dict_lstbox[self.combo_get_parameters['values'][self.selected_get_option]] = new_get_parameter_name
                    
                    self.combo_get_parameters['values'] = new_get_parameters_values
                    
                    self.parent.devices.set(value=new_get_parameters_values)
                    self.parent.lstbox_to_read.after(interval)
                    
                def select_set_option(event):
                    if self.combo_set_parameters.current() != -1:
                        self.selected_set_option = self.combo_set_parameters.current()
                        
                def select_get_option(event):
                    if self.combo_get_parameters.current() != -1:
                        self.selected_get_option = self.combo_get_parameters.current()
                
                self.combo_devices = ttk.Combobox(tw, value = self.parent.combo_to_sweep1['values'])
                self.combo_devices.current(0)
                self.combo_devices.bind(
                    "<<ComboboxSelected>>", update_combo_set_parameters)
                self.combo_devices.grid(row = 1, column = 0, pady = 2)
                
                self.combo_set_parameters = ttk.Combobox(tw, value = [''])
                device_class = types_of_devices[0]
                if device_class != 'Not a class':
                    try:
                        self.combo_set_parameters['values'] = self.parent.sweep_options1['values']
                    except: 
                        self.combo_set_parameters['values'] = getattr(list_of_devices[0], 'set_options')
                    self.combo_set_parameters.current(0)
                    self.combo_set_parameters.bind(
                        "<<ComboboxSelected>>", select_set_option)
                else:
                    self.combo_set_parameters['values'] = ['']
                    self.combo_set_parameters.current(0)
                self.combo_set_parameters.grid(row = 2, column = 0, pady = 2)
                
                parameters = parameters_to_read
                
                if len(parameters) == 0:
                    parameters = ['']
                
                self.get_current = tk.StringVar()
                self.combo_get_parameters = ttk.Combobox(tw, value = parameters, textvariable = self.get_current)
                self.combo_get_parameters.current(0)
                
                
                self.combo_get_parameters.bind(
                    "<<ComboboxSelected>>", select_get_option)
                self.combo_get_parameters.grid(row = 3, column = 0, pady = 2)
                
                button_change_name_device = tk.Button(tw, text = 'Change device name', command = update_names_devices)
                button_change_name_device.grid(row = 1, column = 1, pady = 2)
                
                self.selected_device = 0
                self.selected_set_option = 0
                self.selected_get_option = 0
                
                button_change_name_set_parameters = tk.Button(tw, text = 'Change set name', command = update_names_set_parameters)
                button_change_name_set_parameters.grid(row = 2, column = 1, pady = 2)
                
                button_change_name_get_parameters = tk.Button(tw, text = 'Change get name', command = update_names_get_parameters)
                button_change_name_get_parameters.grid(row = 3, column = 1, pady = 2)
                
                def hide_toplevel():
                    tw = self.name_toplevel
                    self.name_toplevel = None
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
        def CreateNameToplevel(widget, parent):
            
            toplevel = ChangeName(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show) 
            
        CreateNameToplevel(self.sweep_options1, self)
        CreateNameToplevel(self.combo_to_sweep1, self)

        label_from = tk.Label(self, text='From', font=LARGE_FONT)
        label_from.place(relx=0.12, rely=0.24)

        label_to = tk.Label(self, text='To', font=LARGE_FONT)
        label_to.place(relx=0.12, rely=0.28)

        if self.count_option1 == 'ratio':
            self.label_ratio = tk.Label(self, text='Ratio, \n Δ/s', font=LARGE_FONT)
            CreateToolTip(self.label_ratio, 'Speed of 1d-sweep')
        elif self.count_option1 == 'step':
            self.label_ratio = tk.Label(self, text='Step, Δ', font=LARGE_FONT)
            CreateToolTip(self.label_ratio, 'Step of 1d-sweep')
        self.label_ratio.place(relx=0.12, rely=0.32)

        self.entry_from = tk.Entry(self)
        self.entry_from.insert(0, self.from1_init)
        self.entry_from.place(relx=0.17, rely=0.24)
        self.entry_from.after(1000, self.rewrite_preset)


        self.entry_to = tk.Entry(self)
        self.entry_to.insert(0, self.to1_init)
        self.entry_to.place(relx=0.17, rely=0.28)

        self.entry_ratio = tk.Entry(self)
        self.entry_ratio.insert(0, self.ratio1_init)
        self.entry_ratio.place(relx=0.17, rely=0.32)
        
        button_swap = tk.Button(self, text = r'🆚', font = ('Verdana', 8), command = self.swap_ratio_step1)
        button_swap.place(relx = 0.1, rely = 0.32)
        CreateToolTip(button_swap, 'Change Ratio/Step')

        label_delay_factor = tk.Label(
            self, text='Delay factor, s', justify=tk.LEFT, font=LARGE_FONT)
        label_delay_factor.place(relx=0.12, rely=0.4)
        CreateToolTip(label_delay_factor, 'Sleep time per 1 point')

        self.entry_delay_factor = tk.Entry(self)
        self.entry_delay_factor.insert(0, self.delay_factor1_init)
        self.entry_delay_factor.place(relx=0.12, rely=0.46)
            
        # initials
        self.manual_sweep_flags = [0]

        self.checkbox_manual1 = ttk.Checkbutton(self, text='Maunal sweep select',
                                          variable=self.status_manual, onvalue=1,
                                          offvalue=0, command=lambda: self.save_manual_status())
        self.checkbox_manual1.place(relx=0.12, rely=0.52)

        if self.status_manual.get() == 0:
                self.entry_from.config(state= "normal")
                self.entry_to.config(state= "normal")
                self.entry_ratio.config(state= "normal")
        else:
                self.entry_from.config(state= "disabled")
                self.entry_to.config(state= "disabled")
                self.entry_ratio.config(state= "disabled")

        button_new_manual = tk.Button(self, text = '🖊', font = LARGE_FONT, command=lambda: self.open_blank())
        button_new_manual.place(relx=0.12, rely=0.56)
        CreateToolTip(button_new_manual, 'Create new sweep instruction')

        button_explore_manual = tk.Button(
            self, text = '🔎', font = LARGE_FONT, command=lambda: self.explore_files())
        button_explore_manual.place(relx=0.15, rely=0.56)
        CreateToolTip(button_explore_manual, 'Explore existing sweep instruction')

        self.text_condition = tk.Text(self, width = 40, height = 7)
        self.text_condition.delete('1.0', tk.END)
        self.text_condition.insert(tk.END, self.condition)
        self.text_condition.place(relx = 0.1, rely = 0.7)
        CreateToolTip(self.text_condition, 'Master sweep: x\nSet condition for a sweep map \nRight click to configure script')

        self.filename_textvariable = tk.StringVar(self, value = self.filename_sweep)
        width = int(len(self.filename_textvariable.get()) * 0.95)
        self.entry_filename = tk.Entry(self, textvariable = self.filename_textvariable, font = LARGE_FONT, 
                                       width = width)
        self.entry_filename.place(relx = 0.97 - width / 100, rely = 0.9)

        self.script = ''
        
        class Script(object):
            
            def __init__(self, widget, parent):
                self.script_toplevel = None
                self.script_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x = y = 0
                self.script_toplevel = tw = tk.Toplevel(self.script_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_script = tk.Label(tw, text = 'Manual script', font = LARGE_FONT)
                label_script.grid(row = 0, column = 0, pady = 2)
                
                def ctrlEvent(event):
                    if event.state == 4 and event.keysym == 'c':
                        content = self.text_script.selection_get()
                        tw.clipboard_clear()
                        tw.clipboard_append(content)
                        return "break"
                    elif event.state == 4 and event.keysym == 'v':
                        self.text_script.insert('end', tw.selection_get(selection='CLIPBOARD'))
                        return "break"
                    elif event.state == 4 and event.keysym == 'a':
                        self.text_script.tag_add("sel", "1.0","end")
                        return "break"
                    elif event.state == 4 and event.keysym == 'z':
                        self.text_script.delete('sel.first','sel.last')
                        return "break"
                    
                self.text_script = tk.Text(tw, width = 60, height = 10)
                self.text_script.grid(row = 1, column = 0, pady = 2, rowspan = 3)
                self.text_script.configure(font = LARGE_FONT)
                self.text_script.bind("<Key>", ctrlEvent)
                
                def hide_toplevel():
                    tw = self.script_toplevel
                    self.script_toplevel = None
        
                    tw.destroy()
                
                def explore_script(interval = 1):
                    
                    if exists(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')):
                        init = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')
                    else:
                        init = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')
                    
                    script_filename = tk.filedialog.askopenfilename(initialdir=init,
                                                                             title='Select a script')
                    with open(script_filename, 'r') as file:
                        try:
                            script = file.read()
                        except Exception as e:
                            print(f'Exception happened while exploring existing script: {e}')
                            file.close()
                        finally:
                            file.close()
                            
                    self.text_script.delete(1.0, tk.END)
                    self.text_script.insert(tk.END, script)
                    self.text_script.after(interval)
                    self.script_toplevel.deiconify() #show toplevel again
                    
                def set_script():
                    self.parent.script = self.text_script.get(1.0, tk.END)[:-1]
                    hide_toplevel()
                    
                def save_script():
                    
                    if not exists(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')):
                        os.mkdir(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts'))
                    
                    self.script_filename = tk.filedialog.asksaveasfilename(title='Save the file',
                                            initialfile=os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}',
                                            'scripts', f'script{datetime.today().strftime("%H_%M_%d_%m_%Y")}'),
                                            defaultextension='.csv')
                    
                    self.parent.script = self.text_script.get(1.0, tk.END)[:-1]
                    
                    with open(self.script_filename, 'w') as file:
                        try:
                            file.write(self.parent.script)
                        except Exception as e:
                            print(f'Exception happened while saving the script: {e}')
                            file.close()
                        finally:
                            file.close()
                    
                    self.script_toplevel.deiconify() #show toplevel again
                
                button_explore_script = tk.Button(
                    tw, text='🔎', font = SUPER_LARGE, command = explore_script)
                button_explore_script.grid(row = 1, column = 1, pady = 2)
                CreateToolTip(button_explore_script, 'Explore existing script')
                
                button_save_script = tk.Button(
                    tw, text='💾', font = SUPER_LARGE, command = save_script)
                button_save_script.grid(row = 2, column = 1, pady = 2)
                CreateToolTip(button_save_script, 'Save this script')
                
                self.script_filename = ''
                
                button_set_script = tk.Button(
                    tw, text = 'Apply script', font = LARGE_FONT, command = set_script)
                button_set_script.grid(row = 3, column = 1, pady = 2)
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
            
        def CreateScriptToplevel(widget, parent):
            
            toplevel = Script(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show) 
            
        CreateScriptToplevel(self.text_condition, self)

        button_filename = tk.Button(
            self, text = 'Browse...', command=lambda: self.set_filename_sweep())
        button_filename.place(relx=0.85, rely=0.9)

        graph_button = tk.Button(
            self, text='📊', font = SUPER_LARGE, command=lambda: self.open_graph())
        graph_button.place(relx=0.7, rely=0.76)
        CreateToolTip(graph_button, 'Graph')
        
        class ImageLabel(tk.Label):
            """
            A Label that displays images, and plays them if they are gifs
            :im: A PIL Image instance or a string filename
            """
            def load(self, im):
                if isinstance(im, str):
                    im = Image.open(im)
                frames = []
         
                try:
                    for i in count(1):
                        frames.append(ImageTk.PhotoImage(im.copy()))
                        im.seek(i)
                except EOFError:
                    pass
                self.frames = cycle(frames)
         
                try:
                    self.delay = im.info['duration']
                except:
                    self.delay = 100
         
                if len(frames) == 1:
                    self.config(image=next(self.frames))
                else:
                    self.next_frame()
         
            def unload(self):
                self.config(image=None)
                self.frames = None
         
            def next_frame(self):
                if self.frames:
                    self.config(image=next(self.frames))
                    self.after(self.delay, self.next_frame)
                  
        self.cur_walk1 = 1  
                  
        def animate():
            
            def get_time_remaining():
                global zero_time
                global from_sweep1
                global to_sweep1
                global sweeper_write
                
                def ConvertSectoDay(n):

                    n = int(n)
                    day = n // (24 * 3600)
                    n = n % (24 * 3600)
                    hour = n // 3600
                    n %= 3600
                    minutes = n // 60
                    n %= 60
                    seconds = n
                    if day == 0:
                        if hour == 0:
                            if minutes == 0:
                                s = f'{seconds} s'
                            else:
                                s = f'{minutes} m\n{seconds} s'
                        else:
                            s = f'{hour} h\n{minutes} m\n{seconds} s'
                    else:
                        s = f'{day} d\n{hour} h\n{minutes} m\n{seconds} s'
                
                    return s
                
                t = time.perf_counter() - zero_time
                delta = abs(from_sweep1 - to_sweep1)
                
                if sweeper_write.sweepable1:
                    x = float(sweeper_write.current_value)
                else:
                    x = float(sweeper_write.value1)
                    
                try:    
                    if self.status_back_and_forth_master.get() == 0:
                        tau = t * abs(to_sweep1 - x) / abs(x - from_sweep1)
                    else:
                        tau = t * ((self.back_and_forth_master_count - self.cur_walk1) * delta + abs(to_sweep1 - x)) / ((self.cur_walk1 - 1)*delta + abs(x - from_sweep1))
                    return ConvertSectoDay(tau)
                except ZeroDivisionError:
                    return '...'
            
            if self.start_sweep_flag:
                if not hasattr(self, 'gif_label'):
                    self.gif_label = ImageLabel(self)
                    self.gif_label.place(relx = 0.75, rely = 0.5)
                    if 'loading.gif' in os.listdir(os.path.join(core_dir, 'config')):
                        self.gif_label.load(os.path.join(core_dir, 'config', 'loading.gif'))
                if not hasattr(self, 'time_label'):
                    self.time_label = tk.Label(self, text = 'Time left: ...', font = LARGE_FONT)
                    self.time_label.place(relx = 0.8, rely = 0.5)
                else:
                    self.time_label.config(text = f'Time left: {get_time_remaining()}')
            else:
                if hasattr(self, 'gif_label'):
                    self.gif_label.place_forget()
                    del self.gif_label
                if hasattr(self, 'time_label'):
                    self.time_label.place_forget()
                    del self.time_label
            self.after(1000, animate)
            
        self.start_sweep_flag = False
        animate()

    def update_sweep_parameters(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        
        ind = self.combo_to_sweep1.current()
        class_of_sweeper_device1 = types_of_devices[ind]
        device1 = list_of_devices[ind]
        if class_of_sweeper_device1 != 'Not a class':
            self.sweep_options1['value'] = getattr(
                device1, 'set_options')
            try:
                self.sweep_options1.current(self.sweep_options1_current)
            except tk.TclError:
                self.sweep_options1.current(0)
            self.sweep_options1.after(interval)
        else:
            self.sweep_options1['value'] = ['']
            self.sweep_options1.current(0)
            self.sweep_options1.after(interval)
            
        if self.combo_to_sweep1.current() != self.combo_to_sweep1_current:
            self.preset.loc[0, 'combo_to_sweep1'] = self.combo_to_sweep1.current()
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
            
        self.back_ratio1_init = ''
        self.back_delay_factor1_init = ''
            
    def swap_ratio_step1(self):
        if self.count_option1 == 'step':
            self.count_option1 = 'ratio'
        elif self.count_option1 == 'ratio':
            self.count_option1 = 'step'
            
        if self.count_option1 == 'step' and self.label_ratio['text'].startswith('Ratio'):
            self.label_ratio.configure(text = 'Step, Δ')
            self.update()
        
        if self.count_option1 == 'ratio' and self.label_ratio['text'].startswith('Step'):
            self.label_ratio.configure(text = 'Ratio, \n Δ/s')
            self.update()

        self.preset.loc[0, 'count_option1'] = self.count_option1
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        
            
    def update_sweep_options(self, event):
        if self.sweep_options1.current() != self.sweep_options1_current:
            self.preset.loc[0, 'sweep_options1'] = self.sweep_options1.current()
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
            
    def rewrite_preset(self):
        
        time.sleep(0.05)
        
        if self.entry_from.get() != self.from1_init:
            self.preset.loc[0, 'from1'] = self.entry_from.get()
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        if self.entry_to.get() != self.to1_init:
            self.preset.loc[0, 'to1'] = self.entry_to.get()
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        if self.entry_ratio.get() != self.ratio1_init:
            self.preset.loc[0, 'ratio1'] = self.entry_ratio.get()
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        self.preset.loc[0, 'back_ratio1'] = self.back_ratio1_init
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        if self.entry_delay_factor.get() != self.delay_factor1_init:
            self.preset.loc[0, 'delay_factor1'] = self.entry_delay_factor.get()
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        self.preset.loc[0, 'back_delay_factor1'] = self.back_delay_factor1_init
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)
            
        current_filename = self.entry_filename.get()
        path_current = os.path.normpath(current_filename).split(os.path.sep)
        name = path_current[-1]
        path_current = path_current[:-1]
        current_filename = basename(name)
        current_filename = os.path.join(*path_current, current_filename)
        current_filename = fix_unicode(current_filename)
        
        memory_filename = self.filename_sweep
        path_memory = os.path.normpath(memory_filename).split(os.path.sep)
        memory_filename = path_memory[-1]
        path_memory = path_memory[:-1]
        memory_filename = basename(memory_filename)
        memory_filename = os.path.join(*path_memory, memory_filename)
        memory_filename = fix_unicode(memory_filename) 
            
        if current_filename != basename(self.filename_sweep):
            self.preset.loc[0, 'filename_sweep'] = current_filename
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        
        #self.entry_from.after(1000, self.rewrite_preset)

    def update_sweep_configuration(self):
        global from_sweep1
        global to_sweep1
        global ratio_sweep1
        global delay_factor1
        
        if self.start_sweep_flag:
            
            try:
                from_sweep1 = float(self.entry_from.get())
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from.get()} to float')
                return
                
            try:
                to_sweep1 = float(self.entry_to.get())
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to.get()} to float')
                return
            
            try:
                ratio_sweep1 = float(self.entry_ratio.get())
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio.get()} to float')
                return

            try:
                delay_factor1 = float(self.entry_delay_factor.get())
            except:
                messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delaty_factor.get()} to float')
                return
                    
            delta = to_sweep1 - from_sweep1
            step1 = globals()['sweeper_write'].step1
            
            if np.sign(delta * step1) < 0:
                to_sweep1 = float(self.entry_from.get())
                from_sweep1 = float(self.entry_to.get())
                ratio_sweep1 = - ratio_sweep1
            
            if self.count_option1 == 'step':
                step1 = ratio_sweep1
                ratio_sweep1 = ratio_sweep1 / delay_factor1
                if globals()['sweeper_write'].sweepable1 != True:
                    globals()['sweeper_write'].step1 = step1
                else:
                    globals()['sweeper_write'].step1 = np.sign(step1) * delta
            else:
                ratio_sweep1 = ratio_sweep1 
                step1 = ratio_sweep1 * delay_factor1
                if globals()['sweeper_write'].sweepable1 != True:
                    globals()['sweeper_write'].step1 = step1
                else:
                    globals()['sweeper_write'].step1 = np.sign(step1) * delta
            
            self.from_sweep1 = from_sweep1
            self.to_sweep1 = to_sweep1
            self.ratio_sweep1 = ratio_sweep1
            self.delay_fector1 = delay_factor1
            
        self.rewrite_preset()
        
    def update_listbox(self, interval = 10000):
        global parameters_to_read
        self.devices = tk.StringVar()
        self.devices.set(value=parameters_to_read)
        self.lstbox_to_read.configure(listvariable = self.devices,
                                         height=len(parameters_to_read) * 1)
        
        if len(parameters_to_read) < 10:
            self.lstbox_height = len(parameters_to_read) / 47
            self.lstbox_to_read.place(relx=0.3, rely=0.16)
            self.button_pause.place(relx = 0.3, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.3375, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.375, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.3, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.3, rely = 0.21 + self.lstbox_height)
        else:
            self.lstbox_height = 18 / 47
            self.lstbox_to_read.place(relx=0.3, rely=0.16, height = 300)
            self.button_pause.place(relx = 0.3, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.3375, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.375, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.3, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.3, rely = 0.21 + self.lstbox_height)
    
    def save_manual_status(self):
        global filename_sweep
        if self.manual_sweep_flags[0] != self.status_manual.get():
            self.manual_sweep_flags[0] = self.status_manual.get()

        if self.status_manual.get() == 0:
            self.manual_filenames = ['']
            if hasattr(self, 'entry_from'):
                self.entry_from.config(state= "normal")
                self.entry_to.config(state= "normal")
                self.entry_ratio.config(state= "normal")
        else:
            if hasattr(self, 'entry_from'):
                self.entry_from.config(state= "disabled")
                self.entry_to.config(state= "disabled")
                self.entry_ratio.config(state= "disabled")
            
        #update preset
        self.preset.loc[0, 'manual_filename1'] = str(self.manual_filenames[0])
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)
            
        self.preset.loc[0, 'status_manual1'] = self.status_manual.get()
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)

    def save_back_and_forth_master_status(self):
        global back_and_forth_master
        
        if self.status_back_and_forth_master.get() == 0:
            back_and_forth_master = 1
        else:
            back_and_forth_master = self.back_and_forth_master_count
            
        self.preset.loc[0, 'status_back_and_forth1'] = self.status_back_and_forth_master.get()
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)

    def open_blank(self):
        filename = str(self.entry_filename.get())
        tomake = os.path.normpath(filename).split(os.path.sep)
        name = tomake[-1]
        tomake = tomake[:-1]
        tomake = os.path.join(*tomake)
        tomake = fix_unicode(tomake)
        if not exists(tomake):
            os.makedirs(tomake)
        filename = os.path.join(tomake, filename)
        filename = fix_unicode(filename)
        idx = get_filename_index(filename, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        name = name[:len(name) - name[::-1].index('-') - 1]
        filename =  os.path.join(tomake, f'{name}_manual{i+1}d{idx}.csv')
        filename = fix_unicode(filename)
        df = pd.DataFrame(columns=['steps'])
        df.to_csv(filename, index=False)
        self.manual_filenames[0] = filename
        os.startfile(filename)
        self.status_manual.set(1)
        #update preset
        self.preset.loc[0, 'status_manual1'] = 1
        self.preset.loc[0, 'manual_filename1'] = str(self.manual_filenames[0])
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)

    def explore_files(self):
        self.manual_filenames[0] = tk.filedialog.askopenfilename(initialdir=cur_dir + '',
                                                                 title='Select a manual sweeper',
                                                                 filetypes=(('CSV files', '*.csv*'),
                                                                            ('all files', '*.*')))
        self.status_manual.set(1)
        self.preset.loc[0, 'status_manual1'] = 1
        self.preset.loc[0, 'manual_filename1'] = str(self.manual_filenames[0])
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)

    def set_filename_sweep(self):
        global filename_sweep

        path = os.path.normpath(self.filename_sweep).split(os.path.sep)
        
        if 'data_files' not in path:
            to_make = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}', 'data_files')
            to_make = fix_unicode(to_make)
            if not exists(to_make):
                os.makedirs(to_make)
        else:
            to_make = os.path.join(*path[:-1])

        filename_sweep = tk.filedialog.asksaveasfilename(title='Save the file',
                                                         initialfile=to_make,
                                                         defaultextension='.csv')
        
        self.entry_filename.delete(0, tk.END)
        self.entry_filename.insert(0, filename_sweep)
        self.entry_filename.after(1)
        
        width = int(len(self.filename_textvariable.get()) * 0.95)
        self.entry_filename.config(width = width)
        
        current_filename = self.entry_filename.get()
        path_current = os.path.normpath(current_filename).split(os.path.sep)
        name = path_current[-1]
        path_current = path_current[:-1]
        current_filename = basename(name)
        current_filename = os.path.join(*path_current, current_filename)
        current_filename = fix_unicode(current_filename)
        
        memory_filename = self.filename_sweep
        path_memory = os.path.normpath(memory_filename).split(os.path.sep)
        memory_filename = path_memory[-1]
        path_memory = path_memory[:-1]
        memory_filename = basename(memory_filename)
        memory_filename = os.path.join(*path_memory, memory_filename)
        memory_filename = fix_unicode(memory_filename) 
        
        if current_filename != memory_filename:
            self.preset.loc[0, 'filename_sweep'] = current_filename
            self.preset.to_csv(globals()['sweeper1d_path'], index = False)
            
    def open_graph(self):
        
        global cur_animation_num
        global columns
        
        def return_range(x, n):
            if x % n == 0:
                return [x + p for p in range(n)]
            elif x % n == n - 1:
                return [x - p for p in range(n)][::-1]
            else:
                return return_range(x + 1, n)
        
        globals()[f'graph_object{globals()["cur_animation_num"]}'] = Graph(globals()['filename_sweep'])
        for i in return_range(cur_animation_num, 3):
            preset = pd.read_csv(globals()['graph_preset_path'], sep = ',')
            preset = preset.fillna('')
            x_current = int(preset[f'x{i + 1}_current'].values[0])
            y_current = int(preset[f'y{i + 1}_current'].values[0])
            globals()[f'x{i + 1}'] = []
            if x_current < len(columns):
                globals()[f'x{i + 1}_status'] = x_current
            else:
                globals()[f'x{i + 1}_status'] = 0
            globals()[f'y{i + 1}'] = []
            if y_current < len(columns):
                globals()[f'y{i + 1}_status'] = y_current
            else:
                globals()[f'y{i + 1}_status'] = 0
            globals()[f'ani{i+1}'] = StartAnimation
            globals()[f'ani{i+1}'].start(globals()['filename_sweep'])
        
    def pause(self):
        global pause_flag
        
        def update_button_text():
            if self.button_pause['text'] == '⏸️':
                self.button_pause.configure(text = '▶️')
            elif self.button_pause['text'] == '▶️':
                self.button_pause.configure(text = '⏸️')
        
        pause_flag = not(pause_flag)
        
        self.button_pause.after(100, update_button_text())
                
        tk.Frame(self).update_idletasks()
        tk.Frame(self).update()
        
        
    def stop(self):
        
        global stop_flag
        
        stop_flag = True
        
    def tozero(self):
        
        global tozero_flag
        
        answer = messagebox.askyesno('Abort', 'Are you sure you want to set all parameters to 0?')
        
        if answer:
            tozero_flag = True
       
    def determine_filename_sweep(self):
        global filename_sweep
        global cur_dir
        global core_dir
        
        if self.entry_filename.get() != '':
            filename_sweep = self.entry_filename.get()

        filename_sweep = fix_unicode(filename_sweep)

        self.filename_index = get_filename_index(filename = filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')

        core = os.path.normpath(filename_sweep)
        core = core.split(os.sep)
        name = core[-1]
        
        if 'data_files' in core and len(core) >= 3:
            cur_dir = os.path.join(*core[:core.index('data_files')])
            path = os.path.normpath(cur_dir).split(os.path.sep)
            date = path[-1]
            if date != f'{YEAR}{MONTH}{DAY}':
                cur_dir = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}')
                self.filename_index = 1
            cur_dir = fix_unicode(cur_dir)
            
            to_make = os.path.join(cur_dir, 'data_files')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
                
            filename_sweep = os.path.join(cur_dir, 'data_files', name)
            filename_sweep = fix_unicode(filename_sweep)
            
        elif ('data_files' in core and len(core) < 3) or ('data_files' not in core and len(core) < 2):
            name = core[-1]
            
            cur_dir = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')
            
            to_make = os.path.join(cur_dir, 'data_files')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
                
            filename_sweep = os.path.join(cur_dir, 'data_files', name)
            filename_sweep = fix_unicode(filename_sweep)
            
        elif 'data_files' not in core and len(core) >= 2:
            name = core[-1]
            
            cur_dir = os.path.join(*core[:-1], f'{YEAR}{MONTH}{DAY}')
            cur_dir = fix_unicode(cur_dir)
            
            to_make = os.path.join(cur_dir, 'data_files')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
                
            filename_sweep = os.path.join(*core[:-1], f'{YEAR}{MONTH}{DAY}', 'data_files', name)
            filename_sweep = fix_unicode(filename_sweep)
            
        self.entry_filename.delete(0, tk.END)
        self.entry_filename.insert(0, filename_sweep)
        self.entry_filename.after(1)
        
    def start_logs(self):
        global list_of_devices
        global list_of_device_addresses
        global types_of_devices
        global device_to_sweep1
        global parameters_to_read
        global cur_dir
        global filename_sweep
        
        all_addresses = [list_of_devices_addresses[self.combo_to_sweep1.current()]]
        
        for parameter in parameters_to_read:
            address = parameter[:len(parameter) - parameter[::-1].index('.') - 1]
            all_addresses.append(address)
            
        all_addresses = np.unique(all_addresses)
        
        self.filename_index = get_filename_index(filename = filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        
        core = os.path.normpath(filename_sweep)
        core = core.split(os.sep)
        _name = core[-1]
        
        try:
            folder_name = _name[:len(_name) - _name[::-1].index('.') - 1]
        except ValueError:
            folder_name = _name
        try:
            folder_name = folder_name[:len(folder_name) - folder_name[::-1].index('-') - 1]
        except ValueError:
            folder_name = _name
        folder_name = unify_filename(folder_name)
        
        for address in all_addresses:
            
            device = list_of_devices[list_of_devices_addresses.index(address)]
            if hasattr(device, 'loggable'):
                to_make = os.path.join(cur_dir, 'logs', f'{folder_name}_{self.filename_index}')
                to_make = fix_unicode(to_make)
                if not exists(to_make):
                    os.makedirs(to_make)
                name = types_of_devices[list_of_devices_addresses.index(address)]
                valid_address = "".join(x for x in address if x.isalnum())
                log_filename = os.path.join(to_make, f'logs_{name}_{valid_address}_{self.filename_index}.csv')
                log_filename = fix_unicode(log_filename)
                t = time.localtime()
                cur_time = time.strftime("%H:%M:%S", t)
                
                log = f'Name: {name}\nAddress: {address}\nTime: {cur_time}\n'
                
                for log_parameter in device.loggable:
                    log += f'{log_parameter}: {getattr(device, log_parameter)()}\n'
                
                log = log[:-1
                          ]
                with open(log_filename, 'w') as file:
                    try:    
                        file.write(log)
                    except Exception as e:
                        print(f'Exception happened while writing log for {name}, {address}: {e}')
                        file.close()
                    finally:
                        file.close()
        
    def pre_sweep(self):
        global sweeper_write
        global device_to_sweep1
        global parameter_to_sweep1
        device = device_to_sweep1
        parameter = parameter_to_sweep1
        try:
            sweepable = device.sweepable[device.set_options.index(parameter)]
        except:
            sweepable = False
            
        try:
            from_sweep = self.from_sweep1
            to_sweep = self.to_sweep1
            ratio_sweep = self.ratio_sweep1
        except AttributeError:
            if self.manual_sweep_flags[0] == 1:
                data = pd.read_csv(self.manual_filenames[0])
                steps = data['steps']
                from_sweep = steps.values[0]
                to_sweep = steps.values[-1]
                ratio_sweep = self.delay_factor1 * steps.values.shape[0]
            else:
                raise Exception('Couldn\'t configure \'from_sweep\', \'to_sweep\'')
        delta = abs(to_sweep - from_sweep)
        
        try:
            eps = float(device.eps[device.set_options.index(parameter)])
        except:
            eps = 0.0001 * delta
        
        try:
            cur_value = float(getattr(device, parameter)())
        except Exception as e:
            print(f'Exception happened in pre-sweep 1: {e}')
            self.start_logs()
            sweeper_write = Sweeper_write()
            self.open_graph()
            return

        if abs(cur_value - from_sweep) <= eps:
            self.start_logs()
            sweeper_write = Sweeper_write()
            self.open_graph()
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current master value is {cur_value}. \nStarting position is {from_sweep}, go to start?')
            if answer == True:
                
                def start_toplevel():
                    self.pop = tk.Toplevel(self)
                    
                    def center(toplevel):
                        toplevel.update_idletasks()
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop)
                    
                    self.label_approaching = tk.Label(self.pop, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching.grid(row = 0, column = 0)
                    
                    self.label_position = tk.Label(self.pop, text = '', font = LARGE_FONT)
                    self.label_position.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position - from_sweep)) > eps:
                        self.current_position = float(getattr(device, parameter)())
                        self.label_position.config(text = f'{"{:.3e}".format(self.current_position)} / {"{:.3e}".format(from_sweep)}')
                        self.label_position.after(100, update_position)
                    else:
                        self.pop.destroy()
                        self.start_logs()
                        sweeper_write = Sweeper_write()
                        self.open_graph()
                        
                def slow_approach(steps: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if len(steps) > 0:
                        getattr(device, f'set_{parameter}')(value = steps[0])
                        self.label_position.after(int(delay * 1000), lambda steps = steps[1:], delay = delay: slow_approach(steps, delay))

                
                if not sweepable:
                    answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                    if answer2 == False:
                        getattr(device, f'set_{parameter}')(value = from_sweep)
                        self.start_logs()
                        sweeper_write = Sweeper_write()
                        self.open_graph()
                    elif answer2 == True:
                        _delta = abs(cur_value - from_sweep)
                        step = ratio_sweep * self.delay_factor1
                        nsteps = abs(int(_delta // step) + 1)
                        steps = list(np.linspace(cur_value, from_sweep, nsteps + 1))
                        start_toplevel()
                        self.current_position = float(getattr(device, parameter)())
                        update_position()
                        slow_approach(steps, self.delay_factor1)
                                
                    else:
                        return
                        
                else:
                    getattr(device, f'set_{parameter}')(value = from_sweep, speed = ratio_sweep)
                    
                    start_toplevel()
                    self.current_position = float(getattr(device, parameter)())
                    update_position()
                        
            elif answer == False:
                self.start_logs()
                sweeper_write = Sweeper_write()
                self.open_graph()
            else:
                return

    def start_sweeping(self):

        global list_of_devices
        global types_of_devices
        global device_to_sweep1
        global parameter_to_sweep1
        global from_sweep1
        global to_sweep1
        global ratio_sweep1
        global back_ratio_sweep1
        global delay_factor1
        global back_delay_factor1
        global parameters_to_read
        global parameters_to_read_dict
        global sweeper_flag1
        global sweeper_flag2
        global sweeper_flag3
        global stop_flag
        global pause_flag
        global columns
        global script
        global manual_filenames
        global manual_sweep_flags
        global zero_time
        global sweeper_write

        self.start_sweep_flag = True
 
        if self.status_manual.get() == 0:
    
            try:
                self.from_sweep1 = float(self.entry_from.get())
                from_sweep1 = self.from_sweep1
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from.get()} to float')
                self.start_sweep_flag = False
                
            try:
                self.to_sweep1 = float(self.entry_to.get())
                to_sweep1 = self.to_sweep1
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to.get()} to float')
                self.start_sweep_flag = False
        
        try:
            self.delay_factor1 = float(self.entry_delay_factor.get())
            delay_factor1 = self.delay_factor1
        except:
            messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delaty_factor.get()} to float')
            self.start_sweep_flag = False
        
        if self.status_manual.get() == 0:
        
            try:
                self.ratio_sweep1 = float(self.entry_ratio.get())
                
                if self.back_ratio1_init == '':
                    back_ratio_sweep1 = self.ratio_sweep1
                else:
                    try:
                        back_ratio_sweep1 = float(self.back_ratio1_init)
                    except:
                        messagebox.showerror('Invalid value in "back_ratio1" entrybox', f'Can not convert {self.back_ratio1_init} to float')
                        back_ratio_sweep1 = self.ratio_sweep1
                        self.start_sweep_flag = False
                
                if self.count_option1 == 'step':
                    self.ratio_sweep1 = self.ratio_sweep1 / self.delay_factor1
                if self.from_sweep1 > self.to_sweep1 and self.ratio_sweep1 > 0:
                    self.ratio_sweep1 = - self.ratio_sweep1
                ratio_sweep1 = self.ratio_sweep1
                
                if self.back_delay_factor1_init == '':
                    back_delay_factor1 = delay_factor1
                else:
                    try:
                        back_delay_factor1 = float(self.back_delay_factor1_init)
                    except:
                        messagebox.showerror('Invalid value in "back_delay_factor1" entrybox', f'Can not convert {self.back_delay_factor1_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option1 == 'step':
                    back_ratio_sweep1 = back_ratio_sweep1 / back_delay_factor1
                if back_ratio_sweep1 * ratio_sweep1 > 0:
                    back_ratio_sweep1 = - back_ratio_sweep1
                
            except:
                messagebox.showerror('Invalid value in "ratio" entrybox', f'Can not convert {self.entry_ratio.get()} to float')
                self.start_sweep_flag = False
        
        def get_key(val, my_dict):
            for key, value in my_dict.items():
                if val == value:
                    return key
        
        self.list_to_read = []
        # asking multichoise to get parameters to read
        selection = self.lstbox_to_read.curselection()
        for i in selection:
            entrada = self.lstbox_to_read.get(i)
            self.list_to_read.append(get_key(entrada, self.dict_lstbox))
        parameters_to_read = self.list_to_read
        parameters_to_read_dict = self.dict_lstbox

        # creating columns
        device_to_sweep1 = list_of_devices[self.combo_to_sweep1.current()]
        parameters = device_to_sweep1.set_options
        parameter_to_sweep1 = parameters[self.sweep_options1.current()]
        columns_device = self.combo_to_sweep1['values'][self.combo_to_sweep1.current()]
        columns_parameters = self.sweep_options1['values'][self.sweep_options1.current()]
        columns = ['time', columns_device + '.' + columns_parameters + '_sweep']
        for option in parameters_to_read:
            columns.append(parameters_to_read_dict[option])
            
        self.determine_filename_sweep()

        sweeper_flag1 = True
        sweeper_flag2 = False
        sweeper_flag3 = False
        self.save_manual_status()
        self.save_back_and_forth_master_status()
        manual_filenames = self.manual_filenames
        manual_sweep_flags = self.manual_sweep_flags
        script = self.script
        
        self.rewrite_preset()

        if self.start_sweep_flag:
            zero_time = time.perf_counter()
            pause_flag = False
            stop_flag = False
            sweeper_flag1 = True
            sweeper_flag2 = False
            sweeper_flag3 = False
            self.pre_sweep()


class Sweeper2d(tk.Frame):

    def __init__(self, parent, controller):

        tk.Frame.__init__(self, parent)
        
        self.preset = pd.read_csv(globals()['sweeper2d_path'], sep = ',', dtype = str)
        self.preset = self.preset.fillna('')
        self.combo_to_sweep1_current = int(self.preset['combo_to_sweep1'].values[0])
        self.sweep_options1_current = int(self.preset['sweep_options1'].values[0])
        self.combo_to_sweep2_current = int(self.preset['combo_to_sweep2'].values[0])
        self.sweep_options2_current = int(self.preset['sweep_options2'].values[0])
        self.from1_init = self.preset['from1'].values[0]
        self.to1_init = self.preset['to1'].values[0]
        self.ratio1_init = self.preset['ratio1'].values[0]
        self.back_ratio1_init = self.preset['back_ratio1'].values[0]
        self.count_option1 = self.preset['count_option1'][0]
        self.delay_factor1_init = self.preset['delay_factor1'].values[0]
        self.back_delay_factor1_init = self.preset['back_delay_factor1'].values[0]
        self.from2_init = self.preset['from2'].values[0]
        self.to2_init = self.preset['to2'].values[0]
        self.ratio2_init = self.preset['ratio2'].values[0]
        self.back_ratio2_init = self.preset['back_ratio2'].values[0]
        self.count_option2 = self.preset['count_option2'][0]
        self.delay_factor2_init = self.preset['delay_factor2'].values[0]
        self.back_delay_factor2_init = self.preset['back_delay_factor2'].values[0]
        self.manual_filenames = [self.preset['manual_filename1'].values[0], self.preset['manual_filename2'].values[0]]
        self.status_back_and_forth_master = tk.IntVar(value = int(self.preset['status_back_and_forth1'].values[0]))
        self.status_manual1 = tk.IntVar(value = int(self.preset['status_manual1'].values[0]))
        self.status_back_and_forth_slave = tk.IntVar(value = int(self.preset['status_back_and_forth2'].values[0]))
        #self.status_fastmode_master = tk.IntVar(value = int(self.preset['status_fastmode2'].values[0]))
        self.status_snakemode_master = tk.IntVar(value = int(self.preset['status_snakemode2'].values[0]))
        self.status_manual2 = tk.IntVar(value = int(self.preset['status_manual2'].values[0]))
        self.condition = str(self.preset['condition'].values[0])
        self.filename_sweep = self.preset['filename_sweep'].values[0]
        self.filename_sweep = fix_unicode(self.filename_sweep)
        self.interpolated = int(self.preset['interpolated'].values[0])
        self.uniform = int(self.preset['interpolated'].values[0])
        
        self.filename_index = get_filename_index(filename = self.filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        
        #updates filename with respect to date and current index
        try:
            path = os.path.normpath(self.filename_sweep)
            path = path.split(os.sep)
            name = path[-1]
            if '.' in name: #if name has the extension, remove it
                name = name[:len(name) - name[::-1].index('.') - 1]
            if int(name[:2]) in np.linspace(0, 99, 100, dtype = int) \
                and int(name[2:4]) in np.linspace(1, 12, 12, dtype = int) \
                    and int(name[4:6]) in np.linspace(1, 32, 32, dtype = int): #If filename is in yy.mm.dd format, make it current day
                self.filename_sweep = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}-{self.filename_index}.csv')
                fix_unicode(self.filename_sweep)
        except:
            path = os.path.normpath(self.filename_sweep)
            path = path.split(os.sep)
            name = path[-1]
            if '.' in name: #if name has the extension, remove it
                name = name[:len(name) - name[::-1].index('.') - 1] 
            self.filename_sweep = os.path.join(*path[:-1], f'{name}-{self.filename_index}.csv')
            fix_unicode(filename_sweep)
    
        globals()['setget_flag'] = False
        #globals()['parameters_to_read'] = globals()['parameters_to_read_copy']

        label = tk.Label(self, text='2dSweeper', font=LARGE_FONT)
        label.pack(pady=10, padx=10)

        button_home = tk.Button(self, text='Back to Home',
                                 command=lambda: controller.show_frame(StartPage))
        button_home.pack()

        label_to_sweep1 = tk.Label(self, text='To sweep:', font=LARGE_FONT)
        label_to_sweep1.place(relx=0.15, rely=0.12)
    
        label_to_sweep2 = tk.Label(self, text='To sweep:', font=LARGE_FONT)
        label_to_sweep2.place(relx=0.3, rely=0.12)
    
        label_to_read = tk.Label(self, text='To read:', font=LARGE_FONT)
        label_to_read.place(relx=0.45, rely=0.12)
        
        label_master = tk.Label(self, text = 'Master', font = LARGE_FONT)
        label_master.place(relx = 0.15, rely = 0.17)
        
        label_slave = tk.Label(self, text = 'Slave', font = LARGE_FONT)
        label_slave.place(relx = 0.3, rely = 0.17)

        label_devices = tk.Label(self, text = 'Devices:', font=LARGE_FONT)
        label_devices.place(relx = 0.05, rely = 0.21)

        self.combo_to_sweep1 = ttk.Combobox(self, value=list_of_devices_addresses)
        self.combo_to_sweep1.bind(
            "<<ComboboxSelected>>", self.update_sweep_parameters1)
        self.combo_to_sweep1.place(relx=0.15, rely=0.21)
        
        self.sweep_options1 = ttk.Combobox(self)
        self.sweep_options1.bind(
            "<<ComboboxSelected>>", self.update_sweep_options1)
        self.sweep_options1.place(relx=0.15, rely=0.25)

        self.sweep_options2 = ttk.Combobox(self)
        self.sweep_options2.bind(
            "<<ComboboxSelected>>", self.update_sweep_options2)
        self.sweep_options2.place(relx=0.3, rely=0.25)
        
        try:
            self.combo_to_sweep1.current(self.combo_to_sweep1_current)
            self.update_sweep_parameters1(event = None)
        except:
            self.combo_to_sweep1.current(0)
            if self.combo_to_sweep1['values'][0] != '':
                self.update_sweep_parameters1(event = None)

        self.combo_to_sweep2 = ttk.Combobox(self, value=list_of_devices_addresses)
        self.combo_to_sweep2.bind(
            "<<ComboboxSelected>>", self.update_sweep_parameters2)
        self.combo_to_sweep2.place(relx=0.3, rely=0.21)
        
        try:
            self.combo_to_sweep2.current(self.combo_to_sweep2_current)
            self.update_sweep_parameters2(event = None)
        except:
            self.combo_to_sweep2.current(0)
            if self.combo_to_sweep2['values'][0] != '':
                self.update_sweep_parameters2(event = None)
        
        global back_and_forth_master
        global back_and_forth_slave
        
        back_and_forth_master = 1
        back_and_forth_slave = 1
        
        self.back_and_forth_master_count = 2
        self.back_and_forth_slave_count = 2
        
        self.save_back_and_forth_master_status()
        self.save_back_and_forth_slave_status()
    
        class BackAndForthMaster(object):
            
            def __init__(self, widget, parent):
                self.master_toplevel = None
                self.master_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.master_widget.bbox('all')
                x = x + self.master_widget.winfo_rootx()
                y = y + self.master_widget.winfo_rooty()
                self.master_toplevel = tw = tk.Toplevel(self.master_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                label_back_and_forth_slave = tk.Label(tw, text = 'Set number of back and forth\n walks for slave axis', font = LARGE_FONT)
                label_back_and_forth_slave.grid(row = 0, column = 0, pady = 2)
                
                self.combo_back_and_forth_master = ttk.Combobox(tw, value = [2, 'custom', 'continious'])
                if self.parent.status_back_and_forth_master.get() == 0:
                    self.combo_back_and_forth_master.current(0)
                else:
                    self.combo_back_and_forth_master.current(1)
                    self.combo_back_and_forth_master.delete(0, tk.END)
                    self.combo_back_and_forth_master.insert(0, self.parent.back_and_forth_master_count)
                self.combo_back_and_forth_master.grid(row = 1, column = 0, pady = 2)
                
                def update_back_and_forth_master_count():
                    if self.combo_back_and_forth_master.current() == 0:
                        self.parent.back_and_forth_master_count = 2
                    elif self.combo_back_and_forth_master.current() == -1:
                        self.parent.back_and_forth_master_count = int(self.combo_back_and_forth_slave.get())
                    elif self.combo_back_and_forth_master.current() == 2:
                        self.parent.back_and_forth_master_count = int(1e5)
                    else:
                        raise Exception(f'Insert proper back_and_forth_master. Should be int, but given {type(self.combo_back_and_forth_master.get())}')
                    
                    self.parent.entry_ratio1.delete(0, tk.END)
                    self.parent.entry_ratio1.insert(0, self.entry_ratio1.get())
                    self.parent.back_ratio1_init = self.entry_back_ratio1.get()
                    
                    self.parent.entry_delay_factor1.delete(0, tk.END)
                    self.parent.entry_delay_factor1.insert(0, self.entry_delay_factor1.get())
                    self.parent.back_delay_factor1_init = self.entry_back_delay_factor1.get()
                
                button_set_back_and_forth_master = tk.Button(tw, text = 'Set', command = update_back_and_forth_master_count)
                button_set_back_and_forth_master.grid(row = 1, column = 1, pady = 2)
                
                def hide_toplevel():
                    tw = self.master_toplevel
                    self.master_toplevel = None
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
            def update_ratio1(self):
                tw = self.master_toplevel
                
                count_option1 = self.parent.count_option1
                
                self.entry_ratio_label = tk.Label(tw, text = f'Forward {count_option1}')
                self.entry_ratio_label.grid(row = 2, column = 0, pady = 2)
                
                self.entry_back_ratio_label = tk.Label(tw, text = f'Back {count_option1}')
                self.entry_back_ratio_label.grid(row = 2, column = 1, pady = 2)
                
                self.entry_ratio1 = tk.Entry(tw)
                self.entry_ratio1.insert(0, self.parent.entry_ratio1.get())
                self.entry_ratio1.grid(row = 3, column = 0, pady = 2)
                
                self.entry_back_ratio1 = tk.Entry(tw)
                self.entry_back_ratio1.insert(0, self.parent.back_ratio1_init)
                self.entry_back_ratio1.grid(row = 3, column = 1, pady = 2)
                
                self.entry_delay_factor_label = tk.Label(tw, text = 'Forward delay factor')
                self.entry_delay_factor_label.grid(row = 4, column = 0, pady = 2)
                
                self.entry_back_delay_factor_label = tk.Label(tw, text = 'Back delay factor')
                self.entry_back_delay_factor_label.grid(row = 4, column = 1, pady = 2)
                
                self.entry_delay_factor1 = tk.Entry(tw)
                self.entry_delay_factor1.insert(0, self.parent.entry_delay_factor1.get())
                self.entry_delay_factor1.grid(row = 5, column = 0, pady = 2)
                
                self.entry_back_delay_factor1 = tk.Entry(tw)
                self.entry_back_delay_factor1.insert(0, self.parent.back_delay_factor1_init)
                self.entry_back_delay_factor1.grid(row = 5, column = 1, pady = 2)
                
        def CreateMasterToplevel(widget, parent):
            
            toplevel = BackAndForthMaster(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                toplevel.update_ratio1()
                
            widget.bind('<Button-3>', show)
    
        class BackAndForthSlave(object):
            
            def __init__(self, widget, parent):
                self.slave_toplevel = None
                self.slave_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.slave_widget.bbox('all')
                x = x + self.slave_widget.winfo_rootx()
                y = y + self.slave_widget.winfo_rooty()
                self.slave_toplevel = tw = tk.Toplevel(self.slave_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                label_back_and_forth_slave = tk.Label(tw, text = 'Set number of back and forth\n walks for slave axis', font = LARGE_FONT)
                label_back_and_forth_slave.grid(row = 0, column = 0, pady = 2)
                
                self.combo_back_and_forth_slave = ttk.Combobox(tw, value = [2, 'custom', 'continious'])
                if self.parent.status_back_and_forth_slave.get() == 0:
                    self.combo_back_and_forth_slave.current(0)
                else:
                    self.combo_back_and_forth_slave.current(1)
                    self.combo_back_and_forth_slave.delete(0, tk.END)
                    self.combo_back_and_forth_slave.insert(0, self.parent.back_and_forth_master_count)
                self.combo_back_and_forth_slave.grid(row = 1, column = 0, pady = 2)
                
                def update_back_and_forth_slave_count():
                    if self.combo_back_and_forth_slave.current() == 0:
                        self.parent.back_and_forth_slave_count = 2
                    elif self.combo_back_and_forth_slave.current() == -1:
                        self.parent.back_and_forth_slave_count = int(self.combo_back_and_forth_slave.get())
                    elif self.combo_back_and_forth_slave.current() == 2:
                        self.parent.back_and_forth_slave_count = int(1e5)
                    else:
                        raise Exception(f'Insert proper back_and_forth_master. Should be int, but given {type(self.combo_back_and_forth_slave.get())}')
                
                    self.parent.entry_ratio2.delete(0, tk.END)
                    self.parent.entry_ratio2.insert(0, self.entry_ratio2.get())
                    self.parent.back_ratio2_init = self.entry_back_ratio2.get()
                    
                    self.parent.entry_delay_factor2.delete(0, tk.END)
                    self.parent.entry_delay_factor2.insert(0, self.entry_delay_factor2.get())
                    self.parent.back_delay_factor2_init = self.entry_back_delay_factor2.get()
                
                button_set_back_and_forth_slave = tk.Button(tw, text = 'Set', command = update_back_and_forth_slave_count)
                button_set_back_and_forth_slave.grid(row = 1, column = 1, pady = 2)
                
                #label_fast_master = tk.Label(tw, text = 'Fast mode')
                #label_fast_master.grid(row = 2, column = 0, pady = 2)
                
                label_snake_master = tk.Label(tw, text = 'Snake mode')
                label_snake_master.grid(row = 2, column = 0, pady = 2)
                
                def fastmode_pressed():
                    
                    self.parent.preset.loc[0, 'status_fastmode2'] = self.parent.status_fastmode_master.get()
                    self.parent.preset.to_csv(globals()['sweeper2d_path'], index = False)
                    
                    if self.parent.status_fastmode_master.get() == 1:
                        self.checkbox_snake_master.config(state = 'disable')
                    else:
                        self.checkbox_snake_master.config(state = 'normal')
                    
                def snakemode_pressed():
                    
                    self.parent.preset.loc[0, 'status_snakemode2'] = self.parent.status_snakemode_master.get()
                    self.parent.preset.to_csv(globals()['sweeper2d_path'], index = False)
                    
                    
                    #if self.parent.status_snakemode_master.get() == 1:
                    #    self.checkbox_fast_master.config(state = 'disable')
                    #else:
                    #    self.checkbox_fast_master.config(state = 'normal')
                    
                
                #self.checkbox_fast_master = ttk.Checkbutton(tw, variable = self.parent.status_fastmode_master, onvalue = 1, offvalue = 0, command = fastmode_pressed)
                #self.checkbox_fast_master.grid(row = 2, column = 1, pady = 1)
                
                #if self.parent.status_snakemode_master.get() == 1:
                #    self.checkbox_fast_master.config(state = 'disable')
                
                self.checkbox_snake_master = ttk.Checkbutton(tw, variable = self.parent.status_snakemode_master, onvalue = 1, offvalue = 0, command = snakemode_pressed)
                self.checkbox_snake_master.grid(row = 2, column = 1, pady = 1)
                
                #if self.parent.status_fastmode_master.get() == 1:
                #    self.checkbox_snake_master.config(state = 'disable')
                
                def hide_toplevel():
                    tw = self.slave_toplevel
                    self.slave_toplevel = None
                    #if self.parent.status_fastmode_master.get() == 1:
                    #    globals()['fastmode_master_flag'] = True
                    #else:
                    #    globals()['fastmode_master_flag'] = False
                    if self.parent.status_snakemode_master.get() == 1:
                        globals()['snakemode_master_flag'] = True
                    else:
                        globals()['snakemode_master_flag'] = False
                
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
            def update_ratio2(self):
                tw = self.slave_toplevel
                
                count_option2 = self.parent.count_option2
                
                self.entry_ratio_label = tk.Label(tw, text = f'Forward {count_option2}')
                self.entry_ratio_label.grid(row = 3, column = 0, pady = 2)
                
                self.entry_back_ratio_label = tk.Label(tw, text = f'Back {count_option2}')
                self.entry_back_ratio_label.grid(row = 3, column = 1, pady = 2)
                
                self.entry_ratio2 = tk.Entry(tw)
                self.entry_ratio2.insert(0, self.parent.entry_ratio2.get())
                self.entry_ratio2.grid(row = 4, column = 0, pady = 2)
                
                self.entry_back_ratio2 = tk.Entry(tw)
                self.entry_back_ratio2.insert(0, self.parent.back_ratio2_init)
                self.entry_back_ratio2.grid(row = 4, column = 1, pady = 2)
                
                self.entry_delay_factor_label = tk.Label(tw, text = 'Forward delay factor')
                self.entry_delay_factor_label.grid(row = 5, column = 0, pady = 2)
                
                self.entry_back_delay_factor_label = tk.Label(tw, text = 'Back delay factor')
                self.entry_back_delay_factor_label.grid(row = 5, column = 1, pady = 2)
                
                self.entry_delay_factor2 = tk.Entry(tw)
                self.entry_delay_factor2.insert(0, self.parent.entry_delay_factor2.get())
                self.entry_delay_factor2.grid(row = 6, column = 0, pady = 2)
                
                self.entry_back_delay_factor2 = tk.Entry(tw)
                self.entry_back_delay_factor2.insert(0, self.parent.back_delay_factor2_init)
                self.entry_back_delay_factor2.grid(row = 6, column = 1, pady = 2)
                
        def CreateSlaveToplevel(widget, parent):
            
            toplevel = BackAndForthSlave(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                toplevel.update_ratio2()
                
            widget.bind('<Button-3>', show)
    
        self.checkbox_back_and_forth_master = ttk.Checkbutton(self,
                                           variable=self.status_back_and_forth_master, onvalue=1,
                                           offvalue=0, command=lambda: self.save_back_and_forth_master_status())
        self.checkbox_back_and_forth_master.place(relx=0.22, rely=0.61)
        CreateMasterToplevel(self.checkbox_back_and_forth_master, self)
        
        self.label_back_and_forth_master = tk.Label(self, text = '🔁', font = SUPER_LARGE)
        self.label_back_and_forth_master.place(relx = 0.2335, rely = 0.6)
        CreateToolTip(self.label_back_and_forth_master, 'Back and forth sweep\nfor this axis \nRight click to configure')
        CreateMasterToplevel(self.label_back_and_forth_master, self)

        self.checkbox_back_and_forth_slave = ttk.Checkbutton(self,
                                           variable=self.status_back_and_forth_slave, onvalue=1,
                                           offvalue=0, command=lambda: self.save_back_and_forth_slave_status())
        self.checkbox_back_and_forth_slave.place(relx=0.38, rely=0.61)
        CreateSlaveToplevel(self.checkbox_back_and_forth_slave, self)
        
        self.label_back_and_forth_slave = tk.Label(self, text = '🔁', font = SUPER_LARGE)
        self.label_back_and_forth_slave.place(relx = 0.3935, rely = 0.6)
        CreateToolTip(self.label_back_and_forth_slave, 'Back and forth sweep\nfor this axis')
        CreateSlaveToplevel(self.label_back_and_forth_slave, self)
    
        def stepper_mode():
            global stepper_flag
            
            if stepper_flag == True:
                stepper_flag = False
            elif stepper_flag == False:
                stepper_flag = True

        self.checkbox_stepper = tk.Checkbutton(self, text = r'🦶', font = LARGE_FONT, command = stepper_mode)
        if stepper_flag == True:
            self.checkbox_stepper.select()
        self.checkbox_stepper.place(relx = 0.425, rely = 0.605)
        CreateToolTip(self.checkbox_stepper, 'Stepper mode')
    
        devices = tk.StringVar()
        devices.set(value=parameters_to_read)
        self.lstbox_to_read = tk.Listbox(self, listvariable=devices,
                                         selectmode='multiple', exportselection=False,
                                         width=40, height=len(parameters_to_read) * 1)
        self.lstbox_to_read.place(relx=0.45, rely=0.17)
        
        self.dict_lstbox = {}
        
        for parameter in parameters_to_read:
            self.dict_lstbox[parameter] = parameter
            
        self.lstbox_height = len(parameters_to_read) / 47
        
        self.button_update_sweep = tk.Button(self, text = 'Update sweep', command = lambda: self.update_sweep_configuration())
        self.button_update_sweep.place(relx = 0.45, rely = 0.21 +  self.lstbox_height)

        self.button_pause = tk.Button(self, text = '⏸️', font = LARGE_FONT, command = lambda: self.pause())
        self.button_pause.place(relx = 0.45, rely = 0.25 + self.lstbox_height)
        CreateToolTip(self.button_pause, 'Pause\Continue sweep')
        
        self.button_stop = tk.Button(self, text = '⏹️', font = LARGE_FONT, command = lambda: self.stop())
        self.button_stop.place(relx = 0.4875, rely = 0.25 + self.lstbox_height)
        CreateToolTip(self.button_stop, 'Stop sweep')
        
        self.button_tozero = tk.Button(self, text = 'To zero', width = 11, command = lambda: self.tozero())
        self.button_tozero.place(relx = 0.45, rely = 0.3 + self.lstbox_height)
        
        self.button_start_sweeping = tk.Button(
            self, text="▶", command=lambda: self.start_sweeping(), font = LARGE_FONT)
        self.button_start_sweeping.place(relx=0.525, rely=0.21 + self.lstbox_height, height= 90, width=30)
        CreateToolTip(self.button_start_sweeping, 'Start sweeping')
        
        class ChangeName(object):
            
            def __init__(self, widget, parent):
                self.name_toplevel = None
                self.name_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x = y = 0
                x = x + self.name_widget.winfo_rootx()
                y = y + self.name_widget.winfo_rooty()
                self.name_toplevel = tw = tk.Toplevel(self.name_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_names = tk.Label(tw, text = 'Change names:', font = LARGE_FONT)
                label_names.grid(row = 0, column = 0, pady = 2)
                    
                def update_combo_set_parameters(event, interval = 100):
                    global types_of_devices
                    global list_of_devices
                    ind = self.combo_devices.current()
                    class_of_sweeper_device = types_of_devices[ind]
                    device = list_of_devices[ind]
                    
                    if self.combo_devices.current() != -1:
                        self.selected_device = ind
                    if class_of_sweeper_device != 'Not a class':
                        self.combo_set_parameters['values'] = getattr(device, 'set_options')
                        self.combo_set_parameters.after(interval)
                    else:
                        self.combo_set_parameters['values'] = ['']
                        self.combo_set_parameters.current(0)
                        self.combo_set_parameters.after(interval)

                def update_names_devices():
                    new_device_name = self.combo_devices.get()
                    new_device_values = list(self.combo_devices['values'])
                    new_device_values[self.selected_device] = new_device_name
                    self.combo_devices['values'] = new_device_values
                    self.combo_devices.after(1)
                    
                    try:
                        self.parent.combo_to_sweep1['values'] = new_device_values
                        self.parent.combo_to_sweep1.current(self.selected_device)
                    except:
                        pass
                    try:
                        self.parent.combo_to_sweep2['values'] = new_device_values
                        self.parent.combo_to_sweep2.current(self.selected_device)
                    except:
                        pass
                    
                    self.parent.after(1)
                    
                def update_names_set_parameters():
                    new_set_parameter_name = self.combo_set_parameters.get()
                    new_set_parameters_values = list(self.combo_set_parameters['values'])
                    new_set_parameters_values[self.selected_set_option] = new_set_parameter_name
                    self.combo_set_parameters['values'] = new_set_parameters_values
                    try:
                        self.parent.sweep_options1['values'] = new_set_parameters_values
                        self.parent.sweep_options1.current(self.selected_set_options)
                    except:
                        pass
                    try:
                        self.parent.sweep_options2['values'] = new_set_parameters_values
                        self.parent.sweep_options2.current(self.selected_set_options)
                    except:
                        pass

                    self.parent.after(1)
                    
                def update_names_get_parameters(interval = 1000):
                    new_get_parameter_name = self.get_current.get()
                    new_get_parameters_values = list(self.combo_get_parameters['values'])
                    new_get_parameters_values[self.selected_get_option] = new_get_parameter_name
                    
                    self.parent.dict_lstbox[self.combo_get_parameters['values'][self.selected_get_option]] = new_get_parameter_name
                    
                    self.combo_get_parameters['values'] = new_get_parameters_values
                    
                    self.parent.devices.set(value=new_get_parameters_values)
                    self.parent.lstbox_to_read.after(interval)
                    
                def select_set_option(event):
                    if self.combo_set_parameters.current() != -1:
                        self.selected_set_option = self.combo_set_parameters.current()
                        
                def select_get_option(event):
                    if self.combo_get_parameters.current() != -1:
                        self.selected_get_option = self.combo_get_parameters.current()
                
                self.combo_devices = ttk.Combobox(tw, value = self.parent.combo_to_sweep1['values'])
                self.combo_devices.current(0)
                self.combo_devices.bind(
                    "<<ComboboxSelected>>", update_combo_set_parameters)
                self.combo_devices.grid(row = 1, column = 0, pady = 2)
                
                self.combo_set_parameters = ttk.Combobox(tw, value = [''])
                device_class = types_of_devices[0]
                if device_class != 'Not a class':
                    try:
                        self.combo_set_parameters['values'] = self.parent.sweep_options1['values']
                    except: 
                        self.combo_set_parameters['values'] = getattr(list_of_devices[0], 'set_options')
                    self.combo_set_parameters.current(0)
                    self.combo_set_parameters.bind(
                        "<<ComboboxSelected>>", select_set_option)
                else:
                    self.combo_set_parameters['values'] = ['']
                    self.combo_set_parameters.current(0)
                self.combo_set_parameters.grid(row = 2, column = 0, pady = 2)
                
                parameters = parameters_to_read
                
                if len(parameters) == 0:
                    parameters = ['']
                
                self.get_current = tk.StringVar()
                self.combo_get_parameters = ttk.Combobox(tw, value = parameters, textvariable = self.get_current)
                self.combo_get_parameters.current(0)
                self.combo_get_parameters.bind(
                    "<<ComboboxSelected>>", select_get_option)
                self.combo_get_parameters.grid(row = 3, column = 0, pady = 2)
                
                button_change_name_device = tk.Button(tw, text = 'Change device name', command = update_names_devices)
                button_change_name_device.grid(row = 1, column = 1, pady = 2)
                
                self.selected_device = 0
                self.selected_set_option = 0
                self.selected_get_option = 0
                
                button_change_name_set_parameters = tk.Button(tw, text = 'Change set name', command = update_names_set_parameters)
                button_change_name_set_parameters.grid(row = 2, column = 1, pady = 2)
                
                button_change_name_get_parameters = tk.Button(tw, text = 'Change get name', command = update_names_get_parameters)
                button_change_name_get_parameters.grid(row = 3, column = 1, pady = 2)
                
                def hide_toplevel():
                    tw = self.name_toplevel
                    self.name_toplevel = None
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
        def CreateNameToplevel(widget, parent):
            
            toplevel = ChangeName(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show) 
            
        CreateNameToplevel(self.sweep_options1, self)
        CreateNameToplevel(self.combo_to_sweep1, self)
        CreateNameToplevel(self.sweep_options2, self)
        CreateNameToplevel(self.combo_to_sweep2, self)
        
        if len(parameters_to_read) < 10:
            self.lstbox_to_read.place(relx=0.45, rely=0.16)
        else:
            self.lstbox_height = 18 / 47
            self.lstbox_to_read.place(relx=0.45, rely=0.16, height = 300)
            self.button_pause.place(relx = 0.45, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.4875, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.525, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.45, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.45, rely = 0.21 + self.lstbox_height)
        self.lstbox_to_read.bind('<Button-3>', self.update_listbox)
        
        scrollbar= ttk.Scrollbar(self, orient = 'vertical')
        scrollbar.place(relx = 0.65, rely = 0.16, height = 75)
        
        self.lstbox_to_read.config(yscrollcommand= scrollbar.set)
        scrollbar.config(command= self.lstbox_to_read.yview)

        label_options = tk.Label(self, text = 'Options:', font=LARGE_FONT)
        label_options.place(relx = 0.05, rely = 0.25)

        label_from1 = tk.Label(self, text='From', font=LARGE_FONT)
        label_from1.place(relx=0.12, rely=0.29)

        label_to1 = tk.Label(self, text='To', font=LARGE_FONT)
        label_to1.place(relx=0.12, rely=0.33)

        if self.count_option1 == 'ratio':
            self.label_ratio1 = tk.Label(self, text='Ratio, \n Δ/s', font=LARGE_FONT)
            CreateToolTip(self.label_ratio1, 'Speed of 1d-sweep')
        elif self.count_option1 == 'step':
            self.label_ratio1 = tk.Label(self, text='Step, Δ', font=LARGE_FONT)
            CreateToolTip(self.label_ratio1, 'Step of 1d-sweep')
        self.label_ratio1.place(relx=0.12, rely=0.37)

        self.entry_from1 = tk.Entry(self)
        self.entry_from1.insert(0, self.from1_init)
        self.entry_from1.place(relx=0.17, rely=0.29)
        self.entry_from1.after(1000, self.rewrite_preset)

        self.entry_to1 = tk.Entry(self)
        self.entry_to1.insert(0, self.to1_init)
        self.entry_to1.place(relx=0.17, rely=0.33)

        self.entry_ratio1 = tk.Entry(self)
        self.entry_ratio1.insert(0, self.ratio1_init)
        self.entry_ratio1.place(relx=0.17, rely=0.37)
        
        button_swap1 = tk.Button(self, text = r'🆚', font = ('Verdana', 8), command = self.swap_ratio_step1)
        button_swap1.place(relx = 0.1, rely = 0.4)
        CreateToolTip(button_swap1, 'Change Ratio/Step')

        label_delay_factor1 = tk.Label(
            self, text='Delay factor, s', justify=tk.LEFT, font=LARGE_FONT)
        label_delay_factor1.place(relx=0.12, rely=0.45)
        CreateToolTip(label_delay_factor1, 'Sleep time per 1 point')

        self.entry_delay_factor1 = tk.Entry(self)
        self.entry_delay_factor1.insert(0, self.delay_factor1_init)
        self.entry_delay_factor1.place(relx=0.12, rely=0.51)

        label_from2 = tk.Label(self, text='From', font=LARGE_FONT)
        label_from2.place(relx=0.27, rely=0.29)

        label_to2 = tk.Label(self, text='To', font=LARGE_FONT)
        label_to2.place(relx=0.27, rely=0.33)

        if self.count_option2 == 'ratio':
            self.label_ratio2 = tk.Label(self, text='Ratio, \n Δ/s', font=LARGE_FONT)
            CreateToolTip(self.label_ratio2, 'Speed of 1d-sweep')
        elif self.count_option2 == 'step':
            self.label_ratio2 = tk.Label(self, text='Step, Δ', font=LARGE_FONT)
            CreateToolTip(self.label_ratio2, 'Step of 1d-sweep')
        self.label_ratio2.place(relx=0.27, rely=0.37)

        self.entry_from2 = tk.Entry(self)
        self.entry_from2.insert(0, self.from2_init)
        self.entry_from2.place(relx=0.32, rely=0.29)

        self.entry_to2 = tk.Entry(self)
        self.entry_to2.insert(0, self.to2_init)
        self.entry_to2.place(relx=0.32, rely=0.33)

        self.entry_ratio2 = tk.Entry(self)
        self.entry_ratio2.insert(0, self.ratio2_init)
        self.entry_ratio2.place(relx=0.32, rely=0.37)
        
        button_swap2 = tk.Button(self, text = r'🆚', font = ('Verdana', 8), command = self.swap_ratio_step2)
        button_swap2.place(relx = 0.25, rely = 0.4)
        CreateToolTip(button_swap2, 'Change Ratio/Step')

        label_delay_factor2 = tk.Label(
            self, text='Delay factor, s', justify=tk.LEFT, font=LARGE_FONT)
        label_delay_factor2.place(relx=0.27, rely=0.45)
        CreateToolTip(label_delay_factor2, 'Sleep time per 1 point')

        self.entry_delay_factor2 = tk.Entry(self)
        self.entry_delay_factor2.insert(0, self.delay_factor2_init)
        self.entry_delay_factor2.place(relx=0.27, rely=0.51)

        # section of manual sweep points selection
        self.filename = filename_sweep[:-4] + '_manual' + '.csv'

        # initials

        self.manual_sweep_flags = [0, 0]

        self.checkbox_manual1 = ttk.Checkbutton(self, text='Maunal sweep select',
                                           variable=self.status_manual1, onvalue=1,
                                           offvalue=0, command=lambda: self.save_manual_status(i=1))
        self.checkbox_manual1.place(relx=0.12, rely=0.57)
        
        if self.status_manual1.get() == 0:
            self.entry_from1.config(state= "normal")
            self.entry_to1.config(state= "normal")
            self.entry_ratio1.config(state= "normal")
        else:
            self.entry_from1.config(state= "disabled")
            self.entry_to1.config(state= "disabled")
            self.entry_ratio1.config(state= "disabled")

        button_new_manual1 = tk.Button(self, text='🖊', font = LARGE_FONT, command=lambda: self.open_blank(i=0))
        button_new_manual1.place(relx=0.12, rely=0.6)
        CreateToolTip(button_new_manual1, 'Create new sweep instruction')

        button_explore_manual1 = tk.Button(
            self, text='🔎', font = LARGE_FONT, command=lambda: self.explore_files(i=0))
        button_explore_manual1.place(relx=0.15, rely=0.6)
        CreateToolTip(button_explore_manual1, 'Explore existing sweep instruction')

        self.checkbox_manual2 = ttk.Checkbutton(self, text='Maunal sweep select',
                                           variable=self.status_manual2, onvalue=1,
                                           offvalue=0, command=lambda: self.save_manual_status(i=2))
        self.checkbox_manual2.place(relx=0.27, rely=0.57)

        if self.status_manual2.get() == 0:
            self.entry_from2.config(state= "normal")
            self.entry_to2.config(state= "normal")
            self.entry_ratio2.config(state= "normal")
        else:
            self.entry_from2.config(state= "disabled")
            self.entry_to2.config(state= "disabled")
            self.entry_ratio2.config(state= "disabled")

        button_new_manual2 = tk.Button(self, text='🖊', font = LARGE_FONT, command=lambda: self.open_blank(i=1))
        button_new_manual2.place(relx=0.27, rely=0.6)
        CreateToolTip(button_new_manual2, 'Create new sweep instruction')

        button_explore_manual2 = tk.Button(
            self, text='🔎', font = LARGE_FONT, command=lambda: self.explore_files(i=1))
        button_explore_manual2.place(relx=0.3, rely=0.6)
        CreateToolTip(button_explore_manual2, 'Explore existing sweep instruction')
        
        label_condition = tk.Label(self, text = 'Constraints:', font = LARGE_FONT)
        label_condition.place(relx = 0.12, rely = 0.66)
        CreateToolTip(label_condition, 'Master sweep: x\nSlave sweep: y\nSet condition for a sweep map \nRight click to configure script')
        
        self.text_condition = tk.Text(self, width = 40, height = 7)
        self.text_condition.delete('1.0', tk.END)
        self.text_condition.insert(tk.END, self.condition)
        self.text_condition.place(relx = 0.12, rely = 0.7)
        CreateToolTip(self.text_condition, 'Master sweep: x\nSlave sweep: y\nSet condition for a sweep map \nRight click to configure script')

        self.filename_textvariable = tk.StringVar(self, value = self.filename_sweep)
        width = int(len(self.filename_textvariable.get()) * 0.95)
        self.entry_filename = tk.Entry(self, textvariable = self.filename_textvariable, font = LARGE_FONT, 
                                       width = width)
        self.entry_filename.place(relx = 0.97 - width / 100, rely = 0.9)

        self.script = ''
        
        class Script(object):
            
            def __init__(self, widget, parent):
                self.script_toplevel = None
                self.script_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x = y = 0
                self.script_toplevel = tw = tk.Toplevel(self.script_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_script = tk.Label(tw, text = 'Manual script', font = LARGE_FONT)
                label_script.grid(row = 0, column = 0, pady = 2)
                
                def ctrlEvent(event):
                    if event.state == 4 and event.keysym == 'c':
                        content = self.text_script.selection_get()
                        tw.clipboard_clear()
                        tw.clipboard_append(content)
                        return "break"
                    elif event.state == 4 and event.keysym == 'v':
                        self.text_script.insert('end', tw.selection_get(selection='CLIPBOARD'))
                        return "break"
                    elif event.state == 4 and event.keysym == 'a':
                        self.text_script.tag_add("sel", "1.0","end")
                        return "break"
                    elif event.state == 4 and event.keysym == 'z':
                        self.text_script.delete('sel.first','sel.last')
                        return "break"
                    
                self.text_script = tk.Text(tw, width = 60, height = 10)
                self.text_script.grid(row = 1, column = 0, pady = 2, rowspan = 3)
                self.text_script.configure(font = LARGE_FONT)
                self.text_script.bind("<Key>", ctrlEvent)
                
                def hide_toplevel():
                    tw = self.script_toplevel
                    self.script_toplevel = None
        
                    tw.destroy()
                
                def explore_script(interval = 1):
                    
                    if exists(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')):
                        init = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')
                    else:
                        init = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')
                    
                    script_filename = tk.filedialog.askopenfilename(initialdir=init,
                                                                             title='Select a script')
                    with open(script_filename, 'r') as file:
                        try:
                            script = file.read()
                        except Exception as e:
                            print(f'Exception happened while exploring existing script: {e}')
                            file.close()
                        finally:
                            file.close()
                            
                    self.text_script.delete(1.0, tk.END)
                    self.text_script.insert(tk.END, script)
                    self.text_script.after(interval)
                    self.script_toplevel.deiconify() #show toplevel again
                    
                def set_script():
                    self.parent.script = self.text_script.get(1.0, tk.END)[:-1]
                    hide_toplevel()
                    
                def save_script():
                    
                    if not exists(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')):
                        os.mkdir(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts'))
                    
                    self.script_filename = tk.filedialog.asksaveasfilename(title='Save the file',
                                            initialfile=os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}',
                                            'scripts', f'script{datetime.today().strftime("%H_%M_%d_%m_%Y")}'),
                                            defaultextension='.csv')
                    
                    self.parent.script = self.text_script.get(1.0, tk.END)[:-1]
                    
                    with open(self.script_filename, 'w') as file:
                        try:
                            file.write(self.parent.script)
                        except Exception as e:
                            print(f'Exception happened while saving the script: {e}')
                            file.close()
                        finally:
                            file.close()
                    
                    self.script_toplevel.deiconify() #show toplevel again
                
                button_explore_script = tk.Button(
                    tw, text='🔎', font = SUPER_LARGE, command = explore_script)
                button_explore_script.grid(row = 1, column = 1, pady = 2)
                CreateToolTip(button_explore_script, 'Explore existing script')
                
                button_save_script = tk.Button(
                    tw, text='💾', font = SUPER_LARGE, command = save_script)
                button_save_script.grid(row = 2, column = 1, pady = 2)
                CreateToolTip(button_save_script, 'Save this script')
                
                self.script_filename = ''
                
                button_set_script = tk.Button(
                    tw, text = 'Apply script', font = LARGE_FONT, command = set_script)
                button_set_script.grid(row = 3, column = 1, pady = 2)
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
            
        def CreateScriptToplevel(widget, parent):
            
            toplevel = Script(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show) 
            
        CreateScriptToplevel(self.text_condition, self)

        button_filename = tk.Button(
            self, text = 'Browse...', command=lambda: self.set_filename_sweep())
        button_filename.place(relx=0.85, rely=0.9)

        class Interpolated(object):
            
            def __init__(self, widget, parent):
                self.interpolated_toplevel = None
                self.interpolated_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.interpolated_widget.bbox('all')
                x = x + self.interpolated_widget.winfo_rootx()
                y = y + self.interpolated_widget.winfo_rooty()
                self.interpolated_toplevel = tw = tk.Toplevel(self.interpolated_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_interpolation = tk.Label(tw, text = 'Interpolate\n2D map?', font = LARGE_FONT)
                label_interpolation.grid(row = 0, column = 0, pady = 2)
                
                self.status_interpolated = tk.IntVar()
                self.status_interpolated.set(self.parent.interpolated)
                
                self.checkbox_interpolation = tk.Checkbutton(tw, variable = self.status_interpolated, 
                                                             onvalue = 1, offvalue = 0, 
                                                             command = self.change_status_interpolated) 
                self.checkbox_interpolation.grid(row = 0, column = 1, pady = 2)
                
                if self.parent.interpolated == 1:
                    self.label_uniform = tk.Label(tw, text = 'Uniform grid', font = LARGE_FONT)
                    self.label_uniform.grid(row = 1, column = 0, pady = 2)
                    
                    self.status_uniform = tk.IntVar()
                    self.status_uniform.set(self.parent.uniform)
                    
                    self.checkbox_uniform = tk.Checkbutton(tw, variable = self.status_uniform,
                                                           onvalue = 1, offvalue = 0,
                                                           command = self.change_status_uniform)
                    self.checkbox_uniform.grid(row = 1, column = 1, pady = 2)
                    
            
                def hide_toplevel():
                    tw = self.interpolated_toplevel
                    self.interpolated_toplevel = None
        
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
            
            def change_status_interpolated(self):
                self.parent.interpolated = self.status_interpolated.get()
                
                if self.status_interpolated.get() == 0:
                    self.checkbox_uniform.grid_forget()
                    self.label_uniform.grid_forget()
                else:
                    self.label_uniform = tk.Label(self.interpolated_toplevel, text = 'Uniform grid', font = LARGE_FONT)
                    self.label_uniform.grid(row = 1, column = 0, pady = 2)
                    
                    self.status_uniform = tk.IntVar()
                    self.status_uniform.set(self.parent.uniform)
                    
                    self.checkbox_uniform = tk.Checkbutton(self.interpolated_toplevel, variable = self.status_uniform,
                                                           onvalue = 1, offvalue = 0,
                                                           command = self.change_status_uniform)
                    self.checkbox_uniform.grid(row = 1, column = 1, pady = 2)
                
            def change_status_uniform(self):
                self.parent.uniform= self.status_uniform.get()
                
        def CreateInterpolatedToplevel(widget, parent):
            
            toplevel = Interpolated(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show)

        graph_button = tk.Button(
            self, text='📊', font = SUPER_LARGE, command=lambda: self.open_graph())
        graph_button.place(relx=0.7, rely=0.8)
        CreateToolTip(graph_button, 'Graph')
        CreateInterpolatedToplevel(graph_button, self)
        
        class ImageLabel(tk.Label):
            """
            A Label that displays images, and plays them if they are gifs
            :im: A PIL Image instance or a string filename
            """
            def load(self, im):
                if isinstance(im, str):
                    im = Image.open(im)
                frames = []
         
                try:
                    for i in count(1):
                        frames.append(ImageTk.PhotoImage(im.copy()))
                        im.seek(i)
                except EOFError:
                    pass
                self.frames = cycle(frames)
         
                try:
                    self.delay = im.info['duration']
                except:
                    self.delay = 100
         
                if len(frames) == 1:
                    self.config(image=next(self.frames))
                else:
                    self.next_frame()
         
            def unload(self):
                self.config(image=None)
                self.frames = None
         
            def next_frame(self):
                if self.frames:
                    self.config(image=next(self.frames))
                    self.after(self.delay, self.next_frame)
                    
        self.cur_walk1 = 1  
        self.cur_walk2 = 1
                  
        def animate():
            
            def get_time_remaining():
                global zero_time
                global from_sweep1
                global to_sweep1
                global ratio_sweep1
                global from_sweep2
                global to_sweep2
                global delay_factor1
                global sweeper_write
                
                def ConvertSectoDay(n):
                    
                    try:
                        n = int(n)
                    except OverflowError:
                        n = int(1e6)
                    day = n // (24 * 3600)
                    n = n % (24 * 3600)
                    hour = n // 3600
                    n %= 3600
                    minutes = n // 60
                    n %= 60
                    seconds = n
                    if day == 0:
                        if hour == 0:
                            if minutes == 0:
                                s = f'{seconds} s'
                            else:
                                s = f'{minutes} m\n{seconds} s'
                        else:
                            s = f'{hour} h\n{minutes} m\n{seconds} s'
                    else:
                        s = f'{day} d\n{hour} h\n{minutes} m\n{seconds} s'
                
                    return s
                
                t = time.perf_counter() - zero_time
                delta = abs(from_sweep2 - to_sweep2)
                nstep1 = np.ceil(abs((from_sweep1 - to_sweep1) / ratio_sweep1 / delay_factor1) + 1)
                
                if sweeper_write.sweepable1:
                    x = float(sweeper_write.current_value)
                else:
                    x = float(sweeper_write.value2)
                    
                try:    
                    if self.status_back_and_forth_slave.get() == 0:
                        back_and_forth_slave = 1
                    else:
                        back_and_forth_slave = self.back_and_forth_slave_count
                    if self.status_back_and_forth_master.get() == 0:
                        back_and_forth_master = 1
                    else:
                        back_and_forth_master = self.back_and_forth_master_count
                    
                    tau = (self.cur_walk1 - nstep1) * delay_factor1 + (t + (self.cur_walk1 - 1) * delay_factor1) * ((nstep1*back_and_forth_master*back_and_forth_slave - self.cur_walk2) * delta + (to_sweep2 - x)) / ((self.cur_walk2 - 1) * delta + (x - from_sweep2)) #time * how musch to go / how much has gone already
                    
                    return ConvertSectoDay(tau)
                except ZeroDivisionError as e:
                    print(f'ZeroDivisionException happened: {e}')
                    return '...'
                except RuntimeWarning as e:
                    print(f'RuntimeWarning happened: {e}')
                    return '...'
            
            if self.start_sweep_flag:
                if not hasattr(self, 'gif_label'):
                    self.gif_label = ImageLabel(self)
                    self.gif_label.place(relx = 0.75, rely = 0.5)
                    if 'loading.gif' in os.listdir(os.path.join(core_dir, 'config')):
                        self.gif_label.load(os.path.join(core_dir, 'config', 'loading.gif'))
                if not hasattr(self, 'time_label'):
                    self.time_label = tk.Label(self, text = 'Time left: ...', font = LARGE_FONT)
                    self.time_label.place(relx = 0.8, rely = 0.5)
                else:
                    self.time_label.config(text = f'Time left: {get_time_remaining()}')
            else:
                if hasattr(self, 'gif_label'):
                    self.gif_label.place_forget()
                    del self.gif_label
                if hasattr(self, 'time_label'):
                    self.time_label.place_forget()
                    del self.time_label
            self.after(1000, animate)
            
        self.start_sweep_flag = False
        animate()

    def update_sweep_parameters1(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        ind = self.combo_to_sweep1.current()
        class_of_sweeper_device1 = types_of_devices[ind]
        device1 = list_of_devices[ind]
        if class_of_sweeper_device1 != 'Not a class':
            self.sweep_options1['value'] = getattr(
                device1, 'set_options')
            try:
                self.sweep_options1.current(self.sweep_options1_current)
            except tk.TclError:
                self.sweep_options1.current(0)
            self.sweep_options1.after(interval)
        else:
            self.sweep_options1['value'] = ['']
            self.sweep_options1.current(0)
            self.sweep_options1.after(interval)
            
        if self.combo_to_sweep1.current() != self.combo_to_sweep1_current:
            self.preset.loc[0, 'combo_to_sweep1'] = self.combo_to_sweep1.current()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        
        self.back_ratio1_init = ''
        self.back_delay_factor1_init = ''
            
    def update_sweep_options1(self, event):
        if self.sweep_options1.current() != self.sweep_options1_current:
            self.preset.loc[0, 'sweep_options1'] = self.sweep_options1.current()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)

    def update_sweep_parameters2(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        ind = self.combo_to_sweep2.current()
        class_of_sweeper_device2 = types_of_devices[ind]
        device2 = list_of_devices[ind]
        if class_of_sweeper_device2 != 'Not a class':
            self.sweep_options2['value'] = getattr(
                device2, 'set_options')
            try:
                self.sweep_options2.current(self.sweep_options2_current)
            except tk.TclError:
                self.sweep_options2.current(0)
            self.sweep_options2.after(interval)
        else:
            self.sweep_options2['value'] = ['']
            self.sweep_options2.current(0)
            self.sweep_options2.after(interval)
            
        if self.combo_to_sweep2.current() != self.combo_to_sweep2_current:
            self.preset.loc[0, 'combo_to_sweep2'] = self.combo_to_sweep2.current()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
            
        self.back_ratio2_init = ''
        self.back_delay_factor2_init = ''
            
    def update_sweep_options2(self, event):
        if self.sweep_options2.current() != self.sweep_options2_current:
            self.preset.loc[0, 'sweep_options2'] = self.sweep_options2.current()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
            
    def swap_ratio_step1(self):
        if self.count_option1 == 'step':
            self.count_option1 = 'ratio'
        elif self.count_option1 == 'ratio':
            self.count_option1 = 'step'
            
        if self.count_option1 == 'step' and self.label_ratio1['text'].startswith('Ratio'):
            self.label_ratio1.configure(text = 'Step, Δ')
            self.update()
        
        if self.count_option1 == 'ratio' and self.label_ratio1['text'].startswith('Step'):
            self.label_ratio1.configure(text = 'Ratio, \n Δ/s')
            self.update()
        
        self.preset.loc[0, 'count_option1'] = self.count_option1
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        
    def swap_ratio_step2(self):
        if self.count_option2 == 'step':
            self.count_option2 = 'ratio'
        elif self.count_option2 == 'ratio':
            self.count_option2 = 'step'
            
        if self.count_option2 == 'step' and self.label_ratio2['text'].startswith('Ratio'):
            self.label_ratio2.configure(text = 'Step, Δ')
            self.update()
        
        if self.count_option2 == 'ratio' and self.label_ratio2['text'].startswith('Step'):
            self.label_ratio2.configure(text = 'Ratio, \n Δ/s')
            self.update()
        
        self.preset.loc[0, 'count_option2'] = self.count_option2
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
            
    def rewrite_preset(self):
        time.sleep(0.05)
        if self.entry_from1.get() != self.from1_init:
            self.preset.loc[0, 'from1'] = self.entry_from1.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        if self.entry_to1.get() != self.to1_init:
            self.preset.loc[0, 'to1'] = self.entry_to1.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        if self.entry_ratio1.get() != self.ratio1_init:
            self.preset.loc[0, 'ratio1'] = self.entry_ratio1.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        self.preset.loc[0, 'back_ratio1'] = self.back_ratio1_init
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        self.preset.loc[0, 'back_delay_factor1'] = self.back_delay_factor1_init
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        if self.entry_delay_factor1.get() != self.delay_factor1_init:
            self.preset.loc[0, 'delay_factor1'] = self.entry_delay_factor1.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        if self.entry_from2.get() != self.from2_init:
            self.preset.loc[0, 'from2'] = self.entry_from2.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        if self.entry_to2.get() != self.to2_init:
            self.preset.loc[0, 'to2'] = self.entry_to2.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        if self.entry_ratio2.get() != self.ratio2_init:
            self.preset.loc[0, 'ratio2'] = self.entry_ratio2.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        self.preset.loc[0, 'back_ratio2'] = self.back_ratio2_init
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        self.preset.loc[0, 'back_delay_factor2'] = self.back_delay_factor2_init
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        if self.entry_delay_factor2.get() != self.delay_factor2_init:
            self.preset.loc[0, 'delay_factor2'] = self.entry_delay_factor2.get()
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
            
        current_filename = self.entry_filename.get()
        path_current = os.path.normpath(current_filename).split(os.path.sep)
        name = path_current[-1]
        path_current = path_current[:-1]
        current_filename = basename(name)
        current_filename = os.path.join(*path_current, current_filename)
        current_filename = fix_unicode(current_filename)
        
        memory_filename = self.filename_sweep
        path_memory = os.path.normpath(memory_filename).split(os.path.sep)
        memory_filename = path_memory[-1]
        path_memory = path_memory[:-1]
        memory_filename = basename(memory_filename)
        memory_filename = os.path.join(*path_memory, memory_filename)
        memory_filename = fix_unicode(memory_filename) 
            
        if current_filename != memory_filename:
            self.preset.loc[0, 'filename_sweep'] = current_filename
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        
        self.preset.loc[0, 'condition'] = self.text_condition.get(1.0, tk.END)[:-1]
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        self.preset.loc[0, 'interpolated'] = self.interpolated
        self.preset.loc[0, 'uniform'] = self.uniform
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        
        #self.entry_from1.after(1000, self.rewrite_preset)

    def update_sweep_configuration(self):
        global from_sweep1
        global to_sweep1
        global ratio_sweep1
        global delay_factor1
        global from_sweep2
        global to_sweep2
        global ratio_sweep2
        global delay_factor2
        
        if self.start_sweep_flag:
            
            try:
                from_sweep1 = float(self.entry_from1.get())
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from1.get()} to float')
                return
                
            try:
                to_sweep1 = float(self.entry_to1.get())
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to1.get()} to float')
                return
            
            try:
                ratio_sweep1 = float(self.entry_ratio1.get())
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio1.get()} to float')
                return

            try:
                delay_factor1 = float(self.entry_delay_factor1.get())
            except:
                messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delay_factor1.get()} to float')
                return
            
            try:
                from_sweep2 = float(self.entry_from2.get())
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from2.get()} to float')
                return
                
            try:
                to_sweep2 = float(self.entry_to2.get())
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to2.get()} to float')
                return
            
            try:
                ratio_sweep2 = float(self.entry_ratio2.get())
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio2.get()} to float')
                return

            try:
                delay_factor2 = float(self.entry_delay_factor2.get())
            except:
                messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delay_factor2.get()} to float')
                return
                    
            delta1 = to_sweep1 - from_sweep1
            step1 = globals()['sweeper_write'].step1
            
            delta2 = to_sweep2 - from_sweep2
            step2 = globals()['sweeper_write'].step2
            
            if np.sign(delta1 * step1) < 0:
                to_sweep1 = float(self.entry_from1.get())
                from_sweep1 = float(self.entry_to1.get())
                ratio_sweep1 = - ratio_sweep1
                
            if np.sign(delta2 * step2) < 0:
                to_sweep2 = float(self.entry_from2.get())
                from_sweep2 = float(self.entry_to2.get())
                ratio_sweep2 = - ratio_sweep2
            
            if self.count_option1 == 'step':
                step1 = ratio_sweep1
                ratio_sweep1 = ratio_sweep1 / delay_factor1
                if globals()['sweeper_write'].sweepable1 != True:
                    globals()['sweeper_write'].step1 = step1
                else:
                    globals()['sweeper_write'].step1 = np.sign(step1) * delta1
            else:
                ratio_sweep1 = ratio_sweep1 
                step1 = ratio_sweep1 * delay_factor1
                if globals()['sweeper_write'].sweepable1 != True:
                    globals()['sweeper_write'].step1 = step1
                else:
                    globals()['sweeper_write'].step1 = np.sign(step1) * delta1
                    
            if self.count_option2 == 'step':
                step2 = ratio_sweep2
                ratio_sweep2 = ratio_sweep2 / delay_factor2
                if globals()['sweeper_write'].sweepable2 != True:
                    globals()['sweeper_write'].step2 = step2
                else:
                    globals()['sweeper_write'].step2 = np.sign(step2) * delta2
            else:
                ratio_sweep2 = ratio_sweep2 
                step2 = ratio_sweep2 * delay_factor2
                if globals()['sweeper_write'].sweepable2 != True:
                    globals()['sweeper_write'].step2 = step2
                else:
                    globals()['sweeper_write'].step2 = np.sign(step2) * delta2
            
            self.from_sweep1 = from_sweep1
            self.to_sweep1 = to_sweep1
            self.ratio_sweep1 = ratio_sweep1
            self.delay_fector1 = delay_factor1
            self.from_sweep2 = from_sweep2
            self.to_sweep2 = to_sweep2
            self.ratio_sweep2 = ratio_sweep2
            self.delay_fector2 = delay_factor2
            
        self.rewrite_preset()
        
    def update_listbox(self, interval = 10000):
        global parameters_to_read
        self.devices = tk.StringVar()
        self.devices.set(value=parameters_to_read)
        
        if len(parameters_to_read) < 10:
            self.lstbox_to_read.configure(listvariable = self.devices,
                                             height=len(parameters_to_read) * 1)
            
            self.lstbox_height = len(parameters_to_read) / 47
            
            self.button_pause.place(relx = 0.45, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.4875, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.525, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.45, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.45, rely = 0.21 + self.lstbox_height)
        else:
            self.lstbox_to_read.configure(listvariable = self.devices,
                                             height=300)
            
            self.lstbox_height = 18 / 47
            
            self.button_pause.place(relx = 0.45, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.4875, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.525, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.45, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.45, rely = 0.21 + self.lstbox_height)

    def save_manual_status(self, i):
        if self.manual_sweep_flags[i - 1] != getattr(self, 'status_manual' + str(i)).get():
            self.manual_sweep_flags[i - 1] = getattr(self, 'status_manual' + str(i)).get()

        if getattr(self, f'status_manual{i}').get() == 0:
            self.manual_filenames[i - 1] = ''
            if hasattr(self, f'entry_from{i}'):
                getattr(self, f'entry_from{i}').config(state= "normal")
                getattr(self, f'entry_to{i}').config(state= "normal")
                getattr(self, f'entry_ratio{i}').config(state= "normal")
        else:
            if hasattr(self, f'entry_from{i}'):
                getattr(self, f'entry_from{i}').config(state= "disabled")
                getattr(self, f'entry_to{i}').config(state= "disabled")
                getattr(self, f'entry_ratio{i}').config(state= "disabled")
            
        #update preset
        self.preset.loc[0, f'manual_filename{i}'] = str(self.manual_filenames[i - 1])
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
            
        self.preset.loc[0, f'status_manual{i}'] = self.__dict__[f'status_manual{i}'].get()
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
            
    def save_back_and_forth_master_status(self):
        global back_and_forth_master
        
        if self.status_back_and_forth_master.get() == 0:
            back_and_forth_master = 1
        else:
            back_and_forth_master = self.back_and_forth_master_count
            
        self.preset.loc[0, 'status_back_and_forth1'] = self.status_back_and_forth_master.get()
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
            
    def save_back_and_forth_slave_status(self):
        global back_and_forth_slave
        
        if self.status_back_and_forth_slave.get() == 0:
            back_and_forth_slave = 1
        else:
            back_and_forth_slave = self.back_and_forth_slave_count
            
        self.preset.loc[0, 'status_back_and_forth2'] = self.status_back_and_forth_slave.get()
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
    
    def open_blank(self, i):
        filename = str(self.entry_filename.get())
        tomake = os.path.normpath(filename).split(os.path.sep)
        name = tomake[-1]
        tomake = tomake[:-1]
        tomake = os.path.join(*tomake)
        tomake = fix_unicode(tomake)
        if not exists(tomake):
            os.makedirs(tomake)
        filename = os.path.join(tomake, filename)
        filename = fix_unicode(filename)
        idx = get_filename_index(filename, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        name = name[:len(name) - name[::-1].index('-') - 1]
        filename =  os.path.join(tomake, f'{name}_manual{i+1}d{idx}.csv')
        filename = fix_unicode(filename)
        df = pd.DataFrame(columns=['steps'])
        df.to_csv(filename, index=False)
        self.manual_filenames[i] = filename
        os.startfile(filename)
        self.__dict__[f'status_manual{i + 1}'].set(1)
        #update preset
        self.preset.loc[0, f'status_manual{i + 1}'] = 1
        self.preset.loc[0, f'manual_filename{i + 1}'] = str(self.manual_filenames[i])
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)

    def explore_files(self, i):
        self.manual_filenames[i] = tk.filedialog.askopenfilename(initialdir=cur_dir,
                                                                 title='Select a manual sweeper',
                                                                 filetypes=(('CSV files', '*.csv*'),
                                                                            ('all files', '*.*')))
        
        self.__dict__[f'status_manual{i + 1}'].set(1)
        #update preset
        self.preset.loc[0, f'status_manual{i + 1}'] = 1
        self.preset.loc[0, f'manual_filename{i + 1}'] = str(self.manual_filenames[i])
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)

    def set_filename_sweep(self):
        global filename_sweep

        path = os.path.normpath(self.filename_sweep).split(os.path.sep)
        
        if 'data_files' not in path:
            to_make = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}', 'data_files')
            to_make = fix_unicode(to_make)
            if not exists(to_make):
                os.makedirs(to_make)
        else:
            to_make = os.path.join(*path[:-1])

        filename_sweep = tk.filedialog.asksaveasfilename(title='Save the file',
                                                         initialfile=to_make,
                                                         defaultextension='.csv')
        
        self.entry_filename.delete(0, tk.END)
        self.entry_filename.insert(0, filename_sweep)
        self.entry_filename.after(1)
        
        current_filename = self.entry_filename.get()
        path_current = os.path.normpath(current_filename).split(os.path.sep)
        name = path_current[-1]
        path_current = path_current[:-1]
        current_filename = basename(name)
        current_filename = os.path.join(*path_current, current_filename)
        current_filename = fix_unicode(current_filename)
        
        memory_filename = self.filename_sweep
        path_memory = os.path.normpath(memory_filename).split(os.path.sep)
        memory_filename = path_memory[-1]
        path_memory = path_memory[:-1]
        memory_filename = basename(memory_filename)
        memory_filename = os.path.join(*path_memory, memory_filename)
        memory_filename = fix_unicode(memory_filename) 
        
        if current_filename != memory_filename:
            self.preset.loc[0, 'filename_sweep'] = current_filename
            self.preset.to_csv(globals()['sweeper2d_path'], index = False)

    def open_graph(self):
        
        global cur_animation_num
        global columns
        
        def return_range(x, n):
            if x % n == 0:
                return [x + p for p in range(n)]
            elif x % n == n - 1:
                return [x - p for p in range(n)][::-1]
            else:
                return return_range(x + 1, n)
        
        globals()[f'graph_object{globals()["cur_animation_num"]}'] = Graph(globals()['filename_sweep'])
        for i in return_range(cur_animation_num, 3):
            preset = pd.read_csv(globals()['graph_preset_path'], sep = ',')
            preset = preset.fillna('')
            x_current = int(preset[f'x{i + 1}_current'].values[0])
            y_current = int(preset[f'y{i + 1}_current'].values[0])
            globals()[f'x{i + 1}'] = []
            if x_current < len(columns):
                globals()[f'x{i + 1}_status'] = x_current
            else:
                globals()[f'x{i + 1}_status'] = 0
            globals()[f'y{i + 1}'] = []
            if y_current < len(columns):
                globals()[f'y{i + 1}_status'] = y_current
            else:
                globals()[f'y{i + 1}_status'] = 0
            globals()[f'ani{i+1}'] = StartAnimation
            globals()[f'ani{i+1}'].start(globals()['filename_sweep'])
        
    def pause(self):
        global pause_flag
        
        pause_flag = not(pause_flag)
        
        if self.button_pause['text'] == '⏸️':
            self.button_pause.configure(text = '▶️')
        if self.button_pause['text'] == '▶️':
            self.button_pause.configure(text = '⏸️')
            
        self.button_pause.after(100)
        
    def stop(self):
        
        global stop_flag
        
        stop_flag = True
        
    def tozero(self):
        
        global tozero_flag
        
        answer = messagebox.askyesno('Abort', 'Are you sure you want to set all parameters to 0?')
        
        if answer:
            tozero_flag = True
            
    def determine_filename_sweep(self):
        global filename_sweep
        global cur_dir
        global core_dir
        
        if self.entry_filename.get() != '':
            filename_sweep = self.entry_filename.get()

        filename_sweep = fix_unicode(filename_sweep)

        self.filename_index = get_filename_index(filename = filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')

        core = os.path.normpath(filename_sweep)
        core = core.split(os.sep)
        name = core[-1]
        
        try:
            folder_name = name[:len(name) - name[::-1].index('.') - 1]
        except ValueError:
            pass
        try:
            folder_name = folder_name[:len(folder_name) - folder_name[::-1].index('-') - 1]
        except ValueError:
            pass
        folder_name = unify_filename(folder_name)
        
        if 'data_files' in core and len(core) >= 3:
            cur_dir = os.path.join(*core[:core.index('data_files')])
            path = os.path.normpath(cur_dir).split(os.path.sep)
            date = path[-1]
            if date != f'{YEAR}{MONTH}{DAY}':
                cur_dir = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}')
                self.filename_index = 1
            cur_dir = fix_unicode(cur_dir)
            
            to_make = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
                
            filename_sweep = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}', f'{name}')
            filename_sweep = fix_unicode(filename_sweep)
            
        elif ('data_files' in core and len(core) < 3) or ('data_files' not in core and len(core) < 2):
            name = core[-1]
            
            cur_dir = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')
            
            to_make = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
                
            filename_sweep = os.path.join(cur_dir, 'data_files', f'{name}_{self.filename_index}', f'{name}')
            filename_sweep = fix_unicode(filename_sweep)
            
        elif 'data_files' not in core and len(core) >= 2:
            name = core[-1]
            
            cur_dir = os.path.join(*core[:-1], f'{YEAR}{MONTH}{DAY}')
            cur_dir = fix_unicode(cur_dir)
            
            to_make = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
            
            filename_sweep = os.path.join(*core[:-1], f'{YEAR}{MONTH}{DAY}', 'data_files', f'{folder_name}_{self.filename_index}', f'{name}')
            filename_sweep = fix_unicode(filename_sweep)
            
        self.entry_filename.delete(0, tk.END)
        self.entry_filename.insert(0, filename_sweep)
        self.entry_filename.after(1)
        
    def start_logs(self):
        global list_of_devices
        global list_of_device_addresses
        global types_of_devices
        global device_to_sweep1
        global parameters_to_read
        global cur_dir
        global filename_sweep
        
        all_addresses = [list_of_devices_addresses[self.combo_to_sweep1.current()],
                         list_of_devices_addresses[self.combo_to_sweep2.current()]]
        
        for parameter in parameters_to_read:
            address = parameter[:len(parameter) - parameter[::-1].index('.') - 1]
            all_addresses.append(address)
            
        all_addresses = np.unique(all_addresses)
        
        self.filename_index = get_filename_index(filename = filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        
        core = os.path.normpath(filename_sweep)
        core = core.split(os.sep)
        _name = core[-1]
        try:
            folder_name = _name[:len(_name) - _name[::-1].index('.') - 1]
        except ValueError:
            folder_name = _name
        try:
            folder_name = folder_name[:len(folder_name) - folder_name[::-1].index('-') - 1]
        except ValueError:
            folder_name = _name
        folder_name = unify_filename(folder_name)
        
        for address in all_addresses:
            
            device = list_of_devices[list_of_devices_addresses.index(address)]
            if hasattr(device, 'loggable'):
                to_make = os.path.join(cur_dir, 'logs', f'{folder_name}_{self.filename_index}')
                to_make = fix_unicode(to_make)
                if not exists(to_make):
                    os.makedirs(to_make)
                name = types_of_devices[list_of_devices_addresses.index(address)]
                valid_address = "".join(x for x in address if x.isalnum())
                log_filename = os.path.join(to_make, f'logs_{name}_{valid_address}_{self.filename_index}.csv')
                log_filename = fix_unicode(log_filename)
                t = time.localtime()
                cur_time = time.strftime("%H:%M:%S", t)
                
                log = f'Name: {name}\nAddress: {address}\nTime: {cur_time}\n'
                
                for log_parameter in device.loggable:
                    log += f'{log_parameter}: {getattr(device, log_parameter)()}\n'
                
                log = log[:-1
                          ]
                with open(log_filename, 'w') as file:
                    try:    
                        file.write(log)
                    except Exception as e:
                        print(f'Exception happened while writing log for {name}, {address}: {e}')
                        file.close()
                    finally:
                        file.close()
        
    def pre_sweep1(self):
        global sweeper_write
        global condition
        device = globals()['device_to_sweep1']
        parameter = globals()['parameter_to_sweep1']
        try:
            sweepable = device.sweepable[device.set_options.index(parameter)]
        except:
            sweepable = False
        try:
            from_sweep = self.from_sweep1
            to_sweep = self.to_sweep1
            ratio_sweep = self.ratio_sweep1
        except AttributeError:
            if self.manual_sweep_flags[0] == 1:
                data = pd.read_csv(self.manual_filenames[0])
                steps = data['steps']
                from_sweep = steps.values[0]
                to_sweep = steps.values[-1]
                ratio_sweep = self.delay_factor1 * steps.values.shape[0]
            else:
                raise Exception('Couldn\'t configure \'from_sweep\', \'to_sweep\'')
        delta = abs(to_sweep - from_sweep)
        
        try:
            self.eps1 = float(device.eps[device.set_options.index(parameter)])
        except:
            self.eps1 = 0.0001 * delta
        
        try:
            cur_value = float(getattr(device, parameter)())
        except Exception as e:
            print(f'Exception happened in pre-sweep 1: {e}')
            return

        if abs(cur_value - from_sweep) <= self.eps1:
            self.start_sweep_flag = True
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current master value is {cur_value}. \nStarting position is {from_sweep}, go to start?')
            
            if answer == True:
                
                def start_toplevel():
                    self.pop1 = tk.Toplevel(self)
                    
                    def center(toplevel):
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop1)
                    
                    self.label_approaching1 = tk.Label(self.pop1, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching1.grid(row = 0, column = 0)
                    
                    self.label_position1 = tk.Label(self.pop1, text = '', font = LARGE_FONT)
                    self.label_position1.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position1 - from_sweep)) > self.eps1:
                        self.current_position1 = float(getattr(device, parameter)())
                        self.label_position1.config(text = f'{"{:.3e}".format(self.current_position1)} / {"{:.3e}".format(from_sweep)}')
                        self.label_position1.after(100, update_position)
                        self.start_sweep_flag = False
                    else:
                        self.start_sweep_flag = True
                        self.pop1.destroy()
                        
                def slow_approach(steps: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if len(steps) > 0:
                        getattr(device, f'set_{parameter}')(value = steps[0])
                        self.label_position1.after(int(delay * 1000), lambda steps = steps[1:], delay = delay: slow_approach(steps, delay))
                
                if not sweepable:
                    answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                    if answer2 == False:
                        getattr(device, f'set_{parameter}')(value = from_sweep)
                        self.start_sweep_flag = True
                    elif answer2 == True:
                       _delta = abs(cur_value - from_sweep)
                       step = ratio_sweep * self.delay_factor1
                       nsteps = abs(int(_delta // step) + 1)
                       steps = list(np.linspace(cur_value, from_sweep, nsteps + 1))
                       start_toplevel()
                       self.current_position1 = float(getattr(device, parameter)())
                       update_position()
                       slow_approach(steps, self.delay_factor1)
                    else:
                        return
                        
                else:
                    getattr(device, f'set_{parameter}')(value = from_sweep, speed = ratio_sweep)
                    
                    start_toplevel()
                    self.current_position1 = float(getattr(device, parameter)())
                    update_position()
                    
            elif answer == False:
                self.start_sweep_flag = True
            else:
                self.start_sweep_flag = False
                return
                
    def pre_sweep2(self):
        global sweeper_write
        device = globals()['device_to_sweep2']
        parameter = globals()['parameter_to_sweep2']
        
        def try_start():
            global sweeper_write
            if self.start_sweep_flag:
                self.start_logs()
                sweeper_write = Sweeper_write()
                self.open_graph()
            else:
                self.after(100, try_start)
        
        try:
            sweepable = device.sweepable[device.set_options.index(parameter)]
        except:
            sweepable = False
        try:
            from_sweep = self.from_sweep2
            to_sweep = self.to_sweep2
            ratio_sweep = self.ratio_sweep2
        except AttributeError:
            if self.manual_sweep_flags[1] == 1:
                data = pd.read_csv(self.manual_filenames[1])
                steps = data['steps']
                from_sweep = steps.values[0]
                to_sweep = steps.values[-1]
                ratio_sweep = self.delay_factor2 * steps.values.shape[0]
            else:
                raise Exception('Couldn\'t configure \'from_sweep\', \'to_sweep\'')
        delta = abs(to_sweep - from_sweep)

        try:
            self.eps2 = float(device.eps[device.set_options.index(parameter)])
        except:
            self.eps2 = 0.0001 * delta
        
        try:
            cur_value = float(getattr(device, parameter)())
        except Exception as e:
            print(f'Exception happened in pre-sweep 2: {e}')
            try_start()
            return

        if abs(cur_value - from_sweep) <= self.eps2:
            try_start()
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current slave value is {cur_value}. \nStarting position is {from_sweep}, go to start?')
            if answer == True:
                
                def start_toplevel():
                    self.pop2 = tk.Toplevel(self)
                    
                    def center(toplevel):
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop2)
                    
                    self.label_approaching2 = tk.Label(self.pop2, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching2.grid(row = 0, column = 0)
                    
                    self.label_position2 = tk.Label(self.pop2, text = '', font = LARGE_FONT)
                    self.label_position2.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position2 - from_sweep)) > self.eps2:
                        self.current_position2 = float(getattr(device, parameter)())
                        self.label_position2.config(text = f'{"{:.3e}".format(self.current_position2)} / {"{:.3e}".format(from_sweep)}')
                        self.label_position2.after(100, update_position)
                    else:
                        self.pop2.destroy()
                        try_start()
                        
                def slow_approach(steps: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if len(steps) > 0:
                        getattr(device, f'set_{parameter}')(value = steps[0])
                        self.label_position2.after(int(delay * 1000), lambda steps = steps[1:], delay = delay: slow_approach(steps, delay))
                
                if not sweepable:
                    answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                    if answer2 == False:
                        getattr(device, f'set_{parameter}')(value = from_sweep)
                        try_start()
                    elif answer2 == True:
                        _delta = abs(cur_value - from_sweep)
                        step = ratio_sweep * self.delay_factor2
                        nsteps = abs(int(_delta // step) + 1)
                        steps = list(np.linspace(cur_value, from_sweep, nsteps + 1))
                        start_toplevel()
                        self.current_position2 = float(getattr(device, parameter)())
                        update_position()
                        slow_approach(steps, self.delay_factor2)
                    else:
                        return
                        
                else:
                    getattr(device, f'set_{parameter}')(value = from_sweep, speed = ratio_sweep)
                    
                    start_toplevel()
                    self.current_position2 = float(getattr(device, parameter)())
                    update_position()
                    
            elif answer == False:
                try_start()
            else:
                self.start_sweep_flag = False
                return
            
    def pre_double_sweep(self, i = 1, j=2):
        global sweeper_write
        global condition
        device1 = globals()[f'device_to_sweep{i}']
        parameter1 = globals()[f'parameter_to_sweep{i}']
        device2 = globals()[f'device_to_sweep{j}']
        parameter2 = globals()[f'parameter_to_sweep{j}']
        
        def try_start():
            global sweeper_write
            if self.start_sweep_flag:
                self.start_logs()
                sweeper_write = Sweeper_write()
                self.open_graph()
            else:
                self.after(100, try_start)
        
        from_sweep1 = self.__dict__[f'from_sweep{i}']
        to_sweep1 = self.__dict__[f'to_sweep{i}']
        ratio_sweep1 = self.__dict__[f'ratio_sweep{i}']
        
        from_sweep2 = self.__dict__[f'from_sweep{j}']
        to_sweep2 = self.__dict__[f'to_sweep{j}']
        ratio_sweep2 = self.__dict__[f'ratio_sweep{j}']
                
        delta1 = abs(to_sweep1 - from_sweep1)
        delta2 = abs(to_sweep2 - from_sweep2)
        
        try:
            self.eps1 = float(device1.eps[device1.set_options.index(parameter1)])
        except:
            self.eps1 = 0.0001 * delta1
        
        try:
            self.eps2 = float(device2.eps[device2.set_options.index(parameter2)])
        except:
            self.eps2 = 0.0001 * delta2
        
        try:
            cur_value1 = float(getattr(device1, parameter1)())
            cur_value2 = float(getattr(device2, parameter2)())
        except Exception as e:
            print(f'Exception happened in pre-double-sweep: {e}')
            try_start()
            return

        func = condition_2_func(condition, from_sweep2)
        try:
            start_master = optimize.newton(func, x0 = from_sweep1, maxiter = 500)
        except Exception as e:
            messagebox.showerror('Solution not find', f'Exception in pre-double-sweep: {e}')
            return

        if (abs(cur_value1 - start_master) <= self.eps1) and (abs(cur_value2 - from_sweep2) <= self.eps2):
            try_start()
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current (master; slave) is ({cur_value1};{cur_value2}). \nStarting position is ({start_master};{from_sweep2}), go to start?')
            if answer == True:
                
                def start_toplevel():
                    self.pop = tk.Toplevel(self)
                    
                    def center(toplevel):
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop)
                    
                    self.label_approaching = tk.Label(self.pop, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching.grid(row = 0, column = 0)
                    
                    self.label_position = tk.Label(self.pop, text = '', font = LARGE_FONT)
                    self.label_position.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position1 - start_master) > self.eps1) or (abs(self.current_position2 - from_sweep2) > self.eps2):
                        self.current_position1 = float(getattr(device1, parameter1)())
                        self.current_position2 = float(getattr(device2, parameter2)())
                        self.label_position.config(text = f'({"{:.3e}".format(self.current_position1)};{"{:.3e}".format(self.current_position2)}) / ({"{:.3e}".format(start_master)};{"{:.3e}".format(from_sweep2)})')
                        self.label_position.after(100, update_position)
                    else:
                        self.pop.destroy()
                        try_start()
                        
                def slow_approach(steps1: list, steps2: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if max(len(steps1), len(steps2)) > 0:
                        try:
                            getattr(device1, f'set_{parameter1}')(value = steps1[0])
                        except IndexError:
                            pass
                        try:
                            getattr(device2, f'set_{parameter2}')(value = steps2[0])
                        except IndexError:
                            pass
                        self.label_position.after(int(delay * 1000), 
                                                  lambda steps1 = steps1[1:], 
                                                  steps2 = steps2[1:], 
                                                  delay = delay: slow_approach(steps1, steps2, delay))
                
                answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                if answer2 == False:
                    getattr(device1, f'set_{parameter1}')(value = start_master)
                    getattr(device2, f'set_{parameter2}')(value = from_sweep2)
                    try_start()
                elif answer2 == True:
                    
                    _delta1 = abs(cur_value1 - start_master)
                    step1 = ratio_sweep1 * self.__dict__[f'delay_factor{i}']
                    nsteps1 = abs(int(_delta1 // step1) + 1)
                    steps1 = list(np.linspace(cur_value1, start_master, nsteps1 + 1))
                    _delta2 = abs(cur_value2 - from_sweep2)
                    step2 = ratio_sweep2 * self.__dict__[f'delay_factor{j}']
                    nsteps2 = abs(int(_delta2 // step2) + 1)
                    steps2 = list(np.linspace(cur_value2, from_sweep2, nsteps2 + 1))
                    start_toplevel()
                    self.current_position1 = float(getattr(device1, parameter1)())
                    self.current_position2 = float(getattr(device2, parameter2)())
                    update_position()
                    slow_approach(steps1, steps2, max(self.__dict__[f'delay_factor{i}'], self.__dict__[f'delay_factor{j}']))
                                  
                else:
                    return

                    
            elif answer == False:
                try_start()
            else:
                return

    def start_sweeping(self):

        global list_of_devices
        global types_of_devices
        global device_to_sweep1
        global device_to_sweep2
        global parameter_to_sweep1
        global parameter_to_sweep2
        global from_sweep1
        global to_sweep1
        global ratio_sweep1
        global back_ratio_sweep1
        global delay_factor1
        global back_delay_factor1
        global from_sweep2
        global to_sweep2
        global ratio_sweep2
        global back_ratio_sweep2
        global delay_factor2
        global back_delay_factor2
        global parameters_to_read
        global parameter_to_read_dict
        global sweeper_flag1
        global sweeper_flag2
        global sweeper_flag3
        global stop_flag
        global pause_flag
        global condition
        global script
        global interpolated2D
        global uniform2D
        global columns
        global manual_sweep_flags
        global manual_filenames
        global zero_time
        global back_and_forth_master
        global back_and_forth_slave
        global snakemode_master_flag
        #global fastmode_master_flag
        global sweeper_write

        self.start_sweep_flag = True

        if self.status_manual1.get() == 0:

            try:
                self.from_sweep1 = float(self.entry_from1.get())
                from_sweep1 = self.from_sweep1
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from1.get()} to float')
                self.start_sweep_flag = False
                
            try:
                self.to_sweep1 = float(self.entry_to1.get())
                to_sweep1 = self.to_sweep1
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to1.get()} to float')
                self.start_sweep_flag = False
        
        try:
            self.delay_factor1 = float(self.entry_delay_factor1.get())
            delay_factor1 = self.delay_factor1
        except:
            messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delay_factor1.get()} to float')
            self.start_sweep_flag = False
        
        if self.status_manual1.get() == 0:
        
            try:
                self.ratio_sweep1 = float(self.entry_ratio1.get())
                
                if self.back_ratio1_init == '':
                    back_ratio_sweep1 = self.ratio_sweep1
                else:
                    try:
                        back_ratio_sweep1 = float(self.back_ratio1_init)
                    except:
                        messagebox.showerror('Invalid value in "back_ratio1" entrybox', f'Can not convert {self.back_ratio1_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option1 == 'step':
                    self.ratio_sweep1 = self.ratio_sweep1 / self.delay_factor1
                if self.from_sweep1 > self.to_sweep1 and self.ratio_sweep1 > 0:
                    self.ratio_sweep1 = - self.ratio_sweep1
                ratio_sweep1 = self.ratio_sweep1
                
                if self.back_delay_factor1_init == '':
                    back_delay_factor1 = delay_factor1
                else:
                    try:
                        back_delay_factor1 = float(self.back_delay_factor1_init)
                    except:
                        messagebox.showerror('Invalid value in "back_delay_factor1" entrybox', f'Can not convert {self.back_delay_factor1_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option1 == 'step':
                    back_ratio_sweep1 = back_ratio_sweep1 / back_delay_factor1
                if back_ratio_sweep1 * ratio_sweep1 > 0:
                    back_ratio_sweep1 = - back_ratio_sweep1
                
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio1.get()} to float')
                self.start_sweep_flag = False
            
        if self.status_manual2.get() == 0:
            
            try:
                self.from_sweep2 = float(self.entry_from2.get())
                from_sweep2 = self.from_sweep2
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from2.get()} to float')
                self.start_sweep_flag = False
                
            try:
                self.to_sweep2 = float(self.entry_to2.get())
                to_sweep2 = self.to_sweep2
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to2.get()} to float')
                self.start_sweep_flag = False
        
        try:
            self.delay_factor2 = float(self.entry_delay_factor2.get())
            delay_factor2 = self.delay_factor2
        except:
            messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delay_factor2.get()} to float')
            self.start_sweep_flag = False
        
        if self.status_manual2.get() == 0:
        
            try:
                self.ratio_sweep2 = float(self.entry_ratio2.get())
                
                if self.back_ratio2_init == '':
                    back_ratio_sweep2 = self.ratio_sweep2
                else:
                    try:
                        back_ratio_sweep2 = float(self.back_ratio2_init)
                    except:
                        messagebox.showerror('Invalid value in "back_ratio2" entrybox', f'Can not convert {self.back_ratio2_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option2 == 'step':
                    self.ratio_sweep2 = self.ratio_sweep2 / self.delay_factor2
                if self.from_sweep2 > self.to_sweep2 and self.ratio_sweep2 > 0:
                    self.ratio_sweep2 = - self.ratio_sweep2
                ratio_sweep2 = self.ratio_sweep2
                
                if self.back_delay_factor2_init == '':
                    back_delay_factor2 = delay_factor2
                else:
                    try:
                        back_delay_factor2 = float(self.back_delay_factor2_init)
                    except:
                        messagebox.showerror('Invalid value in "back_delay_factor2" entrybox', f'Can not convert {self.back_delay_factor2_init} to float')
                        self.start_sweep_flag = False
                        
                if self.count_option2 == 'step':
                    back_ratio_sweep2 = back_ratio_sweep2 / back_delay_factor2
                if back_ratio_sweep2 * ratio_sweep2 > 0:
                    back_ratio_sweep2 = - back_ratio_sweep2
                
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio2.get()} to float')
                self.start_sweep_flag = False

        def get_key(val, my_dict):
            for key, value in my_dict.items():
                if val == value:
                    return key
        
        self.list_to_read = []
        # asking multichoise to get parameters to read
        selection = self.lstbox_to_read.curselection()
        for i in selection:
            entrada = self.lstbox_to_read.get(i)
            self.list_to_read.append(get_key(entrada, self.dict_lstbox))
        parameters_to_read = self.list_to_read
        parameters_to_read_dict = self.dict_lstbox

        # creating columns
        device_to_sweep1 = list_of_devices[self.combo_to_sweep1.current()]
        parameters1 = device_to_sweep1.set_options
        parameter_to_sweep1 = parameters1[self.sweep_options1.current()]
        
        device_to_sweep2 = list_of_devices[self.combo_to_sweep2.current()]
        parameters2 = device_to_sweep2.set_options
        parameter_to_sweep2 = parameters2[self.sweep_options2.current()]
        
        columns_device1 = self.combo_to_sweep1['values'][self.combo_to_sweep1.current()]
        columns_parameters1 = self.sweep_options1['values'][self.sweep_options1.current()]
        
        columns_device2 = self.combo_to_sweep2['values'][self.combo_to_sweep2.current()]
        columns_parameters2 = self.sweep_options2['values'][self.sweep_options2.current()]
        
        columns = ['time', columns_device1 + '.' + columns_parameters1 + '_sweep',
                   columns_device2 + '.' + columns_parameters2 + '_sweep']
            
        for option in parameters_to_read:
            columns.append(parameters_to_read_dict[option])

        # fixing sweeper parmeters
        
        self.determine_filename_sweep()
        
        interpolated2D = self.interpolated
        uniform2D = self.uniform
        
        for i in range(1, 3):
            self.save_manual_status(i)
        self.save_back_and_forth_master_status()
        self.save_back_and_forth_slave_status()
        condition = self.text_condition.get(1.0, tk.END)[:-1]
        script = self.script
        manual_sweep_flags = self.manual_sweep_flags
        manual_filenames = self.manual_filenames

        self.rewrite_preset()

        if self.start_sweep_flag:
            zero_time = time.perf_counter()
            stop_flag = False
            pause_flag = False
            sweeper_flag1 = False
            sweeper_flag2 = True
            sweeper_flag3 = False
            snakemode_master_flag = self.status_snakemode_master.get()
            #fastmode_master_flag = self.status_fastmode_master.get()
            conds = rm_all(condition)
            if len(conds) == 1:
                conds = conds[0]
                if ('x' in conds or 'X' in conds) and ('y' in conds or 'Y' in conds) and ('==' in conds or '=' in conds):
                    self.pre_double_sweep()
            else:
                self.pre_sweep1()
                self.pre_sweep2()


class Sweeper3d(tk.Frame):

    def __init__(self, parent, controller):

        tk.Frame.__init__(self, parent)
        
        self.preset = pd.read_csv(globals()['sweeper3d_path'], sep = ',', dtype = str)
        self.preset = self.preset.fillna('')
        self.combo_to_sweep1_current = int(self.preset['combo_to_sweep1'].values[0])
        self.sweep_options1_current = int(self.preset['sweep_options1'].values[0])
        self.combo_to_sweep2_current = int(self.preset['combo_to_sweep2'].values[0])
        self.sweep_options2_current = int(self.preset['sweep_options2'].values[0])
        self.combo_to_sweep3_current = int(self.preset['combo_to_sweep3'].values[0])
        self.sweep_options3_current = int(self.preset['sweep_options3'].values[0])
        self.from1_init = self.preset['from1'].values[0]
        self.to1_init = self.preset['to1'].values[0]
        self.ratio1_init = self.preset['ratio1'].values[0]
        self.back_ratio1_init = self.preset['back_ratio1'].values[0]
        self.count_option1 = self.preset['count_option1'][0]
        self.delay_factor1_init = self.preset['delay_factor1'].values[0]
        self.back_delay_factor1_init = self.preset['back_delay_factor1'].values[0]
        self.from2_init = self.preset['from2'].values[0]
        self.to2_init = self.preset['to2'].values[0]
        self.ratio2_init = self.preset['ratio2'].values[0]
        self.back_ratio2_init = self.preset['back_ratio2'].values[0]
        self.count_option2 = self.preset['count_option2'][0]
        self.delay_factor2_init = self.preset['delay_factor2'].values[0]
        self.back_delay_factor2_init = self.preset['back_delay_factor2'].values[0]
        self.from3_init = self.preset['from3'].values[0]
        self.to3_init = self.preset['to3'].values[0]
        self.ratio3_init = self.preset['ratio3'].values[0]
        self.back_ratio3_init = self.preset['back_ratio3'].values[0]
        self.count_option3 = self.preset['count_option3'][0]
        self.delay_factor3_init = self.preset['delay_factor3'].values[0]
        self.back_delay_factor3_init = self.preset['back_delay_factor3'].values[0]
        self.manual_filenames = [self.preset['manual_filename1'].values[0], self.preset['manual_filename2'].values[0], self.preset['manual_filename3'].values[0]]
        self.status_back_and_forth_master = tk.IntVar(value = int(self.preset['status_back_and_forth1'].values[0]))
        self.status_manual1 = tk.IntVar(value = int(self.preset['status_manual1'].values[0]))
        self.status_back_and_forth_slave = tk.IntVar(value = int(self.preset['status_back_and_forth2'].values[0]))
        #self.status_fastmode_master = tk.IntVar(value = int(self.preset['status_fastmode2'].values[0]))
        self.status_snakemode_master = tk.IntVar(value = int(self.preset['status_snakemode2'].values[0]))
        self.status_manual2 = tk.IntVar(value = int(self.preset['status_manual2'].values[0]))
        self.status_back_and_forth_slave_slave = tk.IntVar(value = int(self.preset['status_back_and_forth3'].values[0]))
        #self.status_fastmode_slave = tk.IntVar(value = int(self.preset['status_fastmode3'].values[0]))
        self.status_snakemode_slave = tk.IntVar(value = int(self.preset['status_snakemode3'].values[0]))
        self.status_manual3 = tk.IntVar(value = int(self.preset['status_manual3'].values[0]))
        self.filename_sweep = self.preset['filename_sweep'].values[0]
        self.filename_sweep = fix_unicode(self.filename_sweep)
        self.condition = str(self.preset['condition'].values[0])
        self.interpolated = int(self.preset['interpolated'].values[0])
        self.uniform = int(self.preset['uniform'].values[0])
        
        self.filename_index = get_filename_index(filename = self.filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        
        #updates filename with respect to date and current index
        try:
            path = os.path.normpath(self.filename_sweep)
            path = path.split(os.sep)
            name = path[-1]
            if '.' in name: #if name has the extension, remove it
                name = name[:len(name) - name[::-1].index('.') - 1]
            if int(name[:2]) in np.linspace(0, 99, 100, dtype = int) \
                and int(name[2:4]) in np.linspace(1, 12, 12, dtype = int) \
                    and int(name[4:6]) in np.linspace(1, 32, 32, dtype = int): #If filename is in yy.mm.dd format, make it current day
                self.filename_sweep = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}-{self.filename_index}.csv')
                if ':' in self.filename_sweep and ':\\' not in self.filename_sweep:
                    i = self.filename_sweep.index(':')
                    self.filename_sweep = self.filename_sweep[:i+1] + '\\' + self.filename_sweep[i+1:]
        except:
            path = os.path.normpath(self.filename_sweep)
            path = path.split(os.sep)
            name = path[-1]
            if '.' in name: #if name has the extension, remove it
                name = name[:len(name) - name[::-1].index('.') - 1] 
            self.filename_sweep = os.path.join(*path[:-1], f'{name}-{self.filename_index}.csv')
            if ':' in self.filename_sweep and ':\\' not in self.filename_sweep:
                i = self.filename_sweep.index(':')
                self.filename_sweep = self.filename_sweep[:i+1] + '\\' + self.filename_sweep[i+1:]
        
        globals()['setget_flag'] = False
        #globals()['parameters_to_read'] = globals()['parameters_to_read_copy']
        
        label = tk.Label(self, text='3dSweeper', font=LARGE_FONT)
        label.pack(pady=10, padx=10)

        button_home = tk.Button(self, text='Back to Home',
                                 command=lambda: controller.show_frame(StartPage))
        button_home.pack()

        label_to_sweep1 = tk.Label(self, text='To sweep:', font=LARGE_FONT)
        label_to_sweep1.place(relx=0.15, rely=0.12)

        label_to_sweep2 = tk.Label(self, text='To sweep:', font=LARGE_FONT)
        label_to_sweep2.place(relx=0.3, rely=0.12)

        label_to_sweep3 = tk.Label(self, text='To sweep:', font=LARGE_FONT)
        label_to_sweep3.place(relx=0.45, rely=0.12)

        label_to_read = tk.Label(self, text='To read:', font=LARGE_FONT)
        label_to_read.place(relx=0.6, rely=0.12)

        label_master = tk.Label(self, text = 'Master', font = LARGE_FONT)
        label_master.place(relx = 0.15, rely = 0.17)
        
        label_slave = tk.Label(self, text = 'Slave', font = LARGE_FONT)
        label_slave.place(relx = 0.3, rely = 0.17)
        
        label_slave_slave = tk.Label(self, text = 'Slave slave', font = LARGE_FONT)
        label_slave_slave.place(relx = 0.45, rely = 0.17)
        
        label_devices = tk.Label(self, text = 'Devices:', font=LARGE_FONT)
        label_devices.place(relx = 0.05, rely = 0.21)
        
        self.lstbox_height = len(parameters_to_read) / 47
        
        self.button_update_sweep = tk.Button(self, text = 'Update sweep', command = lambda: self.update_sweep_configuration)
        self.button_update_sweep.place(relx = 0.6, rely = 0.21 + self.lstbox_height)
        
        self.button_pause = tk.Button(self, text = '⏸️', font = LARGE_FONT, command = lambda: self.pause())
        self.button_pause.place(relx = 0.6, rely = 0.25 + self.lstbox_height)
        CreateToolTip(self.button_pause, 'Pause\Continue sweep')
        
        self.button_stop = tk.Button(self, text = '⏹️', font = LARGE_FONT, command = lambda: self.stop())
        self.button_stop.place(relx = 0.6335, rely = 0.25 + self.lstbox_height)
        CreateToolTip(self.button_stop, 'Stop sweep')
        
        self.button_tozero = tk.Button(self, text = 'To zero', width = 11, command = lambda: self.tozero())
        self.button_tozero.place(relx = 0.6, rely = 0.3 + self.lstbox_height)
        
        self.button_start_sweeping = tk.Button(
            self, text="▶", command=lambda: self.start_sweeping(), font = LARGE_FONT)
        self.button_start_sweeping.place(relx=0.675, rely=0.21 + self.lstbox_height, height= 90, width=30)
        CreateToolTip(self.button_start_sweeping, 'Start sweeping')

        self.combo_to_sweep1 = ttk.Combobox(self, value=list_of_devices_addresses)
        self.combo_to_sweep1.bind(
            "<<ComboboxSelected>>", self.update_sweep_parameters1)
        self.combo_to_sweep1.place(relx=0.15, rely=0.21)
        
        self.sweep_options1 = ttk.Combobox(self)
        self.sweep_options1.bind(
            "<<ComboboxSelected>>", self.update_sweep_options1)
        self.sweep_options1.place(relx=0.15, rely=0.25)

        self.sweep_options2 = ttk.Combobox(self)
        self.sweep_options2.bind(
            "<<ComboboxSelected>>", self.update_sweep_options2)
        self.sweep_options2.place(relx=0.3, rely=0.25)

        self.sweep_options3 = ttk.Combobox(self)
        self.sweep_options3.bind(
            "<<ComboboxSelected>>", self.update_sweep_options3)
        self.sweep_options3.place(relx=0.45, rely=0.25)
    
        try:
            self.combo_to_sweep1.current(self.combo_to_sweep1_current)
            self.update_sweep_parameters1(event = None)
        except:
            self.combo_to_sweep1.current(0)
            if self.combo_to_sweep1['values'][0] != '':
                self.update_sweep_parameters1(event = None)
                
        global back_and_forth_master
        global back_and_forth_slave
        global back_and_forth_slave_slave
        
        back_and_forth_master = 1
        back_and_forth_slave = 1
        back_and_forth_slave_slave = 1
    
        self.back_and_forth_master_count = 2
        
        class BackAndForthMaster(object):
            
            def __init__(self, widget, parent):
                self.master_toplevel = None
                self.master_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.master_widget.bbox('all')
                x = x + self.master_widget.winfo_rootx()
                y = y + self.master_widget.winfo_rooty()
                self.master_toplevel = tw = tk.Toplevel(self.master_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                label_back_and_forth_slave = tk.Label(tw, text = 'Set number of back and forth\n walks for slave axis', font = LARGE_FONT)
                label_back_and_forth_slave.grid(row = 0, column = 0, pady = 2)
                
                self.combo_back_and_forth_master = ttk.Combobox(tw, value = [2, 'custom', 'continious'])
                if self.parent.status_back_and_forth_master.get() == 0:
                    self.combo_back_and_forth_master.current(0)
                else:
                    self.combo_back_and_forth_master.current(1)
                    self.combo_back_and_forth_master.delete(0, tk.END)
                    self.combo_back_and_forth_master.insert(0, self.parent.back_and_forth_master_count)
                self.combo_back_and_forth_master.grid(row = 1, column = 0, pady = 2)
                
                def update_back_and_forth_master_count():
                    if self.combo_back_and_forth_master.current() == 0:
                        self.parent.back_and_forth_master_count = 2
                    elif self.combo_back_and_forth_master.current() == -1:
                        self.parent.back_and_forth_master_count = int(self.combo_back_and_forth_slave.get())
                    elif self.combo_back_and_forth_master.current() == 2:
                        self.parent.back_and_forth_master_count = int(1e5)
                    else:
                        raise Exception(f'Insert proper back_and_forth_master. Should be int, but given {type(self.combo_back_and_forth_master.get())}')
                    
                    self.parent.entry_ratio1.delete(0, tk.END)
                    self.parent.entry_ratio1.insert(0, self.entry_ratio1.get())
                    self.parent.back_ratio1_init = self.entry_back_ratio1.get()
                    
                    self.parent.entry_delay_factor1.delete(0, tk.END)
                    self.parent.entry_delay_factor1.insert(0, self.entry_delay_factor1.get())
                    self.parent.back_delay_factor1_init = self.entry_back_delay_factor1.get()
                
                button_set_back_and_forth_master = tk.Button(tw, text = 'Set', command = update_back_and_forth_master_count)
                button_set_back_and_forth_master.grid(row = 1, column = 1, pady = 2)
                
                def hide_toplevel():
                    tw = self.master_toplevel
                    self.master_toplevel = None
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
            def update_ratio1(self):
                tw = self.master_toplevel
                
                count_option1 = self.parent.count_option1
                
                self.entry_ratio_label = tk.Label(tw, text = f'Forward {count_option1}')
                self.entry_ratio_label.grid(row = 2, column = 0, pady = 2)
                
                self.entry_back_ratio_label = tk.Label(tw, text = f'Back {count_option1}')
                self.entry_back_ratio_label.grid(row = 2, column = 1, pady = 2)
                
                self.entry_ratio1 = tk.Entry(tw)
                self.entry_ratio1.insert(0, self.parent.entry_ratio1.get())
                self.entry_ratio1.grid(row = 3, column = 0, pady = 2)
                
                self.entry_back_ratio1 = tk.Entry(tw)
                self.entry_back_ratio1.insert(0, self.parent.back_ratio1_init)
                self.entry_back_ratio1.grid(row = 3, column = 1, pady = 2)
                
                self.entry_delay_factor_label = tk.Label(tw, text = 'Forward delay factor')
                self.entry_delay_factor_label.grid(row = 4, column = 0, pady = 2)
                
                self.entry_back_delay_factor_label = tk.Label(tw, text = 'Back delay factor')
                self.entry_back_delay_factor_label.grid(row = 4, column = 1, pady = 2)
                
                self.entry_delay_factor1 = tk.Entry(tw)
                self.entry_delay_factor1.insert(0, self.parent.entry_delay_factor1.get())
                self.entry_delay_factor1.grid(row = 5, column = 0, pady = 2)
                
                self.entry_back_delay_factor1 = tk.Entry(tw)
                self.entry_back_delay_factor1.insert(0, self.parent.back_delay_factor1_init)
                self.entry_back_delay_factor1.grid(row = 5, column = 1, pady = 2)
                
        def CreateMasterToplevel(widget, parent):
            
            toplevel = BackAndForthMaster(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                toplevel.update_ratio1()
                
            widget.bind('<Button-3>', show)
    
        self.checkbox_back_and_forth_master = ttk.Checkbutton(self,
                                           variable=self.status_back_and_forth_master, onvalue=1,
                                           offvalue=0, command=lambda: self.save_back_and_forth_master_status())
        self.checkbox_back_and_forth_master.place(relx=0.22, rely=0.62)
        CreateMasterToplevel(self.checkbox_back_and_forth_master, self)
        
        self.label_back_and_forth_master = tk.Label(self, text = '🔁', font = SUPER_LARGE)
        self.label_back_and_forth_master.place(relx = 0.2335, rely = 0.61)
        CreateToolTip(self.label_back_and_forth_master, 'Back and forth sweep\nfor this axis \n Right click to configure')
        CreateMasterToplevel(self.label_back_and_forth_master, self)

        self.combo_to_sweep2 = ttk.Combobox(self, value=list_of_devices_addresses)
        self.combo_to_sweep2.bind(
            "<<ComboboxSelected>>", self.update_sweep_parameters2)
        self.combo_to_sweep2.place(relx=0.3, rely=0.21)
        
        try:
            self.combo_to_sweep2.current(self.combo_to_sweep2_current)
            self.update_sweep_parameters2(event = None)
        except:
            self.combo_to_sweep2.current(0)
            if self.combo_to_sweep2['values'][0] != '':
                self.update_sweep_parameters2(event = None)
    
        self.back_and_forth_slave_count = 2
        
        class BackAndForthSlave(object):
            
            def __init__(self, widget, parent):
                self.slave_toplevel = None
                self.slave_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.slave_widget.bbox('all')
                x = x + self.slave_widget.winfo_rootx()
                y = y + self.slave_widget.winfo_rooty()
                self.slave_toplevel = tw = tk.Toplevel(self.slave_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                label_back_and_forth_slave = tk.Label(tw, text = 'Set number of back and forth\n walks for slave axis', font = LARGE_FONT)
                label_back_and_forth_slave.grid(row = 0, column = 0, pady = 2)
                
                self.combo_back_and_forth_slave = ttk.Combobox(tw, value = [2, 'custom', 'continious'])
                if self.parent.status_back_and_forth_slave.get() == 0:
                    self.combo_back_and_forth_slave.current(0)
                else:
                    self.combo_back_and_forth_slave.current(1)
                    self.combo_back_and_forth_slave.delete(0, tk.END)
                    self.combo_back_and_forth_slave.insert(0, self.parent.back_and_forth_slave_count)
                self.combo_back_and_forth_slave.grid(row = 1, column = 0, pady = 2)
                
                def update_back_and_forth_slave_count():
                    if self.combo_back_and_forth_slave.current() == 0:
                        self.parent.back_and_forth_slave_count = 2
                    elif self.combo_back_and_forth_slave.current() == -1:
                        self.parent.back_and_forth_slave_count = int(self.combo_back_and_forth_slave.get())
                    elif self.combo_back_and_forth_slave.current() == 2:
                        self.parent.back_and_forth_slave_count = int(1e5)
                    else:
                        raise Exception(f'Insert proper back_and_forth_master. Should be int, but given {type(self.combo_back_and_forth_slave.get())}')
                
                    self.parent.entry_ratio2.delete(0, tk.END)
                    self.parent.entry_ratio2.insert(0, self.entry_ratio2.get())
                    self.parent.back_ratio2_init = self.entry_back_ratio2.get()
                    
                    self.parent.entry_delay_factor2.delete(0, tk.END)
                    self.parent.entry_delay_factor2.insert(0, self.entry_delay_factor2.get())
                    self.parent.back_delay_factor2_init = self.entry_back_delay_factor2.get()
                
                button_set_back_and_forth_slave = tk.Button(tw, text = 'Set', command = update_back_and_forth_slave_count)
                button_set_back_and_forth_slave.grid(row = 1, column = 1, pady = 2)
                
                #label_fast_master = tk.Label(tw, text = 'Fast mode')
                #label_fast_master.grid(row = 2, column = 0, pady = 2)
                
                label_snake_master = tk.Label(tw, text = 'Snake mode')
                label_snake_master.grid(row = 2, column = 0, pady = 2)
                
                def fastmode_pressed():
                    
                    self.parent.preset.loc[0, 'status_fastmode2'] = self.parent.status_fastmode_master.get()
                    self.parent.preset.to_csv(globals()['sweeper3d_path'], index = False)
                    
                    if self.parent.status_fastmode_master.get() == 1:
                        self.checkbox_snake_master.config(state = 'disable')
                    else:
                        self.checkbox_snake_master.config(state = 'normal')
                    
                def snakemode_pressed():
                    
                    self.parent.preset.loc[0, 'status_snakemode2'] = self.parent.status_snakemode_master.get()
                    self.parent.preset.to_csv(globals()['sweeper3d_path'], index = False)
                    
                    #if self.parent.status_snakemode_master.get() == 1:
                    #    self.checkbox_fast_master.config(state = 'disable')
                    #else:
                    #   self.checkbox_fast_master.config(state = 'normal')
                
                #self.checkbox_fast_master = ttk.Checkbutton(tw, variable = self.parent.status_fastmode_master, onvalue = 1, offvalue = 0, command = fastmode_pressed)
                #self.checkbox_fast_master.grid(row = 2, column = 1, pady = 1)
                
                #if self.parent.status_snakemode_master.get() == 1:
                #    self.checkbox_fast_master.config(state = 'disable')
                
                self.checkbox_snake_master = ttk.Checkbutton(tw, variable = self.parent.status_snakemode_master, onvalue = 1, offvalue = 0, command = snakemode_pressed)
                self.checkbox_snake_master.grid(row = 2, column = 1, pady = 1)
                
                #if self.parent.status_fastmode_master.get() == 1:
                #    self.checkbox_snake_master.config(state = 'disable')
                
                def hide_toplevel():
                    tw = self.slave_toplevel
                    self.slave_toplevel = None
                    #if self.parent.status_fastmode_master.get() == 1:
                    #    globals()['fastmode_master_flag'] = True
                    #else:
                    #    globals()['fastmode_master_flag'] = False
                    if self.parent.status_snakemode_master.get() == 1:
                        globals()['snakemode_master_flag'] = True
                    else:
                        globals()['snakemode_master_flag'] = False
                
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
            def update_ratio2(self):
                tw = self.slave_toplevel
                
                count_option2 = self.parent.count_option2
                
                self.entry_ratio_label = tk.Label(tw, text = f'Forward {count_option2}')
                self.entry_ratio_label.grid(row = 3, column = 0, pady = 2)
                
                self.entry_back_ratio_label = tk.Label(tw, text = f'Back {count_option2}')
                self.entry_back_ratio_label.grid(row = 3, column = 1, pady = 2)
                
                self.entry_ratio2 = tk.Entry(tw)
                self.entry_ratio2.insert(0, self.parent.entry_ratio2.get())
                self.entry_ratio2.grid(row = 4, column = 0, pady = 2)
                
                self.entry_back_ratio2 = tk.Entry(tw)
                self.entry_back_ratio2.insert(0, self.parent.back_ratio2_init)
                self.entry_back_ratio2.grid(row = 4, column = 1, pady = 2)
                
                self.entry_delay_factor_label = tk.Label(tw, text = 'Forward delay factor')
                self.entry_delay_factor_label.grid(row = 5, column = 0, pady = 2)
                
                self.entry_back_delay_factor_label = tk.Label(tw, text = 'Back delay factor')
                self.entry_back_delay_factor_label.grid(row = 5, column = 1, pady = 2)
                
                self.entry_delay_factor2 = tk.Entry(tw)
                self.entry_delay_factor2.insert(0, self.parent.entry_delay_factor2.get())
                self.entry_delay_factor2.grid(row = 6, column = 0, pady = 2)
                
                self.entry_back_delay_factor2 = tk.Entry(tw)
                self.entry_back_delay_factor2.insert(0, self.parent.back_delay_factor2_init)
                self.entry_back_delay_factor2.grid(row = 6, column = 1, pady = 2)
                
        def CreateSlaveToplevel(widget, parent):
            
            toplevel = BackAndForthSlave(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                toplevel.update_ratio2()
                
            widget.bind('<Button-3>', show)
    
        self.checkbox_back_and_forth_slave = ttk.Checkbutton(self,
                                           variable=self.status_back_and_forth_slave, onvalue=1,
                                           offvalue=0, command=lambda: self.save_back_and_forth_slave_status())
        self.checkbox_back_and_forth_slave.place(relx=0.35, rely=0.62)
        CreateSlaveToplevel(self.checkbox_back_and_forth_slave, self)
        
        self.label_back_and_forth_slave = tk.Label(self, text = '🔁', font = SUPER_LARGE)
        self.label_back_and_forth_slave.place(relx = 0.3635, rely = 0.61)
        CreateToolTip(self.label_back_and_forth_slave, 'Back and forth sweep\nfor this axis \n Right click to configure')
        CreateSlaveToplevel(self.label_back_and_forth_slave, self)

        self.combo_to_sweep3 = ttk.Combobox(self, value=list_of_devices_addresses)
        self.combo_to_sweep3.current(0)
        self.combo_to_sweep3.bind(
            "<<ComboboxSelected>>", self.update_sweep_parameters3)
        self.combo_to_sweep3.place(relx=0.45, rely=0.21)
        
        try:
            self.combo_to_sweep3.current(self.combo_to_sweep3_current)
            self.update_sweep_parameters3(event = None)
        except:
            self.combo_to_sweep3.current(0)
            if self.combo_to_sweep3['values'][0] != '':
                self.update_sweep_parameters3(event = None)
        
        self.back_and_forth_slave_slave_count = 2
        
        class BackAndForthSlaveSlave(object):
            
            def __init__(self, widget, parent):
                self.slave_slave_toplevel = None
                self.slave_slave_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.slave_slave_widget.bbox('all')
                x = x + self.slave_slave_widget.winfo_rootx()
                y = y + self.slave_slave_widget.winfo_rooty()
                self.slave_slave_toplevel = tw = tk.Toplevel(self.slave_slave_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                label_back_and_forth_slave = tk.Label(tw, text = 'Set number of back and forth\n walks for slave-slave axis', font = LARGE_FONT)
                label_back_and_forth_slave.grid(row = 0, column = 0, pady = 2)
                
                self.combo_back_and_forth_slave_slave = ttk.Combobox(tw, value = [2, 'custom', 'continious'])
                if self.parent.status_back_and_forth_slave_slave.get() == 0:
                    self.combo_back_and_forth_slave_slave.current(0)
                else:
                    self.combo_back_and_forth_slave_slave.current(1)
                    self.combo_back_and_forth_slave_slave.delete(0, tk.END)
                    self.combo_back_and_forth_slave_slave.insert(0, self.parent.back_and_forth_slave_slave_count)
                self.combo_back_and_forth_slave_slave.grid(row = 1, column = 0, pady = 2)
                
                def update_back_and_forth_slave_slave_count():
                    if self.combo_back_and_forth_slave_slave.current() == 0:
                        self.parent.back_and_forth_slave_slave_count = 2
                    elif self.parent.combo_back_and_forth_slave_slave.current() == -1:
                        self.back_and_forth_slave_slave_count = int(self.combo_back_and_forth_slave.get())
                    elif self.parent.combo_back_and_forth_slave_slave.current() == 2:
                        self.back_and_forth_slave_slave_count = int(1e5)
                    else:
                        raise Exception(f'Insert proper back_and_forth_master. Should be int, but given {type(self.combo_back_and_forth_slave_slave.get())}')
                
                    self.parent.entry_ratio3.delete(0, tk.END)
                    self.parent.entry_ratio3.insert(0, self.entry_ratio3.get())
                    self.parent.back_ratio3_init = self.entry_back_ratio3.get()
                    
                    self.parent.entry_delay_factor3.delete(0, tk.END)
                    self.parent.entry_delay_factor3.insert(0, self.entry_delay_factor3.get())
                    self.parent.back_delay_factor3_init = self.entry_back_delay_factor3.get()
                
                button_set_back_and_forth_slave_slave = tk.Button(tw, text = 'Set', command = update_back_and_forth_slave_slave_count)
                button_set_back_and_forth_slave_slave.grid(row = 1, column = 1, pady = 2)
                
                #label_fast_master = tk.Label(tw, text = 'Fast mode')
                #label_fast_master.grid(row = 2, column = 0, pady = 2)
                
                label_snake_master = tk.Label(tw, text = 'Snake mode')
                label_snake_master.grid(row = 2, column = 0, pady = 2)
                
                def fastmode_pressed():
                    
                    self.parent.preset.loc[0, 'status_fastmode3'] = self.parent.status_fastmode_slave.get()
                    self.parent.preset.to_csv(globals()['sweeper3d_path'], index = False)
                    
                    if self.parent.status_fastmode_slave.get() == 1:
                        self.checkbox_snake_slave.config(state = 'disable')
                    else:
                        self.checkbox_snake_slave.config(state = 'normal')
                    
                def snakemode_pressed():
                    
                    self.parent.preset.loc[0, 'status_snakemode3'] = self.parent.status_snakemode_slave.get()
                    self.parent.preset.to_csv(globals()['sweeper3d_path'], index = False)
                    
                    #if self.parent.status_snakemode_slave.get() == 1:
                    #    self.checkbox_fast_slave.config(state = 'disable')
                    #else:
                    #    self.checkbox_fast_slave.config(state = 'normal')
                
                #self.checkbox_fast_slave = ttk.Checkbutton(tw, variable = self.parent.status_fastmode_slave, onvalue = 1, offvalue = 0, command = fastmode_pressed)
                #self.checkbox_fast_slave.grid(row = 2, column = 1, pady = 1)
                
                #if self.parent.status_snakemode_slave.get() == 1:
                #    self.checkbox_fast_slave.config(state = 'disable')
                
                self.checkbox_snake_slave = ttk.Checkbutton(tw, variable = self.parent.status_snakemode_slave, onvalue = 1, offvalue = 0, command = snakemode_pressed)
                self.checkbox_snake_slave.grid(row = 2, column = 1, pady = 1)
                
                #if self.parent.status_fastmode_slave.get() == 1:
                #    self.checkbox_snake_slave.config(state = 'disable')
                
                def hide_toplevel():
                    tw = self.slave_slave_toplevel
                    self.slave_slave_toplevel = None
                    if self.parent.status_snakemode_slave.get() == 1:
                        globals()['snakemode_slave_flag'] = True
                    else:
                        globals()['snakemode_slave_flag'] = False
                
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
            def update_ratio3(self):
                tw = self.slave_slave_toplevel
                
                count_option3 = self.parent.count_option3
                
                self.entry_ratio_label = tk.Label(tw, text = f'Forward {count_option3}')
                self.entry_ratio_label.grid(row = 3, column = 0, pady = 2)
                
                self.entry_back_ratio_label = tk.Label(tw, text = f'Back {count_option3}')
                self.entry_back_ratio_label.grid(row = 3, column = 1, pady = 2)
                
                self.entry_ratio3 = tk.Entry(tw)
                self.entry_ratio3.insert(0, self.parent.entry_ratio3.get())
                self.entry_ratio3.grid(row = 4, column = 0, pady = 2)
                
                self.entry_back_ratio3 = tk.Entry(tw)
                self.entry_back_ratio3.insert(0, self.parent.back_ratio3_init)
                self.entry_back_ratio3.grid(row = 4, column = 1, pady = 2)
                
                self.entry_delay_factor_label = tk.Label(tw, text = 'Forward delay factor')
                self.entry_delay_factor_label.grid(row = 5, column = 0, pady = 2)
                
                self.entry_back_delay_factor_label = tk.Label(tw, text = 'Back delay factor')
                self.entry_back_delay_factor_label.grid(row = 5, column = 1, pady = 2)
                
                self.entry_delay_factor3 = tk.Entry(tw)
                self.entry_delay_factor3.insert(0, self.parent.entry_delay_factor3.get())
                self.entry_delay_factor3.grid(row = 6, column = 0, pady = 2)
                
                self.entry_back_delay_factor3 = tk.Entry(tw)
                self.entry_back_delay_factor3.insert(0, self.parent.back_delay_factor3_init)
                self.entry_back_delay_factor3.grid(row = 6, column = 1, pady = 2)
                
        def CreateSlaveSlaveToplevel(widget, parent):
            
            toplevel = BackAndForthSlaveSlave(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                toplevel.update_ratio3()
                
            widget.bind('<Button-3>', show)
    
        self.checkbox_back_and_forth_slave_slave = ttk.Checkbutton(self,
                                           variable=self.status_back_and_forth_slave_slave, onvalue=1,
                                           offvalue=0, command=lambda: self.save_back_and_forth_slave_slave_status())
        self.checkbox_back_and_forth_slave_slave.place(relx=0.5, rely=0.62)
        CreateSlaveSlaveToplevel(self.checkbox_back_and_forth_slave_slave, self)
        
        self.label_back_and_forth_slave = tk.Label(self, text = '🔁', font = SUPER_LARGE)
        self.label_back_and_forth_slave.place(relx = 0.5135, rely = 0.61)
        CreateToolTip(self.label_back_and_forth_slave, 'Back and forth sweep\nfor this axis \n Right click to configure')
        CreateSlaveSlaveToplevel(self.label_back_and_forth_slave, self)

        def stepper_mode():
            global stepper_flag
            
            if stepper_flag == True:
                stepper_flag = False
            elif stepper_flag == False:
                stepper_flag = True
        
        self.checkbox_stepper = tk.Checkbutton(self, text = r'🦶', font = LARGE_FONT, command = stepper_mode)
        if stepper_flag == True:
            self.checkbox_stepper.select()
        self.checkbox_stepper.place(relx = 0.55, rely = 0.615)
        CreateToolTip(self.checkbox_stepper, 'Stepper mode')

        self.save_back_and_forth_master_status()
        self.save_back_and_forth_slave_status()
        self.save_back_and_forth_slave_slave_status()

        self.devices = tk.StringVar()
        self.devices.set(value=parameters_to_read)
        self.lstbox_to_read = tk.Listbox(self, listvariable=self.devices,
                                         selectmode='multiple', exportselection=False,
                                         width=40, height=len(parameters_to_read) * 1)
        self.lstbox_to_read.place(relx=0.6, rely=0.17)
        
        if len(parameters_to_read) < 10:
            self.lstbox_to_read.place(relx=0.6, rely=0.16)
        else:
            self.lstbox_height = 18 / 47
            self.lstbox_to_read.place(relx=0.6, rely=0.16, height = 300)
            self.button_pause.place(relx = 0.6, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.6375, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.675, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.6, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.6, rely = 0.21 + self.lstbox_height)
            
        self.lstbox_to_read.bind('<Button-3>', self.update_listbox)
        
        scrollbar= ttk.Scrollbar(self, orient = 'vertical')
        scrollbar.place(relx = 0.8, rely = 0.16, height = 75)
        
        self.lstbox_to_read.config(yscrollcommand= scrollbar.set)
        scrollbar.config(command= self.lstbox_to_read.yview)
        
        self.dict_lstbox = {}
        
        for parameter in parameters_to_read:
            self.dict_lstbox[parameter] = parameter
        
        class ChangeName(object):
            
            def __init__(self, widget, parent):
                self.name_toplevel = None
                self.name_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x = y = 0
                x = x + self.name_widget.winfo_rootx()
                y = y + self.name_widget.winfo_rooty()
                self.name_toplevel = tw = tk.Toplevel(self.name_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_names = tk.Label(tw, text = 'Change names:', font = LARGE_FONT)
                label_names.grid(row = 0, column = 0, pady = 2)
                    
                def update_combo_set_parameters(event, interval = 100):
                    global types_of_devices
                    global list_of_devices
                    ind = self.combo_devices.current()
                    class_of_sweeper_device = types_of_devices[ind]
                    device = list_of_devices[ind]
                    
                    if self.combo_devices.current() != -1:
                        self.selected_device = ind
                    if class_of_sweeper_device != 'Not a class':
                        self.combo_set_parameters['values'] = getattr(device, 'set_options')
                        self.combo_set_parameters.after(interval)
                    else:
                        self.combo_set_parameters['values'] = ['']
                        self.combo_set_parameters.current(0)
                        self.combo_set_parameters.after(interval)

                def update_names_devices():
                    new_device_name = self.combo_devices.get()
                    new_device_values = list(self.combo_devices['values'])
                    new_device_values[self.selected_device] = new_device_name
                    self.combo_devices['values'] = new_device_values
                    self.combo_devices.after(1)
                    
                    try:
                        self.parent.combo_to_sweep1['values'] = new_device_values
                        self.parent.combo_to_sweep1.current(self.selected_device)
                    except:
                        pass
                    try:
                        self.parent.combo_to_sweep2['values'] = new_device_values
                        self.parent.combo_to_sweep2.current(self.selected_device)
                    except:
                        pass
                    try:
                        self.parent.combo_to_sweep3['values'] = new_device_values
                        self.parent.combo_to_sweep3.current(self.selected_device)
                    except:
                        pass
                    
                    self.parent.after(1)
                    
                def update_names_set_parameters():
                    new_set_parameter_name = self.combo_set_parameters.get()
                    new_set_parameters_values = list(self.combo_set_parameters['values'])
                    new_set_parameters_values[self.selected_set_option] = new_set_parameter_name
                    self.combo_set_parameters['values'] = new_set_parameters_values
                    try:
                        self.parent.sweep_options1['values'] = new_set_parameters_values
                        self.parent.sweep_options1.current(self.selected_set_options)
                    except:
                        pass
                    try:
                        self.parent.sweep_options2['values'] = new_set_parameters_values
                        self.parent.sweep_options2.current(self.selected_set_options)
                    except:
                        pass
                    try:
                        self.parent.combo_to_sweep3['values'] = new_set_parameters_values
                        self.parent.combo_to_sweep3.current(self.selected_device)
                    except:
                        pass

                    self.parent.after(1)
                    
                def update_names_get_parameters(interval = 1000):
                    new_get_parameter_name = self.get_current.get()
                    new_get_parameters_values = list(self.combo_get_parameters['values'])
                    new_get_parameters_values[self.selected_get_option] = new_get_parameter_name
                    
                    self.parent.dict_lstbox[self.combo_get_parameters['values'][self.selected_get_option]] = new_get_parameter_name
                    
                    self.combo_get_parameters['values'] = new_get_parameters_values
                    
                    self.parent.devices.set(value=new_get_parameters_values)
                    self.parent.lstbox_to_read.after(interval)
                    
                def select_set_option(event):
                    if self.combo_set_parameters.current() != -1:
                        self.selected_set_option = self.combo_set_parameters.current()
                        
                def select_get_option(event):
                    if self.combo_get_parameters.current() != -1:
                        self.selected_get_option = self.combo_get_parameters.current()
                
                self.combo_devices = ttk.Combobox(tw, value = self.parent.combo_to_sweep1['values'])
                self.combo_devices.current(0)
                self.combo_devices.bind(
                    "<<ComboboxSelected>>", update_combo_set_parameters)
                self.combo_devices.grid(row = 1, column = 0, pady = 2)
                
                self.combo_set_parameters = ttk.Combobox(tw, value = [''])
                device_class = types_of_devices[0]
                if device_class != 'Not a class':
                    try:
                        self.combo_set_parameters['values'] = self.parent.sweep_options1['values']
                    except: 
                        self.combo_set_parameters['values'] = getattr(list_of_devices[0], 'set_options')
                    self.combo_set_parameters.current(0)
                    self.combo_set_parameters.bind(
                        "<<ComboboxSelected>>", select_set_option)
                else:
                    self.combo_set_parameters['values'] = ['']
                    self.combo_set_parameters.current(0)
                self.combo_set_parameters.grid(row = 2, column = 0, pady = 2)
                
                parameters = parameters_to_read
                
                if len(parameters) == 0:
                    parameters = ['']
                
                self.get_current = tk.StringVar()
                self.combo_get_parameters = ttk.Combobox(tw, value = parameters, textvariable = self.get_current)
                self.combo_get_parameters.current(0)
                self.combo_get_parameters.bind(
                    "<<ComboboxSelected>>", select_get_option)
                self.combo_get_parameters.grid(row = 3, column = 0, pady = 2)
                
                button_change_name_device = tk.Button(tw, text = 'Change device name', command = update_names_devices)
                button_change_name_device.grid(row = 1, column = 1, pady = 2)
                
                self.selected_device = 0
                self.selected_set_option = 0
                self.selected_get_option = 0
                
                button_change_name_set_parameters = tk.Button(tw, text = 'Change set name', command = update_names_set_parameters)
                button_change_name_set_parameters.grid(row = 2, column = 1, pady = 2)
                
                button_change_name_get_parameters = tk.Button(tw, text = 'Change get name', command = update_names_get_parameters)
                button_change_name_get_parameters.grid(row = 3, column = 1, pady = 2)
                
                def hide_toplevel():
                    tw = self.name_toplevel
                    self.name_toplevel = None
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
                
        def CreateNameToplevel(widget, parent):
            
            toplevel = ChangeName(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show) 
            
        CreateNameToplevel(self.sweep_options1, self)
        CreateNameToplevel(self.combo_to_sweep1, self)
        CreateNameToplevel(self.sweep_options2, self)
        CreateNameToplevel(self.combo_to_sweep2, self)
        CreateNameToplevel(self.sweep_options3, self)
        CreateNameToplevel(self.combo_to_sweep3, self)
        
        label_options = tk.Label(self, text = 'Options:', font=LARGE_FONT)
        label_options.place(relx = 0.05, rely = 0.25)

        label_from1 = tk.Label(self, text='From', font=LARGE_FONT)
        label_from1.place(relx=0.12, rely=0.29)

        label_to1 = tk.Label(self, text='To', font=LARGE_FONT)
        label_to1.place(relx=0.12, rely=0.33)

        if self.count_option1 == 'ratio':
            self.label_ratio1 = tk.Label(self, text='Ratio, \n Δ/s', font=LARGE_FONT)
            CreateToolTip(self.label_ratio1, 'Speed of 1d-sweep')
        elif self.count_option1 == 'step':
            self.label_ratio1 = tk.Label(self, text='Step, Δ', font=LARGE_FONT)
            CreateToolTip(self.label_ratio1, 'Step of 1d-sweep')
        self.label_ratio1.place(relx=0.12, rely=0.37)

        self.entry_from1 = tk.Entry(self)
        self.entry_from1.insert(0, self.from1_init)
        self.entry_from1.place(relx=0.17, rely=0.29)
        self.entry_from1.after(1000, self.rewrite_preset)

        self.entry_to1 = tk.Entry(self)
        self.entry_to1.insert(0, self.to1_init)
        self.entry_to1.place(relx=0.17, rely=0.33)

        self.entry_ratio1 = tk.Entry(self)
        self.entry_ratio1.insert(0, self.ratio1_init)
        self.entry_ratio1.place(relx=0.17, rely=0.37)
        
        button_swap1 = tk.Button(self, text = r'🆚', font = ('Verdana', 8), command = self.swap_ratio_step1)
        button_swap1.place(relx = 0.1, rely = 0.4)
        CreateToolTip(button_swap1, 'Change Ratio/Step')

        label_delay_factor1 = tk.Label(
            self, text='Delay factor, s', justify=tk.LEFT, font=LARGE_FONT)
        label_delay_factor1.place(relx=0.12, rely=0.45)
        CreateToolTip(label_delay_factor1, 'Sleep time per 1 point')

        self.entry_delay_factor1 = tk.Entry(self)
        self.entry_delay_factor1.insert(0, self.delay_factor1_init)
        self.entry_delay_factor1.place(relx=0.12, rely=0.51)

        label_from2 = tk.Label(self, text='From', font=LARGE_FONT)
        label_from2.place(relx=0.27, rely=0.29)

        label_to2 = tk.Label(self, text='To', font=LARGE_FONT)
        label_to2.place(relx=0.27, rely=0.33)

        if self.count_option2 == 'ratio':
            self.label_ratio2 = tk.Label(self, text='Ratio, \n Δ/s', font=LARGE_FONT)
            CreateToolTip(self.label_ratio2, 'Speed of 1d-sweep')
        elif self.count_option2 == 'step':
            self.label_ratio2 = tk.Label(self, text='Step, Δ', font=LARGE_FONT)
            CreateToolTip(self.label_ratio2, 'Step of 1d-sweep')
        self.label_ratio2.place(relx=0.27, rely=0.37)

        self.entry_from2 = tk.Entry(self)
        self.entry_from2.insert(0, self.from2_init)
        self.entry_from2.place(relx=0.32, rely=0.29)

        self.entry_to2 = tk.Entry(self)
        self.entry_to2.insert(0, self.to2_init)
        self.entry_to2.place(relx=0.32, rely=0.33)

        self.entry_ratio2 = tk.Entry(self)
        self.entry_ratio2.insert(0, self.ratio2_init)
        self.entry_ratio2.place(relx=0.32, rely=0.37)
        
        button_swap2 = tk.Button(self, text = r'🆚', font = ('Verdana', 8), command = self.swap_ratio_step2)
        button_swap2.place(relx = 0.25, rely = 0.4)
        CreateToolTip(button_swap2, 'Change Ratio/Step')

        label_delay_factor2 = tk.Label(
            self, text='Delay factor, s', justify=tk.LEFT, font=LARGE_FONT)
        label_delay_factor2.place(relx=0.27, rely=0.45)
        CreateToolTip(label_delay_factor2, 'Sleep time per 1 point')

        self.entry_delay_factor2 = tk.Entry(self)
        self.entry_delay_factor2.insert(0, self.delay_factor2_init)
        self.entry_delay_factor2.place(relx=0.27, rely=0.51)

        label_from3 = tk.Label(self, text='From', font=LARGE_FONT)
        label_from3.place(relx=0.42, rely=0.29)

        label_to3 = tk.Label(self, text='To', font=LARGE_FONT)
        label_to3.place(relx=0.42, rely=0.33)

        if self.count_option3 == 'ratio':
            self.label_ratio3 = tk.Label(self, text='Ratio, \n Δ/s', font=LARGE_FONT)
            CreateToolTip(self.label_ratio3, 'Speed of 1d-sweep')
        elif self.count_option3 == 'step':
            self.label_ratio3 = tk.Label(self, text='Step, Δ', font=LARGE_FONT)
            CreateToolTip(self.label_ratio3, 'Step of 1d-sweep')
        self.label_ratio3.place(relx=0.42, rely=0.37)

        self.entry_from3 = tk.Entry(self)
        self.entry_from3.insert(0, self.from3_init)
        self.entry_from3.place(relx=0.47, rely=0.29)

        self.entry_to3 = tk.Entry(self)
        self.entry_to3.insert(0, self.to3_init)
        self.entry_to3.place(relx=0.47, rely=0.33)

        self.entry_ratio3 = tk.Entry(self)
        self.entry_ratio3.insert(0, self.ratio3_init)
        self.entry_ratio3.place(relx=0.47, rely=0.37)
        
        button_swap3 = tk.Button(self, text = r'🆚', font = ('Verdana', 8), command = self.swap_ratio_step3)
        button_swap3.place(relx = 0.4, rely = 0.4)
        CreateToolTip(button_swap3, 'Change Ratio/Step')

        label_delay_factor3 = tk.Label(
            self, text='Delay factor, s', justify=tk.LEFT, font=LARGE_FONT)
        label_delay_factor3.place(relx=0.42, rely=0.45)
        CreateToolTip(label_delay_factor3, 'Sleep time per 1 point')

        self.entry_delay_factor3 = tk.Entry(self)
        self.entry_delay_factor3.insert(0, self.delay_factor3_init)
        self.entry_delay_factor3.place(relx=0.42, rely=0.51)

        # initials
        self.manual_sweep_flags = [0, 0, 0]

        self.checkbox_manual1 = ttk.Checkbutton(self, text='Maunal sweep select',
                                           variable=self.status_manual1, onvalue=1,
                                           offvalue=0, command=lambda: self.save_manual_status(i=1))
        self.checkbox_manual1.place(relx=0.12, rely=0.57)
        
        if self.status_manual1.get() == 0:
            self.entry_from1.config(state= "normal")
            self.entry_to1.config(state= "normal")
            self.entry_ratio1.config(state= "normal")
        else:
            self.entry_from1.config(state= "disabled")
            self.entry_to1.config(state= "disabled")
            self.entry_ratio1.config(state= "disabled")
        
        button_new_manual1 = tk.Button(self, text='🖊', font = LARGE_FONT, command=lambda: self.open_blank(i=0))
        button_new_manual1.place(relx=0.12, rely=0.61)
        CreateToolTip(button_new_manual1, 'Create new sweep instruction')

        button_explore_manual1 = tk.Button(
            self, text='🔎', font = LARGE_FONT, command=lambda: self.explore_files(i=0))
        button_explore_manual1.place(relx=0.15, rely=0.61)
        CreateToolTip(button_explore_manual1, 'Explore existing sweep instruction')

        self.checkbox_manual2 = ttk.Checkbutton(self, text='Maunal sweep select',
                                           variable=self.status_manual2, onvalue=1,
                                           offvalue=0, command=lambda: self.save_manual_status(i=2))
        self.checkbox_manual2.place(relx=0.27, rely=0.57)

        if self.status_manual3.get() == 0:
            self.entry_from2.config(state= "normal")
            self.entry_to2.config(state= "normal")
            self.entry_ratio2.config(state= "normal")
        else:
            self.entry_from2.config(state= "disabled")
            self.entry_to2.config(state= "disabled")
            self.entry_ratio2.config(state= "disabled")

        button_new_manual2 = tk.Button(self, text='🖊', font = LARGE_FONT, command=lambda: self.open_blank(i=1))
        button_new_manual2.place(relx=0.27, rely=0.61)
        CreateToolTip(button_new_manual2, 'Create new sweep instruction')

        button_explore_manual2 = tk.Button(
            self, text='🔎', font = LARGE_FONT, command=lambda: self.explore_files(i=1))
        button_explore_manual2.place(relx=0.3, rely=0.61)
        CreateToolTip(button_explore_manual2, 'Explore existing sweep instruction')

        self.checkbox_manual3 = ttk.Checkbutton(self, text='Maunal sweep select',
                                           variable=self.status_manual3, onvalue=1,
                                           offvalue=0, command=lambda: self.save_manual_status(i=3))
        self.checkbox_manual3.place(relx=0.42, rely=0.57)

        if self.status_manual3.get() == 0:
            self.entry_from3.config(state= "normal")
            self.entry_to3.config(state= "normal")
            self.entry_ratio3.config(state= "normal")
        else:
            self.entry_from3.config(state= "disabled")
            self.entry_to3.config(state= "disabled")
            self.entry_ratio3.config(state= "disabled")

        button_new_manual3 = tk.Button(self, text='🖊', font = LARGE_FONT, command=lambda: self.open_blank(i=2))
        button_new_manual3.place(relx=0.42, rely=0.61)
        CreateToolTip(button_new_manual3, 'Create new sweep instruction')

        button_explore_manual3 = tk.Button(
            self, text='🔎', font = LARGE_FONT, command=lambda: self.explore_files(i=2))
        button_explore_manual3.place(relx=0.45, rely=0.61)
        CreateToolTip(button_explore_manual3, 'Explore existing sweep instruction')
        
        label_condition = tk.Label(self, text = 'Constraints:', font = LARGE_FONT)
        label_condition.place(relx = 0.12, rely = 0.66)
        CreateToolTip(label_condition, 'Master sweep: x\nSlave sweep: y\nSlave-slave sweep: z\nSet condition for a sweep map \nRight click to configure the sweep')
        
        self.text_condition = tk.Text(self, width = 60, height = 7)
        self.text_condition.delete('1.0', tk.END)
        self.text_condition.insert(tk.END, self.condition)
        self.text_condition.place(relx = 0.12, rely = 0.7)
        CreateToolTip(self.text_condition, 'Master sweep: x\nSlave sweep: y\nSlave-slave sweep: z\nSet condition for a sweep map \nRight click to configure the sweep')

        self.filename_textvariable = tk.StringVar(self, value = self.filename_sweep)
        width = int(len(self.filename_textvariable.get()) * 0.95)
        self.entry_filename = tk.Entry(self, textvariable = self.filename_textvariable, font = LARGE_FONT, 
                                       width = width)
        self.entry_filename.place(relx = 0.97 - width / 100, rely = 0.9)

        self.script = ''
        
        class Script(object):
            
            def __init__(self, widget, parent):
                self.script_toplevel = None
                self.script_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x = y = 0
                self.script_toplevel = tw = tk.Toplevel(self.script_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_script = tk.Label(tw, text = 'Manual script', font = LARGE_FONT)
                label_script.grid(row = 0, column = 0, pady = 2)
                
                def ctrlEvent(event):
                    if event.state == 4 and event.keysym == 'c':
                        content = self.text_script.selection_get()
                        tw.clipboard_clear()
                        tw.clipboard_append(content)
                        return "break"
                    elif event.state == 4 and event.keysym == 'v':
                        self.text_script.insert('end', tw.selection_get(selection='CLIPBOARD'))
                        return "break"
                    elif event.state == 4 and event.keysym == 'a':
                        self.text_script.tag_add("sel", "1.0","end")
                        return "break"
                    elif event.state == 4 and event.keysym == 'z':
                        self.text_script.delete('sel.first','sel.last')
                        return "break"
                    
                self.text_script = tk.Text(tw, width = 60, height = 10)
                self.text_script.grid(row = 1, column = 0, pady = 2, rowspan = 3)
                self.text_script.configure(font = LARGE_FONT)
                self.text_script.bind("<Key>", ctrlEvent)
                
                def hide_toplevel():
                    tw = self.script_toplevel
                    self.script_toplevel = None
        
                    tw.destroy()
                
                def explore_script(interval = 1):
                    
                    if exists(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')):
                        init = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')
                    else:
                        init = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')
                    
                    script_filename = tk.filedialog.askopenfilename(initialdir=init,
                                                                             title='Select a script')
                    with open(script_filename, 'r') as file:
                        try:
                            script = file.read()
                        except Exception as e:
                            print(f'Exception happened while exploring existing script: {e}')
                            file.close()
                        finally:
                            file.close()
                            
                    self.text_script.delete(1.0, tk.END)
                    self.text_script.insert(tk.END, script)
                    self.text_script.after(interval)
                    self.script_toplevel.deiconify() #show toplevel again
                    
                def set_script():
                    self.parent.script = self.text_script.get(1.0, tk.END)[:-1]
                    hide_toplevel()
                    
                def save_script():
                    
                    if not exists(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts')):
                        os.mkdir(os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}', 'scripts'))
                    
                    self.script_filename = tk.filedialog.asksaveasfilename(title='Save the file',
                                            initialfile=os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}',
                                            'scripts', f'script{datetime.today().strftime("%H_%M_%d_%m_%Y")}'),
                                            defaultextension='.csv')
                    
                    self.parent.script = self.text_script.get(1.0, tk.END)[:-1]
                    
                    with open(self.script_filename, 'w') as file:
                        try:
                            file.write(self.parent.script)
                        except Exception as e:
                            print(f'Exception happened while saving the script: {e}')
                            file.close()
                        finally:
                            file.close()
                    
                    self.script_toplevel.deiconify() #show toplevel again
                
                button_explore_script = tk.Button(
                    tw, text='🔎', font = SUPER_LARGE, command = explore_script)
                button_explore_script.grid(row = 1, column = 1, pady = 2)
                CreateToolTip(button_explore_script, 'Explore existing script')
                
                button_save_script = tk.Button(
                    tw, text='💾', font = SUPER_LARGE, command = save_script)
                button_save_script.grid(row = 2, column = 1, pady = 2)
                CreateToolTip(button_save_script, 'Save this script')
                
                self.script_filename = ''
                
                button_set_script = tk.Button(
                    tw, text = 'Apply script', font = LARGE_FONT, command = set_script)
                button_set_script.grid(row = 3, column = 1, pady = 2)
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
            
        def CreateScriptToplevel(widget, parent):
            
            toplevel = Script(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show) 
            
        CreateScriptToplevel(self.text_condition, self)

        button_filename = tk.Button(
            self, text = 'Browse...', command=lambda: self.set_filename_sweep())
        button_filename.place(relx=0.85, rely=0.9)

        class Interpolated(object):
            
            def __init__(self, widget, parent):
                self.interpolated_toplevel = None
                self.interpolated_widget = widget
                self.parent = parent
            
            def show_toplevel(self):
                x, y, _, _ = self.interpolated_widget.bbox('all')
                x = x + self.interpolated_widget.winfo_rootx()
                y = y + self.interpolated_widget.winfo_rooty()
                self.interpolated_toplevel = tw = tk.Toplevel(self.interpolated_widget)
                tw.wm_geometry("+%d+%d" % (x, y))
                
                label_interpolation = tk.Label(tw, text = 'Interpolate\n2D map?', font = LARGE_FONT)
                label_interpolation.grid(row = 0, column = 0, pady = 2)
                
                self.status_interpolated = tk.IntVar()
                self.status_interpolated.set(self.parent.interpolated)
                
                self.checkbox_interpolation = tk.Checkbutton(tw, variable = self.status_interpolated, 
                                                             onvalue = 1, offvalue = 0, 
                                                             command = self.change_status_interpolated) 
                self.checkbox_interpolation.grid(row = 0, column = 1, pady = 2)
                
                if self.parent.interpolated == 1:
                    self.label_uniform = tk.Label(tw, text = 'Uniform grid', font = LARGE_FONT)
                    self.label_uniform.grid(row = 1, column = 0, pady = 2)
                    
                    self.status_uniform = tk.IntVar()
                    self.status_uniform.set(self.parent.uniform)
                    
                    self.checkbox_uniform = tk.Checkbutton(tw, variable = self.status_uniform,
                                                           onvalue = 1, offvalue = 0,
                                                           command = self.change_status_uniform)
                    self.checkbox_uniform.grid(row = 1, column = 1, pady = 2)
                    
            
                def hide_toplevel():
                    tw = self.interpolated_toplevel
                    self.interpolated_toplevel = None
        
                    tw.destroy()
                
                tw.protocol("WM_DELETE_WINDOW", hide_toplevel)
            
            def change_status_interpolated(self):
                self.parent.interpolated = self.status_interpolated.get()
                
                if self.status_interpolated.get() == 0:
                    self.checkbox_uniform.grid_forget()
                    self.label_uniform.grid_forget()
                else:
                    self.label_uniform = tk.Label(self.interpolated_toplevel, text = 'Uniform grid', font = LARGE_FONT)
                    self.label_uniform.grid(row = 1, column = 0, pady = 2)
                    
                    self.status_uniform = tk.IntVar()
                    self.status_uniform.set(self.parent.uniform)
                    
                    self.checkbox_uniform = tk.Checkbutton(self.interpolated_toplevel, variable = self.status_uniform,
                                                           onvalue = 1, offvalue = 0,
                                                           command = self.change_status_uniform)
                    self.checkbox_uniform.grid(row = 1, column = 1, pady = 2)
                
            def change_status_uniform(self):
                self.parent.uniform= self.status_uniform.get()
                
        def CreateInterpolatedToplevel(widget, parent):
            
            toplevel = Interpolated(widget, parent)
            
            def show(event):
                toplevel.show_toplevel()
                
            widget.bind('<Button-3>', show)

        graph_button = tk.Button(
            self, text='📊', font = SUPER_LARGE, command=lambda: self.open_graph())
        graph_button.place(relx=0.75, rely=0.8)
        CreateToolTip(graph_button, 'Graph')
        CreateInterpolatedToplevel(graph_button, self)
        
        class ImageLabel(tk.Label):
            """
            A Label that displays images, and plays them if they are gifs
            :im: A PIL Image instance or a string filename
            """
            def load(self, im):
                if isinstance(im, str):
                    im = Image.open(im)
                frames = []
         
                try:
                    for i in count(1):
                        frames.append(ImageTk.PhotoImage(im.copy()))
                        im.seek(i)
                except EOFError:
                    pass
                self.frames = cycle(frames)
         
                try:
                    self.delay = im.info['duration']
                except:
                    self.delay = 100
         
                if len(frames) == 1:
                    self.config(image=next(self.frames))
                else:
                    self.next_frame()
         
            def unload(self):
                self.config(image=None)
                self.frames = None
         
            def next_frame(self):
                if self.frames:
                    self.config(image=next(self.frames))
                    self.after(self.delay, self.next_frame)
                    
        self.cur_walk1 = 1  
        self.cur_walk2 = 1
        self.cur_walk3 = 1
                  
        def animate():
            
            def get_time_remaining():
                global zero_time
                global from_sweep1
                global to_sweep1
                global ratio_sweep1
                global delay_factor1
                global from_sweep2
                global to_sweep2
                global ratio_sweep2
                global delay_factor2
                global from_sweep3
                global to_sweep3
                global sweeper_write
                
                def ConvertSectoDay(n):
                    
                    try:
                        n = int(n)
                    except OverflowError:
                        n = int(1e6)
                    day = n // (24 * 3600)
                    n = n % (24 * 3600)
                    hour = n // 3600
                    n %= 3600
                    minutes = n // 60
                    n %= 60
                    seconds = n
                    if day == 0:
                        if hour == 0:
                            if minutes == 0:
                                s = f'{seconds} s'
                            else:
                                s = f'{minutes} m\n{seconds} s'
                        else:
                            s = f'{hour} h\n{minutes} m\n{seconds} s'
                    else:
                        s = f'{day} d\n{hour} h\n{minutes} m\n{seconds} s'
                
                    return s
                
                t = time.perf_counter() - zero_time
                delta = abs(from_sweep3 - to_sweep3)
                nstep1 = np.ceil(abs((from_sweep1 - to_sweep1) / ratio_sweep1 / delay_factor1) + 1)
                nstep2 = np.ceil(abs((from_sweep2 - to_sweep2) / ratio_sweep2 / delay_factor2) + 1)
                
                if sweeper_write.sweepable1:
                    x = float(sweeper_write.current_value)
                else:
                    x = float(sweeper_write.value3)
                    
                try:    
                    if self.status_back_and_forth_slave.get() == 0:
                        back_and_forth_slave = 1
                    else:
                        back_and_forth_slave = self.back_and_forth_slave_count
                    if self.status_back_and_forth_master.get() == 0:
                        back_and_forth_master = 1
                    else:
                        back_and_forth_master = self.back_and_forth_master_count
                    if self.status_back_and_forth_slave_slave.get() == 0:
                        back_and_forth_slave_slave = 1
                    else:
                        back_and_forth_slave_slave = self.back_and_forth_slave_slave_count
                    
                    tau = (self.cur_walk1 - nstep1) * delay_factor1 + (self.cur_walk2 - nstep2) * delay_factor2 + (t + (self.cur_walk1 - 1) * delay_factor1 + (self.cur_walk2 - 1) * delay_factor2) * ((nstep1*nstep2*back_and_forth_master*back_and_forth_slave*back_and_forth_slave_slave - self.cur_walk2) * delta + (to_sweep3 - x)) / ((self.cur_walk3 - 1) * delta + (x - from_sweep3)) #time * how musch to go / how much has gone already
                    
                    return ConvertSectoDay(tau)
                except ZeroDivisionError as e:
                    print(f'ZeroDivisionException happened: {e}')
                    return '...'
                except RuntimeWarning as e:
                    print(f'RuntimeWarning happened: {e}')
                    return '...'
            
            if self.start_sweep_flag:
                if not hasattr(self, 'gif_label'):
                    self.gif_label = ImageLabel(self)
                    self.gif_label.place(relx = 0.75, rely = 0.5)
                    if 'loading.gif' in os.listdir(os.path.join(core_dir, 'config')):
                        self.gif_label.load(os.path.join(core_dir, 'config', 'loading.gif'))
                if not hasattr(self, 'time_label'):
                    self.time_label = tk.Label(self, text = 'Time left: ...', font = LARGE_FONT)
                    self.time_label.place(relx = 0.8, rely = 0.5)
                else:
                    self.time_label.config(text = f'Time left: {get_time_remaining()}')
            else:
                if hasattr(self, 'gif_label'):
                    self.gif_label.place_forget()
                    del self.gif_label
                if hasattr(self, 'time_label'):
                    self.time_label.place_forget()
                    del self.time_label
            self.after(1000, animate)
            
        self.start_sweep_flag = False
        animate()

    def update_sweep_parameters1(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        ind = self.combo_to_sweep1.current()
        class_of_sweeper_device1 = types_of_devices[ind]
        device1 = list_of_devices[ind]
        if class_of_sweeper_device1 != 'Not a class':
            self.sweep_options1['value'] = getattr(
                device1, 'set_options')
            try:
                self.sweep_options1.current(self.sweep_options1_current)
            except tk.TclError:
                self.sweep_options1.current(0)
            self.sweep_options1.after(interval)
        else:
            self.sweep_options1['value'] = ['']
            self.sweep_options1.current(0)
            self.sweep_options1.after(interval)
            
        if self.combo_to_sweep1.current() != self.combo_to_sweep1_current:
            self.preset.loc[0, 'combo_to_sweep1'] = self.combo_to_sweep1.current()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
        self.back_ratio1_init = ''
        self.back_delay_factor1_init = ''

    def update_sweep_parameters2(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        
        ind = self.combo_to_sweep2.current()
        class_of_sweeper_device2 = types_of_devices[ind]
        device2 = list_of_devices[ind]
        if class_of_sweeper_device2 != 'Not a class':
            self.sweep_options2['value'] = getattr(
                device2, 'set_options')
            try:
                self.sweep_options2.current(self.sweep_options2_current)
            except tk.TclError:
                self.sweep_options2.current(0)
            self.sweep_options2.after(interval)
        else: 
            self.sweep_options2['value'] = ['']
            self.sweep_options2.current(0)
            self.sweep_options2.after(interval)
            
        if self.combo_to_sweep2.current() != self.combo_to_sweep2_current:
            self.preset.loc[0, 'combo_to_sweep2'] = self.combo_to_sweep2.current()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
        self.back_ratio2_init = ''
        self.back_delay_factor2_init = ''

    def update_sweep_parameters3(self, event, interval=100):
        global types_of_devices
        global list_of_devices
        ind = self.combo_to_sweep3.current()
        class_of_sweeper_device3 = types_of_devices[ind]
        device3 = list_of_devices[ind]
        if class_of_sweeper_device3 != 'Not a class':
            self.sweep_options3['value'] = getattr(
                device3, 'set_options')
            try:
                self.sweep_options3.current(self.sweep_options3_current)
            except tk.TclError:
                self.sweep_options3.current(0)
            self.sweep_options3.after(interval)
        else:
            self.sweep_options3['value'] = ['']
            self.sweep_options3.current(0)
            self.sweep_options3.after(interval)
            
        if self.combo_to_sweep3.current() != self.combo_to_sweep3_current:
            self.preset.loc[0, 'combo_to_sweep3'] = self.combo_to_sweep3.current()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
        self.back_ratio3_init = ''
        self.back_delay_factor3_init = ''
            
    def update_sweep_options1(self, event):
        if self.sweep_options1.current() != self.sweep_options1_current:
            self.preset.loc[0, 'sweep_options1'] = self.sweep_options1.current()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
    
    def update_sweep_options2(self, event):
        if self.sweep_options2.current() != self.sweep_options2_current:
            self.preset.loc[0, 'sweep_options2'] = self.sweep_options2.current()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
    def update_sweep_options3(self, event):
        if self.sweep_options3.current() != self.sweep_options3_current:
            self.preset.loc[0, 'sweep_options3'] = self.sweep_options3.current()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
    def swap_ratio_step1(self):
        if self.count_option1 == 'step':
            self.count_option1 = 'ratio'
        elif self.count_option1 == 'ratio':
            self.count_option1 = 'step'
            
        if self.count_option1 == 'step' and self.label_ratio1['text'].startswith('Ratio'):
            self.label_ratio1.configure(text = 'Step, Δ')
            self.update()
        
        if self.count_option1 == 'ratio' and self.label_ratio1['text'].startswith('Step'):
            self.label_ratio1.configure(text = 'Ratio, \n Δ/s')
            self.update()
        
        self.preset.loc[0, 'count_option1'] = self.count_option1
        self.preset.to_csv(globals()['sweeper1d_path'], index = False)
        
    def swap_ratio_step2(self):
        if self.count_option2 == 'step':
            self.count_option2 = 'ratio'
        elif self.count_option2 == 'ratio':
            self.count_option2 = 'step'
            
        if self.count_option2 == 'step' and self.label_ratio2['text'].startswith('Ratio'):
            self.label_ratio2.configure(text = 'Step, Δ')
            self.update()
        
        if self.count_option2 == 'ratio' and self.label_ratio2['text'].startswith('Step'):
            self.label_ratio2.configure(text = 'Ratio, \n Δ/s')
            self.update()
        
        self.preset.loc[0, 'count_option2'] = self.count_option2
        self.preset.to_csv(globals()['sweeper2d_path'], index = False)
        
    def swap_ratio_step3(self):
        if self.count_option3 == 'step':
            self.count_option3 = 'ratio'
        elif self.count_option3 == 'ratio':
            self.count_option3 = 'step'
            
        if self.count_option3 == 'step' and self.label_ratio3['text'].startswith('Ratio'):
            self.label_ratio3.configure(text = 'Step, Δ')
            self.update()
        
        if self.count_option3 == 'ratio' and self.label_ratio3['text'].startswith('Step'):
            self.label_ratio3.configure(text = 'Ratio, \n Δ/s')
            self.update()
        
        self.preset.loc[0, 'count_option3'] = self.count_option3
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
    def rewrite_preset(self):
        
        time.sleep(0.05)
        
        if self.entry_from1.get() != self.from1_init:
            self.preset.loc[0, 'from1'] = self.entry_from1.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_to1.get() != self.to1_init:
            self.preset.loc[0, 'to1'] = self.entry_to1.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_ratio1.get() != self.ratio1_init:
            self.preset.loc[0, 'ratio1'] = self.entry_ratio1.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        self.preset.loc[0, 'back_ratio1'] = self.back_ratio1_init
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        self.preset.loc[0, 'back_delay_factor1'] = self.back_delay_factor1_init
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_delay_factor1.get() != self.delay_factor1_init:
            self.preset.loc[0, 'delay_factor1'] = self.entry_delay_factor1.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_from2.get() != self.from2_init:
            self.preset.loc[0, 'from2'] = self.entry_from2.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_to2.get() != self.to2_init:
            self.preset.loc[0, 'to2'] = self.entry_to2.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_ratio2.get() != self.ratio2_init:
            self.preset.loc[0, 'ratio2'] = self.entry_ratio2.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        self.preset.loc[0, 'back_ratio2'] = self.back_ratio2_init
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        self.preset.loc[0, 'back_delay_factor2'] = self.back_delay_factor2_init
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_delay_factor2.get() != self.delay_factor2_init:
            self.preset.loc[0, 'delay_factor2'] = self.entry_delay_factor2.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_from3.get() != self.from3_init:
            self.preset.loc[0, 'from3'] = self.entry_from3.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_to3.get() != self.to3_init:
            self.preset.loc[0, 'to3'] = self.entry_to3.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_ratio3.get() != self.ratio3_init:
            self.preset.loc[0, 'ratio3'] = self.entry_ratio3.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        self.preset.loc[0, 'back_ratio3'] = self.back_ratio3_init
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        self.preset.loc[0, 'back_delay_factor3'] = self.back_delay_factor3_init
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        if self.entry_delay_factor3.get() != self.delay_factor3_init:
            self.preset.loc[0, 'delay_factor3'] = self.entry_delay_factor3.get()
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
        current_filename = self.entry_filename.get()
        path_current = os.path.normpath(current_filename).split(os.path.sep)
        name = path_current[-1]
        path_current = path_current[:-1]
        current_filename = basename(name)
        current_filename = os.path.join(*path_current, current_filename)
        current_filename = fix_unicode(current_filename)
        
        memory_filename = self.filename_sweep
        path_memory = os.path.normpath(memory_filename).split(os.path.sep)
        memory_filename = path_memory[-1]
        path_memory = path_memory[:-1]
        memory_filename = basename(memory_filename)
        memory_filename = os.path.join(*path_memory, memory_filename)
        memory_filename = fix_unicode(memory_filename)  
        
        if current_filename != memory_filename:
            self.preset.loc[0, 'filename_sweep'] = current_filename
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        self.preset.loc[0, 'condition'] = self.text_condition.get(1.0, tk.END)[:-1]
        self.preset.loc[0, 'interpolated'] = self.interpolated
        self.preset.loc[0, 'uniform'] = self.uniform
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        
        #self.entry_from1.after(1000, self.rewrite_preset)
            
    def update_sweep_configuration(self):
        global from_sweep1
        global to_sweep1
        global ratio_sweep1
        global delay_factor1
        global from_sweep2
        global to_sweep2
        global ratio_sweep2
        global delay_factor2
        global from_sweep3
        global to_sweep3
        global ratio_sweep3
        global delay_factor3
        
        if self.start_sweep_flag:
            
            try:
                from_sweep1 = float(self.entry_from1.get())
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from1.get()} to float')
                return
                
            try:
                to_sweep1 = float(self.entry_to1.get())
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to1.get()} to float')
                return
            
            try:
                ratio_sweep1 = float(self.entry_ratio1.get())
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio1.get()} to float')
                return

            try:
                delay_factor1 = float(self.entry_delay_factor1.get())
            except:
                messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delay_factor1.get()} to float')
                return
            
            try:
                from_sweep2 = float(self.entry_from2.get())
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from2.get()} to float')
                return
                
            try:
                to_sweep2 = float(self.entry_to2.get())
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to2.get()} to float')
                return
            
            try:
                ratio_sweep2 = float(self.entry_ratio2.get())
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio2.get()} to float')
                return

            try:
                delay_factor2 = float(self.entry_delay_factor2.get())
            except:
                messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delay_factor2.get()} to float')
                return
            
            try:
                from_sweep3 = float(self.entry_from3.get())
            except:
                messagebox.showerror('Invalid value in "From" entrybox', f'Can not convert {self.entry_from3.get()} to float')
                return
                
            try:
                to_sweep3 = float(self.entry_to3.get())
            except:
                messagebox.showerror('Invalid value in "To" entrybox', f'Can not convert {self.entry_to3.get()} to float')
                return
            
            try:
                ratio_sweep3 = float(self.entry_ratio3.get())
            except:
                messagebox.showerror('Invalid value in "Ratio" entrybox', f'Can not convert {self.entry_ratio3.get()} to float')
                return

            try:
                delay_factor3 = float(self.entry_delay_factor3.get())
            except:
                messagebox.showerror('Invalid value in "Delay factor" entrybox', f'Can not convert {self.entry_delay_factor3.get()} to float')
                return
                    
            delta1 = to_sweep1 - from_sweep1
            step1 = globals()['sweeper_write'].step1
            
            delta2 = to_sweep2 - from_sweep2
            step2 = globals()['sweeper_write'].step2
            
            delta3 = to_sweep2 - from_sweep3
            step3 = globals()['sweeper_write'].step3
            
            if np.sign(delta1 * step1) < 0:
                to_sweep1 = float(self.entry_from1.get())
                from_sweep1 = float(self.entry_to1.get())
                ratio_sweep1 = - ratio_sweep1
                
            if np.sign(delta2 * step2) < 0:
                to_sweep2 = float(self.entry_from2.get())
                from_sweep2 = float(self.entry_to2.get())
                ratio_sweep2 = - ratio_sweep2
                
            if np.sign(delta3 * step3) < 0:
                to_sweep3 = float(self.entry_from3.get())
                from_sweep3 = float(self.entry_to3.get())
                ratio_sweep3 = - ratio_sweep3
            
            if self.count_option1 == 'step':
                step1 = ratio_sweep1
                ratio_sweep1 = ratio_sweep1 / delay_factor1
                globals()['sweeper_write'].step1 = step1
            else:
                ratio_sweep1 = ratio_sweep1 
                step1 = ratio_sweep1 * delay_factor1
                globals()['sweeper_write'].step1 = step1
                    
            if self.count_option2 == 'step':
                step2 = ratio_sweep2
                ratio_sweep2 = ratio_sweep2 / delay_factor2
                globals()['sweeper_write'].step2 = step2
            else:
                ratio_sweep2 = ratio_sweep2 
                step2 = ratio_sweep2 * delay_factor2
                globals()['sweeper_write'].step2 = step2
                    
            if self.count_option3 == 'step':
                step3 = ratio_sweep3
                ratio_sweep3 = ratio_sweep3 / delay_factor3
                if globals()['sweeper_write'].sweepable3 != True:
                    globals()['sweeper_write'].step3 = step3
                else:
                    globals()['sweeper_write'].step3 = np.sign(step3) * delta3
            else:
                ratio_sweep3 = ratio_sweep3 
                step3 = ratio_sweep3 * delay_factor3
                if globals()['sweeper_write'].sweepable3 != True:
                    globals()['sweeper_write'].step3 = step3
                else:
                    globals()['sweeper_write'].step3 = np.sign(step3) * delta3
            
            self.from_sweep1 = from_sweep1
            self.to_sweep1 = to_sweep1
            self.ratio_sweep1 = ratio_sweep1
            self.delay_fector1 = delay_factor1
            self.from_sweep2 = from_sweep2
            self.to_sweep2 = to_sweep2
            self.ratio_sweep2 = ratio_sweep2
            self.delay_fector2 = delay_factor2
            self.from_sweep3 = from_sweep3
            self.to_sweep3 = to_sweep3
            self.ratio_sweep3 = ratio_sweep3
            self.delay_fector3 = delay_factor3
            
        self.rewrite_preset()
        
    def update_listbox(self, interval = 1):
        global parameters_to_read
        self.devices = tk.StringVar()
        self.devices.set(value=parameters_to_read)
        
        if len(parameters_to_read) < 10:
            self.lstbox_to_read.configure(listvariable = self.devices,
                                             height=len(parameters_to_read) * 1)
            
            self.lstbox_height = len(parameters_to_read) / 47
            
            self.button_pause.place(relx = 0.6, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.6375, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.675, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.6, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.6, rely = 0.21 + self.lstbox_height)
        else:
            self.lstbox_to_read.configure(listvariable = self.devices,
                                             height=300)
            
            self.lstbox_height = 18 / 47
            
            self.button_pause.place(relx = 0.6, rely = 0.25 + self.lstbox_height)
            self.button_stop.place(relx = 0.6375, rely = 0.25 + self.lstbox_height)
            self.button_start_sweeping.place(relx = 0.675, rely = 0.21 + self.lstbox_height)
            self.button_tozero.place(relx = 0.6, rely = 0.3 + self.lstbox_height)
            self.button_update_sweep.place(relx = 0.6, rely = 0.21 + self.lstbox_height)

    def save_manual_status(self, i):
        if self.manual_sweep_flags[i - 1] != getattr(self, 'status_manual' + str(i)).get():
            self.manual_sweep_flags[i - 1] = getattr(self, 'status_manual' + str(i)).get()

        if getattr(self, f'status_manual{i}').get() == 0:
            self.manual_filenames[i - 1] = ''
            if hasattr(self, f'entry_from{i}'):
                getattr(self, f'entry_from{i}').config(state= "normal")
                getattr(self, f'entry_to{i}').config(state= "normal")
                getattr(self, f'entry_ratio{i}').config(state= "normal")
        else:
            if hasattr(self, f'entry_from{i}'):
                getattr(self, f'entry_from{i}').config(state= "disabled")
                getattr(self, f'entry_to{i}').config(state= "disabled")
                getattr(self, f'entry_ratio{i}').config(state= "disabled")
            
        #update preset
        self.preset.loc[0, f'manual_filename{i}'] = str(self.manual_filenames[i - 1])
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
        self.preset.loc[0, f'status_manual{i}'] = getattr(self, 'status_manual' + str(i)).get()
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)

    def save_back_and_forth_master_status(self):
        global back_and_forth_master
        
        if self.status_back_and_forth_master.get() == 0:
            back_and_forth_master = 1
        else:
            back_and_forth_master = self.back_and_forth_master_count
            
        self.preset.loc[0, 'status_back_and_forth1'] = self.status_back_and_forth_master.get()
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
            
    def save_back_and_forth_slave_status(self):
        global back_and_forth_slave
        
        if self.status_back_and_forth_slave.get() == 0:
            back_and_forth_slave = 1
        else:
            back_and_forth_slave = self.back_and_forth_slave_count
            
        self.preset.loc[0, 'status_back_and_forth2'] = self.status_back_and_forth_slave.get()
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
        
    def save_back_and_forth_slave_slave_status(self):
        global back_and_forth_slave_slave
        
        if self.status_back_and_forth_slave_slave.get() == 0:
            back_and_forth_slave_slave = 1
        else:
            back_and_forth_slave_slave = self.back_and_forth_slave_slave_count
            
        self.preset.loc[0, 'status_back_and_forth3'] = self.status_back_and_forth_slave_slave.get()
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)
    
    def open_blank(self, i):
        filename = str(self.entry_filename.get())
        tomake = os.path.normpath(filename).split(os.path.sep)
        name = tomake[-1]
        tomake = tomake[:-1]
        tomake = os.path.join(*tomake)
        tomake = fix_unicode(tomake)
        if not exists(tomake):
            os.makedirs(tomake)
        filename = os.path.join(tomake, filename)
        filename = fix_unicode(filename)
        idx = get_filename_index(filename, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        name = name[:len(name) - name[::-1].index('-') - 1]
        filename =  os.path.join(tomake, f'{name}_manual{i+1}d{idx}.csv')
        filename = fix_unicode(filename)
        df = pd.DataFrame(columns=['steps'])
        df.to_csv(filename, index=False)
        self.manual_filenames[i] = filename
        os.startfile(filename)
        self.__dict__[f'status_manual{i + 1}'].set(1)
        
        #update preset
        self.preset.loc[0, f'status_manual{i + 1}'] = 1
        self.preset.loc[0, f'manual_filename{i + 1}'] = str(self.manual_filenames[i])
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)

    def explore_files(self, i):
        self.manual_filenames[i] = tk.filedialog.askopenfilename(initialdir=cur_dir,
                                                                 title='Select a manual sweeper',
                                                                 filetypes=(('CSV files', '*.csv*'),
                                                                            ('all files', '*.*')))
        
        self.__dict__[f'status_manual{i + 1}'].set(1)
        
        #update preset
        self.preset.loc[0, f'status_manual{i + 1}'] = 1
        self.preset.loc[0, f'manual_filename{i + 1}'] = str(self.manual_filenames[i])
        self.preset.to_csv(globals()['sweeper3d_path'], index = False)

    def set_filename_sweep(self):
        global filename_sweep

        path = os.path.normpath(self.filename_sweep).split(os.path.sep)
        
        if 'data_files' not in path:
            to_make = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}', 'data_files')
            to_make = fix_unicode(to_make)
            if not exists(to_make):
                os.makedirs(to_make)
        else:
            to_make = os.path.join(*path[:-1])

        filename_sweep = tk.filedialog.asksaveasfilename(title='Save the file',
                                                         initialfile=to_make,
                                                         defaultextension='.csv')
        
        self.entry_filename.delete(0, tk.END)
        self.entry_filename.insert(0, filename_sweep)
        self.entry_filename.after(1)
        
        current_filename = self.entry_filename.get()
        path_current = os.path.normpath(current_filename).split(os.path.sep)
        name = path_current[-1]
        path_current = path_current[:-1]
        current_filename = basename(name)
        current_filename = os.path.join(*path_current, current_filename)
        current_filename = fix_unicode(current_filename)
        
        memory_filename = self.filename_sweep
        path_memory = os.path.normpath(memory_filename).split(os.path.sep)
        memory_filename = path_memory[-1]
        path_memory = path_memory[:-1]
        memory_filename = basename(memory_filename)
        memory_filename = os.path.join(*path_memory, memory_filename)
        memory_filename = fix_unicode(memory_filename)  
        
        if current_filename != memory_filename:
            self.preset.loc[0, 'filename_sweep'] = current_filename
            self.preset.to_csv(globals()['sweeper3d_path'], index = False)

    def open_graph(self):
        
        global cur_animation_num
        global columns
        
        def return_range(x, n):
            if x % n == 0:
                return [x + p for p in range(n)]
            elif x % n == n - 1:
                return [x - p for p in range(n)][::-1]
            else:
                return return_range(x + 1, n)
        
        globals()[f'graph_object{globals()["cur_animation_num"]}'] = Graph(globals()['filename_sweep'])
        for i in return_range(cur_animation_num, 3):
            preset = pd.read_csv(globals()['graph_preset_path'], sep = ',')
            preset = preset.fillna('')
            x_current = int(preset[f'x{i + 1}_current'].values[0])
            y_current = int(preset[f'y{i + 1}_current'].values[0])
            globals()[f'x{i + 1}'] = []
            if x_current < len(columns):
                globals()[f'x{i + 1}_status'] = x_current
            else:
                globals()[f'x{i + 1}_status'] = 0
            globals()[f'y{i + 1}'] = []
            if y_current < len(columns):
                globals()[f'y{i + 1}_status'] = y_current
            else:
                globals()[f'y{i + 1}_status'] = 0
            globals()[f'ani{i+1}'] = StartAnimation
            globals()[f'ani{i+1}'].start(globals()['filename_sweep'])
        
    def pause(self):
        global pause_flag
        
        pause_flag = not(pause_flag)
        
        if self.button_pause['text'] == '⏸️':
            self.button_pause['text'] = '▶️'
        if self.button_pause['text'] == '▶️':
            self.button_pause['text'] = '⏸️'
            
        self.button_pause.after(1000)
        
    def stop(self):
        
        global stop_flag
        
        stop_flag = True
        
    def tozero(self):
        
        global tozero_flag
        
        answer = messagebox.askyesno('Abort', 'Are you sure you want to set all parameters to 0?')
        
        if answer:
            tozero_flag = True
            
    def determine_filename_sweep(self):
        global filename_sweep
        global cur_dir
        global core_dir
        
        if self.entry_filename.get() != '':
            filename_sweep = self.entry_filename.get()
        else:
            return

        filename_sweep = fix_unicode(filename_sweep)

        self.filename_index = get_filename_index(filename = filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')

        core = os.path.normpath(filename_sweep)
        core = core.split(os.sep)
        name = core[-1]
        try:
            folder_name = name[:len(name) - name[::-1].index('.') - 1]
        except ValueError:
            pass
        try:
            folder_name = folder_name[:len(folder_name) - folder_name[::-1].index('-') - 1]
        except ValueError:
            pass
        folder_name = unify_filename(folder_name)
        
        if 'data_files' in core and len(core) >= 3:
            cur_dir = os.path.join(*core[:core.index('data_files')])
            path = os.path.normpath(cur_dir).split(os.path.sep)
            date = path[-1]
            if date != f'{YEAR}{MONTH}{DAY}':
                cur_dir = os.path.join(*path[:-1], f'{YEAR}{MONTH}{DAY}')
                self.filename_index = 1
            cur_dir = fix_unicode(cur_dir)
            
            to_make = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
                
            filename_sweep = os.path.join(to_make, f'{name}')
            filename_sweep = fix_unicode(filename_sweep)
            
        elif ('data_files' in core and len(core) < 3) or ('data_files' not in core and len(core) < 2):
            name = core[-1]
            
            cur_dir = os.path.join(core_dir, f'{YEAR}{MONTH}{DAY}')
            
            to_make = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
                
            filename_sweep = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}', f'{name}')
            filename_sweep = fix_unicode(filename_sweep)
            
        elif 'data_files' not in core and len(core) >= 2:
            name = core[-1]
            
            cur_dir = os.path.join(*core[:-1], f'{YEAR}{MONTH}{DAY}')
            cur_dir = fix_unicode(cur_dir)
            
            to_make = os.path.join(cur_dir, 'data_files', f'{folder_name}_{self.filename_index}')
            to_make = fix_unicode(to_make)
            
            if not exists(to_make):
                os.makedirs(to_make)
            
            filename_sweep = os.path.join(*core[:-1], f'{YEAR}{MONTH}{DAY}', 'data_files', f'{folder_name}_{self.filename_index}', f'{name}')
            filename_sweep = fix_unicode(filename_sweep)
        
        self.entry_filename.delete(0, tk.END)
        self.entry_filename.insert(0, filename_sweep)
        self.entry_filename.after(1)
            
    def start_logs(self):
        global list_of_devices
        global list_of_device_addresses
        global types_of_devices
        global device_to_sweep1
        global parameters_to_read
        global cur_dir
        global filename_sweep
        
        all_addresses = [list_of_devices_addresses[self.combo_to_sweep1.current()],
                         list_of_devices_addresses[self.combo_to_sweep2.current()],
                         list_of_devices_addresses[self.combo_to_sweep3.current()]]
        
        for parameter in parameters_to_read:
            address = parameter[:len(parameter) - parameter[::-1].index('.') - 1]
            all_addresses.append(address)
            
        all_addresses = np.unique(all_addresses)
        
        self.filename_index = get_filename_index(filename = filename_sweep, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
        
        core = os.path.normpath(filename_sweep)
        core = core.split(os.sep)
        _name = core[-1]
        try:
            folder_name = _name[:len(_name) - _name[::-1].index('.') - 1]
        except ValueError:
            folder_name = _name
        try:
            folder_name = folder_name[:len(folder_name) - folder_name[::-1].index('-') - 1]
        except ValueError:
            folder_name = _name
        folder_name = unify_filename(folder_name)
        
        for address in all_addresses:
            
            device = list_of_devices[list_of_devices_addresses.index(address)]
            if hasattr(device, 'loggable'):
                to_make = os.path.join(cur_dir, 'logs', f'{folder_name}_{self.filename_index}')
                to_make = fix_unicode(to_make)
                if not exists(to_make):
                    os.makedirs(to_make)
                name = types_of_devices[list_of_devices_addresses.index(address)]
                valid_address = "".join(x for x in address if x.isalnum())
                log_filename = os.path.join(to_make, f'logs_{name}_{valid_address}_{self.filename_index}.csv')
                log_filename = fix_unicode(log_filename)
                t = time.localtime()
                cur_time = time.strftime("%H:%M:%S", t)
                
                log = f'Name: {name}\nAddress: {address}\nTime: {cur_time}\n'
                
                for log_parameter in device.loggable:
                    log += f'{log_parameter}: {getattr(device, log_parameter)()}\n'
                
                log = log[:-1]
                
                with open(log_filename, 'w') as file:
                    try:    
                        file.write(log)
                    except Exception as e:
                        print(f'Exception happened while writing log for {name}, {address}: {e}')
                        file.close()
                    finally:
                        file.close()
        
    def pre_sweep1(self):
        global sweeper_write
        device = globals()['device_to_sweep1']
        parameter = globals()['parameter_to_sweep1']
        try:
            sweepable = device.sweepable[device.set_options.index(parameter)]
        except:
            sweepable = False
        try:
            from_sweep = self.from_sweep1
            to_sweep = self.to_sweep1
            ratio_sweep = self.ratio_sweep1
        except AttributeError:
            if self.manual_sweep_flags[0] == 1:
                data = pd.read_csv(self.manual_filenames[0])
                steps = data['steps']
                from_sweep = steps.values[0]
                to_sweep = steps.values[-1]
                ratio_sweep = self.delay_factor1 * steps.values.shape[0]
            else:
                raise Exception('Couldn\'t configure \'from_sweep\', \'to_sweep\'')
        delta = abs(to_sweep - from_sweep)
        
        try:
            self.eps1 = float(device.eps[device.set_options.index(parameter)])
        except:
            self.eps1 = 0.0001 * delta
        
        try:
            cur_value = float(getattr(device, parameter)())
        except Exception as e:
            print(f'Exception happened in pre-sweep 1: {e}')
            return

        if abs(cur_value - from_sweep) <= self.eps1:
            self.start_sweep_flag = True
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current master value is {cur_value}. \nStarting position is {from_sweep}, go to start?')
            if answer == True:
                
                def start_toplevel():
                    self.pop1 = tk.Toplevel(self)
                    
                    def center(toplevel):
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop1)
                    
                    self.label_approaching1 = tk.Label(self.pop1, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching1.grid(row = 0, column = 0)
                    
                    self.label_position1 = tk.Label(self.pop1, text = '', font = LARGE_FONT)
                    self.label_position1.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position1 - from_sweep)) > self.eps1:
                        self.current_position1 = float(getattr(device, parameter)())
                        self.label_position1.config(text = f'{"{:.3e}".format(self.current_position1)} / {"{:.3e}".format(from_sweep)}')
                        self.label_position1.after(100, update_position)
                        self.start_sweep_flag = False
                    else:
                        self.start_sweep_flag = True
                        self.pop1.destroy()
                        
                def slow_approach(steps: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if len(steps) > 0:
                        getattr(device, f'set_{parameter}')(value = steps[0])
                        self.label_position1.after(int(delay * 1000), lambda steps = steps[1:], delay = delay: slow_approach(steps, delay))
                
                if not sweepable:
                    answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                    if answer2 == False:
                        getattr(device, f'set_{parameter}')(value = from_sweep)
                        self.start_sweep_flag = True
                    elif answer2 == True:
                       _delta = abs(cur_value - from_sweep)
                       step = ratio_sweep * self.delay_factor1
                       nsteps = abs(int(_delta // step) + 1)
                       steps = list(np.linspace(cur_value, from_sweep, nsteps + 1))
                       start_toplevel()
                       self.current_position1 = float(getattr(device, parameter)())
                       update_position()
                       slow_approach(steps, self.delay_factor1)
                    else:
                        return
                        
                else:
                    getattr(device, f'set_{parameter}')(value = from_sweep, speed = ratio_sweep)
                    
                    start_toplevel()
                    self.current_position1 = float(getattr(device, parameter)())
                    update_position()
                    
            elif answer == False:
                self.start_sweep_flag = True
            else:
                self.start_sweep_flag = False
                return
                    
    def pre_sweep2(self):
        global sweeper_write
        device = globals()['device_to_sweep2']
        parameter = globals()['parameter_to_sweep2']
        try:
            sweepable = device.sweepable[device.set_options.index(parameter)]
        except:
            sweepable = False
        try:
            from_sweep = self.from_sweep2
            to_sweep = self.to_sweep2
            ratio_sweep = self.ratio_sweep2
        except AttributeError:
            if self.manual_sweep_flags[1] == 1:
                data = pd.read_csv(self.manual_filenames[1])
                steps = data['steps']
                from_sweep = steps.values[0]
                to_sweep = steps.values[-1]
                ratio_sweep = self.delay_factor2 * steps.values.shape[0]
            else:
                raise Exception('Couldn\'t configure \'from_sweep\', \'to_sweep\'')
        delta = abs(to_sweep - from_sweep)
        
        try:
            self.eps2 = float(device.eps[device.set_options.index(parameter)])
        except:
            self.eps2 = 0.0001 * delta
        
        try:
            cur_value = float(getattr(device, parameter)())
        except Exception as e:
            print(f'Exception happened in pre-sweep 1: {e}')
            return

        if abs(cur_value - from_sweep) <= self.eps2:
            self.start_sweep_flag = True
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current slave value is {cur_value}. \nStarting position is {from_sweep}, go to start?')
            if answer == True:
                
                def start_toplevel():
                    self.pop2 = tk.Toplevel(self)
                    
                    def center(toplevel):
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop2)
                    
                    self.label_approaching2 = tk.Label(self.pop2, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching2.grid(row = 0, column = 0)
                    
                    self.label_position2 = tk.Label(self.pop2, text = '', font = LARGE_FONT)
                    self.label_position2.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position2 - from_sweep)) > self.eps2:
                        self.current_position2 = float(getattr(device, parameter)())
                        self.label_position2.config(text = f'{"{:.3e}".format(self.current_position2)} / {"{:.3e}".format(from_sweep)}')
                        self.label_position2.after(100, update_position)
                        self.start_sweep_flag = False
                    else:
                        self.start_sweep_flag = True
                        self.pop2.destroy()
                        
                def slow_approach(steps: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if len(steps) > 0:
                        getattr(device, f'set_{parameter}')(value = steps[0])
                        self.label_position2.after(int(delay * 1000), lambda steps = steps[1:], delay = delay: slow_approach(steps, delay))
                
                if not sweepable:
                    answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                    if answer2 == False:
                        getattr(device, f'set_{parameter}')(value = from_sweep)
                        self.start_sweep_flag = True
                    elif answer2 == True:
                       _delta = abs(cur_value - from_sweep)
                       step = ratio_sweep * self.delay_factor2
                       nsteps = abs(int(_delta // step) + 1)
                       steps = list(np.linspace(cur_value, from_sweep, nsteps + 1))
                       start_toplevel()
                       self.current_position2 = float(getattr(device, parameter)())
                       update_position()
                       slow_approach(steps, self.delay_factor2)
                    else:
                        return
                        
                else:
                    getattr(device, f'set_{parameter}')(value = from_sweep, speed = ratio_sweep)
                    
                    start_toplevel()
                    self.current_position2 = float(getattr(device, parameter)())
                    update_position()
                    
            elif answer == False:
                self.start_sweep_flag = True
            else:
                self.start_sweep_flag = False
                return
                
    def pre_sweep3(self):
        
        def try_start():
            global sweeper_write
            if self.start_sweep_flag:
                self.start_logs()
                sweeper_write = Sweeper_write()
                self.open_graph()
            else:
                self.after(100, try_start)
        
        global sweeper_write
        device = globals()['device_to_sweep3']
        parameter = globals()['parameter_to_sweep3']
        try:
            sweepable = device.sweepable[device.set_options.index(parameter)]
        except:
            sweepable = False
        try:
            from_sweep = self.from_sweep3
            to_sweep = self.to_sweep3
            ratio_sweep = self.ratio_sweep3
        except AttributeError:
            if self.manual_sweep_flags[2] == 1:
                data = pd.read_csv(self.manual_filenames[2])
                steps = data['steps']
                from_sweep = steps.values[0]
                to_sweep = steps.values[-1]
                ratio_sweep = self.delay_factor3 * steps.values.shape[0]
            else:
                raise Exception('Couldn\'t configure \'from_sweep\', \'to_sweep\'')
        delta = abs(to_sweep - from_sweep)
        
        try:
            self.eps3 = float(device.eps[device.set_options.index(parameter)])
        except:
            self.eps3 = 0.0001 * delta
        
        try:
            cur_value = float(getattr(device, parameter)())
        except Exception as e:
            print(f'Exception happened in pre-sweep 3: {e}')
            try_start()
            return

        if abs(cur_value - from_sweep) <= self.eps3:
            try_start()
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current slave-slave value is {cur_value}. \nStarting position is {from_sweep}, go to start?')
            if answer == True:
                
                def start_toplevel():
                    self.pop3 = tk.Toplevel(self)
                    
                    def center(toplevel):
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop3)
                    
                    self.label_approaching3 = tk.Label(self.pop3, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching3.grid(row = 0, column = 0)
                    
                    self.label_position3 = tk.Label(self.pop3, text = '', font = LARGE_FONT)
                    self.label_position3.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position3 - from_sweep)) > self.eps3:
                        self.current_position3 = float(getattr(device, parameter)())
                        self.label_position3.config(text = f'{"{:.3e}".format(self.current_position3)} / {"{:.3e}".format(from_sweep)}')
                        self.label_position3.after(100, update_position)
                    else:
                        self.pop3.destroy()
                        try_start()
                        
                def slow_approach(steps: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if len(steps) > 0:
                        getattr(device, f'set_{parameter}')(value = steps[0])
                        self.label_position3.after(int(delay * 1000), lambda steps = steps[1:], delay = delay: slow_approach(steps, delay))
                
                if not sweepable:
                    answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                    if answer2 == False:
                        getattr(device, f'set_{parameter}')(value = from_sweep)
                        try_start()
                    elif answer2 == True:
                        _delta = abs(cur_value - from_sweep)
                        step = ratio_sweep * self.delay_factor3
                        nsteps = abs(int(_delta // step) + 1)
                        steps = list(np.linspace(cur_value, from_sweep, nsteps + 1))
                        start_toplevel()
                        self.current_position3 = float(getattr(device, parameter)())
                        update_position()
                        slow_approach(steps, self.delay_factor3)
                    else:
                        return
                        
                else:
                    getattr(device, f'set_{parameter}')(value = from_sweep, speed = ratio_sweep)
                    
                    start_toplevel()
                    self.current_position3 = float(getattr(device, parameter)())
                    update_position()
                    
            elif answer == False:
                try_start()
            else:
                self.start_sweep_flag = False
                return
            
    def pre_double_sweep(self, i, j):
        global sweeper_write
        global condition
        device1 = globals()[f'device_to_sweep{i}']
        parameter1 = globals()[f'parameter_to_sweep{i}']
        device2 = globals()[f'device_to_sweep{j}']
        parameter2 = globals()[f'parameter_to_sweep{j}']
        
        def try_start():
            global sweeper_write
            if self.start_sweep_flag:
                self.start_logs()
                sweeper_write = Sweeper_write()
                self.open_graph()
            else:
                self.after(100, try_start)
        
        from_sweep1 = self.__dict__[f'from_sweep{i}']
        to_sweep1 = self.__dict__[f'to_sweep{i}']
        ratio_sweep1 = self.__dict__[f'ratio_sweep{i}']
        
        from_sweep2 = self.__dict__[f'from_sweep{j}']
        to_sweep2 = self.__dict__[f'to_sweep{j}']
        ratio_sweep2 = self.__dict__[f'ratio_sweep{j}']
                
        delta1 = abs(to_sweep1 - from_sweep1)
        delta2 = abs(to_sweep2 - from_sweep2)
        
        try:
            self.eps1 = float(device1.eps[device1.set_options.index(parameter1)])
        except:
            self.eps1 = 0.0001 * delta1
        
        try:
            self.eps2 = float(device2.eps[device2.set_options.index(parameter2)])
        except:
            self.eps2 = 0.0001 * delta2
        
        try:
            cur_value1 = float(getattr(device1, parameter1)())
            cur_value2 = float(getattr(device2, parameter2)())
        except Exception as e:
            print(f'Exception happened in pre-double-sweep: {e}')
            try_start()
            return

        func = condition_2_func(condition, from_sweep2)
        try:
            start_master = optimize.newton(func, x0 = from_sweep1, maxiter = 500)
        except Exception as e:
            messagebox.showerror('Solution not find', f'Exception in pre-double-sweep: {e}')
            return

        if (abs(cur_value1 - start_master) <= self.eps1) and (abs(cur_value2 - from_sweep2) <= self.eps2):
            try_start()
            return
        else:
            answer = messagebox.askyesnocancel('Start warning', f'Current (master; slave) is ({cur_value1};{cur_value2}). \nStarting position is ({start_master};{from_sweep2}), go to start?')
            if answer == True:
                
                def start_toplevel():
                    self.pop = tk.Toplevel(self)
                    
                    def center(toplevel):
                    
                        screen_width = toplevel.winfo_screenwidth()
                        screen_height = toplevel.winfo_screenheight()
                    
                        size = tuple(int(_) for _ in toplevel.geometry().split('+')[0].split('x'))
                        x = screen_width/2 - size[0]/2
                        y = screen_height/2 - size[1]/2
                    
                        toplevel.geometry("+%d+%d" % (x, y))
                    
                    center(self.pop)
                    
                    self.label_approaching = tk.Label(self.pop, text = 'Approaching start', font = LARGE_FONT)
                    self.label_approaching.grid(row = 0, column = 0)
                    
                    self.label_position = tk.Label(self.pop, text = '', font = LARGE_FONT)
                    self.label_position.grid(row = 1, column = 0)
                    
                def update_position():
                    global sweeper_write
                    if (abs(self.current_position1 - start_master) > self.eps1) or (abs(self.current_position2 - from_sweep2) > self.eps2):
                        self.current_position1 = float(getattr(device1, parameter1)())
                        self.current_position2 = float(getattr(device2, parameter2)())
                        self.label_position.config(text = f'({"{:.3e}".format(self.current_position1)};{"{:.3e}".format(self.current_position2)}) / ({"{:.3e}".format(start_master)};{"{:.3e}".format(from_sweep2)})')
                        self.label_position.after(100, update_position)
                    else:
                        self.pop.destroy()
                        try_start()
                        
                def slow_approach(steps1: list, steps2: list, delay: float):
                    '''
                    Parameters
                    ----------
                    steps : list
                        List of values for device to set.
                    delay : float
                        Time to sleep between steps
                    '''
                    global sweeper_write
                    if max(len(steps1), len(steps2)) > 0:
                        try:
                            getattr(device1, f'set_{parameter1}')(value = steps1[0])
                        except IndexError:
                            pass
                        try:
                            getattr(device2, f'set_{parameter2}')(value = steps2[0])
                        except IndexError:
                            pass
                        self.label_position.after(int(delay * 1000), 
                                                  lambda steps1 = steps1[1:], 
                                                  steps2 = steps2[1:], 
                                                  delay = delay: slow_approach(steps1, steps2, delay))
                
                answer2 = messagebox.askyesnocancel('Start approach', 'Go slow (Yes) or jump to start (No)?')
                if answer2 == False:
                    getattr(device1, f'set_{parameter1}')(value = start_master)
                    getattr(device2, f'set_{parameter2}')(value = from_sweep2)
                    try_start()
                elif answer2 == True:
                    
                    _delta1 = abs(cur_value1 - start_master)
                    step1 = ratio_sweep1 * self.__dict__[f'delay_factor{i}']
                    nsteps1 = abs(int(_delta1 // step1) + 1)
                    steps1 = list(np.linspace(cur_value1, start_master, nsteps1 + 1))
                    _delta2 = abs(cur_value2 - from_sweep2)
                    step2 = ratio_sweep2 * self.__dict__[f'delay_factor{j}']
                    nsteps2 = abs(int(_delta2 // step2) + 1)
                    steps2 = list(np.linspace(cur_value2, from_sweep2, nsteps2 + 1))
                    start_toplevel()
                    self.current_position1 = float(getattr(device1, parameter1)())
                    self.current_position2 = float(getattr(device2, parameter2)())
                    update_position()
                    slow_approach(steps1, steps2, max(self.__dict__[f'delay_factor{i}'], self.__dict__[f'delay_factor{j}']))
                                  
                else:
                    return

                    
            elif answer == False:
                try_start()
            else:
                return

    def start_sweeping(self):

        global list_of_devices
        global types_of_devices
        global device_to_sweep1
        global device_to_sweep2
        global device_to_sweep3
        global parameter_to_sweep1
        global parameter_to_sweep2
        global parameter_to_sweep3
        global from_sweep1
        global to_sweep1
        global ratio_sweep1
        global back_ratio_sweep1
        global delay_factor1
        global back_delay_factor1
        global from_sweep2
        global to_sweep2
        global ratio_sweep2
        global back_ratio_sweep2
        global delay_factor2
        global back_delay_factor2
        global from_sweep3
        global to_sweep3
        global ratio_sweep3
        global back_ratio_sweep3
        global delay_factor3
        global back_delay_factor3
        global parameters_to_read_dict
        global parameters_to_read
        global sweeper_flag1
        global sweeper_flag2
        global sweeper_flag3
        global stop_flag
        global pause_flag
        global condition
        global script
        global interpolated3D
        global uniform3D
        global columns
        global manual_filenames
        global manual_sweep_flags
        global zero_time
        global back_and_forth_master
        #global fastmode_master_flag
        global snakemode_master_flag
        global back_and_forth_slave
        #global fastmode_slave_flag
        global snakemode_slave_flag
        global back_and_forth_slave_slave
        global sweeper_write
        
        self.start_sweep_flag = True

        if self.status_manual1.get() == 0:    

            try:
                self.from_sweep1 = float(self.entry_from1.get())
                from_sweep1 = self.from_sweep1
            except:
                messagebox.showerror('Invalid value in "From1" entrybox', f'Can not convert {self.entry_from1.get()} to float')
                self.start_sweep_flag = False
                
            try:
                self.to_sweep1 = float(self.entry_to1.get())
                to_sweep1 = self.to_sweep1
            except:
                messagebox.showerror('Invalid value in "To1" entrybox', f'Can not convert {self.entry_to1.get()} to float')
                self.start_sweep_flag = False
        
        try:
            self.delay_factor1 = float(self.entry_delay_factor1.get())
            delay_factor1 = self.delay_factor1
        except:
            messagebox.showerror('Invalid value in "Delay factor1" entrybox', f'Can not convert {self.entry_delay_factor1.get()} to float')
            self.start_sweep_flag = False
        
        if self.status_manual1.get() == 0:  
        
            try:
                self.ratio_sweep1 = float(self.entry_ratio1.get())
                
                if self.back_ratio1_init == '':
                    back_ratio_sweep1 = self.ratio_sweep1
                else:
                    try:
                        back_ratio_sweep1 = float(self.back_ratio1_init)
                    except:
                        messagebox.showerror('Invalid value in "back_ratio1" entrybox', f'Can not convert {self.back_ratio1_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option1 == 'step':
                    self.ratio_sweep1 = self.ratio_sweep1 / self.delay_factor1
                if self.from_sweep1 > self.to_sweep1 and self.ratio_sweep1 > 0:
                    self.ratio_sweep1 = - self.ratio_sweep1
                ratio_sweep1 = self.ratio_sweep1
                        
                if self.back_delay_factor1_init == '':
                    back_delay_factor1 = delay_factor1
                else:
                    try:
                        back_delay_factor1 = float(self.back_delay_factor1_init)
                    except:
                        messagebox.showerror('Invalid value in "back_delay_factor1" entrybox', f'Can not convert {self.back_delay_factor1_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option1 == 'step':
                    back_ratio_sweep1 = back_ratio_sweep1 / back_delay_factor1
                if back_ratio_sweep1 * ratio_sweep1 > 0:
                    back_ratio_sweep1 = - back_ratio_sweep1
                
            except:
                messagebox.showerror('Invalid value in "Ratio1" entrybox', f'Can not convert {self.entry_ratio1.get()} to float')
                self.start_sweep_flag = False
            
        if self.status_manual2.get() == 0:  
            
            try:
                self.from_sweep2 = float(self.entry_from2.get())
                from_sweep2 = self.from_sweep2
            except:
                messagebox.showerror('Invalid value in "From2" entrybox', f'Can not convert {self.entry_from2.get()} to float')
                self.start_sweep_flag = False
                
            try:
                self.to_sweep2 = float(self.entry_to2.get())
                to_sweep2 = self.to_sweep2
            except:
                messagebox.showerror('Invalid value in "To2" entrybox', f'Can not convert {self.entry_to2.get()} to float')
                self.start_sweep_flag = False
        
        try:
            self.delay_factor2 = float(self.entry_delay_factor2.get())
            delay_factor2 = self.delay_factor2
        except:
            messagebox.showerror('Invalid value in "Delay factor2" entrybox', f'Can not convert {self.entry_delay_factor2.get()} to float')
            self.start_sweep_flag = False
        
        if self.status_manual2.get() == 0:  
        
            try:
                self.ratio_sweep2 = float(self.entry_ratio2.get())
                
                if self.back_ratio2_init == '':
                    back_ratio_sweep2 = self.ratio_sweep2
                else:
                    try:
                        back_ratio_sweep2 = float(self.back_ratio2_init)
                    except:
                        messagebox.showerror('Invalid value in "back_ratio2" entrybox', f'Can not convert {self.back_ratio2_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option2 == 'step':
                    self.ratio_sweep2 = self.ratio_sweep2 / self.delay_factor2
                if self.from_sweep2 > self.to_sweep2 and self.ratio_sweep2 > 0:
                    self.ratio_sweep2 = - self.ratio_sweep2
                ratio_sweep2 = self.ratio_sweep2
                
                if self.back_delay_factor2_init == '':
                    back_delay_factor2 = delay_factor2
                else:
                    try:
                        back_delay_factor2 = float(self.back_delay_factor2_init)
                    except:
                        messagebox.showerror('Invalid value in "back_delay_factor2" entrybox', f'Can not convert {self.back_delay_factor2_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option2 == 'step':
                    back_ratio_sweep2 = back_ratio_sweep2 / back_delay_factor2
                if back_ratio_sweep2 * ratio_sweep2 > 0:
                    back_ratio_sweep2 = - back_ratio_sweep2
                
            except:
                messagebox.showerror('Invalid value in "Ratio2" entrybox', f'Can not convert {self.entry_ratio2.get()} to float')
                self.start_sweep_flag = False
                
        if self.status_manual3.get() == 0:  
                
            try:
                self.from_sweep3 = float(self.entry_from3.get())
                from_sweep3 =self.from_sweep3
            except:
                messagebox.showerror('Invalid value in "From3" entrybox', f'Can not convert {self.entry_from3.get()} to float')
                self.start_sweep_flag = False
                
            try:
                self.to_sweep3 = float(self.entry_to3.get())
                to_sweep3 = self.to_sweep3
            except:
                messagebox.showerror('Invalid value in "To3" entrybox', f'Can not convert {self.entry_to3.get()} to float')
                self.start_sweep_flag = False
        
        try:
            self.delay_factor3 = float(self.entry_delay_factor3.get())
            delay_factor3 = self.delay_factor3
        except:
            messagebox.showerror('Invalid value in "Delay factor3" entrybox', f'Can not convert {self.entry_delay_factor3.get()} to float')
            self.start_sweep_flag = False
        
        if self.status_manual3.get() == 0:  
        
            try:
                self.ratio_sweep3 = float(self.entry_ratio3.get())
                
                if self.back_ratio3_init == '':
                    back_ratio_sweep3 = self.ratio_sweep3
                else:
                    try:
                        back_ratio_sweep3 = float(self.back_ratio3_init)
                    except:
                        messagebox.showerror('Invalid value in "back_ratio3" entrybox', f'Can not convert {self.back_ratio3_init} to float')
                        self.start_sweep_flag = False
                
                if self.count_option3 == 'step':
                    self.ratio_sweep3 = self.ratio_sweep3 / self.delay_factor3
                if self.from_sweep3 > self.to_sweep3 and self.ratio_sweep3 > 0:
                    self.ratio_sweep3 = - self.ratio_sweep3
                ratio_sweep3 = self.ratio_sweep3
                        
                if self.back_delay_factor3_init == '':
                    back_delay_factor3 = delay_factor3
                else:
                    try:
                        back_delay_factor3 = float(self.back_delay_factor3_init)
                    except:
                        messagebox.showerror('Invalid value in "back_delay_factor3" entrybox', f'Can not convert {self.back_delay_factor3_init} to float')
                        self.start_sweep_flag = False
                 
                if self.count_option3 == 'step':
                    back_ratio_sweep3 = back_ratio_sweep3 / back_delay_factor3
                if back_ratio_sweep3 * ratio_sweep3 > 0:
                    back_ratio_sweep3 = - back_ratio_sweep3
                
            except:
                messagebox.showerror('Invalid value in "ratio3" entrybox', f'Can not convert {self.entry_ratio3.get()} to float')
                self.start_sweep_flag = False
            
        def get_key(val, my_dict):
            for key, value in my_dict.items():
                if val == value:
                    return key
        
        self.list_to_read = []
        # asking multichoise to get parameters to read
        selection = self.lstbox_to_read.curselection()
        for i in selection:
            entrada = self.lstbox_to_read.get(i)
            self.list_to_read.append(get_key(entrada, self.dict_lstbox))
        parameters_to_read = self.list_to_read
        parameters_to_read_dict = self.dict_lstbox

        # creating columns
        device_to_sweep1 = list_of_devices[self.combo_to_sweep1.current()]
        parameters1 = device_to_sweep1.set_options
        parameter_to_sweep1 = parameters1[self.sweep_options1.current()]
        
        device_to_sweep2 = list_of_devices[self.combo_to_sweep2.current()]
        parameters2 = device_to_sweep2.set_options
        parameter_to_sweep2 = parameters2[self.sweep_options2.current()]
        
        device_to_sweep3 = list_of_devices[self.combo_to_sweep3.current()]
        parameters3 = device_to_sweep3.set_options
        parameter_to_sweep3 = parameters3[self.sweep_options3.current()]
        
        manual_filenames = self.manual_filenames
        manual_sweep_flags = self.manual_sweep_flags
        
        columns_device1 = self.combo_to_sweep1['values'][self.combo_to_sweep1.current()]
        columns_parameters1 = self.sweep_options1['values'][self.sweep_options1.current()]
        
        columns_device2 = self.combo_to_sweep2['values'][self.combo_to_sweep2.current()]
        columns_parameters2 = self.sweep_options2['values'][self.sweep_options2.current()]
        
        columns_device3 = self.combo_to_sweep3['values'][self.combo_to_sweep3.current()]
        columns_parameters3 = self.sweep_options3['values'][self.sweep_options3.current()]
        
        columns = ['Time', columns_device1 + '.' + columns_parameters1 + '_sweep',
                   columns_device2 + '.' + columns_parameters2 + '_sweep',
                   columns_device3 + '.' + columns_parameters3 + '_sweep']
        
        for option in parameters_to_read:
            columns.append(parameters_to_read_dict[option])

        # fixing sweeper parmeters
        
        self.determine_filename_sweep()
        
        interpolated3D = self.interpolated
        uniform3D = self.uniform
        
        for i in range(1, 4):
            self.save_manual_status(i)
        self.save_back_and_forth_master_status()
        self.save_back_and_forth_slave_status()
        self.save_back_and_forth_slave_slave_status()
        condition = self.text_condition.get(1.0, tk.END)[:-1]
        script = self.script
        manual_sweep_flags = self.manual_sweep_flags
        manual_filenames = self.manual_filenames 
        
        self.rewrite_preset()

        if self.start_sweep_flag:
            zero_time = time.perf_counter()
            stop_flag = False
            pause_flag = False
            sweeper_flag1 = False
            sweeper_flag2 = False
            sweeper_flag3 = True
            snakemode_master_flag = self.status_snakemode_master.get()
            #fastmode_master_flag = self.status_fastmode_master.get()
            snakemode_slave_flag = self.status_snakemode_slave.get()
            #fastmode_slave_flag = self.status_fastmode_slave.get()
            conds = rm_all(condition)

            if len(conds) == 1:
                conds = conds[0]
                if ('z' in conds or 'Z' in conds) and ('y' in conds or 'Y' in conds) and ('==' in conds or '=' in conds):
                    self.pre_double_sweep(2, 3)
                elif ('x' in conds or 'X' in conds) and ('y' in conds or 'Y' in conds) and ('==' in conds or '=' in conds):
                    self.pre_double_sweep(1, 2)
            else:
                self.pre_sweep1()
                self.pre_sweep2()
                self.pre_sweep3()

class Sweeper_write(threading.Thread):

    def __init__(self):

        threading.Thread.__init__(self)
        
        self.sweeper_flag1 = sweeper_flag1
        self.sweeper_flag2 = sweeper_flag2
        self.sweeper_flag3 = sweeper_flag3
        self.setget_flag = setget_flag
        self.device_to_sweep1 = device_to_sweep1
        self.parameter_to_sweep1 = parameter_to_sweep1
        self.parameters_to_read = parameters_to_read
        self.parameters_to_read_dict = parameters_to_read_dict
        print(f'Parameters to read are {self.parameters_to_read}')
        if manual_sweep_flags[0] == 1:
            data = pd.read_csv(manual_filenames[0])
            self.from_sweep1 = data['steps'].values[0]
            self.to_sweep1 = data['steps'].values[-1]
        else:
            self.from_sweep1 = float(from_sweep1)
            self.to_sweep1 = float(to_sweep1)
        self.cur_manual_index1 = 0
        self.ratio_sweep1 = float(ratio_sweep1)
        self.delay_factor1 = float(delay_factor1)
        self.value1 = float(self.from_sweep1)
        if parameter_to_sweep1 in device_to_sweep1.get_options:
            self.value1 = float(getattr(device_to_sweep1, parameter_to_sweep1)())

        self.condition = condition
        self.condition_status = 'unknown'
        self.time1 = (float(from_sweep1) - float(to_sweep1)) / float(ratio_sweep1)
        self.filename_sweep = filename_sweep
        self.columns = columns
        self.sweepable1 = False
        self.started = False
        self.inner_count = 0
        
        if hasattr(device_to_sweep1, 'sweepable') and len(manual_sweep_flags) == 1 and stepper_flag == False:
            if device_to_sweep1.sweepable[device_to_sweep1.set_options.index(parameter_to_sweep1)]:
                self.sweepable1 = True
                self.upcoming_value1 = self.value1
        
        globals()['dataframe'] = []
        
        if self.sweepable1 == False:
            self.step1 = float(delay_factor1) * float(ratio_sweep1)
            self.back_step1 = float(back_delay_factor1) * float(back_ratio_sweep1)
        else:
            if stepper_flag == False:
                self.step1 = (float(to_sweep1) - float(self.value1))
                self.back_step1 = float(self.value1) - float(from_sweep1)
            else:
                self.step1 = float(delay_factor1) * float(ratio_sweep1)
                self.back_step1 = float(back_delay_factor1) * float(back_ratio_sweep1)
        
        try:
            self.nstep1 = (float(to_sweep1) - float(from_sweep1)) / self.ratio_sweep1 / self.delay_factor1
            self.nstep1 = int(abs(self.nstep1))
        except ValueError:
            self.nstep1 = 1
            
        if self.sweepable1 == True and stepper_flag == False:
            self.nstep = 1
            
        if self.sweeper_flag2 == True:
            self.device_to_sweep2 = device_to_sweep2
            self.parameter_to_sweep2 = parameter_to_sweep2
            print(f'Parameter to sweep 2 is {self.parameter_to_sweep2}')
            if manual_sweep_flags[1] == 1:
                data = pd.read_csv(manual_filenames[1])
                self.from_sweep2 = data['steps'].values[0]
                self.to_sweep2 = data['steps'].values[-1]
                globals()['from_sweep2'] = self.from_sweep2
                globals()['to_sweep2'] = self.to_sweep2
            else:
                self.from_sweep2 = float(from_sweep2)
                self.to_sweep2 = float(to_sweep2)
            self.cur_manual_index2 = 0
            self.ratio_sweep2 = float(ratio_sweep2)
            self.delay_factor2 = float(delay_factor2)
            self.filename_sweep = filename_sweep
            self.value2 = float(self.from_sweep2)
            if parameter_to_sweep2 in device_to_sweep2.get_options:
                self.value2 = float(getattr(device_to_sweep2, parameter_to_sweep2)())
            self.columns = columns
            self.time2 = (float(from_sweep2) - float(to_sweep2)) / float(ratio_sweep2)
            
            try:
                self.nstep2 = (float(to_sweep2) - float(from_sweep2)) / self.ratio_sweep2 / self.delay_factor2
                self.nstep2 = int(abs(self.nstep2))
                
                filename = globals()['filename_sweep']
                index = get_filename_index(filename = filename, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
                self.mapper2D = mapper2D(self.parameter_to_sweep1, self.parameter_to_sweep2, 
                                         self.parameters_to_read, filename_sweep, interpolated = interpolated2D,
                                         uniform = uniform2D, _from = self.from_sweep2, _to = self.to_sweep2,
                                         nsteps = self.nstep2, walks = globals()['back_and_forth_slave'], 
                                         index_filename = index)
                
            except ValueError:
                self.nstep2 = 1
                
            self.sweepable2 = False
                
            if hasattr(device_to_sweep2, 'sweepable') and len(manual_sweep_flags) == 2  and stepper_flag == False:
                if device_to_sweep2.sweepable[device_to_sweep2.set_options.index(parameter_to_sweep2)]:
                            self.sweepable2 = True
                            self.upcoming_value2 = self.value2
                            
            if self.sweepable2 == False:
                self.step2 = float(delay_factor2) * float(ratio_sweep2)
                self.back_step2 = float(back_delay_factor2) * float(back_ratio_sweep2)
            else:
                if stepper_flag == False:
                    self.step2 = (float(to_sweep2) - float(self.value2))
                    self.back_step2 = float(self.value2) - float(from_sweep2)
                else:
                    self.step2 = float(delay_factor2) * float(ratio_sweep2)
                    self.back_step2 = float(back_delay_factor2) * float(back_ratio_sweep2)
                
            if self.sweepable2 == True and stepper_flag == False:
                self.nstep2 = 1
                
            self.step1 = float(delay_factor1) * float(ratio_sweep1)
            self.back_step1 = float(back_delay_factor1) * float(back_ratio_sweep1)
            
            try:
                self.nstep1 = (float(to_sweep1) - float(from_sweep1)) / self.ratio_sweep1 / self.delay_factor1
                self.nstep1 = int(abs(self.nstep1))
            except ValueError:
                self.nstep1 = 1
                
            globals()['from_sweep1'] -+ self.step1
            globals()['to_sweep1'] += self.step1
            
        if self.sweeper_flag3 == True:
            self.device_to_sweep2 = device_to_sweep2
            self.device_to_sweep3 = device_to_sweep3
            self.parameter_to_sweep2 = parameter_to_sweep2
            self.parameter_to_sweep3 = parameter_to_sweep3
            if manual_sweep_flags[1] == 1:
                data = pd.read_csv(manual_filenames[1])
                self.from_sweep2 = data['steps'].values[0]
                self.to_sweep2 = data['steps'].values[-1]
                globals()['from_sweep2'] = self.from_sweep2
                globals()['to_sweep2'] = self.to_sweep2
            else:
                self.from_sweep2 = float(from_sweep2)
                self.to_sweep2 = float(to_sweep2)
            self.cur_manual_index2 = 0
            self.ratio_sweep2 = float(ratio_sweep2)
            self.delay_factor2 = float(delay_factor2)
            if manual_sweep_flags[2] == 1:
                data = pd.read_csv(manual_filenames[2])
                self.from_sweep3 = data['steps'].values[0]
                self.to_sweep3 = data['steps'].values[-1]
                globals()['from_sweep3'] = self.from_sweep3
                globals()['to_sweep3'] = self.to_sweep3
            else:
                self.from_sweep3 = float(from_sweep3)
                self.to_sweep3 = float(to_sweep3)
            self.cur_manual_index3 = 0
            self.ratio_sweep3 = float(ratio_sweep3)
            self.delay_factor3 = float(delay_factor3)
            self.filename_sweep = filename_sweep
            self.value2 = float(self.from_sweep2)
            if parameter_to_sweep2 in device_to_sweep2.get_options:
                self.value2 = float(getattr(device_to_sweep2, parameter_to_sweep2)())
            self.value3 = float(self.from_sweep3)
            if parameter_to_sweep3 in device_to_sweep3.get_options:
                self.value3 = float(getattr(device_to_sweep3, parameter_to_sweep3)())
            self.columns = columns
            self.step2 = float(delay_factor2) * float(ratio_sweep2)
            self.step3 = float(delay_factor3) * float(ratio_sweep3)
            self.time2 = (float(from_sweep2) - float(to_sweep2)) / float(ratio_sweep2)
            self.time3 = (float(from_sweep3) - float(to_sweep3)) / float(ratio_sweep3)
            
            try:
                self.nstep2 = (float(to_sweep2) - float(from_sweep2)) / self.ratio_sweep2 / self.delay_factor2
                self.nstep2 = int(abs(self.nstep2))
            except ValueError:
                self.nstep2 = 1
                
            try:
                self.nstep3 = (float(to_sweep3) - float(from_sweep3)) / self.ratio_sweep3 / self.delay_factor3
                self.nstep3 = int(abs(self.nstep3))
                
                filename = globals()['filename_sweep']
                index = get_filename_index(filename = filename, core_dir = core_dir, YMD = f'{YEAR}{MONTH}{DAY}')
                self.mapper3D = mapper3D(self.parameter_to_sweep1, self.parameter_to_sweep2, self.parameter_to_sweep3, 
                                         self.parameters_to_read, filename_sweep, interpolated = interpolated3D,
                                         uniform = uniform3D, _from = self.from_sweep3, _to = self.to_sweep3,
                                         nsteps = self.nstep3, walks = globals()['back_and_forth_slave_slave'],
                                         index_filename = index)
                
            except ValueError:
                self.nstep3 = 1
                
            self.sweepable2 = False
            
            self.sweepable3 = False

            if hasattr(device_to_sweep3, 'sweepable') and len(manual_sweep_flags) == 3  and stepper_flag == False:
                if device_to_sweep3.sweepable[device_to_sweep3.set_options.index(parameter_to_sweep3)]:
                            self.sweepable3 = True
                            self.upcoming_value3 = self.value3
                            
            if self.sweepable3 == False:
                self.step3 = float(delay_factor3) * float(ratio_sweep3)
                self.back_step3 = float(back_delay_factor3) * float(back_ratio_sweep3)
            else:
                if stepper_flag == False:
                    self.step3 = (float(to_sweep3) - float(self.value3))
                    self.back_step3 = float(self.value3) - float(from_sweep3)
                else:
                    self.step3 = float(delay_factor3) * float(ratio_sweep3)
                    self.back_step3 = float(back_delay_factor3) * float(back_ratio_sweep3)
                
            self.step1 = float(delay_factor1) * float(ratio_sweep1)
            self.step2 = float(delay_factor2) * float(ratio_sweep2)
            self.back_step1 = float(back_delay_factor1) * float(back_ratio_sweep1)
            self.back_step2 = float(back_delay_factor2) * float(back_ratio_sweep2)
            
            try:
                self.nstep1 = (float(to_sweep1) - float(from_sweep1)) / self.ratio_sweep1 / self.delay_factor1
                self.nstep1 = int(abs(self.nstep1))
            except ValueError:
                self.nstep1 = 1
                
            if self.sweepable3 == True and stepper_flag == False:
                self.nstep3 = 1
                
            globals()['from_sweep1'] -+ self.step1
            globals()['to_sweep1'] += self.step1
            globals()['from_sweep2'] -+ self.step2
            globals()['to_sweep2'] += self.step2
            
        #print(f'Manual_sweep_flags are {manual_sweep_flags}\nrange1 = [{from_sweep1}:{to_sweep1}), ratio_sweep1 = {ratio_sweep1}\nrange2 = [{from_sweep2}:{to_sweep2}), ratio_sweep2 = {ratio_sweep2}\nrange3 = [{from_sweep3}:{to_sweep3}), ratio_sweep3 = {ratio_sweep3}')

        print(f'Step1 is {self.step1}, nstep1 is {self.nstep1}')
        try: 
            print(f'step2 is {self.step2}, nstep2 is {self.nstep2}')
        except:
            pass
        try:
            print(f'step3 is {self.step3}, nstep3 is {self.nstep3}')
        except:
            pass

        print(f'Sweepable1 = {self.sweepable1}')
        
        try:
            print(f'Sweepable2 = {self.sweepable2}')
        except:
            pass
        
        try:
            print(f'Sweepable3 = {self.sweepable3}')
        except:
            pass

        try:
            threading.Thread.__init__(self)
            self.daemon = True
            self.start()
        except NameError:
            pass

        self.grid_space = True

        self.conds = rm_all(self.condition)

        if len(self.conds) == 1:
            self.conds = self.conds[0]
            if self.sweeper_flag2 == True:
                if ('x' in self.conds or 'X' in self.conds) and ('y' in self.conds or 'Y' in self.conds) and ('==' in self.conds or '=' in self.conds):
                   self.condition_status = 'xy'
                   self.sweepable2 = False
                   func = condition_2_func(self.conds, self.value2)
                   self.value1 = optimize.newton(func, x0 = self.from_sweep1, maxiter = 500)
                else:
                    self.condition_status = 'unknown'
            elif self.sweeper_flag3 == True:
                if ('y' in self.conds or 'Y' in self.conds) and ('z' in self.conds or 'Z' in self.conds) and ('x' not in self.conds and 'X' not in self.conds) and ('==' in self.conds or '=' in self.conds):
                    self.condition_status = 'yz'
                    self.sweepable3 = False
                    func = condition_2_func(self.conds, self.value3)
                    self.value2 = optimize.newton(func, x0 = self.from_sweep2, maxiter = 500)
                    
                    self.mapper2D = mapper2D(self.parameter_to_sweep1, self.parameter_to_sweep3, 
                                             self.parameters_to_read, filename_sweep, interpolated = interpolated3D,
                                             uniform = uniform3D, _from = self.from_sweep3, _to = self.to_sweep3,
                                             nsteps = self.nstep3, walks = globals()['back_and_forth_slave_slave'], 
                                             index_filename = index)
                    
                elif ('y' in self.conds or 'Y' in self.conds) and ('x' in self.conds or 'X' in self.conds) and ('z' not in self.conds and 'Z' not in self.conds) and ('==' in self.conds or '=' in self.conds):
                    self.condition_status = 'yx'
                    func = condition_2_func(self.conds, self.value2)
                    self.value1 = optimize.newton(func, x0 = self.from_sweep1, maxiter = 500)
                    
                    self.mapper2D = mapper2D(self.parameter_to_sweep2, self.parameter_to_sweep3, 
                                             self.parameters_to_read, filename_sweep, interpolated = interpolated3D,
                                             uniform = uniform3D, _from = self.from_sweep3, _to = self.to_sweep3,
                                             nsteps = self.nstep3, walks = globals()['back_and_forth_slave_slave'], 
                                             index_filename = index)
                    
                else:
                    self.condition_status = 'unknown'    
        if self.condition_status != 'unknown':
            pass
        elif any(s in self.condition for s in ['==', '=', '!=', '>=', '<=', '<', '>']):
            #creating grid space for sweep parameters
            if self.sweeper_flag2 == True:
                ax1 = np.linspace(self.from_sweep1, self.to_sweep1, self.nstep1 + 1)
                ax2 = np.linspace(self.from_sweep2, self.to_sweep2, self.nstep2 + 1)
                AX1, AX2 = np.meshgrid(ax1, ax2)
                space = AX1.tolist().copy()
                self.grid_space = []
                for i in range(AX1.shape[0]):
                    for j in range(AX1.shape[1]):
                        space[i][j] = (np.array([AX1[i][j], AX2[i][j]]) * self.func(tup = tuple((AX1[i][j], AX2[i][j])), condition_str = self.condition, sweep_dimension = 2)).tolist()
                        
                        if not np.isnan(space[i][j][0]):
                            self.grid_space.append(space[i][j])
                
                        
            elif self.sweeper_flag3 == True: 
                ax1 = np.linspace(self.from_sweep1, self.to_sweep1, self.nstep1 + 1)
                ax2 = np.linspace(self.from_sweep2, self.to_sweep2, self.nstep2 + 1)
                ax3 = np.linspace(self.from_sweep3, self.to_sweep3, self.nstep3 + 1)
                AX1, AX2, AX3 = np.meshgrid(ax1, ax2, ax3)
                space = AX1.tolist().copy()
                self.grid_space = []
                for i in range(AX1.shape[0]):
                    for j in range(AX1.shape[1]):
                        for k in range(AX1.shape[2]):
                            space[i][j][k] = (np.array((AX1[i][j][k], AX2[i][j][k], AX3[i][j][k]))) * self.func(tup = tuple((AX1[i][j][k], AX2[i][j][k], AX3[i][j][k])), condition_str = self.condition, sweep_dimension = 3)

                            if not np.isnan(space[i][j][k][0]):
                                self.grid_space.append(space[i][j][k])
                                
        print(f'grid is {self.grid_space}')
                                

    def func(self, tup, condition_str, sweep_dimension):
        '''input: tup - tuple, contains coordinates of phase space of sweep parameters,
        dtup: tuple of steps along sweep axis
        condition_str - python-like condition, written by user in a form of string
        sweep_dimension - 2 or 3: how many sweep parameters are there
        #############
        return 1 if point (in phase space with coordinates in tup) included in condition
        np.nan if not included'''
        
        def isequal(a, b):
            '''equality with tolerance'''
            return abs(a-b) <= 0

        def notequal(a, b):
            '''not equality with tolerance'''
            return abs(a-b) > 0

        def ismore(a, b):
            '''if one lement is more than other with tolerance'''
            return (a-b) > 0

        def ismoreequal(a, b):
            '''if one element is more or equal than other with tolerance'''
            return (a-b) >= 0

        def isless(a, b):
            '''if one lement is less than other with tolerance'''
            return (a-b) < 0

        def islessequal(a, b):
            '''if one lement is less or equal than other with tolerance'''
            return (a-b) <= 0
        
        result = 1
        
        conditions = condition_str.split('\n')
        
        dict_operations = {' = ': isequal, ' == ': isequal, ' != ': notequal, ' > ': ismore, 
                           ' < ': isless, ' >= ': ismoreequal, ' <= ': islessequal}
        
        dict_variables = {'x': 'tup[0]', 'X': 'tup[0]', 'y': 'tup[1]', 'Y': 'tup[1]',
                          'z': 'tup[2]', 'Z': 'tup[2]', 'Master': 'tup[0]', 'Slave': 'tup[1]',
                          'SlaveSlave': 'tup[2]'}
        
        for condition in conditions:
            
            for variable in list(dict_variables.keys()):
                condition = condition.replace(variable, dict_variables[variable])
            
            for operation in list(dict_operations.keys()):
                if operation in condition:
                
                    lhs = condition.split(operation)[0]
                    rhs = condition.split(operation)[1]
                    
                    if dict_operations[operation](eval(lhs, locals()), eval(rhs, locals())):
                        result *= 1
                    else:
                        result *= np.nan
                
            if sweep_dimension == 1 or rhs == '' or lhs == '':
                return 1
            
        return result

    def transposition(self, a, b):
        
        global manual_sweep_flags
        '''changes device_a and device_b order'''
        
        if 1 in manual_sweep_flags:
            pass
        else:
            print('Transposition happened')
            a = str(a)
            b = str(b)
            globals()[f'device_to_sweep{a}'] = getattr(self, f'device_to_sweep{b}')
            globals()[f'device_to_sweep{b}'] = getattr(self, f'device_to_sweep{a}')
            globals()[f'parameter_to_sweep{a}'] = getattr(self, f'parameter_to_sweep{b}')
            globals()[f'parameter_to_sweep{b}'] = getattr(self, f'parameter_to_sweep{a}')
            globals()[f'from_sweep{a}'] = float(getattr(self, f'from_sweep{b}'))
            globals()[f'to_sweep{a}'] = float(getattr(self, f'to_sweep{b}'))
            globals()[f'ratio_sweep{a}'] = float(getattr(self, f'ratio_sweep{b}'))
            globals()[f'delay_factor{a}'] = float(getattr(self, f'delay_factor{b}'))
            globals()[f'from_sweep{b}'] = float(getattr(self, f'from_sweep{a}'))
            globals()[f'to_sweep{b}'] = float(getattr(self, f'to_sweep{a}'))
            globals()[f'ratio_sweep{b}'] = float(getattr(self, f'ratio_sweep{a}'))
            globals()[f'delay_factor{b}'] = float(getattr(self, f'delay_factor{a}'))
            globals()[f'step{a}']  = float(getattr(self, f'delay_factor{b}')) * float(getattr(self, f'ratio_sweep{b}'))
            globals()[f'step{b}'] = float(getattr(self, f'delay_factor{a}')) * float(getattr(self, f'ratio_sweep{a}'))
            globals()[f'value{a}'] = float(getattr(self, f'from_sweep{b}'))
            globals()[f'value{b}'] = float(getattr(self, f'from_sweep{a}'))
            globals()[f'time{a}'] = (float(getattr(self, f'from_sweep{b}')) - float(getattr(self, f'to_sweep{b}')) / float(getattr(self, f'ratio_sweep{b}')))
            globals()[f'time{b}'] = (float(getattr(self, f'from_sweep{a}')) - float(getattr(self, f'to_sweep{a}')) / float(getattr(self, f'ratio_sweep{a}')))

    def isinarea(self, point, grid_area, sweep_dimension = 2):
        '''if point is in grid_area return True. 
        Grid size defined by dgrid_area which is tuple'''
        
        if grid_area == True:
            return True
        else:
            def includance(point, reference,sweep_dimension = 2):
                '''equity with tolerance'''
                if sweep_dimension == 2:
                    return np.isclose(point[0], reference[0], atol = self.step1/2) and np.isclose(point[1], reference[1], atol = self.step2/2)
                if sweep_dimension == 3:
                    return np.isclose(point[0], reference[0], atol = self.step1/2) and np.isclose(point[1], reference[1], atol = self.step2/2) and np.isclose(point[2], reference[2], atol = self.step3/2)
            
            if sweep_dimension == 2:
                for reference in grid_area:
                    if includance(point = point, reference = reference):
                        return True

            if sweep_dimension == 3:
                for reference in grid_area:
                    if includance(point = point, reference = reference,
                                  sweep_dimension = 3):
                        return True

            return False
        
    def run(self):
        global manual_filenames
        global manual_sweep_flags
        global master_flag1
        global master_flag2
        global master_flag3
        global filename_sweep
        global pause_flag
        global stop_flag
        global tozero_flag
        global back_and_forth_slave
        global back_and_forth_master
        global zero_time
        global script
        global setget_delay_factor
        
        
        def setget_write():
            global setget_flag
            global filename_setget
            global pause_flag
            global deli
            
            while setget_flag:
                if not pause_flag:
                    dataframe = []
                    dataframe.append(round(time.perf_counter() - zero_time, 2))
                    
                    for parameter in self.parameters_to_read:
                        index_dot = len(parameter) - parameter[::-1].find('.') - 1
                        adress = parameter[:index_dot]
                        option = parameter[index_dot + 1:]
                        try:
                            parameter_value = getattr(list_of_devices[list_of_devices_addresses.index(adress)],
                                                      option)()
                            dataframe.append(parameter_value)
                        except Exception as e:
                            print(f'Exception happened in setget_write: {e}')
                            dataframe.append(None)
                            return
                            
                    time.sleep(setget_delay_factor)
                        
                    with open(filename_setget, 'a', newline = '') as f_object:
                        try:
                            writer_object = writer(f_object, delimiter = deli)
                            writer_object.writerow(dataframe)
                            f_object.close()
                        except KeyboardInterrupt:
                            f_object.close()
                        except Exception as e:
                            print(f'Exception happened in setget_write append: {e}')
                        finally:
                            f_object.close()
                else:
                    time.sleep(setget_delay_factor)
        
        def append_read_parameters():
            '''appends dataframe with parameters to read'''
            
            print('Read parameters appended')
            
            global dataframe
            global data
            global manual_sweep_flag
            
            for parameter in self.parameters_to_read:
                index_dot = len(parameter) - parameter[::-1].find('.') - 1
                adress = parameter[:index_dot]
                option = parameter[index_dot + 1:]
                
                try:
                    parameter_value = getattr(list_of_devices[list_of_devices_addresses.index(adress)],
                                              option)()
                    if str(parameter_value) == '':
                        parameter_value = np.nan
                        
                    if len(manual_sweep_flags) == 2 or (len(manual_sweep_flags) == 3 and self.condition_status != 'unknown'):
                        self.mapper2D.append_parameter(str(parameter), parameter_value)
                    if len(manual_sweep_flags) == 3:
                        self.mapper3D.append_parameter(str(parameter), parameter_value)
                    dataframe.append(parameter_value)
                except:
                    dataframe.append(None)
        
            data = dataframe.copy()
        
        def tofile():
            '''appends file with new row - dataframe'''
            
            global dataframe
            global filename_sweep
            global deli
            
            print('File rewrote')
            
            with open(filename_sweep, 'a', newline='') as f_object:
                try:
                    writer_object = writer(f_object, delimiter = deli)
                    writer_object.writerow(dataframe)
                    f_object.close()
                except KeyboardInterrupt:
                    f_object.close()
                finally:
                    f_object.close()
            return
                  
        def condition(axis):
            
            global stop_flag
            global zero_time
            global manual_sweep_flags
            
            '''Determine if current value is in sweep borders of axis'''
            
            if stop_flag == True:
                for i in [1, 2, 3]:
                    globals()['sweeper_flag' + str(i)] = False
                return False
            
            axis = str(axis)
            value = float(getattr(self, 'value' + axis))
            step = float(getattr(self, 'step' + axis))
            to_sweep = float(globals()['to_sweep' + axis])
            from_sweep = float(globals()['from_sweep' + axis])
            speed = float(globals()['ratio_sweep' + axis])
            device_to_sweep = globals()[f'device_to_sweep{axis}']
            parameter_to_sweep = globals()[f'parameter_to_sweep{axis}']
            result = True
            if hasattr(device_to_sweep, 'eps') == True:
                eps = device_to_sweep.eps[device_to_sweep.set_options.index(parameter_to_sweep)]
            else:
                eps = abs(float(getattr(self, f'step{axis}')) * 0.1)
                
            print(f'Epsilon = {eps}')
            print(f'Step = {step}')
                
            if getattr(self, f'sweepable{axis}') == True:
                self.current_value = float(getattr(device_to_sweep, parameter_to_sweep)())
                print(f'Sweep value is {value}')
                print(f'Current value is {self.current_value}') 
                    
                if (speed > 0 and self.current_value >= value - eps) or ((speed < 0 and self.current_value <= value + eps)): #if current value out of border
                    if not self.started:
                        result = True
                    else:
                        result = False
                else:
                    result = True
                    setattr(self, f'value{axis}', to_sweep - getattr(self, f'step{axis}'))
            else:
                if speed >= 0:
                    result = (value + step >= from_sweep - eps and value + step <= to_sweep + eps)
                else:
                    result = (value + step >= to_sweep - eps and value + step <= from_sweep + eps)
                
            if speed > 0:
                print('Condition checked, result is ' + str(result) + f'\nBoundaries are [{from_sweep};{to_sweep}], Value is {value}, Ratio is positive')
            else:
                print('Condition checked, result is ' + str(result) + f'\nBoundaries are [{from_sweep};{to_sweep}], Value is {value}, Ratio is negative')
                
            return result
            
        def step(axis = 1, value = None, back = False):
            
            '''performs a step along sweep axis'''
            
            def try_tozero():
                
                if len(manual_sweep_flags) == 1:
                    device1 = globals()['device_to_sweep1']
                    parameter1 = globals()['parameter_to_sweep1']
                    try:
                        current1 = float(getattr(device1, parameter1)())
                    except:
                        current1 = self.value1
                    steps1 = np.linspace(current1, 0, 10)
                    if not self.sweepable1:
                        for step in steps1:
                            getattr(device1, f'set_{parameter1}')(value = step)
                            time.sleep(0.1)
                    else:
                        getattr(device1, f'set_{parameter1}')(value = 0)
                
                elif len(manual_sweep_flag) == 2:
                    device1 = globals()['device_to_sweep1']
                    parameter1 = globals()['parameter_to_sweep1']
                    device2 = globals()['device_to_sweep2']
                    parameter2 = globals()['parameter_to_sweep2']
                    try:
                        current1 = float(getattr(device1, parameter1)())
                    except:
                        current1 = self.value1
                    try:
                        current2 = float(getattr(device2, parameter2)())
                    except:
                        current2 = self.value2
                    steps1 = np.linspace(current1, 0, 10)
                    steps2 = np.linspace(current2, 0, 10)
                    if not self.sweepable2:
                        for ind, step in enumerate(steps1):
                            getattr(device1, f'set_{parameter1}')(value = step)
                            getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                            time.sleep(0.1)
                    else:
                        getattr(device2, f'set_{parameter2}')(value = 0)
                        for step in steps1:
                            getattr(device1, f'set_{parameter1}')(value = step)
                            time.sleep(0.1)
                    
                elif len(manual_sweep_flag) == 3:
                    device1 = globals()['device_to_sweep1']
                    parameter1 = globals()['parameter_to_sweep1']
                    device2 = globals()['device_to_sweep2']
                    parameter2 = globals()['parameter_to_sweep2']
                    device3 = globals()['device_to_sweep3']
                    parameter3 = globals()['parameter_to_sweep3']
                    try:
                        current1 = float(getattr(device1, parameter1)())
                    except:
                        current1 = self.value1
                    try:
                        current2 = float(getattr(device2, parameter2)())
                    except:
                        current2 = self.value2
                    try:
                        current3 = float(getattr(device3, parameter3)())
                    except:
                        current3 = self.value3
                    steps1 = np.linspace(current1, 0, 10)
                    steps2 = np.linspace(current2, 0, 10)
                    steps3 = np.linspace(current3, 0, 10)
                    if not self.sweepable3:
                        for ind, step in enumerate(steps1):
                            getattr(device1, f'set_{parameter1}')(value = step)
                            getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                            getattr(device3, f'set_{parameter3}')(value = steps3[ind])
                            time.sleep(0.1)
                    else:
                        getattr(device3, f'set_{parameter3}')(value = 0)
                        for ind, step in enumerate(steps1):
                            getattr(device1, f'set_{parameter1}')(value = step)
                            getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                            time.sleep(0.1)
                
            global zero_time
            global dataframe
            global manual_sweep_flags
            global stop_flag
            global pause_flag
            global tozero_flag
            
            if len(dataframe) == 0:
                dataframe = [np.round(i, 2) for i in [time.perf_counter() - zero_time]]
            else:
                dataframe[0] = [np.round(i, 2) for i in [time.perf_counter() - zero_time]][0]
                
            device_to_sweep = globals()[f'device_to_sweep{str(axis)}']
            parameter_to_sweep = globals()[f'parameter_to_sweep{str(axis)}']
            
            if pause_flag == False:
                self.__dict__[f'paused_{axis}'] = False
                if tozero_flag == False:
                    # sweep process here
                    ###################
                    # set 'parameter_to_sweep' to 'value'
                    if getattr(self, f'sweepable{str(axis)}') == False:
                        if manual_sweep_flags[axis - 1] == 0:
                            value = getattr(self, f'value{str(axis)}')
                            getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
                            delay_factor = globals()['delay_factor' + str(axis)]
                            time.sleep(delay_factor)
                            dataframe.append("{:.3e}".format(getattr(self, 'value' + str(axis))))
                            if back == False:
                                setattr(self, f'value{str(axis)}', getattr(self, f'value{str(axis)}') + getattr(self, f'step{str(axis)}'))
                            else:
                                setattr(self, f'value{str(axis)}', getattr(self, f'value{str(axis)}') - getattr(self, f'step{str(axis)}'))
                        else:
                            value = getattr(self, f'value{str(axis)}')
                            
                            getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value)
                            delay_factor = globals()['delay_factor' + str(axis)]
                            time.sleep(delay_factor)
                            dataframe.append("{:.3e}".format(value))
                        
                        ###################
                        globals()['self'] = self
                        exec(script, globals())
                        return 
                    elif getattr(self, f'sweepable{str(axis)}') == True:
                        if manual_sweep_flags[axis - 1] == 0:
                            value = getattr(self, f'upcoming_value{str(axis)}')
                            if value - getattr(self, f'value{str(axis)}') > getattr(self, f'step{str(axis)}'):
                                if hasattr(device_to_sweep, 'maxsweep'):
                                    speed = device_to_sweep.maxspeed[device_to_sweep.set_options.find(parameter_to_sweep)]
                                else:
                                    speed = float(globals()['ratio_sweep' + str(axis)])
                                            
                            else:
                                speed = float(globals()['ratio_sweep' + str(axis)])
                                
                            if self.inner_count <= 2:
                                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = speed)
                                self.inner_count += 1
                            delay_factor = globals()['delay_factor' + str(axis)]
                            time.sleep(delay_factor)
                            dataframe.append("{:.3e}".format(getattr(self, f'value{str(axis)}')))
                            if back == False:
                                setattr(self, f'value{str(axis)}', getattr(self, f'value{str(axis)}') + getattr(self, f'step{str(axis)}'))
                            else:
                                setattr(self, f'value{str(axis)}', getattr(self, f'value{str(axis)}') - getattr(self, f'step{str(axis)}'))
                            
                            setattr(self, f'upcoming_value{str(axis)}', getattr(self, f'value{str(axis)}'))
                        else:
                            value = getattr(self, f'value{str(axis)}')
                            speed = float(globals()['ratio_sweep' + str(axis)])
                            if self.inner_count <= 2:
                                getattr(device_to_sweep, 'set_' + str(parameter_to_sweep))(value=value, speed = speed)
                                self.inner_count += 1
                            delay_factor = globals()['delay_factor' + str(axis)]
                            time.sleep(delay_factor)
                            dataframe.append("{:.3e}".format(value))
                        globals()['self'] = self
                        exec(script, globals())
                        return 
                        
                else:
                    try_tozero()
                    
                    stop_flag = True
                    
            else:
                if not hasattr(self, f'paused_{axis}'):
                    self.__dict__[f'paused_{axis}'] = True
                    if hasattr(device_to_sweep, 'pause'):
                        device_to_sweep.pause()
                elif getattr(self, f'paused_{axis}') == False:
                    self.__dict__[f'paused_{axis}'] = True
                    if hasattr(device_to_sweep, 'pause'):
                        device_to_sweep.pause()
                time.sleep(0.01)
                step(axis, value)
            
            if value == 'None':
                print('Step was made through axis ' + axis + '\nValue = ' + getattr(self, 'value' + axis))
        
        def double_step():
            
            '''performs a step along two axis with respect to self.condition'''
            
            def try_tozero():
                
                if len(manual_sweep_flag) == 2:
                    device1 = globals()['device_to_sweep1']
                    parameter1 = globals()['parameter_to_sweep1']
                    device2 = globals()['device_to_sweep2']
                    parameter2 = globals()['parameter_to_sweep2']
                    try:
                        current1 = float(getattr(device1, parameter1)())
                    except:
                        current1 = self.value1
                    try:
                        current2 = float(getattr(device2, parameter2)())
                    except:
                        current2 = self.value2
                    steps1 = np.linspace(current1, 0, 10)
                    steps2 = np.linspace(current2, 0, 10)
                    if not self.sweepable2:
                        for ind, step in enumerate(steps1):
                            getattr(device1, f'set_{parameter1}')(value = step)
                            getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                            time.sleep(0.01)
                    else:
                        getattr(device2, f'set_{parameter2}')(value = 0)
                        for step in steps1:
                            getattr(device1, f'set_{parameter1}')(value = step)
                            time.sleep(0.01)
                    
                elif len(manual_sweep_flag) == 3:
                    device1 = globals()['device_to_sweep1']
                    parameter1 = globals()['parameter_to_sweep1']
                    device2 = globals()['device_to_sweep2']
                    parameter2 = globals()['parameter_to_sweep2']
                    device3 = globals()['device_to_sweep3']
                    parameter3 = globals()['parameter_to_sweep3']
                    try:
                        current1 = float(getattr(device1, parameter1)())
                    except:
                        current1 = self.value1
                    try:
                        current2 = float(getattr(device2, parameter2)())
                    except:
                        current2 = self.value2
                    try:
                        current3 = float(getattr(device3, parameter3)())
                    except:
                        current3 = self.value3
                    steps1 = np.linspace(current1, 0, 10)
                    steps2 = np.linspace(current2, 0, 10)
                    steps3 = np.linspace(current3, 0, 10)
                    if not self.sweepable3:
                        for ind, step in enumerate(steps1):
                            getattr(device1, f'set_{parameter1}')(value = step)
                            getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                            getattr(device3, f'set_{parameter3}')(value = steps3[ind])
                            time.sleep(0.01)
                    else:
                        getattr(device3, f'set_{parameter3}')(value = 0)
                        for ind, step in enumerate(steps1):
                            getattr(device1, f'set_{parameter1}')(value = step)
                            getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                            time.sleep(0.01)
                
            global zero_time
            global dataframe
            global manual_sweep_flags
            global stop_flag
            global pause_flag
            global tozero_flag
            
            if len(dataframe) == 0:
                dataframe = [np.round(i, 2) for i in [time.perf_counter() - zero_time]]
            else:
                dataframe[0] = [np.round(i, 2) for i in [time.perf_counter() - zero_time]][0]
                
            device_to_sweep_master = globals()[f'device_to_sweep{len(manual_sweep_flags) - 1}']
            parameter_to_sweep_master = globals()[f'parameter_to_sweep{len(manual_sweep_flags) - 1}']
            device_to_sweep_slave = globals()[f'device_to_sweep{len(manual_sweep_flags)}']
            parameter_to_sweep_slave = globals()[f'parameter_to_sweep{len(manual_sweep_flags)}']
            
            if pause_flag == False:
                self.paused2 = False
                if tozero_flag == False:
                    # sweep process here
                    ###################
                    # set 'parameter_to_sweep' to 'value'
                    dataframe.append("{:.3e}".format(getattr(self, f'value{len(manual_sweep_flags) - 1}')))
                    dataframe.append("{:.3e}".format(getattr(self, f'value{len(manual_sweep_flags)}')))
                    #slave
                    value_slave = getattr(self, f'value{len(manual_sweep_flags)}')
                    getattr(device_to_sweep_slave, 'set_' + str(parameter_to_sweep_slave))(value=value_slave)
                    delay_factor = globals()[f'delay_factor{len(manual_sweep_flags)}']
                    #time.sleep(delay_factor)
                    setattr(self, f'value{len(manual_sweep_flags)}', getattr(self, f'value{len(manual_sweep_flags)}') + getattr(self, f'step{len(manual_sweep_flags)}'))
                    #master
                    value_master = getattr(self, f'value{len(manual_sweep_flags) - 1}')
                    getattr(device_to_sweep_master, 'set_' + str(parameter_to_sweep_master))(value=value_master)
                    delay_factor += globals()[f'delay_factor{len(manual_sweep_flags) - 1}']
                    time.sleep(delay_factor)
                    func = condition_2_func(self.conds, getattr(self, f'value{len(manual_sweep_flags)}'))
                    setattr(self, f'value{len(manual_sweep_flags) - 1}', optimize.newton(func, x0 = getattr(self, f'value{len(manual_sweep_flags) - 1}')))
                    
                    ###################
                    globals()['self'] = self
                    exec(script, globals())
                    return
                else:
                    try_tozero()
                    
                    stop_flag = True
                    
            else:
                if not hasattr(self, 'paused2'):
                    self.__dict__['paused2'] = True
                    if hasattr(device_to_sweep_master, 'pause'):
                        device_to_sweep_master.pause()
                    if hasattr(device_to_sweep_slave, 'pause'):
                        device_to_sweep_slave.pause()
                elif self.paused2 == False:
                    self.paused2 = True
                    if hasattr(device_to_sweep_master, 'pause'):
                        device_to_sweep_master.pause()
                    if hasattr(device_to_sweep_slave, 'pause'):
                        device_to_sweep_slave.pause()
                time.sleep(0.01)
                double_step()
        
        def double_step_yx():
            
            '''performs a step along two axis with respect to self.condition'''
            
            def try_tozero():
                
                device1 = globals()['device_to_sweep1']
                parameter1 = globals()['parameter_to_sweep1']
                device2 = globals()['device_to_sweep2']
                parameter2 = globals()['parameter_to_sweep2']
                device3 = globals()['device_to_sweep3']
                parameter3 = globals()['parameter_to_sweep3']
                try:
                    current1 = float(getattr(device1, parameter1)())
                except:
                    current1 = self.value1
                try:
                    current2 = float(getattr(device2, parameter2)())
                except:
                    current2 = self.value2
                try:
                    current3 = float(getattr(device3, parameter3)())
                except:
                    current3 = self.value3
                steps1 = np.linspace(current1, 0, 10)
                steps2 = np.linspace(current2, 0, 10)
                steps3 = np.linspace(current3, 0, 10)
                if not self.sweepable3:
                    for ind, step in enumerate(steps1):
                        getattr(device1, f'set_{parameter1}')(value = step)
                        getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                        getattr(device3, f'set_{parameter3}')(value = steps3[ind])
                        time.sleep(0.1)
                else:
                    getattr(device3, f'set_{parameter3}')(value = 0)
                    for ind, step in enumerate(steps1):
                        getattr(device1, f'set_{parameter1}')(value = step)
                        getattr(device2, f'set_{parameter2}')(value = steps2[ind])
                        time.sleep(0.1)
                
            global zero_time
            global dataframe
            global manual_sweep_flags
            global stop_flag
            global pause_flag
            global tozero_flag
            
            if len(dataframe) == 0:
                dataframe = [np.round(i, 2) for i in [time.perf_counter() - zero_time]]
            else:
                dataframe[0] = [np.round(i, 2) for i in [time.perf_counter() - zero_time]][0]
                
            device_to_sweep_master = globals()['device_to_sweep1']
            parameter_to_sweep_master = globals()['parameter_to_sweep1']
            device_to_sweep_slave = globals()['device_to_sweep2']
            parameter_to_sweep_slave = globals()['parameter_to_sweep2']
            
            if pause_flag == False:
                self.paused2 = False
                if tozero_flag == False:
                    # sweep process here
                    ###################
                    # set 'parameter_to_sweep' to 'value'
                    dataframe.append("{:.3e}".format(self.value1))
                    dataframe.append("{:.3e}".format(self.value2))
                    #slave
                    value_slave = self.value2
                    getattr(device_to_sweep_slave, 'set_' + str(parameter_to_sweep_slave))(value=value_slave)
                    delay_factor = globals()['delay_factor2']
                    #time.sleep(delay_factor)
                    self.value2 += self.step2
                    #master
                    value_master = self.value1
                    getattr(device_to_sweep_master, 'set_' + str(parameter_to_sweep_master))(value=value_master)
                    delay_factor += globals()['delay_factor1']
                    time.sleep(delay_factor)
                    func = condition_2_func(self.conds, self.value2)
                    self.value1 = optimize.newton(func, x0 = self.value1)
                    
                    ###################
                    globals()['self'] = self
                    exec(script, globals())
                    return
                else:
                    try_tozero()
                    
                    stop_flag = True
                    
            else:
                if not hasattr(self, 'paused2'):
                    self.__dict__['paused2'] = True
                    if hasattr(device_to_sweep_master, 'pause'):
                        device_to_sweep_master.pause()
                    if hasattr(device_to_sweep_slave, 'pause'):
                        device_to_sweep_slave.pause()
                elif self.paused2 == False:
                    self.paused2 = True
                    if hasattr(device_to_sweep_master, 'pause'):
                        device_to_sweep_master.pause()
                    if hasattr(device_to_sweep_slave, 'pause'):
                        device_to_sweep_slave.pause()
                time.sleep(0.1)
                double_step()
        
        def update_filename():
            '''Add +1 to filename_sweep'''
            global filename_sweep
            global cur_dir
            global DAY
            global MONTH
            global YEAR
            global deli
            global sweeper_flag1
            global sweeper_flag2
            global sweeper_flag3
            
            files = []
            for (_, _, file_names) in os.walk(os.path.join(cur_dir, 'data_files')): #get all the files from subdirectories
                files.extend(file_names)
            ind = [0]
            path = os.path.normpath(filename_sweep).split(os.path.sep)
            basic_name = path[-1]
            if '.' in basic_name:
                basic_name = basic_name[:(len(basic_name) - basic_name[::-1].find('.') - 1)] #all before last -
            if '-' in basic_name:
                basic_name = basic_name[:(len(basic_name) - basic_name[::-1].find('-') - 1)] #all before last -
            basic_name = unify_filename(basic_name)
            for file in files:
                if basic_name in file and 'manual' not in file and 'setget' not in file:
                    index_start = len(file) - file[::-1].find('-') - 1
                    index_stop = len(file) - file[::-1].find('.') - 1
                    try:
                        ind.append(int(file[index_start + 1 : index_stop]))
                    except:
                        ind.append(np.nan)
            previous_ind = int(np.nanmax(ind))
            if np.isnan(previous_ind):
                previous_ind = 0
            if sweeper_flag1 == True:
                filename_sweep = os.path.join(*path[:-1], f'{basic_name}-{previous_ind + 1}.csv')
            elif sweeper_flag2 == True:
                value1 = self.value1
                filename_sweep = os.path.join(*path[:-1], f'{basic_name}_{cut(value1)}-{previous_ind + 1}.csv')
            elif sweeper_flag3 == True:
                value1 = self.value1
                value2 = self.value2
                filename_sweep = os.path.join(*path[:-1], f'{basic_name}_{cut(value1)}_{cut(value2)}-{previous_ind + 1}.csv')
                
            filename_sweep = fix_unicode(filename_sweep)
            sweeper = globals()['Sweeper_object']
            
            sweeper.entry_filename.delete(0, tk.END)
            sweeper.entry_filename.insert(0, filename_sweep)
            sweeper.entry_filename.after(1)
            
            def get_fract(num):
                if num % 3 == 1:
                    s = [num]
                    while num > 1:
                        num -= 3
                        s.append(num)
                    return s
                else:
                    return num
                
            graphs = get_fract(globals()['cur_animation_num'])
            
            for num in graphs:
                try:
                    graph_object = globals()[f'graph_object{num}']
                    if hasattr(graph_object, 'label_filename'):
                        graph_object.label_filename.config(text = filename_sweep)
                except:
                    pass
            
            globals()['dataframe'] = pd.DataFrame(columns=self.columns)
            globals()['dataframe'].to_csv(filename_sweep, index=False, sep = deli)
            
            print('Filename updated')
        
        def back_and_forth_transposition(axis, full = True):
            
            '''Changes sweep direction'''
            
            axis = str(axis)
            if full == True:
                dub = globals()['to_sweep' + axis]
                globals()['to_sweep' + axis] = globals()['from_sweep' + axis]
                globals()['from_sweep' + axis] = dub
                dub_ratio = globals()['back_ratio_sweep' + axis]
                globals()['back_ratio_sweep' + axis] = globals()['ratio_sweep' + axis]
                globals()['ratio_sweep' + axis] = dub_ratio
                dub_delay_factor = globals()['back_delay_factor' + axis]
                globals()['back_delay_factor' + axis] = globals()['delay_factor' + axis]
                globals()['delay_factor' + axis] = dub_delay_factor
                if self.__dict__[f'sweepable{axis}'] == False:
                    dub_step = self.__dict__['back_step' + axis]
                    setattr(self, 'back_step' + axis, getattr(self, 'step' + axis))
                    setattr(self, 'step' + axis, dub_step)
                else:
                    setattr(self, 'step' + axis, - getattr(self, 'step' + axis))
            else:
                if self.__dict__[f'sweepable{axis}']:
                    from_sweep = float(globals()['from_sweep' + axis])
                    speed = float(globals()['ratio_sweep' + axis])
                    device_to_sweep = globals()[f'device_to_sweep{axis}']
                    parameter_to_sweep = globals()[f'parameter_to_sweep{axis}']
                    if hasattr(device_to_sweep, 'eps'):
                        eps = device_to_sweep.eps[device_to_sweep.set_options.index(parameter_to_sweep)]
                    else:
                        eps = abs(float(getattr(self, f'step{axis}')) * 0.1)
                    if hasattr(device_to_sweep, 'maxspeed'):
                        speed_ = device_to_sweep.maxspeed[device_to_sweep.set_options.index(parameter_to_sweep)]
                        if speed_ != None:
                            speed = speed_
                    getattr(device_to_sweep, f'set_{parameter_to_sweep}')(value = from_sweep, speed = speed)
                    current_value = float(getattr(device_to_sweep, parameter_to_sweep)())
                    delta = abs(current_value - from_sweep)
                    while delta > eps:
                        time.sleep(0.1)
                        getattr(device_to_sweep, f'set_{parameter_to_sweep}')(value = from_sweep, speed = speed)
                        current_value = float(getattr(device_to_sweep, parameter_to_sweep)())
                        delta = abs(current_value - from_sweep)
                
            print(f'Back and forth transposition (axis = {axis}) happened\nNow From is {globals()["from_sweep" + axis]}, To is {globals()["to_sweep" + axis]}')
            
        def determine_step(i, data, axis):
            
            '''Determine a step if sweep is manual
            Go to manual sweep file and substract neares values'''
            
            axis = str(axis)
            setattr(self, 'value' + axis, data[i])
            try:
                setattr(self, 'step' + axis, abs(data[i+1] - data[i-1]) / 2)
            except IndexError as ie:
                print(f'Index error: {ie}')
                try:
                    setattr(self, 'step' + axis, abs(data[i] - data[i-1]))
                except IndexError as ie2:
                    print(f'Index error 2: {ie2}')
                    setattr(self, 'step' + axis, abs(data[i] - data[i+1]))
            except Exception as e:
                print(f'Exception: {e}')
                    
            print('Step was determined')
                    
        def update_dataframe(sure = None):
            
            '''Create dataframe duplicate for further update
            sure = True only for 3D sweep for axis = 2'''
            if len(manual_sweep_flags) == 1:
                globals()['dataframe'] = [np.round(i, 2) for i in [time.perf_counter() - zero_time]]
            if len(manual_sweep_flags) == 2 or sure == True or self.condition_status == 'yx':
                globals()['dataframe'] = [*globals()['dataframe_after']]
            if len(manual_sweep_flags) == 3 and sure == None and self.condition_status != 'yx':
                globals()['dataframe'] = [*globals()['dataframe_after_after']]
                
            print('Dataframe updated')
                
            
        def current_point():
            global manual_sweep_flags
            
            '''Determines current point in sweep space and its boundaries'''
            
            point = []
            for ind, _ in enumerate(manual_sweep_flags):
                point.append(getattr(self, f'value{ind + 1}'))
                    
            print('Current point was determined')
            return point
    
        def double_inner_step():
            global manual_sweep_flags
            '''Performs double step in a slave-axis'''
            
            if len(manual_sweep_flags) == 2:
                globals()['dataframe'] = [np.round(i, 2) for i in [time.perf_counter() - zero_time]]
            else:
                globals()['dataframe'] = [*globals()['dataframe_after']]
                if self.sweepable3 == True:
                    self.mapper2D.append_slave(value = self.current_value)
                else:
                    self.mapper2D.append_slave(value = self.value3)
            double_step()
            append_read_parameters()
            tofile() 
                
            print('Double inner step was made')
    
        def inner_step(value1 = None, value2 = None, value3 = None):
            global manual_sweep_flags
            '''Performs single step in a slave-axis'''
            
            if len(manual_sweep_flags) == 1:
                update_dataframe()
                step(1, value1)
                append_read_parameters()
                tofile() 
            elif len(manual_sweep_flags) == 2:
                point = current_point()
                if self.isinarea(point = point, grid_area = self.grid_space, sweep_dimension = len(manual_sweep_flags)):
                    update_dataframe()
                    if self.sweepable2 == True:
                        self.mapper2D.append_slave(value = self.current_value)
                    else:
                        self.mapper2D.append_slave(value = self.value2)
                    step(2, value2)
                    append_read_parameters()
                    tofile() 
                else:
                    self.mapper2D.append_slave(value = self.value2)
                    if manual_sweep_flags[1] == 0:
                        self.value2 += self.step2
                    for parameter in self.parameters_to_read:
                        self.mapper2D.append_parameter(str(parameter), np.nan)
                  
            elif len(manual_sweep_flags) == 3 and self.condition_status == 'yx':
                  update_dataframe()
                  if self.sweepable3 == True:
                      self.mapper2D.append_slave(value = self.current_value)
                  else:
                      self.mapper2D.append_slave(value = self.value3)
                  step(3, value3)
                  append_read_parameters()
                  tofile() 
            elif len(manual_sweep_flags) == 3 and self.condition_status != 'yx':
                point = current_point()
                if self.isinarea(point = point, grid_area = self.grid_space, sweep_dimension = len(manual_sweep_flags)):
                    update_dataframe()
                    if self.sweepable3 == True:
                        self.mapper3D.append_slave_slave(value = self.current_value)
                    else:
                        self.mapper3D.append_slave_slave(value = self.value3)
                    step(3, value3)
                    append_read_parameters()
                    tofile() 
                else:
                    self.mapper3D.append_slave_slave(value = self.value3)
                    if manual_sweep_flags[2] == 0:
                        self.value3 += self.step3
                    for parameter in self.parameters_to_read:
                        self.mapper3D.append_parameter(str(parameter), np.nan)
            else:
                raise Exception('manual_sweep_flag length is not correct, needs 1, 2 or 3, but got ', len(manual_sweep_flags))
                
            print('Inner step was made')
            
        def final_step(axis):
            global stop_flag 
            global back_and_forth_master
            global back_and_forth_slave
            global back_and_forth_slave_slave
            
            axis = str(axis)
            
            device_to_sweep = globals()[f'device_to_sweep{axis}']
            parameter_to_sweep = globals()[f'parameter_to_sweep{axis}']
            to_sweep = globals()[f'to_sweep{axis}']
            from_sweep = globals()[f'from_sweep{axis}']
            
            ax = None
            
            count = max(back_and_forth_master, back_and_forth_slave, back_and_forth_slave_slave)  
            
            if not getattr(self, f'sweepable{axis}') and manual_sweep_flags[int(axis) - 1] == 0 and count < 9e4:
            
                if hasattr(device_to_sweep, parameter_to_sweep):
                    current = getattr(device_to_sweep, parameter_to_sweep)()
                    
                    if hasattr(device_to_sweep, 'eps') == True:
                        eps = device_to_sweep.eps[device_to_sweep.set_options.index(parameter_to_sweep)]
                    else:
                        eps = abs(float(getattr(self, f'step{axis}')) * 0.1)
                    
                    try:
                        delta = abs(float(current) - float(to_sweep))
                        if (delta > eps) and (delta < getattr(self, f'step{axis}') * 2.1):
                            if axis == '1':
                                inner_step(value1 = to_sweep)
                                if len(manual_sweep_flags) == 3 or len(manual_sweep_flags) == 2:
                                    ax = axis
                            elif axis == '2':
                                inner_step(value2 = to_sweep)
                                if len(manual_sweep_flags) == 3:
                                    ax = axis
                            elif axis == '3':
                                inner_step(value3 = to_sweep)
                    except TypeError as ty:
                        print(f'Exception happened in the last step for axis {axis}: {ty}')
                    
                else:
                    if axis == '1':
                        inner_step(value1 = to_sweep)
                        if len(manual_sweep_flags) == 3 or len(manual_sweep_flags) == 2:
                            ax = axis
                    elif axis == '2':
                        inner_step(value2 = to_sweep)
                        if len(manual_sweep_flags) == 3:
                            ax = axis
                    elif axis == '3':
                        inner_step(value3 = to_sweep)
                
                flags = {1: 'back_and_forth_master', 2: 'back_and_forth_slave', 3: 'back_and_forth_slave_slave'}
                if globals()[flags[len(manual_sweep_flags)]] % 2 == 0:
                    self.__dict__[f'value{axis}'] = to_sweep
                else:
                    self.__dict__[f'value{axis}'] = from_sweep
            
            elif getattr(self, f'sweepable{axis}') and manual_sweep_flags[int(axis) - 1] == 0:
                self.__dict__[f'value{axis}'] = from_sweep
                
            print('Final step was made')
            
            return ax

                
        def inner_loop_single(direction = 1):
            '''commits a walk through mater (for 1d), slave (for 2d) or slave-slave (for 3d) axis'''
            
            if manual_sweep_flags[len(manual_sweep_flags) - 1] == 0:
                while condition(len(manual_sweep_flags)) and manual_sweep_flags[len(manual_sweep_flags) - 1] == 0:
                    inner_step()
                    if not self.started:
                        self.started = True
            elif manual_sweep_flags[len(manual_sweep_flags) - 1] == 1:
                data_inner = pd.read_csv(manual_filenames[len(manual_filenames) - 1]).values.reshape(-1)
                for i, value in enumerate(data_inner[::direction]):
                    if manual_sweep_flags[len(manual_sweep_flags) - 1] == 1:
                        if not self.__dict__[f'cur_manual_index{len(manual_sweep_flags)}'] > i:
                            determine_step(i, data_inner, len(manual_sweep_flags))
                            self.__dict__[f'cur_manual_index{len(manual_sweep_flags)}'] = i 
                            if len(manual_sweep_flags) == 1:
                                inner_step(value1 = value)
                            elif len(manual_sweep_flags) == 2:
                                inner_step(value2 = value)
                            elif len(manual_sweep_flags) == 3:
                                inner_step(value3 = value)
                            else:
                                raise Exception('manual_sweep_flag length is not correct, needs 1, 2 or 3, but got ', len(manual_sweep_flags))
                        
                            if not self.started:
                                self.started = True
                    
                    else:
                        break
                
            else:
                raise Exception('manual_sweep_flag is not correct, needs 0 or 1, but got ', manual_sweep_flags[len(manual_sweep_flags) - 1])
            
            if not stop_flag:
                final_step(axis = len(manual_sweep_flags))
            
            if len(manual_sweep_flags) == 2:
                self.mapper2D.add_sub_slave()
            elif len(manual_sweep_flags) == 3 and self.condition_status == 'yx':
                self.mapper2D.add_sub_slave()
            elif len(manual_sweep_flags) == 3 and self.condition_status != 'yx':
                self.mapper3D.add_sub_slave_slave()
            
            print('Single inner loop was made')
            
        def inner_loop_back_and_forth():
            '''travels through a slave-slave axis back and forth as many times, as was given'''
            global back_and_forth_master
            global back_and_forth_slave
            global back_and_forth_slave_slave
            global manual_sweep_flags
            
            flags_dict = {1: 'back_and_forth_master', 2: 'back_and_forth_slave', 3: 'back_and_forth_slave_slave'}
            walks = globals()[flags_dict[len(manual_sweep_flags)]]
            if walks == 1:
                self.inner_count = 1
                self.__dict__[f'cur_manual_index{len(manual_sweep_flags)}'] = 0
                inner_loop_single()
                globals()['Sweeper_object'].__dict__[f'cur_walk{len(manual_sweep_flags)}'] += 1
                if len(manual_sweep_flags) != 1:
                    back_and_forth_transposition(len(manual_sweep_flags), False)
            
            elif walks > 1:
                for i in range(1, walks + 1):
                    self.inner_count = 1
                    self.__dict__[f'cur_manual_index{len(manual_sweep_flags)}'] = 0
                    inner_loop_single(direction = round(2 * (i % 2) - 1))
                    globals()['Sweeper_object'].__dict__[f'cur_walk{len(manual_sweep_flags)}'] += 1
                    if globals()['snakemode_master_flag'] == True and len(manual_sweep_flags) == 2:
                        if i != walks and back_and_forth_slave != 1:
                            self.mapper2D.walks = 1
                            self.mapper2D.slave_done_walking()
                            self.mapper2D.concatenate_all()
                            self.mapper2D.clear_slave()
                            self.mapper2D.clear_sub_slaves()
                            self.mapper2D.clear_parameters()
                            if manual_sweep_flags[0] == 0:
                                self.mapper2D.append_master(value = self.value1)
                                step(axis = 1)
                                globals()['Sweeper_object'].cur_walk1 += 1
                            else:
                                self.cur_manual_index1 += 1
                                data_outer = pd.read_csv(manual_filenames[0])
                                steps = data_outer.values.reshape(-1)
                                determine_step(self.cur_manual_index1, steps, 1)
                                value = steps[self.cur_manual_index1]
                                self.mapper2D.append_master(value = value)
                                step(axis = 1, value = value)
                                globals()['Sweeper_object'].cur_walk1 += 1
                        elif i == walks and back_and_forth_slave != 1 and manual_sweep_flags[0] == 1:
                            self.cur_manual_index1 += 1
                            
                    elif globals()['snakemode_slave_flag'] == True and len(manual_sweep_flags) == 3 and self.condition_status == 'yx':
                        if i != walks and back_and_forth_slave != 1:
                            self.mapper2D.walks = 1
                            self.mapper2D.slave_done_walking()
                            self.mapper2D.concatenate_all()
                            self.mapper2D.clear_slave()
                            self.mapper2D.clear_sub_slaves()
                            self.mapper2D.clear_parameters()
                            self.mapper2D.append_master(value = self.value2)
                            step(axis = 2)
                            globals()['Sweeper_object'].cur_walk2 += 1
                        elif i == walks and back_and_forth_slave != 1 and manual_sweep_flags[0] == 1:
                            self.cur_manual_index2 += 1
                            
                    elif globals()['snakemode_slave_flag'] == True and len(manual_sweep_flags) == 3 and self.condition_status != 'yx':
                        if i != walks and back_and_forth_slave_slave != 1:
                            self.mapper3D.walks = 1
                            self.mapper3D.slave_slave_done_walking()
                            self.mapper3D.concatenate_all()
                            self.mapper3D.clear_slave_slave()
                            self.mapper3D.clear_sub_slave_slaves()
                            self.mapper3D.clear_parameters()
                            if manual_sweep_flags[1] == 0:
                                self.mapper3D.append_slave(value = self.value2)
                                step(axis = 2)
                            else:
                                self.cur_manual_index2 += 1
                                data_middle = pd.read_csv(manual_filenames[1])
                                steps = data_middle.values.reshape(-1)
                                determine_step(self.cur_manual_index2, steps, 2)
                                value = steps[self.cur_manual_index2]
                                self.mapper3D.append_slave(value = value)
                                step(axis = 2, value = value)
                        elif i == walks and back_and_forth_slave_slave != 1 and manual_sweep_flags[1] == 1:
                            self.cur_manual_index2 += 1
                        
                    back_and_forth_transposition(len(manual_sweep_flags))
                        
                if walks % 2 == 1:
                    back_and_forth_transposition(len(manual_sweep_flags))
                    
            else:
                raise Exception('back_and_forth_slave is not correct, needs >= 1, but got ', back_and_forth_slave)
           
            if len(manual_sweep_flags) == 2:
                self.mapper2D.slave_done_walking()
                self.mapper2D.concatenate_all()
                self.mapper2D.clear_slave()
                self.mapper2D.clear_sub_slaves()
                self.mapper2D.clear_parameters()
                
            elif len(manual_sweep_flags) == 3 and self.condition_status == 'yx':
                self.mapper2D.slave_done_walking()
                self.mapper2D.concatenate_all()
                self.mapper2D.clear_slave()
                self.mapper2D.clear_sub_slaves()
                self.mapper2D.clear_parameters()
                    
            elif len(manual_sweep_flags) == 3 and self.condition_status != 'yx':
                self.mapper3D.slave_slave_done_walking()
                self.mapper3D.concatenate_all()
                self.mapper3D.clear_slave_slave()
                self.mapper3D.clear_sub_slave_slaves()
                self.mapper3D.clear_parameters()
               
            if not hasattr(self, 'time2'):
                self.time2 = time.perf_counter()
               
            print('Inner loop was made back and forth') 
            
        def double_inner_loop_single(direction = 1):
            '''commits a walk through mater (for 1d), slave (for 2d) or slave-slave (for 3d) axis'''
            
            while condition(len(manual_sweep_flags)) and condition(len(manual_sweep_flags) - 1):
                double_inner_step()
                if not self.started:
                    self.started = True
            
            self.mapper2D.add_sub_slave()
            
            print('Single double inner loop was made')
            
        def double_inner_loop_back_and_forth():
            '''travels through a line from self.condition axis back and forth as many times, as was given'''
            global back_and_forth_slave
            global back_and_forth_slave_slave
            global manual_sweep_flags
            
            flags_dict = {2: 'back_and_forth_slave', 3: 'back_and_forth_slave_slave'}
            walks = globals()[flags_dict[len(manual_sweep_flags)]]
            if walks == 1:
                self.inner_count = 1
                self.__dict__[f'cur_manual_index{len(manual_sweep_flags)}'] = 0
                double_inner_loop_single()
                globals()['Sweeper_object'].__dict__[f'cur_walk{len(manual_sweep_flags)}'] += 1
                if len(manual_sweep_flags) != 1:
                    back_and_forth_transposition(len(manual_sweep_flags), False)
            
            elif walks > 1:
                for i in range(1, walks + 1):
                    self.inner_count = 1
                    self.__dict__[f'cur_manual_index{len(manual_sweep_flags)}'] = 0
                    double_inner_loop_single(direction = round(2 * (i % 2) - 1))
                    globals()['Sweeper_object'].__dict__[f'cur_walk{len(manual_sweep_flags)}'] += 1
                    if globals()['snakemode_master_flag'] == True:
                        if i != walks:
                            self.mapper2D.walks = 1
                            self.mapper2D.slave_done_walking()
                            self.mapper2D.concatenate_all()
                            self.mapper2D.clear_slave()
                            self.mapper2D.clear_sub_slaves()
                            self.mapper2D.clear_parameters()
                            self.mapper2D.append_master(value = self.value1)
                            step(axis = 1)
                            globals()['Sweeper_object'].cur_walk1 += 1
                            
                    back_and_forth_transposition(len(manual_sweep_flags))
                    
                if walks % 2 == 1:
                    back_and_forth_transposition(len(manual_sweep_flags))
                    
            else:
                raise Exception('back_and_forth_slave is not correct, needs >= 1, but got ', back_and_forth_slave)
           
            time.sleep(0.01) 
               
            self.mapper2D.slave_done_walking()
            self.mapper2D.concatenate_all()
            self.mapper2D.clear_slave()
            self.mapper2D.clear_sub_slaves()
            self.mapper2D.clear_parameters()
            
            if not hasattr(self, 'time2'):
                self.time2 = time.perf_counter()
               
            print('Double inner loop was made back and forth') 
               
        def double_external_loop_single(direction = 1):
            '''perform sequence of steps through master (for 2-d) or slave (for 3-d) axis
            with inner_loop on each step'''
            
            while condition(1) and condition(2):
                
                self.mapper2D.append_master(value = self.value2)
                double_step_yx()
                
                globals()['Sweeper_object'].__dict__['cur_walk1'] += 1
                globals()['Sweeper_object'].__dict__['cur_walk2'] += 1
                
                globals()['dataframe_after'] = [*globals()['dataframe']]
                            
                inner_loop_back_and_forth()
                update_filename()
            
        def external_walk_back(direction = -1):
            '''commits a backwards walk through slave axis for 3D sweep'''
            
            
            
            if manual_sweep_flags[1] == 0:
                while condition(2) and manual_sweep_flags[1] == 0:
                    step(axis = 2)
            elif manual_sweep_flags[1] == 1:
                data_outer = pd.read_csv(manual_filenames[1]).values.reshape(-1)
                for i, value in enumerate(data_outer[::direction]):
                    if manual_sweep_flags[1] == 1:
                        if not self.cur_manual_index2 > i:
                            determine_step(i, data_outer, len(manual_sweep_flags))
                            self.cur_manual_index2 = i 
                            step(axis = 2, value = value)
                    else:
                        break
                
            else:
                raise Exception('manual_sweep_flag is not correct, needs 0 or 1, but got ', manual_sweep_flags[len(manual_sweep_flags) - 1])
            
        def external_loop_single(direction = 1):
            '''perform sequence of steps through master (for 2-d) or slave (for 3-d) axis
            with inner_loop on each step'''
            
            cur_axis = len(manual_sweep_flags) - 1
            if manual_sweep_flags[-2] == 0:
                while condition(cur_axis) and manual_sweep_flags[-2] == 0:
                    if len(manual_sweep_flags) == 3:
                        update_dataframe(True)
                    if len(manual_sweep_flags) == 2:
                        self.mapper2D.append_master(value = self.value1)
                    if len(manual_sweep_flags) == 3:
                        self.mapper3D.append_slave(value = self.value2)

                    step(cur_axis)
                    
                    globals()['Sweeper_object'].__dict__[f'cur_walk{cur_axis}'] += 1
                    
                    if len(manual_sweep_flags) == 2:
                        globals()['dataframe_after'] = [*globals()['dataframe']]
                    elif len(manual_sweep_flags) == 3:
                        globals()['dataframe_after_after'] = [*globals()['dataframe']]
                    else:
                        raise Exception('manual_sweep_flag is not correct size, should be 1, 2 or 3, but got ', len(manual_sweep_flags))
                
                    inner_loop_back_and_forth()
                    update_filename()
                    
            elif manual_sweep_flags[-2] == 1:
                data_middle = pd.read_csv(manual_filenames[-2]).values.reshape(-1)
                for i, value in enumerate(data_middle[::direction]):
                    if not self.__dict__[f'cur_manual_index{len(manual_sweep_flags) - 1}'] > i:
                        if manual_sweep_flags[-2] == 1:
                            determine_step(i, data_middle, cur_axis)
                            if len(manual_sweep_flags) == 2:
                                self.mapper2D.append_master(value = value)
                            if len(manual_sweep_flags) == 3:
                                self.mapper3D.append_slave(value = value)
                            step(cur_axis, value = value)
                            globals()['Sweeper_object'].__dict__[f'cur_walk{cur_axis}'] += 1
                            if len(manual_sweep_flags) == 2:
                                globals()['dataframe_after'] = [*globals()['dataframe']]
                            else:
                                globals()['dataframe_after_after'] = [*globals()['dataframe']]
                            self.__dict__[f'cur_manual_index{len(manual_sweep_flags) - 1}'] = i
                            inner_loop_back_and_forth()
                            update_filename()
                        else:
                            break
            else:
                raise Exception('manual_sweep_flag is not correct, needs 0 or 1, but got ', manual_sweep_flags[-1])
            
            print('Single external loop was made')
            
        def double_external_loop_back_and_forth():
            '''travels through a slave axis back and forth as many times, as was given'''
            global back_and_forth_master
            global back_and_forth_slave
            global filename_sweep
            
            walks = max(back_and_forth_master, back_and_forth_slave)
            if walks == 1:
                self.cur_manual_index1 = 0
                self.cur_manual_index2 = 0
                double_external_loop_single()
                back_and_forth_transposition(2, False)
            
            elif walks > 1:
                for i in range(1, walks + 1):
                    self.cur_manual_index1 = 0
                    self.cur_manual_index2 = 0
                    double_external_loop_single(round(2 * (i % 2) - 1))
                    if (globals()['snakemode_slave_flag'] == True) or (globals()['snakemode_master_flag'] == True):
                        if i != walks and back_and_forth_slave != 1:
                            step(axis = 1)
                    back_and_forth_transposition(2)
                    #double_step_yx()
                    #double_step_yx()
                    
                if walks % 2 == 1:
                    back_and_forth_transposition(2)
            
        def external_loop_back_and_forth():
            '''travels through a slave axis back and forth as many times, as was given'''
            global back_and_forth_master
            global back_and_forth_slave
            global filename_sweep
            
            flags_dict = {2: 'back_and_forth_master', 3: 'back_and_forth_slave'}
            walks = globals()[flags_dict[len(manual_sweep_flags)]]
            if walks == 1:
                self.__dict__[f'cur_manual_index{len(manual_sweep_flags) - 1}'] = 0
                external_loop_single()
                if len(manual_sweep_flags) == 3:
                    back_and_forth_transposition(2, True)
                    external_walk_back()
                    back_and_forth_transposition(2, True)
            
            elif walks > 1:
                for i in range(1, walks + 1):
                    self.__dict__[f'cur_manual_index{len(manual_sweep_flags) - 1}'] = 0
                    external_loop_single(round(2 * (i % 2) - 1))
                    if globals()['snakemode_master_flag'] == True and len(manual_sweep_flags) == 3:
                        if i != walks and back_and_forth_slave != 1:
                            self.mapper3D.walks = 1
                            self.mapper3D.clear_slave_slave()
                            self.mapper3D.clear_slave()
                            self.mapper3D.clear_parameters()
                            self.mapper3D.stack_iteration()
                            if manual_sweep_flags[1] == 0:
                                self.mapper3D.append_master(value = self.value1)
                                step(axis = 1)
                            else:
                                self.cur_manual_index1 += 1
                                data_outer = pd.read_csv(manual_filenames[0])
                                steps = data_outer.values.reshape(-1)
                                determine_step(self.cur_manual_index1, data_outer, 1)
                                value = steps[self.cur_manual_index1]
                                self.mapper3D.append_master(value = value)
                                step(axis = 1, value = value)
                        elif i == walks and back_and_forth_slave != 1 and manual_sweep_flags[1] == 1:
                            self.cur_manual_index1 += 1
                    back_and_forth_transposition(len(manual_sweep_flags) - 1)
                    
                if walks % 2 == 1:
                    back_and_forth_transposition(len(manual_sweep_flags) - 1)
                        
            
            else:
                raise Exception(f'{flags_dict[len(manual_sweep_flags)]} is not correct, needs > 1, but got ', walks)
    
            if walks >= 3 and walks % 2 == 1 and len(manual_sweep_flags) == 3:
                external_walk_back()
                back_and_forth_transposition(2, True)
            
            if len(manual_sweep_flags) == 3:
                self.mapper3D.clear_slave_slave()
                self.mapper3D.clear_slave()
                self.mapper3D.clear_parameters()
                self.mapper3D.stack_iteration()
    
            print('External loop was made back and forth')
    
        def master_loop_single(direction = 1):
            '''perform sequence of steps through master (3-d) axis
            with external_loop_back_and_forth on each step'''
    
            if manual_sweep_flags[0] == 0:
                while condition(1) and manual_sweep_flags[0] == 0:
                    self.mapper3D.append_master(value = self.value1)
                    step(1)
                    globals()['Sweeper_object'].cur_walk1 += 1
                    globals()['dataframe_after'] = [*globals()['dataframe']]
                    external_loop_back_and_forth()
                    update_filename()
            elif manual_sweep_flags[0] == 1:
                data_external = pd.read_csv(manual_filenames[0]).values.reshape(-1)
                for i, value in enumerate(data_external[::direction]):
                    if not self.cur_manual_index1 >= i:
                        if manual_sweep_flags[0] == 1:
                            determine_step(i, data_external, 1)
                            self.mapper3D.append_master(value = value)
                            step(1, value = value)
                            globals()['Sweeper_object'].cur_walk1 += 1
                            globals()['dataframe_after'] = [*globals()['dataframe']]
                            self.cur_manual_index1 = i
                            external_loop_back_and_forth()
                            update_filename()
                        else:
                            break
                    
            else:
                raise Exception('manual_sweep_flag is not correct, needs 0 or 1, but got ', manual_sweep_flags[-2])
            
            print('Single master loop was made')
            
        def double_master_loop_single(direction = 1):
            '''perform sequence of steps through master (3-d) axis
            with double_inner_loop_back_and_forth on each step'''
    
            while condition(1):
                self.mapper2D.append_master(value = self.value1)
                step(1)
                globals()['Sweeper_object'].cur_walk1 += 1
                globals()['dataframe_after'] = [*globals()['dataframe']]
                double_inner_loop_back_and_forth()
                update_filename()
    
        def master_loop_back_and_forth():
            '''travels through a master axis back and forth as many times, as was given'''
            global back_and_forth_master
            
            walks = back_and_forth_master
            if walks == 1:
                self.cur_manual_index1 = 0
                master_loop_single()
            
            elif walks > 1:
                for i in range(1, walks + 1):
                    self.cur_manual_index1 = 0
                    master_loop_single(round(2 * (i % 2) - 1))
                    back_and_forth_transposition(1)
                    
                if back_and_forth_master % 2 == 1:
                    back_and_forth_transposition(1)
                    
            else:
                raise Exception('back_and_forth_master is not correct, needs > 1, but got ', walks)
    
            print('External loop was made back and forth')
            
        def double_master_loop_back_and_forth():
            '''travels through a double axis back and forth as many times, as was given'''
            global back_and_forth_master
            
            walks = back_and_forth_master
            if walks == 1:
                self.cur_manual_index1 = 0
                double_master_loop_single()
            
            elif walks > 1:
                for i in range(1, walks + 1):
                    self.cur_manual_index1 = 0
                    double_master_loop_single(round(2 * (i % 2) - 1))
                    back_and_forth_transposition(1)
                    #step(axis = 1)
                    #step(axis = 1)
                    
                if back_and_forth_master % 2 == 1:
                    back_and_forth_transposition(1)
                    
            else:
                raise Exception('back_and_forth_master is not correct, needs > 1, but got ', walks)
    
            print('External loop was made back and forth')
        
        if self.sweeper_flag1 == True:
            
            zero_time = time.perf_counter()
    
            update_filename()
            
            if len(manual_sweep_flags) == 1:        
                inner_loop_back_and_forth()
                self.sweeper_flag1 == False
                self.value1 = float(from_sweep1)
                if parameter_to_sweep1 in device_to_sweep1.get_options:
                    self.value1 = float(getattr(device_to_sweep1, parameter_to_sweep1)())
    
        if self.sweeper_flag2 == True:
            
            zero_time = time.perf_counter()
            
            update_filename()
    
            if len(manual_sweep_flags) == 2:
                if self.condition_status == 'unknown':
                    external_loop_back_and_forth()
                elif self.condition_status == 'xy':
                    double_inner_loop_back_and_forth()
                self.sweeper_flag2 == False
                self.value1 = float(from_sweep1)
                if parameter_to_sweep1 in device_to_sweep1.get_options:
                    self.value1 = float(getattr(device_to_sweep1, parameter_to_sweep1)())
                self.value2 = float(from_sweep2)
                if parameter_to_sweep2 in device_to_sweep2.get_options:
                    self.value2 = float(getattr(device_to_sweep2, parameter_to_sweep2)())
    
        if self.sweeper_flag3 == True:
    
            zero_time = time.perf_counter()        
    
            update_filename()
    
            if len(manual_sweep_flags) == 3:
                if self.condition_status == 'unknown':
                    master_loop_back_and_forth()
                elif self.condition_status == 'yz':
                    double_master_loop_back_and_forth()
                elif self.condition_status == 'yx':
                    double_external_loop_back_and_forth()
                self.sweeper_flag3 == False
                self.value1 = float(from_sweep1)
                if parameter_to_sweep1 in device_to_sweep1.get_options:
                    self.value1 = float(getattr(device_to_sweep1, parameter_to_sweep1)())
                self.value2 = float(from_sweep2)
                if parameter_to_sweep2 in device_to_sweep2.get_options:
                    self.value2 = float(getattr(device_to_sweep2, parameter_to_sweep2)())
                self.value3 = float(from_sweep3)
                if parameter_to_sweep3 in device_to_sweep3.get_options:
                    self.value3 = float(getattr(device_to_sweep3, parameter_to_sweep3)())
                
        if self.setget_flag == True:
            setget_write()
        
        globals()['Sweeper_object'].start_sweep_flag = False
        for i in range(1, len(manual_sweep_flags) + 1):
            globals()['Sweeper_object'].__dict__['cur_walk{i}'] = 1
        
        self.sweepable1 = False
        self.sweepable2 = False
        self.sweepable3 = False
        
        for device in list_of_devices:
            
            try:
                device.clear()
            except:
                pass
        
        try:
            if np.array(globals()['dataframe']).shape[0] == 0:
                os.remove(filename_sweep)
        except:
            pass

class FigureSettings(object):
    
    def __init__(self, widget):
        self.widget = widget
        self.id = None
        self.x = self.y = 0
    
    def showsettings(self, ax):
        x, y, _, _ = self.widget.bbox('all')
        x = x + self.widget.winfo_rootx()
        y = y + self.widget.winfo_rooty()
        self.settings_window = tw = tk.Toplevel(self.widget)
        tw.wm_geometry("+%d+%d" % (x, y))
        
        self.position = var2str(ax)
        self.position = self.position[self.position.find('ax') + 2:]
        self.position = int(self.position)
        
        self.preset = pd.read_csv(globals()['graph_preset_path'], sep = ',')
        self.preset = self.preset.fillna('')
        self.title = str(self.preset[f'title{self.position}'].values[0])
        self.x_current = int(self.preset[f'x{self.position}_current'].values[0])
        self.y_current = int(self.preset[f'y{self.position}_current'].values[0])
        self.z_current = int(self.preset[f'z{self.position}_current'].values[0])
        self.x_log = int(self.preset[f'x{self.position}_log'].values[0])
        self.y_log = int(self.preset[f'y{self.position}_log'].values[0])
        self.x_lim_left = str(self.preset[f'x{self.position}_lim_left'].values[0])   
        self.x_lim_right = str(self.preset[f'x{self.position}_lim_right'].values[0])  
        self.x_autoscale = str(self.preset[f'x{self.position}_autoscale'].values[0])
        self.y_lim_left = str(self.preset[f'y{self.position}_lim_left'].values[0])   
        self.y_lim_right = str(self.preset[f'y{self.position}_lim_right'].values[0])  
        self.y_autoscale = str(self.preset[f'y{self.position}_autoscale'].values[0])
        self.x_label = str(self.preset[f'x{self.position}_label'].values[0])
        self.y_label = str(self.preset[f'y{self.position}_label'].values[0])
        self.z_label = str(self.preset[f'z{self.position}_label'].values[0])
        self.x_transform = str(self.preset[f'x{self.position}_transform'].values[0])
        self.y_transform = str(self.preset[f'y{self.position}_transform'].values[0])
        self.z_transform = str(self.preset[f'z{self.position}_transform'].values[0])
        
        if plot_flag == 'Plot' or int(var2str(ax)[2:]) % 3 != 1:
        
            self.entry_title = tk.Entry(tw)
            self.entry_title.insert(index = 0, string = self.title)
            self.entry_title.grid(row = 0, column = 1, pady = 2)
            
            ax.set_title(self.entry_title.get(), fontsize = 8, pad = -5)
            
            button_close = tk.Button(tw, text = 'Save', command = lambda: self.hidesettings(ax))
            button_close.grid(row = 0, column = 5, pady = 2)
            
            label_xlabel = tk.Label(tw, text = 'x label = ')
            label_xlabel.grid(row = 5, column = 0, pady = 2, sticky = tk.W)
            
            self.entry_xlabel = tk.Entry(tw)
            self.entry_xlabel.insert(index = 0, string = self.x_label)
            self.entry_xlabel.grid(row = 5, column = 1)
        
            label_ylabel = tk.Label(tw, text = 'y label = ')
            label_ylabel.grid(row = 6, column = 0, pady = 2, sticky = tk.W)
            
            self.entry_ylabel = tk.Entry(tw)
            self.entry_ylabel.insert(index = 0, string = self.y_label)
            self.entry_ylabel.grid(row = 6, column = 1, pady = 2)
            
            label_x_device = tk.Label(tw, text = 'x')
            label_x_device.grid(row = 1, column = 0, pady = 2, sticky = tk.W)
            
            self.combo_x_device = ttk.Combobox(tw, values=globals()['columns'])
            try:
                self.combo_x_device.current(self.x_current)
                self.ax_update_plot(ax = ax, event = None)
            except:
                pass
            self.combo_x_device.bind("<<ComboboxSelected>>", lambda event: self.ax_update_plot(ax, event))
            self.combo_x_device.grid(row = 1, column = 1, pady = 2)
            
            label_log_x = tk.Label(tw, text = 'log')
            label_log_x.grid(row = 1, column = 3, pady = 2)
            
            self.status_log_x = tk.IntVar()
            self.status_log_x.set(int(self.x_log))
            checkbox_log_x = tk.Checkbutton(tw, 
                                                 command= lambda: self.save_log_x_status(ax),
                                                 variable = self.status_log_x, offvalue = 0, onvalue = 1)
            checkbox_log_x.grid(row = 1, column = 4, pady = 2)
            CreateToolTip(checkbox_log_x, 'Set x logscale')
            #self.save_log_x_status(ax)
            
            label_y_device = tk.Label(tw, text = 'y')
            label_y_device.grid(row = 2, column = 0, pady = 2, sticky = tk.W)
            
            self.combo_y_device = ttk.Combobox(tw, values=globals()['columns'])
            try:
                self.combo_y_device.current(self.y_current)
                self.ax_update_plot(ax = ax, event = None)
            except:
                pass
            self.combo_y_device.bind("<<ComboboxSelected>>", lambda event: self.ax_update_plot(ax, event))
            self.combo_y_device.grid(row = 2, column = 1, pady = 2)
            
            label_log_y = tk.Label(tw, text = 'log')
            label_log_y.grid(row = 2, column = 3, pady = 2)
            
            self.status_log_y = tk.IntVar()
            self.status_log_y.set(int(self.y_log))
            checkbox_log_y = tk.Checkbutton(tw, 
                                                 command=lambda: self.save_log_y_status(ax),
                                                 variable = self.status_log_y, offvalue = 0, onvalue = 1)
            checkbox_log_y.grid(row = 2, column = 4, pady = 2)
            CreateToolTip(checkbox_log_y, 'Set y logscale')
            
            #self.save_log_y_status(ax)
            
            self.status_xlim = tk.IntVar()
            self.status_xlim.set(int(self.x_autoscale))
            
            label_xlim = tk.Label(tw, text = 'x lim = ')
            label_xlim.grid(row = 3, column = 0, pady = 2, sticky = tk.W)
            
            self.entry_x_from = tk.Entry(tw, width = 8)
            self.entry_x_from.insert(index = 0, string = self.x_lim_left)
            self.entry_x_from.grid(row = 3, column = 1, pady = 2, sticky = tk.W)
            
            label_dash_x = tk.Label(tw, text = ' - ')
            label_dash_x.grid(row = 3, column = 1, pady = 2)
            
            self.entry_x_to = tk.Entry(tw, width = 8)
            self.entry_x_to.insert(index = 0, string = self.x_lim_right)
            self.entry_x_to.grid(row = 3, column = 1, pady = 2, sticky = tk.E)
            
            checkbox_xlim = tk.Checkbutton(tw, command = lambda: self.set_xlim(ax),
                                           variable = self.status_xlim, offvalue = 0, onvalue = 1)
            checkbox_xlim.grid(row = 3, column = 3, pady = 2)
            CreateToolTip(checkbox_xlim, 'Set x autoscale on')
            
            #self.set_xlim(ax)
            
            self.status_ylim = tk.IntVar()
            self.status_ylim.set(int(self.y_autoscale))
            
            label_ylim = tk.Label(tw, text = 'y lim = ')
            label_ylim.grid(row = 4, column = 0, pady = 2, sticky = tk.W)
            
            self.entry_y_from = tk.Entry(tw, width = 8)
            self.entry_y_from.insert(index = 0, string = self.y_lim_left)
            self.entry_y_from.grid(row = 4, column = 1, pady = 2, sticky = tk.W)
        
            label_dash_y = tk.Label(tw, text = ' - ')
            label_dash_y.grid(row = 4, column = 1, pady = 2)
            
            self.entry_y_to = tk.Entry(tw, width = 8)
            self.entry_y_to.insert(index = 0, string = self.y_lim_right)
            self.entry_y_to.grid(row = 4, column = 1, pady = 2, sticky = tk.E)
            
            checkbox_ylim = tk.Checkbutton(tw, command = lambda: self.set_ylim(ax),
                                           variable = self.status_ylim, offvalue = 0, onvalue = 1)
            checkbox_ylim.grid(row = 4, column = 3, pady = 2)
            CreateToolTip(checkbox_ylim, 'Set y autoscale on')
            
            #self.set_ylim(ax)
            
            label_x_transformation = tk.Label(tw, text = 'x = ')
            label_x_transformation.grid(row = 7, column = 0, pady = 2, sticky = tk.W)
            CreateToolTip(label_x_transformation, 'X transformation')
            
            self.entry_x_transformation = tk.Entry(tw)
            self.entry_x_transformation.insert(index = 0, string = self.x_transform)
            self.entry_x_transformation.grid(row = 7, column = 1, pady = 2)
            
            label_y_transformation = tk.Label(tw, text = 'y = ')
            label_y_transformation.grid(row = 8, column = 0, pady = 2, sticky = tk.W)
            CreateToolTip(label_y_transformation, 'Y transformation')
            
            self.entry_y_transformation = tk.Entry(tw)
            self.entry_y_transformation.insert(index = 0, string = self.y_transform)
            self.entry_y_transformation.grid(row = 8, column = 1, pady = 2)
        
        elif plot_flag == 'Map' and int(var2str(ax)[2:]) % 3 == 1:
            
            self.preset = pd.read_csv(globals()['graph_preset_path'], sep = ',')
            self.preset = self.preset.fillna('')
            self.title_map = str(self.preset[f'title_map{self.position}'].values[0])
            self.x_label_map = str(self.preset[f'x{self.position}_label_map'].values[0])
            self.y_label_map = str(self.preset[f'y{self.position}_label_map'].values[0])
            self.z_label_map = str(self.preset[f'z{self.position}_label_map'].values[0])
            self.cmap = str(self.preset[f'cmap{self.position}'].values[0])
            self.x_transform_map = str(self.preset[f'x{self.position}_transform_map'].values[0])
            self.y_transform_map = str(self.preset[f'y{self.position}_transform_map'].values[0])
            self.z_transform_map = str(self.preset[f'z{self.position}_transform_map'].values[0])
            
            self.entry_title_map = tk.Entry(tw)
            self.entry_title_map.insert(index = 0, string = self.title_map)
            self.entry_title_map.grid(row = 0, column = 1, pady = 2)
            
            ax.set_title(self.entry_title_map.get(), fontsize = 8, pad = -5)
            
            button_close = tk.Button(tw, text = 'Save', command = lambda: self.hidesettings(ax))
            button_close.grid(row = 0, column = 5, pady = 2)
            
            label_xlabel = tk.Label(tw, text = 'x label = ')
            label_xlabel.grid(row = 2, column = 0, pady = 2, sticky = tk.W)
            
            self.entry_xlabel_map = tk.Entry(tw)
            self.entry_xlabel_map.insert(index = 0, string = self.x_label_map)
            self.entry_xlabel_map.grid(row = 2, column = 1)
        
            label_ylabel = tk.Label(tw, text = 'y label = ')
            label_ylabel.grid(row = 3, column = 0, pady = 2, sticky = tk.W)
            
            self.entry_ylabel_map = tk.Entry(tw)
            self.entry_ylabel_map.insert(index = 0, string = self.y_label_map)
            self.entry_ylabel_map.grid(row = 3, column = 1, pady = 2)
            
            label_zlabel = tk.Label(tw, text = 'z label = ')
            label_zlabel.grid(row = 4, column = 0, pady = 2, sticky = tk.W)
            
            self.entry_zlabel_map = tk.Entry(tw)
            self.entry_zlabel_map.insert(index = 0, string = self.z_label_map)
            self.entry_zlabel_map.grid(row = 4, column = 1)
            
            label_z_device = tk.Label(tw, text = 'z')
            label_z_device.grid(row = 1, column = 0, pady = 2, sticky = tk.W)
            
            if len(manual_sweep_flags) == 2:
                values = globals()['columns'][3:]
            elif len(manual_sweep_flags) == 3:
                values = globals()['columns'][4:]
            self.combo_z_device_map = ttk.Combobox(tw, values=values)
            try:
                self.combo_z_device_map.current(self.z_current)
                self.ax_update_map(ax = ax, event = None)
            except:
                pass
            self.combo_z_device_map.bind("<<ComboboxSelected>>", lambda event: self.ax_update_map(ax, event))
            self.combo_z_device_map.grid(row = 1, column = 1, pady = 2)
            
            label_x_transformation = tk.Label(tw, text = 'x = ')
            label_x_transformation.grid(row = 5, column = 0, pady = 2, sticky = tk.W)
            CreateToolTip(label_x_transformation, 'X transformation')
            
            self.entry_x_transformation_map = tk.Entry(tw)
            self.entry_x_transformation_map.insert(index = 0, string = self.x_transform_map)
            self.entry_x_transformation_map.grid(row = 5, column = 1, pady = 2)
            
            label_y_transformation = tk.Label(tw, text = 'y = ')
            label_y_transformation.grid(row = 6, column = 0, pady = 2, sticky = tk.W)
            CreateToolTip(label_y_transformation, 'Y transformation')
            
            self.entry_y_transformation_map = tk.Entry(tw)
            self.entry_y_transformation_map.insert(index = 0, string = self.y_transform_map)
            self.entry_y_transformation_map.grid(row = 6, column = 1, pady = 2)
            
            label_z_transformation = tk.Label(tw, text = 'z = ')
            label_z_transformation.grid(row = 7, column = 0, pady = 2, sticky = tk.W)
            CreateToolTip(label_z_transformation, 'z transformation')
            
            self.entry_z_transformation_map = tk.Entry(tw)
            self.entry_z_transformation_map.insert(index = 0, string = self.z_transform_map)
            self.entry_z_transformation_map.grid(row = 7, column = 1, pady = 2)
            
            label_cmap = tk.Label(tw, text = 'Colormap')
            label_cmap.grid(row = 8, column = 0, pady = 2)
            
            colormaps = list(plt.colormaps())
            self.combo_cmap = ttk.Combobox(tw, values = colormaps)
            try:
                self.combo_cmap.current(colormaps.index(self.cmap))
            except:
                self.combo_cmap.current(0)
            self.combo_cmap.bind("<<ComboboxSelected>>", lambda event: self.choose_cmap(ax, event))
            self.combo_cmap.grid(row = 8, column = 1, pady = 2)
    
        else:
            raise Exception(f'plot_flag could only obtain values "Plot" or "Map", got {plot_flag}')
        
    def save_log_x_status(self, ax):
        if self.status_log_x.get() == 0:
            ax.set_xscale('linear')
        elif self.status_log_x.get() == 1:
            ax.set_xscale('log')
        self.rewrite_preset()
        
    def save_log_y_status(self, ax):
        if self.status_log_y.get() == 0:
            ax.set_yscale('linear')
        elif self.status_log_y.get() == 1:
            ax.set_yscale('log')
        self.rewrite_preset()
            
    def set_xlim(self, ax):
        if self.status_xlim.get() == 0:
            ax.autoscale(enable = False, axis = 'x')
            try:
                xlims = (float(self.entry_x_from.get()), float(self.entry_x_to.get()))
            except:
                xlims = (0, 1)
            ax.set_xlim(xlims)
            globals()[f'x{var2str(ax)[2:]}_autoscale'] = False
        elif self.status_xlim.get() == 1:
            ax.autoscale(enable = True, axis = 'x')
            globals()[f'x{var2str(ax)[2:]}_autoscale'] = True
        self.rewrite_preset()
        
    def set_ylim(self, ax):
        if self.status_ylim.get() == 0:
            ax.autoscale(enable = False, axis = 'y')
            try:
                ylims = (float(self.entry_y_from.get()), float(self.entry_y_to.get()))
            except:
                ylims = (0, 1)
            ax.set_ylim(ylims)
            globals()[f'y{var2str(ax)[2:]}_autoscale'] = False
        elif self.status_ylim.get() == 1:
            ax.autoscale(enable = True, axis = 'y')
            globals()[f'y{var2str(ax)[2:]}_autoscale'] = True
        self.rewrite_preset()
        
    def ax_update_plot(self, ax, event):
        
        def axes_settings(i, pad = 0, tick_size = 4, label_size = 6, x_pad = 0, y_pad = 1, title_size = 8, title_pad = -5):
            globals()[f'ax{i}'].tick_params(axis='y', which='both', length = 0, pad=pad, labelsize=tick_size)
            globals()[f'ax{i}'].tick_params(axis='x', which='both', length = 0, pad=pad + 1, labelsize=tick_size)
            globals()[f'ax{i}'].set_xlabel(self.entry_xlabel.get(), fontsize = label_size, labelpad = x_pad)
            globals()[f'ax{i}'].set_ylabel(self.entry_ylabel.get(), fontsize = label_size, labelpad = y_pad)
            globals()[f'ax{i}'].set_title(self.entry_title.get(), fontsize = title_size, pad = title_pad)
        
        ax_str = var2str(ax)
        
        order = ax_str[2:]
        
        globals()[f'x{order}_status'] = self.combo_x_device.current()
        globals()[f'y{order}_status'] = self.combo_y_device.current()
        
        xscale_status = ax.get_xscale()
        yscale_status = ax.get_yscale()
        xlims = ax.get_xlim()
        ylims = ax.get_ylim()
        ax.clear()
        ax.set_xscale(xscale_status)
        ax.set_yscale(yscale_status)
        axes_settings(order)
        ax.set_xlim(xlims)
        ax.set_ylim(ylims)
        ax.autoscale(enable = globals()[f'x{order}_autoscale'], axis = 'x')
        ax.autoscale(enable = globals()[f'y{order}_autoscale'], axis = 'y')
        
    def ax_update_map(self, ax, event):
        
        def axes_settings(i, pad = 0, tick_size = 4, label_size = 6, x_pad = 0, y_pad = 1, title_size = 8, title_pad = -5):
            globals()[f'ax{i}'].tick_params(axis='y', which='both', length = 0, pad=pad, labelsize=tick_size)
            globals()[f'ax{i}'].tick_params(axis='x', which='both', length = 0, pad=pad + 1, labelsize=tick_size)
            globals()[f'ax{i}'].set_xlabel(self.entry_xlabel_map.get(), fontsize = label_size, labelpad = x_pad)
            globals()[f'ax{i}'].set_ylabel(self.entry_ylabel_map.get(), fontsize = label_size, labelpad = y_pad)
            globals()[f'colorbar{i}'].set_label(self.entry_zlabel_map.get(), fontsize = label_size, labelpad = x_pad)
            globals()[f'colorbar{i}_label'] = self.entry_zlabel_map.get()
            globals()[f'ax{i}'].set_title(self.entry_title_map.get(), fontsize = title_size, pad = title_pad)
        
        ax_str = var2str(ax)
        
        order = ax_str[2:]
        
        globals()[f'z{order}_status'] = self.combo_z_device_map.current()
        
        
        ax.clear()
        axes_settings(order)
    
    def choose_cmap(self, ax, event):
        
        ax_str = var2str(ax)
        
        order = ax_str[2:]
        
        globals()[f'cmap_{order}'] = plt.colormaps()[self.combo_cmap.current()]
        
        self.preset.loc[0, f'cmap{order}'] = globals()[f'cmap_{order}']
    
    def rewrite_preset(self):
        
        global plot_flag
        
        if plot_flag == 'Plot' or int(self.position) % 3 != 1:
            self.preset.loc[0, f'title{self.position}'] = self.entry_title.get()
            self.preset.loc[0, f'x{self.position}_current'] = self.combo_x_device.current()
            self.preset.loc[0, f'y{self.position}_current'] = self.combo_y_device.current()
            self.preset.loc[0, f'x{self.position}_log'] = self.status_log_x.get()
            self.preset.loc[0, f'y{self.position}_log'] = self.status_log_y.get()
            self.preset.loc[0, f'x{self.position}_lim_left'] = self.entry_x_from.get()
            self.preset.loc[0, f'x{self.position}_lim_right'] = self.entry_x_to.get()
            self.preset.loc[0, f'x{self.position}_autoscale'] = self.status_xlim.get()
            self.preset.loc[0, f'y{self.position}_lim_left'] = self.entry_y_from.get()
            self.preset.loc[0, f'y{self.position}_lim_right'] = self.entry_y_to.get()
            self.preset.loc[0, f'y{self.position}_autoscale'] = self.status_ylim.get()
            self.preset.loc[0, f'x{self.position}_label'] = self.entry_xlabel.get()
            self.preset.loc[0, f'y{self.position}_label'] = self.entry_ylabel.get()
            self.preset.loc[0, f'x{self.position}_transform'] = self.entry_x_transformation.get()
            self.preset.loc[0, f'y{self.position}_transform'] = self.entry_y_transformation.get()
            self.preset.to_csv(globals()['graph_preset_path'], index = False)
            
        elif plot_flag == 'Map'  and int(self.position) % 3 == 1:
            self.preset.loc[0, f'title_map{self.position}'] = self.entry_title_map.get()
            self.preset.loc[0, f'z{self.position}_current'] = self.combo_z_device_map.current()
            self.preset.loc[0, f'z{self.position}_label_map'] = self.entry_zlabel_map.get()
            self.preset.loc[0, f'x{self.position}_label_map'] = self.entry_xlabel_map.get()
            self.preset.loc[0, f'y{self.position}_label_map'] = self.entry_ylabel_map.get()
            self.preset.loc[0, f'x{self.position}_transform_map'] = self.entry_x_transformation_map.get()
            self.preset.loc[0, f'y{self.position}_transform_map'] = self.entry_y_transformation_map.get()
            self.preset.loc[0, f'z{self.position}_transform_map'] = self.entry_z_transformation_map.get()
            self.preset.to_csv(globals()['graph_preset_path'], index = False)
    
        else:
            raise Exception(f'plot_flag could only obtain values "Plot" or "Map", got {plot_flag}')
    
    def hidesettings(self, ax):
        global x_transformation
        global y_transformation
        global plot_flag
        
        tw = self.settings_window
        
        if plot_flag == 'Plot' or int(var2str(ax)[2:]) % 3 != 1:
            if self.status_xlim.get() == 0:
                try:
                    ax.set_xlim((float(self.entry_x_from.get()), float(self.entry_x_to.get())))
                except:
                    pass
            if self.status_ylim.get() == 0:
                try:
                    ax.set_ylim((float(self.entry_y_from.get()), float(self.entry_y_to.get())))
                except:
                    pass
            
            try:
                ax.set_xlabel(self.entry_xlabel.get(), fontsize = 8)
            except:
                pass
            
            try:
                ax.set_ylabel(self.entry_ylabel.get(), fontsize = 8)
            except:
                pass
            
            try:
                ax.set_title(self.entry_title.get(), fontsize = 8, pad = -5)
            except:
                pass
            
            try:
                globals()[f'x_transformation{var2str(ax)[2:]}'] = self.entry_x_transformation.get()
            except:
                pass
        
            try:
                globals()[f'y_transformation{var2str(ax)[2:]}'] = self.entry_y_transformation.get()
            except:
                pass
            
            self.rewrite_preset()
            
            if tw:
                tw.destroy()
                
        elif plot_flag == 'Map' and int(var2str(ax)[2:]) % 3 == 1:
            
            try:
                ax.set_zlabel(self.entry_zlabel_map.get(), fontsize = 8)
            except:
                pass
            
            try:
                ax.set_title(self.entry_title_map.get(), fontsize = 8, pad = -5)
            except:
                pass
            
            try:
                ax.set_xlabel(self.entry_xlabel_map.get(), fontsize = 8)
            except:
                pass
            
            try:
                ax.set_ylabel(self.entry_ylabel_map.get(), fontsize = 8)
            except:
                pass
            
            try:
                globals()[f'x_transformation{var2str(ax)[2:]}'] = self.entry_x_transformation_map.get()
            except:
                pass
        
            try:
                globals()[f'y_transformation{var2str(ax)[2:]}'] = self.entry_y_transformation_map.get()
            except:
                pass
            
            try:
                globals()[f'z_transformation{var2str(ax)[2:]}'] = self.entry_z_transformation_map.get()
            except:
                pass
            
            self.rewrite_preset()
            
            if tw:
                tw.destroy()
            
        else:
            raise Exception(f'plot_flag could only obtain values "Plot" or "Map", got {plot_flag}')
        
class VerticalNavigationToolbar2Tk(NavigationToolbar2Tk):
    def __init__(self, canvas, window):
        super().__init__(canvas, window, pack_toolbar=True)

    #Override pan function so it would return to original autoscale after releasing the button
    def pan(self, *args):
        
        from enum import Enum
        
        class _Mode(str, Enum):
            NONE = ""
            PAN = "pan/zoom"
            ZOOM = "zoom rect"
            
            def __init__(self, NONE):
                self.N = NONE

            def __str__(self):
                return self.value

            @property
            def _navigate_mode(self):
                return self.name if self is not self.N else None
        
        """
        Toggle the pan/zoom tool.

        Pan with left button, zoom with right.
        """
        if self.mode == _Mode.PAN:
            self.mode = _Mode.NONE
            self.canvas.widgetlock.release(self)
            n = globals()['cur_animation_num'] - 3
            autoscale_x = bool(globals()[f'x{n}_autoscale'])
            autoscale_y = bool(globals()[f'y{n}_autoscale'])
            ax = globals()[f'ax{n}']
            ax.autoscale(enable = autoscale_x, axis = 'x')
            ax.autoscale(enable = autoscale_y, axis = 'y')
        else:
            self.mode = _Mode.PAN
            self.canvas.widgetlock(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self.mode._navigate_mode)
        self.set_message(self.mode)

    #Override zoom function so it would return to original autoscale after releasing the button
    def zoom(self, *args):
        
        from enum import Enum
        
        class _Mode(str, Enum):
            NONE = ""
            PAN = "pan/zoom"
            ZOOM = "zoom rect"
            
            def __init__(self, NONE):
                self.N = NONE

            def __str__(self):
                return self.value

            @property
            def _navigate_mode(self):
                return self.name if self is not self.N else None
        
        """Toggle zoom to rect mode."""
        if self.mode == _Mode.ZOOM:
            self.mode = _Mode.NONE
            self.canvas.widgetlock.release(self)
            n = globals()['cur_animation_num'] - 3
            autoscale_x = bool(globals()[f'x{n}_autoscale'])
            autoscale_y = bool(globals()[f'y{n}_autoscale'])
            ax = globals()[f'ax{n}']
            ax.autoscale(enable = autoscale_x, axis = 'x')
            ax.autoscale(enable = autoscale_y, axis = 'y')
        else:
            self.mode = _Mode.ZOOM
            self.canvas.widgetlock(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self.mode._navigate_mode)
        self.set_message(self.mode)

    def drag_pan(self, event):
        """Callback for dragging in pan/zoom mode."""
        for ax in self._pan_info.axes:
            # Using the recorded button at the press is safer than the current
            # button, as multiple buttons can get pressed during motion.
            ax.drag_pan(self._pan_info.button, event.key, event.x, event.y)
            ax.autoscale(enable = False, axis = 'x')
            ax.autoscale(enable = False, axis = 'y')
        self.canvas.draw_idle()
        
    def drag_zoom(self, event):
        """Callback for dragging in zoom mode."""
        start_xy = self._zoom_info.start_xy
        self._zoom_info.axes[0].autoscale(enable = False, axis = 'x')
        self._zoom_info.axes[0].autoscale(enable = False, axis = 'y')
        (x1, y1), (x2, y2) = np.clip(
            [start_xy, [event.x, event.y]], self._zoom_info.axes[0].bbox.min, self._zoom_info.axes[0].bbox.max)
        key = event.key
        # Force the key on colorbars to extend the short-axis bbox
        if self._zoom_info.cbar == "horizontal":
            key = "x"
        elif self._zoom_info.cbar == "vertical":
            key = "y"
        if key == "x":
            y1, y2 = self._zoom_info.axes[0].bbox.intervaly
        elif key == "y":
            x1, x2 = self._zoom_info.axes[0].bbox.intervalx

        self.draw_rubberband(event, x1, y1, x2, y2)

    # override _Button() to re-pack the toolbar button in vertical direction
    def _Button(self, text, image_file, toggle, command):
        b = super()._Button(text, image_file, toggle, command)
        b.pack(side=tk.TOP)  # re-pack button in vertical direction
        return b

    # override _Spacer() to create vertical separator
    def _Spacer(self):
        s = tk.Frame(self, width=26, relief=tk.RIDGE, bg="White", padx=2)
        s.pack(side=tk.TOP, pady = 5, fill="both", expand=True)  # pack in vertical direction
        return s

    # disable showing mouse position in toolbar
    def set_message(self, s):
        pass
        
def CreateFigureSettings(widget, ax):
    globals()[f'settingsFigure{var2str(ax)[2:]}'] = FigureSettings(widget)
    def enter(event):
        globals()[f'settingsFigure{var2str(ax)[2:]}'].showsettings(ax)
    widget.bind('<Button-3>', enter)
    widget.bind('<Double-1>', enter)
    
class StartAnimation:
    
    def start(filename):
        global cur_animation_num
        i = cur_animation_num
        globals()[f'animation{i}'] = animation.FuncAnimation(
            fig = globals()[f'fig{i}'], func = lambda x: my_animate(x, n = i, filename = filename), interval=interval, blit = False)
        cur_animation_num += 1

class Graph():
    
    def __init__(self, filename):
        
        self.filename = filename
        
        self.tw = tk.Toplevel(globals()['Sweeper_object'])
        
        self.tw.geometry("1920x1080")
        self.tw.title("Graph")
        
        self.order = globals()['cur_animation_num']
        
        self.preset = pd.read_csv(globals()['graph_preset_path'], sep = ',')
        self.preset = self.preset.fillna('')
        self.num_plots = int(self.preset['num_plots'].values[0])
        
        self.title1 = str(self.preset[f'title{self.order}'].values[0])
        self.title2 = str(self.preset[f'title{self.order + 1}'].values[0])
        self.title3 = str(self.preset[f'title{self.order + 2}'].values[0])
        
        self.x_log1 = int(self.preset[f'x{self.order}_log'].values[0])
        self.y_log1 = int(self.preset[f'y{self.order}_log'].values[0])
        self.x_log2 = int(self.preset[f'x{self.order + 1}_log'].values[0])
        self.y_log2 = int(self.preset[f'y{self.order + 1}_log'].values[0])
        self.x_log3 = int(self.preset[f'x{self.order + 2}_log'].values[0])
        self.y_log3 = int(self.preset[f'y{self.order + 2}_log'].values[0])
        self.cmap = str(self.preset[f'cmap{self.order}'].values[0])
        
        try:
            self.x_lim_left1 = float(self.preset[f'x{self.order}_lim_left'].values[0]) 
        except ValueError:
            self.x_lim_left1 = 0
        try:
            self.x_lim_right1 = float(self.preset[f'x{self.order}_lim_right'].values[0]) 
        except ValueError:
            self.x_lim_right1 = 1
        self.x_autoscale1 = int(self.preset[f'x{self.order}_autoscale'].values[0])
        try:
            self.y_lim_left1 = float(self.preset[f'y{self.order}_lim_left'].values[0]) 
        except ValueError:
            self.y_lim_left1 = 0  
        try:
            self.y_lim_right1 = float(self.preset[f'x{self.order}_lim_left'].values[0]) 
        except ValueError:
            self.y_lim_right1 = 1  
        self.y_autoscale1 = int(self.preset[f'y{self.order}_autoscale'].values[0])
        try:
            self.x_lim_left2 = float(self.preset[f'x{self.order + 1}_lim_left'].values[0]) 
        except ValueError:
            self.x_lim_left2 = 0
        try:
            self.x_lim_right2 = float(self.preset[f'x{self.order + 1}_lim_right'].values[0]) 
        except ValueError:
            self.x_lim_right2 = 1
        self.x_autoscale2 = int(self.preset[f'x{self.order + 1}_autoscale'].values[0])
        try:
            self.y_lim_left2 = float(self.preset[f'y{self.order + 1}_lim_left'].values[0]) 
        except ValueError:
            self.y_lim_left2 = 0  
        try:
            self.y_lim_right2 = float(self.preset[f'x{self.order + 1}_lim_left'].values[0]) 
        except ValueError:
            self.y_lim_right2 = 1  
        self.y_autoscale2 = int(self.preset[f'y{self.order + 1}_autoscale'].values[0])
        try:
            self.x_lim_left3 = float(self.preset[f'x{self.order + 2}_lim_left'].values[0]) 
        except ValueError:
            self.x_lim_left3 = 0
        try:
            self.x_lim_right3 = float(self.preset[f'x{self.order + 2}_lim_right'].values[0]) 
        except ValueError:
            self.x_lim_right3 = 1
        self.x_autoscale3 = int(self.preset[f'x{self.order + 2}_autoscale'].values[0])
        try:
            self.y_lim_left3 = float(self.preset[f'y{self.order + 2}_lim_left'].values[0]) 
        except ValueError:
            self.y_lim_left3 = 0  
        try:
            self.y_lim_right3 = float(self.preset[f'x{self.order + 2}_lim_left'].values[0]) 
        except ValueError:
            self.y_lim_right3 = 1  
        self.y_autoscale3 = int(self.preset[f'y{self.order + 2}_autoscale'].values[0])
        
        self.x_current1 = int(self.preset[f'x{self.order}_current'].values[0])
        self.y_current1 = int(self.preset[f'y{self.order}_current'].values[0])
        self.x_current2 = int(self.preset[f'x{self.order + 1}_current'].values[0])
        self.y_current2 = int(self.preset[f'y{self.order + 1}_current'].values[0])
        self.x_current3 = int(self.preset[f'x{self.order + 2}_current'].values[0])
        self.y_current3 = int(self.preset[f'y{self.order + 2}_current'].values[0])
        
        self.x_label1 = str(self.preset[f'x{self.order}_label'].values[0])
        self.y_label1 = str(self.preset[f'y{self.order}_label'].values[0])
        self.x_label2 = str(self.preset[f'x{self.order + 1}_label'].values[0])
        self.y_label2 = str(self.preset[f'y{self.order + 1}_label'].values[0])
        self.x_label3 = str(self.preset[f'x{self.order + 2}_label'].values[0])
        self.y_label3 = str(self.preset[f'y{self.order + 2}_label'].values[0])
        
        self.x_transform1 = str(self.preset[f'x{self.order}_transform'].values[0])
        self.y_transform1 = str(self.preset[f'y{self.order}_transform'].values[0])
        self.x_transform2 = str(self.preset[f'x{self.order + 1}_transform'].values[0])
        self.y_transform2 = str(self.preset[f'y{self.order + 1}_transform'].values[0])
        self.x_transform3 = str(self.preset[f'x{self.order + 2}_transform'].values[0])
        self.y_transform3 = str(self.preset[f'y{self.order + 2}_transform'].values[0])
        
        self.label_x1 = tk.Label(self.tw, text='x', font=LARGE_FONT)
        self.label_x1.place(relx=0.02, rely=0.76)

        self.label_y1 = tk.Label(self.tw, text='y', font=LARGE_FONT)
        self.label_y1.place(relx=0.15, rely=0.76)

        self.combo_x1 = ttk.Combobox(self.tw, values=columns)
        self.combo_x1.bind("<<ComboboxSelected>>", self.ax_update)
        self.combo_x1.place(relx=0.035, rely=0.76)

        self.combo_y1 = ttk.Combobox(self.tw, values=columns)
        self.combo_y1.bind("<<ComboboxSelected>>", self.ax_update)
        self.combo_y1.place(relx=0.165, rely=0.76)
        
        try:
            self.combo_x1.current(self.x_current1)
            self.combo_y1.current(self.y_current1)
            self.ax_update(None)
        except:
            pass
        
        self.create_fig(self.order, (2.5, 1.65))
        self.create_fig(self.order + 1, (1.5, 0.8))
        self.create_fig(self.order + 2, (1.5, 0.8))
            
        if self.x_current2 < len(columns):
            globals()[f'x{self.order + 1}_status'] = self.x_current2
        if self.y_current2 < len(columns):
            globals()[f'y{self.order + 1}_status'] = self.y_current2
            
        if self.x_current3 < len(columns):
            globals()[f'x{self.order + 2}_status'] = self.x_current3
        if self.y_current3 < len(columns):
            globals()[f'y{self.order + 2}_status'] = self.y_current3

        globals()[f'self.plot{self.order}'] = FigureCanvasTkAgg(globals()[f'fig{self.order}'], self.tw)
        globals()[f'self.plot{self.order}'].draw()
        globals()[f'self.plot{self.order}'].get_tk_widget().place(relx=0, rely=0)
        CreateFigureSettings(globals()[f'self.plot{self.order}'].get_tk_widget(), globals()[f'ax{self.order}'])
        CreateToolTip(globals()[f'self.plot{self.order}'].get_tk_widget(), 'Right click to configure')

        globals()[f'self.toolbar{self.order}'] = VerticalNavigationToolbar2Tk(globals()[f'self.plot{self.order}'], self.tw)
        globals()[f'self.toolbar{self.order}'].config(background = 'White')
        globals()[f'self.toolbar{self.order}'].update()
        globals()[f'self.toolbar{self.order}'].place(relx=0, rely=0)
        globals()[f'self.plot{self.order}']._tkcanvas.place(relx=0, rely=0)

        globals()[f'self.plot{self.order + 1}'] = FigureCanvasTkAgg(globals()[f'fig{self.order + 1}'], self.tw)
        globals()[f'self.plot{self.order + 1}'].draw()
        globals()[f'self.plot{self.order + 1}'].get_tk_widget().place(relx=0.52, rely=0)
        CreateFigureSettings(globals()[f'self.plot{self.order + 1}'].get_tk_widget(), globals()[f'ax{self.order + 1}'])
        CreateToolTip(globals()[f'self.plot{self.order + 1}'].get_tk_widget(), 'Right click to configure')
        globals()[f'self.plot{self.order + 1}']._tkcanvas.place(relx=0.62, rely=0)

        globals()[f'self.plot{self.order + 2}'] = FigureCanvasTkAgg(globals()[f'fig{self.order + 2}'], self.tw)
        globals()[f'self.plot{self.order + 2}'].draw()
        globals()[f'self.plot{self.order + 2}'].get_tk_widget().place(relx=0.02, rely=0.50)
        CreateFigureSettings(globals()[f'self.plot{self.order + 2}'].get_tk_widget(), globals()[f'ax{self.order + 2}'])
        CreateToolTip(globals()[f'self.plot{self.order + 2}'].get_tk_widget(), 'Right click to configure')
        globals()[f'self.plot{self.order + 2}']._tkcanvas.place(relx=0.62, rely=0.39)
        
        self.button_add = tk.Button(self.tw, text = 'Add graph', font = LARGE_FONT, command = lambda: self.add_graph())
        self.button_close = tk.Button(self.tw, text = r'🗙', font = LARGE_FONT, command = lambda: self.close_graph())
        
        if len(manual_sweep_flags) == 2 or len(manual_sweep_flags) == 3:
            self.button_map = tk.Button(self.tw, text = '🗺', font = LARGE_FONT, command = self.switch)
            self.button_map.place(relx = 0.001, rely = 0.24)
            globals()[f'cmap_{self.order}'] = self.cmap
            if plot_flag == 'Map':
                CreateToolTip(self.button_map, 'Change to plot')
            if plot_flag == 'Plot':
                CreateToolTip(self.button_map, 'Change to map')
        
        if self.num_plots == 1:
            globals()[f'self.plot{self.order + 1}'].get_tk_widget().place_forget()
            globals()[f'self.plot{self.order + 1}']._tkcanvas.place_forget()
            
            globals()[f'self.plot{self.order + 2}'].get_tk_widget().place_forget()
            globals()[f'self.plot{self.order + 2}']._tkcanvas.place_forget()
            
            self.button_add.place(relx = 0.7, rely = 0.1)
            
        elif self.num_plots == 2:
            globals()[f'self.plot{self.order + 2}'].get_tk_widget().place_forget()
            globals()[f'self.plot{self.order + 2}']._tkcanvas.place_forget()
            
            self.button_add.place(relx = 0.7, rely = 0.6)
            self.button_close.place(relx = 0.95, rely = 0)
            
        else:
            
            self.button_close.place(relx = 0.95, rely = 0.38)
            
        self.update_layout()
        
        self.table_dataframe = ttk.Treeview(self.tw, columns = columns, show = 'headings', height = 1)
        self.table_dataframe.place(relx = 0.28, rely = 0.76)
        
        self.initial_value = []
        
        for ind, heading in enumerate(columns):
            self.table_dataframe.heading(ind, text = heading)
            self.table_dataframe.column(ind,anchor=tk.CENTER, stretch=tk.NO, width=80)
            self.initial_value.append(heading)
                
        self.table_dataframe.insert('', tk.END, 'Current dataframe', text = 'Current dataframe', values = self.initial_value)
        
        self.update_item('Current dataframe')
        
        self.button_pause = tk.Button(self.tw, text = '⏸️', font = LARGE_FONT, command = self.pause_clicked)
        self.button_pause.place(relx = 0.02, rely = 0.82)
        CreateToolTip(self.button_pause, 'Pause\Continue sweep')
        
        self.button_stop = tk.Button(self.tw, text = '⏹️', font = LARGE_FONT, command = self.stop_clicked)
        self.button_stop.place(relx = 0.06, rely = 0.82)
        CreateToolTip(self.button_stop, 'Stop sweep')
        
        self.button_tozero = tk.Button(self.tw, text = 'To zero', width = 11, command = lambda: globals()['Sweeper_object'].tozero())
        self.button_tozero.place(relx = 0.1, rely = 0.82, width = 48, height = 32)
        
        if not globals()['setget_flag']:
            
            self.label_filename = tk.Label(self.tw, text = globals()['filename_sweep'], font = LARGE_FONT, justify = tk.RIGHT)
            self.label_filename.place(relx = 0.6, rely = 0.82)
            
        else:
            self.label_setget_filename = tk.Label(self.tw, text = globals()['filename_setget'], font = LARGE_FONT)
            self.label_setget_filename.place(relx = 0.6, rely = 0.82)
        
        def close_graph():
            global plot_flag
            if self.order == globals()['cur_animation_num'] - 3:
                globals()['cur_animation_num'] -= 3
            plot_flag = 'Plot'
            self.tw.destroy()
        
        self.tw.protocol("WM_DELETE_WINDOW", close_graph)
        
    def update_layout(self):
        
        if self.num_plots == 3 and not (globals()[f'self.plot{self.order + 2}']._tkcanvas.winfo_ismapped() or globals()[f'self.plot{self.order + 2}'].get_tk_widget().winfo_ismapped()):
            globals()[f'self.plot{self.order + 2}'].get_tk_widget().place(relx=0.02, rely=0.50)
            globals()[f'self.plot{self.order + 2}']._tkcanvas.place(relx=0.62, rely=0.39)
            
        if self.num_plots == 2 and not (globals()[f'self.plot{self.order + 1}']._tkcanvas.winfo_ismapped() or globals()[f'self.plot{self.order + 1}'].get_tk_widget().winfo_ismapped()):
            globals()[f'self.plot{self.order + 1}'].get_tk_widget().place(relx=0.52, rely=0)
            globals()[f'self.plot{self.order + 1}']._tkcanvas.place(relx=0.62, rely=0)
        elif self.num_plots == 2 and (globals()[f'self.plot{self.order + 2}']._tkcanvas.winfo_ismapped() or globals()[f'self.plot{self.order + 2}'].get_tk_widget().winfo_ismapped()):
            globals()[f'self.plot{self.order + 2}'].get_tk_widget().place_forget()
            globals()[f'self.plot{self.order + 2}']._tkcanvas.place_forget()
            
        if self.num_plots == 1 and (globals()[f'self.plot{self.order + 1}']._tkcanvas.winfo_ismapped() or globals()[f'self.plot{self.order + 1}'].get_tk_widget().winfo_ismapped()):
            globals()[f'self.plot{self.order + 1}'].get_tk_widget().place_forget()
            globals()[f'self.plot{self.order + 1}']._tkcanvas.place_forget()
            
    def add_graph(self):
        
        if self.num_plots < 3:
            self.num_plots += 1
            
        if self.num_plots == 3:
            self.button_add.place_forget()
            self.button_close.place(relx = 0.95, rely = 0.38)
        elif self.num_plots == 2:
            self.button_add.place(relx = 0.7, rely = 0.6)
            self.button_close.place(relx = 0.95, rely = 0)
            
        self.preset.loc[0, 'num_plots'] = self.num_plots
        self.preset.to_csv(globals()['graph_preset_path'], index = False)
        
        self.update_layout()
        
    def close_graph(self):
        if self.num_plots > 1:
            self.num_plots -= 1
            
        if self.num_plots == 2:
            self.button_add.place(relx = 0.7, rely = 0.6)
            self.button_close.place(relx = 0.95, rely = 0)
            
        elif self.num_plots == 1:
            self.button_add.place(relx = 0.7, rely = 0.1)
            self.button_close.place_forget()
        
        self.preset.loc[0, 'num_plots'] = self.num_plots
        self.preset.to_csv(globals()['graph_preset_path'], index = False)
        
        self.update_layout()
        
    def axes_settings(self, i, pad = 0, tick_size = 4, label_size = 6, x_pad =0, y_pad = 1, title_size = 8, title_pad = -5):
        ax = globals()[f'ax{i}']
        dic = {1: 1, 2: 2, 0: 3}
        ax.tick_params(axis='y', which='both', length = 0, pad=pad, labelsize=tick_size)
        ax.tick_params(axis='x', which='both', length = 0, pad=pad + 1, labelsize=tick_size)
        ax.yaxis.offsetText.set_fontsize(tick_size)
        ax.xaxis.offsetText.set_fontsize(tick_size)
        ax.set_xlabel(getattr(self, f'x_label{dic[i % 3]}'), fontsize = label_size, labelpad = x_pad)
        ax.set_ylabel(getattr(self, f'y_label{dic[i % 3]}'), fontsize = label_size, labelpad = y_pad)
        ax.set_title(getattr(self, f'title{dic[i % 3]}'), fontsize = title_size, pad = title_pad)
        if getattr(self, f'x_log{dic[i % 3]}') == 1:
            ax.set_xscale('log')
        elif getattr(self, f'x_log{dic[i % 3]}') == 0:
            ax.set_xscale('linear')
        if getattr(self, f'y_log{dic[i % 3]}') == 1:
            ax.set_yscale('log')
        elif getattr(self, f'y_log{dic[i % 3]}') == 0:
            ax.set_yscale('linear')
            
        if getattr(self, f'x_autoscale{dic[i % 3]}') == 1:
            ax.autoscale(enable = True, axis = 'x')
            globals()[f'x{var2str(ax)[2:]}_autoscale'] = True
        elif getattr(self, f'x_autoscale{dic[i % 3]}') == 0:
            ax.autoscale(enable = False, axis = 'x')
            globals()[f'x{var2str(ax)[2:]}_autoscale'] = False
            #ax.set_xlim(getattr(self, f'x_lim_left{dic[i % 3]}'), getattr(self, f'x_lim_right{dic[i % 3]}'))
        
        if getattr(self, f'y_autoscale{dic[i % 3]}') == 1:
            ax.autoscale(enable = True, axis = 'y')
            globals()[f'y{var2str(ax)[2:]}_autoscale'] = True
        elif getattr(self, f'y_autoscale{dic[i % 3]}') == 0:
            ax.autoscale(enable = False, axis = 'y')
            globals()[f'y{var2str(ax)[2:]}_autoscale'] = False
            #ax.set_ylim(getattr(self, f'y_lim_left{dic[i % 3]}'), getattr(self, f'y_lim_right{dic[i % 3]}'))

        globals()[f'x_transformation{var2str(ax)[2:]}'] = getattr(self, f'x_transform{dic[i % 3]}')
        globals()[f'y_transformation{var2str(ax)[2:]}'] = getattr(self, f'y_transform{dic[i % 3]}')

    def create_fig(self, i, figsize, pad = 0, tick_size = 4, label_size = 6, x_pad = 0, y_pad = 1, title_size = 8, title_pad = -5):
        
        globals()[f'fig{i}'] = Figure(figsize, dpi=300)
        globals()[f'ax{i}'] = globals()[f'fig{i}'].add_subplot(111)
        globals()[f'fig{i}'].subplots_adjust(left = 0.25, bottom = 0.25)
        globals()[f'x_transformation{i}'] = 'x'
        globals()[f'y_transformation{i}'] = 'y'
        globals()[f'z_transformation{i}'] = 'z'
        globals()[f'x{i}_autoscale'] = True
        globals()[f'y{i}_autoscale'] = True
        ax = globals()[f'ax{i}']
        ax.bbox.union([label.get_window_extent() for label in ax.get_xticklabels()])
        self.axes_settings(i, pad, tick_size, label_size, x_pad, y_pad, title_size, title_pad)

    def update_idletasks(self):
        pass
        #self.tw.update_idletasks()
        
    def update(self):
        pass
        #self.tw.update()

    def pause_clicked(self):
        if self.button_pause['text'] == '⏸️':
            self.button_pause.config(text = r'▶')
        elif self.button_pause['text'] == r'▶':
            self.button_pause.config(text = '⏸️')
        globals()['Sweeper_object'].pause()
        
    def stop_clicked(self):
        if not globals()['setget_flag']:
            globals()['Sweeper_object'].stop()
        else:
            globals()['setget_flag'] = False

    def ax_update(self, event):
        global columns
        global plot_flag
        if plot_flag == 'Plot':
            globals()[f'x{self.order}_status'] = self.combo_x1.current()
            globals()[f'y{self.order}_status'] = self.combo_y1.current()
            self.preset.loc[0, f'x{self.order}_current'] = self.combo_x1.current()
            self.preset.loc[0, f'y{self.order}_current'] = self.combo_y1.current()
            self.preset.to_csv(globals()['graph_preset_path'], index = False)
        elif plot_flag == 'Map':
            globals()[f'z{self.order}_status'] = self.combo_x1.current()
        else:
            raise Exception(f'plot_flag could only obtain values "Plot" or "Map", got {plot_flag}')
        
    def disable_autoscale(self, event):
        print(f'autoscale for {self.order} axis disabled')
        globals()[f'y{self.order}_autoscale'] = False
        
    def enable_autoscale(self, event):
        print(f'autoscale for {self.order} axis enabled')
        globals()[f'y{self.order}_autoscale'] = True
        
    def switch(self):
        global plot_flag
        global columns
        global manual_sweep_flags
        global sweeper_write
        
        if plot_flag == 'Plot':
            plot_flag = 'Map'
            self.combo_y1.place_forget()
            self.label_y1.place_forget()
            self.label_x1.configure(text = 'z')
            self.combo_x1.config(value = columns[3:])
            if self.combo_x1.current() > 2:
                globals()[f'z{self.order}_status'] = self.combo_x1.current()
            else:
                self.combo_x1.current(0)
                globals()[f'z{self.order}_status'] = 0
            globals()[f'ax{self.order}'].clear()
            ax = globals()[f'ax{self.order}']
            globals()[f'settingsFigure{self.order}'].showsettings(ax)
            globals()[f'settingsFigure{self.order}'].hidesettings(ax)
            if len(manual_sweep_flags) == 3 and sweeper_write.condition_status == 'unknown':
                self.combo_x1.config(value = columns[4:])
                self.master = globals()['sweeper_write'].mapper3D.master
                self.master_shape = self.master.shape[0]
                self.slider = tk.Scale(self.tw, from_ = 1, to = self.master_shape, variable = self.master_shape, orient = 'vertical')
                self.slider.place(relx = 0.55, rely = 0.075, height = 300)
                self.label_master = tk.Label(self.tw, text = f'{self.master[round(self.slider.get() - 1)]}', font = LARGE_FONT)
                self.label_master.place(relx = 0.55, rely = 0.5)
                
                self.last = True
                self.slider.configure(command = self.change_label)
                
        elif plot_flag == 'Map':
            plot_flag = 'Plot'
            self.combo_y1.place(relx=0.165, rely=0.76)
            self.combo_x1.config(value = columns)
            self.label_y1.place(relx=0.15, rely=0.76)
            self.label_x1.configure(text = 'x')
            try:
                globals()[f'colorbar{self.order}'].remove()
            except:
                pass
            ax = globals()[f'ax{self.order}']
            globals()[f'settingsFigure{self.order}'].showsettings(ax)
            globals()[f'settingsFigure{self.order}'].hidesettings(ax)
            if len(manual_sweep_flags) == 3 and sweeper_write.condition_status == 'unknown':
                
                self.slider.place_forget()
        else:
            raise Exception(f'plot_flag could only obtain values "Plot" or "Map", got {plot_flag}')
        
    def change_label(self, event):
        self.label_master.configure(text = f'{self.master[round(self.slider.get() - 1)]}')
        if round(self.slider.get()) == self.master.shape[0]:
            self.last = True
        else:
            self.last = False
        
        
    def update_item(self, item):
        global deli
        
        name = self.filename
        
        if not 'setget' in self.filename:
            name = globals()['filename_sweep']

        try:
            dataframe = pd.read_csv(name, delimiter = deli, engine='python').tail(1).values.flatten()
            
            for ind, value in enumerate(dataframe):
                try:
                    dataframe[ind] = "{:.3e}".format(value)
                except:
                    pass
            self.table_dataframe.item(item, values=tuple(dataframe))
            self.table_dataframe.after(250, self.update_item, item)
        except:
            self.table_dataframe.after(250, self.update_item, item)


interval = 100


def main():
    
    app = Universal_frontend(classes=(StartPage, Devices, SetGet, Sweeper1d, Sweeper2d, Sweeper3d),
                             start=StartPage)
    app.mainloop()
    
    for device in list_of_devices:
        
        try:
            device.stop()
        except:
            pass
        
        try:
            device.close()
        except:
            pass
    
    while True:
        globals()['stop_flag'] = True
        for i in [1, 2, 3]:
            globals()[f'sweeper_flag{i}'] = False
        sys.exit()


if __name__ == '__main__':
    main()
