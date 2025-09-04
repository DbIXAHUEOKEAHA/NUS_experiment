import time
import numpy
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

'''
if __name__ == '__main__':
    from devices.Vna import Vna
    from devices.keithley2000 import keithley2000
    from devices.asc500 import asc500
    #from devices.KSC101 import KSC101
    
    #from devices.slider import slider
    
    asc500 = asc500('COM3')
    #keithley = keithley2000('GPIB0::6::INSTR')
    vna = Vna('169.254.82.39:5025')
    #slider = KSC101('COM6')
    
else:
    asc500 = list_of_devices[list_of_devices_addresses.index('COM3')]
    #keithley = list_of_devices[list_of_devices_addresses.index('GPIB0::6::INSTR')]
    vna = list_of_devices[list_of_devices_addresses.index('169.254.82.39:5025')]
    slider = list_of_devices[list_of_devices_addresses.index('COM6')]
    
'''
scanner = list_of_devices[list_of_devices_addresses.index('COM3')]
#keithley = list_of_devices[list_of_devices_addresses.index('GPIB0::6::INSTR')]
vna = list_of_devices[list_of_devices_addresses.index('169.254.82.39:5025')]
slider = list_of_devices[list_of_devices_addresses.index('COM6')]
attodry = list_of_devices[list_of_devices_addresses.index('COM4')]
    
Temperature = attodry.Temp()
scanner.set_Temp(Temperature)

def get_V():
    averaging = 5
    #V = getattr(keithley, 'Volt_DC')() #Using DC
    V = 0 
    for i in range(averaging):
        V += getattr(vna, 'linmag_peak')()[1] #Using VNA
    return V/averaging

if 'count_step_T' in list(globals().keys()):
    globals()['count_step_T'] -= 1
else:
    globals()['count_step_T'] = 46

#for axis in ['x', 'y', 'z']: #ungrounding
#    getattr(scanner, f'set_gnd_{axis}')(False)  
#    getattr(scanner, f'set_outp_active_{axis}')(True)
   
#span = float(getattr(vna, 'span_freq')())

#span = span // 1 #decrease span

getattr(slider, 'set_open')()
#getattr(vna, 'set_power')(3)
getattr(vna, 'set_bandwidth')(50)
getattr(vna, 'set_num_points')(201)

time.sleep(6)

max_freq = getattr(vna, 'linmag_peak')()[0]
max_freq = float(max_freq)

#peak_span = getattr(vna, 'linmag_span')()

print(globals()['count_step_T'])

#if  globals()['count_step_T'] == 15 :
#    print('5 K UNTIL 3 DBM')
    
#if  -16 < globals()['count_step_T'] < 20 : #-3 dbm at < 20 K
#    getattr(vna, 'set_power')(-3)
#else:
#    getattr(vna, 'set_power')(3) 

#getattr(vna, 'set_span_freq')(peak_span * 10) #set span
#if  -36 < globals()['count_step_T'] < 40: #No movement > 40 K
#    print('I move center frequency')
#    getattr(vna, 'set_cent_freq')(max_freq) #set central freq
#    print('Bandwidth 200')
#    getattr(vna, 'set_bandwidth')(200)
#else:
print('Bandwidth 200')
getattr(vna, 'set_bandwidth')(200)
getattr(vna, 'set_num_points')(61)

if  globals()['count_step_T'] < -40:
    globals()['count_step_T'] = 46


trashold = 0.25 #difference between final value and max value
fine_trashold = 0.10 #to acoount for noize
iterations = 2

sleep_time = 1

def probe_move(n_probe: int = 5, axis: int = 1):
    """
    Make "n_probe" steps along "axis" to determine the sign of a gradient
    Parameters
    ----------
    n_probe : int
        number of steps to probe gradient. The default is 5.
    axis : str
        Axis alogn which to move. The default is 'x'.
    Returns
    -------
        True if grad_v >= 0
        False if grad_v < 0
    """
    init_v = get_V()
    getattr(scanner, f'set_step_up_{axis}')(n_probe)
    time.sleep(sleep_time)
    grad_v = get_V() - init_v
    if grad_v >= 0:
        return True
    else:
        return False
    
