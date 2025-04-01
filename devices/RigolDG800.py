from pymeasure.instruments import Instrument
import pyvisa as visa
from pyvisa import constants
import numpy as np

rm = visa.ResourceManager()


def get(device, command):
    '''device = rm.open_resource() where this function gets all devices initiaals such as adress, baud_rate, data_bits and so on; 
    command = string Standart Commands for Programmable Instruments (SCPI)'''
    return device.query(command)
    # return np.random.random(1)

class RigolDG800():
    def __init__(self, adress = '192.168.0.102'):
        
        if not adress.startswith('COM'):
            if not adress.startswith('TCPIP'):
                adress = f'TCPIP0::{adress}::inst0::INSTR'
        
        self.device = rm.open_resource(adress)
        
        self.ARB_MAX_SEND = 5000
        
    def apply_settings1(self, value: list = ['SIN', 1000, 5, 0, 0]):
        """Set the function shape of the output

        Parameters
        ----------
        value = (shape, freq, ampl, offset, phase)
        shape: SIN SQU RAMP PULS NOIS DC HARM ARB SEQ
        freq: float
        ampl: float
        offset: float
        phase: float
        """
        
        _type = value[0]
        _freq = value[1]
        _ampl = value[2]
        _offset = value[3]
        _phase = value[4]
        
        self.device.write(f':SOUR1:APPL:{_type} {_freq}{_ampl}{_offset}{_phase}')
    
    def apply_settings2(self, value: list = ['SIN', 1000, 5, 0, 0]):
        """Set the function shape of the output

        Parameters
        ----------
        value = (shape, freq, ampl, offset, phase)
        shape: SIN SQU RAMP PULS NOIS DC HARM ARB SEQ
        freq: float
        ampl: float
        offset: float
        phase: float
        """
        
        _type = value[0]
        _freq = value[1]
        _ampl = value[2]
        _offset = value[3]
        _phase = value[4]
        
        self.device.write(f':SOUR2:APPL:{_type} {_freq}{_ampl}{_offset}{_phase}')
       
    def settings1(self) -> list:
        """

        Returns
        -------
        tuple of settings for a specific channel in the format

        """
        
        ans = get(self.device, ':SOUR1:APPL?')
        if type(ans) == str:
            try:
                ans = ans.split(',')
                _type = str(ans[0][1:])
                _freq = float(ans[1])
                _ampl = float(ans[2])
                _offset = float(ans[3])
                _phase = float(ans[4][:-2])
                ans = [_type, _freq, _ampl, _offset, _phase]
            except Exception as ex:
                print(f'Exception happened calling settings for channel 1: {ex}')
                ans = [None, None, None, None]
        else:
            ans = [None, None, None, None]
        return ans
    
    def settings2(self) -> list:
        """

        Returns
        -------
        String of settings for a specific channel

        """
        
        ans = get(self.device, ':SOUR2:APPL?')
        if type(ans) == str:
            try:
                ans = ans.split(',')
                _type = str(ans[0][1:])
                _freq = float(ans[1])
                _ampl = float(ans[2])
                _offset = float(ans[3])
                _phase = float(ans[4][:-2])
                ans = [_type, _freq, _ampl, _offset, _phase]
            except Exception as ex:
                print(f'Exception happened calling settings for channel 1: {ex}')
                ans = [None, None, None, None]
        else:
            ans = [None, None, None, None]
        return ans
    
    def freq1(self):
        ans = self.settings1()[1]
        return ans
    
    def freq2(self):
        ans = self.settings2()[1]
        return ans
    
    def ampl1(self):
        ans = self.settings1()[2]
        return ans
    
    def ampl2(self):
        ans = self.settings2()[2]
        return ans
    
    def offset1(self):
        ans = self.settings1()[3]
        return ans
    
    def offset2(self):
        ans = self.settings2()[3]
        return ans
    
    def phas1(self):
        ans = self.settings1()[4]
        return ans
    
    def phas2(self):
        ans = self.settings2()[4]
        return ans
    
    def set_type1(self, value):
        
        settings = self.settings1()
        try:
            value = str(value)
        except ValueError:
            value = 0
        settings[0] = value
            
        self.apply_settings1(settings)
    
    def set_type2(self, value):
        
        settings = self.settings1()
        try:
            value = str(value)
        except ValueError:
            value = 0
        settings[0] = value
            
        self.apply_settings2(settings)
    
    def set_freq1(self, value):
        
        settings = self.settings1()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[1] = value
            
        self.apply_settings1(settings)
    
    def set_freq2(self, value):
        
        settings = self.settings2()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[1] = value
        
        self.apply_settings2(settings)
    
    def set_ampl1(self, value):
        
        settings = self.settings1()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[2] = value
            
        self.apply_settings1(settings)
    
    def set_ampl2(self, value):
        
        settings = self.settings2()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[2] = value
            
        self.apply_settings2(settings)
        
    def set_offset1(self, value):
        
        settings = self.settings1()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[3] = value
            
        self.apply_settings1(settings)
    
    def set_offset2(self, value):
        
        settings = self.settings2()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[3] = value
        
        self.apply_settings2(settings)
    
    def set_phas1(self, value):
        
        settings = self.settings1()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[4] = value
            
        self.apply_settings1(settings)
    
    def set_phas2(self, value):
        
        settings = self.settings2()
        try:
            value = float(value)
        except ValueError:
            value = 0
        settings[4] = value
            
        self.apply_settings2(settings)
        
    def set_outp1(self, value: int = 0):
        """

        Parameters
        ----------
        value : 0 - off, 1 - on

        Returns
        -------
        None.

        """
        self.device.write(f':OUTP1:STATE {value}')
    
    def set_outp2(self, value):
        """

        Parameters
        ----------
        value : 0 - off, 1 - on

        Returns
        -------
        None.

        """
        self.device.write(f':OUTP2:STATE {value}')
    
    def set_custom_waveform1(self, waveform: list = [0, 1, 2, 3, 4, 5, 6, 7]):
        
        voltages = np.array(waveform)

        # get length and point spacing
        npts = len(voltages)
        
        f = self.freq1()
        
        period = 1/f
        
        dt = npts/period

        # center and normalize voltages
        offset = np.mean(voltages)
        voltages -= offset
        maxv = max(voltages)
        minv = min(voltages)

        norm = max(abs(maxv), abs(minv))
        vpp = abs(maxv-minv)
        voltages = voltages / norm

        # set amp values to counteract normalization
        self.set_offset1(offset)
        self.set_amplitude1(vpp)

        # make sure data is sent in small enough groups
        npartitions = int(np.ceil(npts / self.ARB_MAX_SEND))
        volts_send = np.array_split(voltages, npartitions)

        # send data in groups
        for i in range(npartitions):

            # get data to send
            volts = volts_send[i]
            npts = len(volts)

            # convert voltages to bytes
            volts = volts * 8191.5 + 8191.5
            volts = volts.astype('<H')
            volts = volts.tobytes()

            # make header line
            nchar = len(str(npts*2))
            if i+1 < npartitions:
                flag = 'CON'
            else:
                flag = 'END'

            header = f'SOUR1:DATA:DAC16 VOLATILE,{flag},#{nchar}{npts*2}'

            # write voltages to out
            self.device.write_raw(bytes(header, 'ascii') + volts)
        
        #self.device.write(f':SOURce1:TRACe:DATA:DAC16 CODE,END,10,20,30,40,50,60,70,80,90,100,200,300,400,500,600,700,800,900,1000,1100,1200,1300,1400,1500,1600,1700,1800,1900,2000,2100,2200,2300')
    
    def set_custom_waveform2(self, waveform, memory_num=5, verify=True):
        
        self.device.write(f':SOUR2:TRAC:DATA:DAC16 VOLT,HEAD,{waveform}')

    def outp1(self):
        
        ans = get(self.device, f':OUTP1:STATE?')
        return ans

    def outp2(self):
        
        ans = get(self.device, f':OUTP2:STATE?')
        return ans
    
def main():
    device = RigolDG800()
    device.set_custom_waveform1([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    device.apply_settings1(['ARB',100.0,1.0,2.0,3.0])

if __name__ == '__main__':
    main()