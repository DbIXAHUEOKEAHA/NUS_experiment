import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

#paste here
line_of_num ='0.9535,0.908,0.91,0.9105,0.908,0.909,0.909,0.907,0.9095,0.906,0.907,0.9055,0.905,0.9055,0.904,0.9045,0.9055,0.9035,0.902,0.902,0.903,0.9045,0.901,0.9015,0.9005,0.8995,0.899,0.8995,0.899,0.897,0.8965,0.8975,0.895,0.896,0.8955,0.8955,0.8955,0.8935,0.893,0.8935,0.893,0.8945,0.8925,0.894,0.8905,0.8905,0.8895,0.8915,0.8885,0.888,0.886,0.89,0.8895,0.8875,0.885,0.888,0.8855,0.8845,0.884,0.885,0.8835,0.8825,0.8825,0.8825,0.882,0.881,0.8815,0.882,0.88,0.88,0.879,0.8785,0.88,0.878,0.877,0.8765,0.8765,0.8755,0.876,0.8745,0.876,0.875,0.8745,0.8745,0.874,0.873,0.874,0.874,0.8735,0.8725,0.8735,0.8705,0.873,0.873,0.87,0.8705,0.869,0.8685,0.8705,0.8695'
nums = line_of_num.split(',')
nums = np.array([float(i) for i in nums])

df = pd.DataFrame(nums)
df.to_clipboard(index=False,header=False)

t = np.arange(0, nums.shape[0], step = 1, dtype = int)

plt.plot(t, nums, 'o-')
plt.plot(t, np.ones_like(nums) * nums[0]**2, '--', alpha = 0.5)
plt.legend()
plt.show()