def move(n_steps: int = 50, n_probe: int = 5, axis: int = 1):
    """
    Parameters
    ----------
    n_steps : int
        max number of steps to go, if max is not found. The default is 50.
    n_probe : int
        number of steps to overshoot potential max. The default is 5.
    axis : str
        Axis alogn which to move. The default is 'x'.

    Returns
    -------
    None.

    """
    
    def flip(direction):
        if direction == 'up': #flip the direction
            direction = 'down'
        else:
            direction = 'up'
        return direction
    
    grad = probe_move(n_probe, axis)
    if grad:
        direction = 'up'
    else:
        direction = 'down'
    
    v = getattr(vna, 'linmag_peak')()[1]

    consecutive_counter = 0

    for i in range(n_steps):
        if consecutive_counter < n_probe: 
            getattr(scanner, f'set_step_{direction}_{axis}')(1) #make 1 step
            time.sleep(sleep_time) #wait 0.05 sec
            cur_v = get_V() #read V

            grad_v = cur_v - v
            
            if grad_v >= 0 and grad_v / v > fine_trashold: #if still increasing, reset the consecutive_counter
                consecutive_counter = 0
            else:
                consecutive_counter += 1 #if started to decrease, add +1 to consecutive counter
            
            v += grad_v
                    
        else: #if peak is found and overshooted, go n_probe steps in the opposite direction
            direction = flip(direction)
            getattr(scanner, f'set_step_{direction}_{axis}')(n_probe)
            break

def movez(n_steps: int, axis: int = 1):
    data = numpy.zeros((2, n_steps * 2))
    for i in range(n_steps):
        getattr(scanner, f'set_step_up_{axis}')(3) #goes up
        time.sleep(sleep_time) #wait
    for i in range(n_steps*2):
        data[0, i] = i
        #getattr(slider, 'set_close')()
        #time.sleep(1.1)
        #data[1, i] = get_V() #read V noise
        #getattr(slider, 'set_open')()
        time.sleep(0.7)
        data[1, i] = get_V()# - data[1, i] #read V signal
        getattr(scanner, f'set_step_down_{axis}')(2) #goes down
        time.sleep(sleep_time) #wait
    result = data[0, np.argmax(data[1, :])]
    result = int(result)
    print(f'Index of max {axis}: {result}')
    #for i in range(n_steps):
    for i in range((n_steps * 2) - 1 - result):
        getattr(scanner, f'set_step_up_{axis}')(3) #goes up
        time.sleep(sleep_time) #wait 0.05 sec    

def move2(n_steps: int, axis: str = 'h'):
    if axis == 'x' or axis == 'X':
        step = 100e-9
    elif axis == 'y' or axis == 'Y':
        step = 100e-9
    else:
        step = 200e-9
    data = numpy.zeros((2, n_steps * 2))
    current_position =  getattr(scanner, f'scanner_{axis}')()
    for i in range(n_steps):
        value = current_position + step
        getattr(scanner, f'set_scanner_{axis}')(value) #goes up
        current_position = value
        time.sleep(0.05) #wait 0.05 s
    for i in range(n_steps*2):
        data[0, i] = i
        #getattr(slider, 'set_close')()
        #time.sleep(1.1)
        #data[1, i] = get_V() #read V noise
        #getattr(slider, 'set_open')()
        time.sleep(0.05)
        data[1, i] = get_V()# - data[1, i] #read V signal
        current_position = value
        print(f'Current {axis} position: {value}, maximum voltage: {data[1, i]}')
        value = current_position - step
        getattr(scanner, f'set_scanner_{axis}')(value) #goes down
        time.sleep(0.05) #wait
    result = data[0, np.argmax(data[1, :])]
    result = int(result)
    print(f'Index of max {axis}: {result}, position of max: {value + step * (n_steps * 2 - result)}')
    for i in range(10):
        getattr(scanner, f'set_scanner_{axis}')(value + step * (n_steps * 2 - result))
        time.sleep(0.1)
    #for i in range(n_steps):
    #for i in range((n_steps * 2) - result - 1):
        #value = current_position + step
       # getattr(scanner, f'set_scanner_{axis}')(value) #goes up
        #current_position = value
       # time.sleep(0.05) #wait 0.05 sec   

