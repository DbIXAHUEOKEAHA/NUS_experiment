import numpy as np
import os
from scipy import interpolate
import matplotlib.pyplot as plt
plt.rcParams.update({'figure.max_open_warning': 0})
from mapper.filename_utils import unify_filename, fix_unicode
from mapper.data2map import save_map
from multiprocessing.pool import ThreadPool

class mapper2D():
    def __init__(self, parameter_to_sweep1: str, parameter_to_sweep2: str, 
                 parameters_to_read, filename_sweep: str, _from: float, _to: float, 
                 nsteps: int, walks: int, index_filename: int,
                 interpolated = True, uniform = True):
        self.slave = np.array([])
        self.master = np.array([])
        self.parameters_to_read = parameters_to_read
        self.parameter_to_sweep1 = parameter_to_sweep1
        self.parameter_to_sweep2 = parameter_to_sweep2
        self.filename_sweep = filename_sweep
        self._from = _from
        self._to = _to
        self.nsteps = nsteps
        self.walks = walks
        self.interpolated = interpolated
        self.uniform = uniform
        self.grid = np.linspace(_from, _to, nsteps + 1)
        self.cur_walk = 0
        self.index_filename = index_filename
        for parameter in self.parameters_to_read:
            self.__dict__[parameter] = np.array([])
        self.maps_to_save = []

    def append_slave(self, value):
        if not hasattr(self, f'slave{self.cur_walk}'):
            self.__dict__[f'slave{self.cur_walk}'] = np.array([value])
        else:
            self.__dict__[f'slave{self.cur_walk}'] = np.concatenate((self.__dict__[f'slave{self.cur_walk}'], [value]))
    
    def append_master(self, value):
        self.master = np.concatenate((self.master, [value]))
        
    def append_parameter(self, parameter: str, value):
        if hasattr(self, parameter):
            self.__dict__[parameter] = np.concatenate((self.__dict__[parameter], [value]))
            
    def add_sub_slave(self):
        self.cur_walk += 1
            
    def slave_done_walking(self):
        self.slave = np.array([])
        for i in range(self.cur_walk):
            self.slave = np.concatenate((self.slave, self.__dict__[f'slave{i}']))
            
    def clear_sub_slaves(self):
        for i in range(self.cur_walk):
            del self.__dict__[f'slave{i}']
        
        self.cur_walk = 0
        
    
    def concatenate_all(self):
        
        if not self.interpolated: #raw data
            
            if not hasattr(self, 'map_slave') and not hasattr(self, 'map_master'):  #first time
                print('Mapper concatenated at first time')
                self.map_slave = np.array([self.slave])
                self.map_master = np.array([np.ones_like(self.slave) * self.master[-1]])
                self.create_files()
            
            elif hasattr(self, 'map_slave') and hasattr(self, 'map_master'):
                print('Mapper concatenated')
                
                self.check_sizes()
                self.map_slave = np.vstack([self.map_slave, self.slave])
                self.map_master = np.vstack([self.map_master, np.ones_like(self.slave) * self.master[-1]])
            else:
                raise Exception(f'Map_slave status {hasattr(self, "map_slave")}, Map_master status {hasattr(self, "map_master")}')
        
            self.concatenate_parameters()
            
        else: #interpolated
            
            if not hasattr(self, 'map_slave') and not hasattr(self, 'map_master'):  #first time
                print('Mapper concatenated at first time')
                if self.uniform == True:
                    grid = []
                    for walk in range(self.walks):
                        grid = np.concatenate((grid, self.grid[::round(-2*(walk % 2 - 0.5))][round(walk % 2):]))
                    self.map_slave = np.array([grid])
                    self.map_master = np.array([np.ones_like(grid) * self.master[-1]]) 
                else:
                    self.reference_slave = []
                    for i in range(self.cur_walk):
                        self.reference_slave.append(self.__dict__[f'slave{i}'])
                    self.map_slave = np.array([self.slave])
                    self.map_master = np.array([np.ones_like(self.slave) * self.master[-1]]) 
                self.create_files()
                
            elif hasattr(self, 'map_slave') and hasattr(self, 'map_master'):
                print('Mapper concatenated')
                if self.uniform:
                    grid = []
                    for walk in range(self.walks):
                        grid = np.concatenate((grid, self.grid[::round(-2*(walk % 2 - 0.5))][round(walk % 2):]))
                    self.map_slave = np.vstack([self.map_slave, grid])
                    self.map_master = np.vstack([self.map_master, np.ones_like(grid) * self.master[-1]])
                else:
                    slave = np.concatenate(self.reference_slave)
                    self.map_slave = np.vstack([self.map_slave, slave])
                    self.map_master = np.vstack([self.map_master, np.ones_like(slave) * self.master[-1]])
        
            else:
                raise Exception(f'Map_slave status {hasattr(self, "map_slave")}, Map_master status {hasattr(self, "map_master")}')
        
            self.concatenate_parameters()
            with ThreadPool() as p:    
                p.map(save_map, self.maps_to_save)
            self.maps_to_save = []
    
    def concatenate_parameters(self):
        
        def concat(parameter):
            if not self.interpolated: #raw
                
                if not hasattr(self, f'map_{parameter}'):
                    
                    if hasattr(self, parameter):
                        self.__dict__[f'map_{parameter}'] = np.array([self.__dict__[parameter]])
                        self.append_line_to_file(parameter, self.__dict__[parameter])
                    else:
                        self.__dict__[f'map_{parameter}'] = np.array([[]])
                    
                elif hasattr(self, f'map_{parameter}'):
                    
                    if hasattr(self, parameter):
                        diff = self.__dict__[f'map_{parameter}'].shape[1] - self.__dict__[parameter].shape[0]
                        if diff < 0:
                            for i in range(abs(diff)):
                                self.__dict__[parameter] =  np.concatenate((self.__dict__[parameter], [np.nan]))
                        elif diff > 0:
                            def stack(parameter):
                                self.__dict__[f'map_{parameter}'] = np.hstack([self.__dict__[f'map_{parameter}'], np.array([np.nan * np.ones(self.__dict__[f'map_{parameter}'].shape[0])]).T])
                            for i in range(diff):
                                stack(parameter
                                      )
                        self.__dict__[f'map_{parameter}'] = np.vstack([self.__dict__[f'map_{parameter}'], self.__dict__[parameter]])
                        self.append_line_to_file(parameter, self.__dict__[parameter])
                    else:
                        self.__dict__[f'map_{parameter}'] = np.array([[]])
            
            else: #interpolated
                
                if not hasattr(self, f'map_{parameter}'):
                    if hasattr(self, parameter):
                        interpolated_parameter = self.interpolate(self.__dict__[parameter])
                        self.__dict__[f'map_{parameter}'] = np.array([interpolated_parameter])
                        self.append_line_to_file(parameter, interpolated_parameter)
                    else:
                        self.__dict__[f'map_{parameter}'] = np.array([[]])
                        
                elif hasattr(self, f'map_{parameter}'):
                    if hasattr(self, parameter):
                        interpolated_parameter = self.interpolate(self.__dict__[parameter])
                        self.__dict__[f'map_{parameter}'] = np.vstack([self.__dict__[f'map_{parameter}'], interpolated_parameter])
                        self.append_line_to_file(parameter, interpolated_parameter)
                    else:
                        self.__dict__[f'map_{parameter}'] = np.array([[]])
                        
        
        for parameter in self.parameters_to_read:
            concat(parameter)
          
    def interpolate(self, parameter):
        res = []
        shape = 0
        
        if self.uniform:
            for ind in range(self.cur_walk):
                try:
                    float(parameter[0])
                except ValueError:
                    x = self.__dict__[f'slave{ind}']
                    parameter = np.empty(x.shape[0])
                    parameter[:] = np.nan
                if ind != self.cur_walk:
                    x = self.__dict__[f'slave{ind}']
                    y = parameter[shape:shape + x.shape[0]]
                    shape += x.shape[0]
                    func = interpolate.interp1d(x, y, kind = 'nearest', fill_value="extrapolate")
                    res.append(func(self.grid[::round(-2*(ind % 2 - 0.5))][round(ind % 2):]))
                else:
                    x = self.__dict__[f'slave{ind}']
                    y = parameter[shape:]
                    func = interpolate.interp1d(x, y, kind = 'nearest', fill_value="extrapolate")
                    res.append(func(self.grid[::round(-2*(ind % 2 - 0.5))][round(ind % 2):]))
        else:
            for ind, sub in enumerate(self.reference_slave):
                try:
                    float(parameter[0])
                except ValueError:
                    x = self.__dict__[f'slave{ind}']
                    parameter = np.empty(x.shape[0])
                    parameter[:] = np.nan
                if ind != self.cur_walk:
                    x = self.__dict__[f'slave{ind}']
                    y = parameter[shape:shape + x.shape[0]]
                    shape += x.shape[0]
                    func = interpolate.interp1d(x, y, kind = 'nearest', fill_value="extrapolate")
                    res.append(func(sub))
                else:
                    x = self.__dict__[f'slave{ind}']
                    y = parameter[shape:]
                    func = interpolate.interp1d(x, y, kind = 'nearest', fill_value="extrapolate")
                    res.append(func(sub))
                
        return np.concatenate(res)
          
    def check_sizes(self):
        
        def stack(parameter):
            self.__dict__[f'map_{parameter}'] = np.hstack([self.__dict__[f'map_{parameter}'], np.array([np.nan * np.ones(self.__dict__[f'map_{parameter}'].shape[0])]).T])
        
        dif = self.slave.shape[0] - self.map_slave.shape[1]
        
        if dif > 0: #current measurment has more points than the previous:
            for i in range(dif):
                self.map_slave = np.hstack([self.map_slave, np.array([np.nan * np.ones(self.map_slave.shape[0])]).T])
                self.map_master = np.hstack([self.map_master, np.array([np.nan * np.ones(self.map_master.shape[0])]).T])
                for parameter in self.parameters_to_read:
                    stack(parameter)
                    
        if dif < 0: #current measurment has less points than the previous
            for i in range(abs(dif)):
                self.slave = np.concatenate((self.slave, [np.nan]))
                for parameter in self.parameters_to_read:
                    self.__dict__[parameter] = np.concatenate((self.__dict__[parameter], [np.nan]))
    
    def clear_slave(self):
        self.slave = np.array([])
        
    def clear_parameters(self):
        for parameter in self.parameters_to_read:
            self.__dict__[parameter] = np.array([])
            
    def append_line_to_file(self, parameter: str, value):
        
        def parameter_to_filename(parameter):
            
            parameter = parameter.replace(':', '')
            path = os.path.normpath(self.filename_sweep).split(os.path.sep)
            name = path[-1]
            try:
                name = name[:len(name) - name[::-1].index('.') - 1]
            except ValueError:
                pass
            name = unify_filename(name)
            name = name[:(len(name) - name[::-1].find('-') - 1)]
            cur_dir = os.path.join(*path[:path.index('data_files')])
            cur_dir = fix_unicode(cur_dir)
            filename = f'{self.index_filename}_{parameter}_map.csv'
            filename = os.path.join(cur_dir, '2d_maps', 'tables', f'{name}_{self.index_filename}', f'{filename}')
            filename = fix_unicode(filename)
            return filename
        
        filename = parameter_to_filename(parameter)
        line = np.concatenate(([self.master[-1]], value))
        line = ','.join(map(str, line))
        with open(filename, 'a') as file:
            try:
                file.write(f'\n{line}')
            except:
                file.close()
            finally:
                file.close()
                
        self.maps_to_save.append(tuple([filename, None, None]))
            
    def create_files(self):
        
        path = os.path.normpath(self.filename_sweep).split(os.path.sep)
        name = path[-1]
        try:
            name = name[:len(name) - name[::-1].index('.') - 1]
        except ValueError:
            pass
        name = unify_filename(name)
        name = name[:(len(name) - name[::-1].find('-') - 1)]
        cur_dir = os.path.join(*path[:path.index('data_files')])
        cur_dir = fix_unicode(cur_dir)
        to_make = os.path.join(cur_dir, '2d_maps', 'tables', f'{name}_{self.index_filename}')
        
        if not os.path.exists(to_make):
            os.makedirs(to_make)
        for parameter in self.parameters_to_read:
            slave = np.concatenate(([f'{self.parameter_to_sweep1} / {self.parameter_to_sweep2}'], self.map_slave[0, :]))
            slave = ','.join(map(str, slave))
            parameter = parameter.replace(':', '')
            filename = os.path.join(to_make, f'{self.index_filename}_{parameter}_map.csv')
            fix_unicode(filename)
            
            with open(filename, 'w') as file:
                try:
                    file.write(f'{slave}')
                except:
                    file.close()
                finally:
                    file.close()