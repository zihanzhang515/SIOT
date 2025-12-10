import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. Load Data
df_resistive = pd.read_csv('plant_data_export.csv') # resistive 
df_capacitive = pd.read_csv('plant_data4.csv')      # capacitive

# 2. Data Preprocessing
# Resistive method takes the first 150 points
res_data = df_resistive['soil'].values[:150]
# For capacitive systems, select the 150 most stable points in the middle
cap_data = df_capacitive['soil'].iloc[50:200].values

# 3. create time axes
t_res = np.arange(len(res_data))
t_cap = np.arange(len(res_data), len(res_data) + len(cap_data))

# 4. draw plot
plt.figure(figsize=(12, 6), dpi=150)

# draw resistive (red - drift & noise)
plt.plot(t_res, res_data, color='#e74c3c', label='Resistive Sensor (Drift & Noise)', linewidth=1.5)

# draw capacitive (green - stable/new)
plt.plot(t_cap, cap_data, color='#2ecc71', label='Capacitive Sensor (Stable)', linewidth=2)

# add vertical line to indicate sensor swap
plt.axvline(x=len(res_data), color='#34495e', linestyle='--', linewidth=2)
plt.text(len(res_data), max(res_data.max(), cap_data.max()) * 0.95, 
         '  Sensor Swapped\n  (Hardware Iteration)', 
         ha='left', va='top', fontsize=12, fontweight='bold', color='#2c3e50')

# plot formatting
plt.title('Signal Stability Comparison: Resistive vs. Capacitive', fontsize=14, fontweight='bold')
plt.xlabel('Sampling Points', fontsize=12)
plt.ylabel('Soil Moisture (Normalized)', fontsize=12)
plt.legend(loc='lower right')
plt.grid(True, linestyle=':', alpha=0.6)

# save and show
plt.tight_layout()
plt.savefig('sensor_comparison_export.png')
plt.show()