'''
def moveZ(n_steps: int, step: float):
    data = numpy.zeros((2, n_steps * 2))
    for i in range(n_steps):
        asc500.set_scanner_down_z(step) #goes up
        time.sleep(sleep_time) #wait
    for i in range(n_steps*2):
        data[0, i] = i
        #getattr(slider, 'set_close')()
        #time.sleep(1.1)
        #data[1, i] = get_V() #read V noise
        #getattr(slider, 'set_open')()
        time.sleep(1.1)
        data[1, i] = get_V()# - data[1, i] #read V signal
        asc500.set_scanner_up_z(step) #goes down
        time.sleep(sleep_time) #wait
    result = data[0, np.argmax(data[1, :])]
    result = int(result)
    print(f'Index of max Z: {result}')
    #for i in range(n_steps):
    for i in range((n_steps * 2) - 1 - result):
        asc500.set_scanner_down_z(step) #goes up
        time.sleep(sleep_time) #wait 0.05 sec   
'''
        
#moveZ(1, 'z', 'down') #down for degrease T

#move2(2, 'z')
#move2(1, 'y')
#move2(1, 'x')

# Z movement per step
#if globals()['count_step_T'] <= 119:
#    asc500.set_step_up_z()
#    asc500.set_step_up_z()
#else:
#    asc500.set_step_down_z()

#step_z = 50e-9

num_steps1 = 4
num_steps2 = 1

move2(num_steps1, 'x') # Scanner X
move2(num_steps1, 'y') # Scanner Y
move2(num_steps1, 'z') # Scanner Z

#movez(num_steps2, 3)
#move2(num_steps2, 2)
#move2(num_steps2, 1)

#time.sleep(20)

#scanner.set_volt_1(35)
#scanner.set_volt_2(35)
#scanner.set_volt_3(40) 

# for i in range(iterations):
#     move2(3, 'y')
#     move2(3, 'x')
#     pass
'''
while n_steps_x > n_probe_x + 2 and n_steps_y > n_probe_y + 2 and n_steps_z > n_probe_z + 2:
    move(n_steps_z, n_probe_z, 'z')
    move(n_steps_x, n_probe_x, 'x')
    move(n_steps_y, n_probe_y, 'y')
    
    n_steps_x -= n_probe_x // 2
    n_steps_y -= n_probe_y // 2
    n_steps_z -= n_probe_z // 2  
''' 


#getattr(vna, 'set_power')(3)

#max_freq = getattr(vna, 'linmag_peak')()[0]
#max_freq = float(max_freq)

#getattr(vna, 'set_cent_freq')(max_freq) #set central freq


getattr(vna, 'set_bandwidth')(50)
getattr(vna, 'set_num_points')(501)
#getattr(vna, 'set_span_freq')(span * 1)

#time.sleep(5.5)

'''getattr(slider, 'set_close')()

print('Im doing bunch of gay staff')

time.sleep(1)

getattr(slider, 'set_open')()
'''

getattr(slider, 'set_close')()

if len(manual_sweep_flags) == 2:
    globals()['dataframe'].append("{:.3e}".format(getattr(self, 'value2')))
elif len(manual_sweep_flags) == 3:
    globals()['dataframe'].append("{:.3e}".format(getattr(self, 'value3')))

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
        
with open(filename_sweep, 'a', newline='') as f_object:
    try:
        writer_object = writer(f_object, delimiter = deli)
        writer_object.writerow(dataframe)
        f_object.close()
    except KeyboardInterrupt:
        f_object.close()
    finally:
        f_object.close()

if globals()['axis'] == len(manual_sweep_flags):
    globals()['dataframe'] = ['Intermideate']
    globals()['dataframe'].append("{:.3e}".format(getattr(self, 'value1')))
    if len(manual_sweep_flags) == 2:
        globals()['dataframe'].append("{:.3e}".format(getattr(self, 'value2')))
    elif len(manual_sweep_flags) == 3:
        globals()['dataframe'].append("{:.3e}".format(getattr(self, 'value3')))
else:
    globals()['dataframe'] = ['Intermideate']
        
getattr(slider, 'set_open')()
time.sleep(0.5)

#for axis in ['x', 'y', 'z']: #grounding
#    getattr(scanner, f'set_gnd_{axis}')(True)   
#    getattr(scanner, f'set_outp_active_{axis}')(False)

    
    


