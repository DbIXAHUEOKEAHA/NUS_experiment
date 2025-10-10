Unisweep. Automation software for acquiring and plotting data, communication with lab equipment and sweeping parameters. Install the packages needed for the specific equipment.
To start using the software, copy the type of devices you want to use from 'devices' folder and paste it into 'resources' folder. 
Configure your devices in the main page of Unisweep in the 'Devices' menu by correlating the type and the address of the device.
Start your sweep by choosing 1/2/3-d sweeper, setting up a device, its parameter and limits of sweeping. Choose options to get and click 'Start sweep'.

A. Installation:

1. Google → Install NI-MAX
2. Google → Install NI-MAX driver 488.2
3. Google → Install Anaconda
4. Google → Install ‘GitBash’ (Click all “next”)
5. Gitbash: 

cd ‘C://’

mkdir Unisweep

cd Unisweep

git clone “https://github.com/DbIXAHUEOKEAHA/NUS_experiment”

1. In “C://Unisweep” copy&paste ‘NUS_experiment’ (make 2 copies of the same folder), Change one name to ‘github’ another one to ‘data’
2. Anaconda prompt:

pip install pyvisa-py IPy pymeasure

1. in C://Unisweep//data//devices delete .py files that do not correspons to your current setup. Example: Setup consist of 2 lockins SR860, 1 lockin SR830, 2 Keithley 2614b and opticool. Files left in ..//devices//: [Time.py](http://Time.py) sr860.py, sr830.py, keithley_series_2600b.py opticool.py
2. To install libraries for each specific device - open correspondent .py file and read imported libraries. For example to install library for opticool, open Anaconda prompt → pip install Multipyvu. Usually the package name installed through pip is the same as it appears in .py file, but in little cases its not (in each case ask google).
3. Run [main.py](http://main.py) through Spyder (or any other IDE / bash)
4. To configure devices addresses open Unisweep → Devices → Set device type (choose address / port and correspondent device type). To manually open or add devices, go to Unisweep//data//config//address_dictionary.txt and write the config in the format: {”address1”: “device1”, “address2”: “device2”}.
