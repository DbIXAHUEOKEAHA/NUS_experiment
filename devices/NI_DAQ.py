import nidaqmx
import numpy as np
import matplotlib.pyplot as plt

class NI_DAQ():
    
    def __init__(self, adress):
        self.name = adress
        self.task = nidaqmx.Task()
        self.rate = 26100
        self.n_sample = int(self.rate / 1)
        for i in range(4):
            self.task.ai_channels.add_ai_voltage_chan(f'{self.name}/ai{i}')
            self.__dict__[f'ch{i}_mean'] = lambda i=i: self.ch_mean(i)
            self.__dict__[f'ch{i}_array'] = lambda i=i: self.ch_array(i)
        self.task.timing.cfg_samp_clk_timing(self.rate, samps_per_chan=self.n_sample)
        
        self.set_options = ['rate', 'n_sample']
        self.get_options = ['ch0_mean', 'ch1_mean', 'ch2_mean', 'ch3_mean', 
                            'ch0_array', 'ch1_array', 'ch2_array', 'ch3_array',
                            'rate', 'n_sample', 'time']
        self.measured_array = [None, None, None, None]
        self.measured_mean = [None, None, None, None]
         
    def set_rate(self, value: float):
         self.rate = value
         self.task.timing.cfg_samp_clk_timing(int(self.rate))
         print(f'Rate was set to {self.rate}')
         
    def set_n_sample(self, value: float):
        self.n_sample = int(value)
        print(f'N_sample was set to {self.n_sample}')
        
    def rate(self):
        return self.rate
    
    def n_sample(self):
        return self.n_sample
    
    def time(self):
        _time = (np.arange(self.n_sample) + 1) / self.rate
        _time = np.array(_time, dtype = str)
        time = ''
        for t in _time:
            time += t
            time += ','
        time = time[:-1]
        return time
    
    def ch_mean(self, i):
        if self.measured_mean[i] == None:
            self.measured_mean = self.task.read(self.n_sample)
            self.close()
            self.task = nidaqmx.Task()
            for j in range(4):
                self.task.ai_channels.add_ai_voltage_chan(f'{self.name}/ai{j}')
            self.task.timing.cfg_samp_clk_timing(self.rate, samps_per_chan=self.n_sample)
        answer = self.measured_mean[i]
        self.measured_mean[i] = None
        answer = np.array(answer).mean()
        return answer
    
    def ch_array(self, i):
        if self.measured_array[i] == None:
            self.measured_array = self.task.read(self.n_sample)
            self.close()
            self.task = nidaqmx.Task()
            for j in range(4):
                self.task.ai_channels.add_ai_voltage_chan(f'{self.name}/ai{j}')
            self.task.timing.cfg_samp_clk_timing(self.rate, samps_per_chan=self.n_sample)
        answer = self.measured_array[i]
        answer = np.array(answer, dtype = str)
        self.measured_array[i] = None
        ans = ''
        for a in answer:
            ans += str(a)
            ans += ','
        try:
            answer = answer.replace(' ', '')
        except:
            pass
        ans = ans[:-1]
        return ans

    def close(self):
        self.task.close()
        
    def clear(self):
        self.measured_array = [None, None, None, None]
        self.measured_mean = [None, None, None, None]
    
def main():
    name = 'cDAQ1Mod1'
    device = NI_DAQ(name)
    
    ch0 = [float(i) for i in device.ch0_array().split(',')]
    ch1 = device.ch1_array()
    ch2 = [float(i) for i in device.ch2_array().split(',')]
    
    fig, ax = plt.subplots()
    ax.plot(ch2, ch0)

if __name__ == '__main__':
    main()
         