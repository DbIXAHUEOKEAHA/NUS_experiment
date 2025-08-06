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
piezo = list_of_devices[list_of_devices_addresses.index('192.168.1.4')]
#keithley = list_of_devices[list_of_devices_addresses.index('GPIB0::6::INSTR')]
vna = list_of_devices[list_of_devices_addresses.index('169.254.82.39:5025')]
slider = list_of_devices[list_of_devices_addresses.index('COM4')]
attodry = list_of_devices[list_of_devices_addresses.index('192.168.1.4')]
    
def get_V():
    #V = getattr(keithley, 'Volt_DC')() #Using DC
    V = getattr(vna, 'linmag_peak')()[1] #Using VNA
    return V

if 'count_step_T' in list(globals().keys()):
    globals()['count_step_T'] += 1
else:
    globals()['count_step_T'] = 0

for j in range(3): #ungrounding
    getattr(piezo, f'set_gnd_{j+1}')(False)  
    getattr(piezo, f'set_outp_active_{j+1}')(True)
   
#span = float(getattr(vna, 'span_freq')())

#span = span // 1 #decrease span

getattr(slider, 'set_open')()
#getattr(vna, 'set_power')(3)
getattr(vna, 'set_bandwidth')(100)
getattr(vna, 'set_num_points')(201)

time.sleep(3)

max_freq = getattr(vna, 'linmag_peak')()[0]
max_freq = float(max_freq)

#peak_span = getattr(vna, 'linmag_span')()

#getattr(vna, 'set_span_freq')(peak_span * 10) #set span
getattr(vna, 'set_cent_freq')(max_freq) #set central freq
getattr(vna, 'set_num_points')(61)

trashold = 0.25 #difference between final value and max value
fine_trashold = 0.10 #to acoount for noize
iterations = 2

n_steps_x = 20
n_probe_x = 3

n_steps_y = 20
n_probe_y = 3

n_steps_z = 20  
n_probe_z = 3

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
    getattr(piezo, f'set_step_up_{axis}')(n_probe)
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
            getattr(piezo, f'set_step_{direction}_{axis}')(1) #make 1 step
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
            getattr(piezo, f'set_step_{direction}_{axis}')(n_probe)
            break

def movez(n_steps: int, axis: int = 1):
    data = numpy.zeros((2, n_steps * 2))
    for i in range(n_steps):
        getattr(piezo, f'set_step_up_{axis}')(3) #goes up
        time.sleep(sleep_time) #wait
    for i in range(n_steps*2):
        data[0, i] = i
        #getattr(slider, 'set_close')()
        #time.sleep(1.1)
        #data[1, i] = get_V() #read V noise
        #getattr(slider, 'set_open')()
        time.sleep(0.7)
        data[1, i] = get_V()# - data[1, i] #read V signal
        getattr(piezo, f'set_step_down_{axis}')(2) #goes down
        time.sleep(sleep_time) #wait
    result = data[0, np.argmax(data[1, :])]
    result = int(result)
    print(f'Index of max {axis}: {result}')
    #for i in range(n_steps):
    for i in range((n_steps * 2) - 1 - result):
        getattr(piezo, f'set_step_up_{axis}')(3) #goes up
        time.sleep(sleep_time) #wait 0.05 sec    

def move2(n_steps: int, axis: int = 1):
    data = numpy.zeros((2, n_steps * 2))
    for i in range(n_steps):
        getattr(piezo, f'set_step_up_{axis}')(2) #goes up
        time.sleep(sleep_time) #wait
    for i in range(n_steps*2):
        data[0, i] = i
        #getattr(slider, 'set_close')()
        #time.sleep(1.1)
        #data[1, i] = get_V() #read V noise
        #getattr(slider, 'set_open')()
        time.sleep(0.7)
        data[1, i] = get_V()# - data[1, i] #read V signal
        getattr(piezo, f'set_step_down_{axis}')(2) #goes down
        time.sleep(sleep_time) #wait
    result = data[0, np.argmax(data[1, :])]
    result = int(result)
    print(f'Index of max {axis}: {result}')
    #for i in range(n_steps):
    for i in range((n_steps * 2) - 1 - result):
        getattr(piezo, f'set_step_up_{axis}')(2) #goes up
        time.sleep(sleep_time) #wait 0.05 sec   

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

num_steps1 = 3
num_steps2 = 1

move2(num_steps1, 1) #X
move2(num_steps1, 2) #Y

movez(num_steps1, 3) #Z

#movez(num_steps2, 3)
#move2(num_steps2, 2)
#move2(num_steps2, 1)

#time.sleep(20)

#piezo.set_volt_1(35)
#piezo.set_volt_2(35)
#piezo.set_volt_3(40) 

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

max_freq = getattr(vna, 'linmag_peak')()[0]
max_freq = float(max_freq)

getattr(vna, 'set_cent_freq')(max_freq) #set central freq


getattr(vna, 'set_bandwidth')(100)
getattr(vna, 'set_num_points')(501)
#getattr(vna, 'set_span_freq')(span * 1)

time.sleep(5.5)

'''getattr(slider, 'set_close')()

print('Im doing bunch of gay staff')

time.sleep(1)

getattr(slider, 'set_open')()
'''

getattr(slider, 'set_close')()
for parameter in self.parameters_to_read:
    index_dot = len(parameter) - parameter[::-1].find('.') - 1
    adress = parameter[:index_dot]
    option = parameter[index_dot + 1:]

    try:
        parameter_value = getattr(list_of_devices[list_of_devices_addresses.index(adress)],
                                  option)()
        if str(parameter_value) == '':
            parameter_value = np.nan
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

dataframe = [np.round(i, 2) for i in [time.perf_counter() - zero_time]]
dataframe.append('Intermediate')
getattr(slider, 'set_open')()
#time.sleep(5.5)

for j in range(3): #grounding
    getattr(piezo, f'set_gnd_{j+1}')(True)   
    getattr(piezo, f'set_outp_active_{j+1}')(False)

    
    


