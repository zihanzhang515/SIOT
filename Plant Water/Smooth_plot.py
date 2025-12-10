import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load datasets
df_raw = pd.read_csv('plant_data_export.csv')
df_smooth = pd.read_csv('plant_data 5 加了平滑系数.csv')

# --- 1. Data Preprocessing ---
# Scale raw slope by 3600 (Unit conversion: /sec -> /hr)
df_raw['slope_scaled'] = df_raw['slope'] * 3600

# Filter for Drying Phase
# Filter Raw data
df_raw_drying = df_raw[(df_raw['slope_scaled'] < -5) & (df_raw['slope_scaled'] > -100)].reset_index(drop=True)
# Filter Smoothed data
df_smooth_drying = df_smooth[(df_smooth['slopeh'] < -5) & (df_smooth['slopeh'] > -100)].reset_index(drop=True)

# --- 2. Automatically Select Best Comparison Window ---
window_size = 20

# A. Select segment with "Max Jitter" from Raw data
max_jitter = 0
best_raw_idx = 0
for i in range(len(df_raw_drying) - window_size):
    segment = df_raw_drying['slope_scaled'].iloc[i:i+window_size]
    jitter = np.sum(np.abs(np.diff(segment)))
    if jitter > max_jitter:
        max_jitter = jitter
        best_raw_idx = i

raw_segment = df_raw_drying.iloc[best_raw_idx : best_raw_idx + window_size].reset_index(drop=True)
raw_mean = raw_segment['slope_scaled'].mean()

# B. Select segment with "Closest Mean" from Smoothed data (Best Match)
best_smooth_idx = 0
min_diff = float('inf')
for i in range(len(df_smooth_drying) - window_size):
    segment = df_smooth_drying['slopeh'].iloc[i:i+window_size]
    diff = abs(segment.mean() - raw_mean)
    if diff < min_diff:
        min_diff = diff
        best_smooth_idx = i

smooth_segment = df_smooth_drying.iloc[best_smooth_idx : best_smooth_idx + window_size].reset_index(drop=True)

# --- 3. Prepare Plotting Data ---
# Generate x-axis: 0, 5, 10, ... (Interval = 5)
time_steps = np.arange(window_size) * 5

# Calculate change amount (Delta)
delta_raw = np.diff(raw_segment['slope_scaled'])
delta_smooth = np.diff(smooth_segment['slopeh'])
time_steps_delta = time_steps[1:] # Delta has one less point

# --- 4. Matplotlib Plotting ---
plt.rcParams.update({'font.family': 'sans-serif', 'font.size': 12})
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), dpi=150)

# === Subplot 1: Trend Comparison ===
color_a = '#ff7f0e' # Orange
color_b = '#1f77b4' # Blue

ax1.set_xlabel('Time (Interval = 5)', fontsize=12)
ax1.set_ylabel('Raw Signal (Slope)', color=color_a, fontsize=12, fontweight='bold')
ax1.plot(time_steps, raw_segment['slope_scaled'], color=color_a, marker='o', markersize=6, label='Line A: Raw Signal')
ax1.tick_params(axis='y', labelcolor=color_a)
ax1.grid(True, linestyle='--', alpha=0.3)

# Plot Smoothed signal on secondary y-axis
ax1b = ax1.twinx()
ax1b.set_ylabel('Smoothed Signal (Slope)', color=color_b, fontsize=12, fontweight='bold')
ax1b.plot(time_steps, smooth_segment['slopeh'], color=color_b, marker='s', markersize=6, linewidth=3, label='Line B: Smoothed Signal')
ax1b.tick_params(axis='y', labelcolor=color_b)
ax1.set_title('Comparison 1: Signal Trend (Raw vs. Smoothed)', fontsize=14, pad=15)

# Combine legends
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax1b.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=2)

# === Subplot 2: Stability Comparison (Variation) ===
ax2.set_xlabel('Time (Interval = 5)', fontsize=12)
ax2.set_ylabel('Signal Fluctuation (Change Amount)', color='black', fontsize=12, fontweight='bold')

# Plot Raw variation
ax2.plot(time_steps_delta, delta_raw, color=color_a, marker='o', linestyle='--', linewidth=2, label='Line A Variation (Raw)')
# Plot Smoothed variation
ax2.plot(time_steps_delta, delta_smooth, color=color_b, marker='s', linewidth=3, label='Line B Variation (Smoothed)')

# Add zero baseline
ax2.axhline(0, color='gray', linestyle='-', alpha=0.5, linewidth=1.5)

ax2.set_title('Comparison 2: Signal Stability (Noise Reduction)', fontsize=14)
ax2.grid(True, linestyle='--', alpha=0.3)
ax2.legend(loc='upper right')

plt.tight_layout()
plt.subplots_adjust(hspace=0.4) # Adjust subplot spacing
plt.show()