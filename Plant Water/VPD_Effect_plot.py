import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 1. Read data
df = pd.read_csv('plant_data 12 outdoor & Indoor.csv')
df['full_time'] = pd.to_datetime(df['full_time'])

# 2. Calculate Effective Drying Rate
# Rate = (Current Soil - Critical Soil) / ETA
# Set critical soil moisture threshold to 0.2
df['effective_rate'] = (df['soil'] - 0.2) / df['eta']

# 3. Filter plotting timeframe (Dec 1, 10:00 - Dec 2, 04:00)
start_plot = pd.to_datetime('2025-12-01 10:00:00')
end_plot = pd.to_datetime('2025-12-02 04:00:00')
df_plot = df[(df['full_time'] >= start_plot) & (df['full_time'] <= end_plot)].copy()

# Define scenario time windows
start_A = pd.to_datetime('2025-12-01 12:00:00')
end_A = pd.to_datetime('2025-12-01 16:00:00')
start_B = pd.to_datetime('2025-12-01 22:00:00')
end_B = pd.to_datetime('2025-12-02 02:00:00')

# 4. Start plotting (3 subplots)
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12), sharex=True)

# --- Subplot 1: Environment (Temp & Hum) ---
color_temp = '#d62728' # Red
color_hum = '#1f77b4' # Blue
ax1.plot(df_plot['full_time'], df_plot['temp'], color=color_temp, label='Temperature', linewidth=2)
ax1.set_ylabel('Temperature (°C)', color=color_temp, fontweight='bold', fontsize=12)
ax1.tick_params(axis='y', labelcolor=color_temp)

ax1b = ax1.twinx()
ax1b.plot(df_plot['full_time'], df_plot['hum'], color=color_hum, label='Humidity', linewidth=2, linestyle='--')
ax1b.set_ylabel('Humidity (%)', color=color_hum, fontweight='bold', fontsize=12)
ax1b.tick_params(axis='y', labelcolor=color_hum)
ax1.set_title('A. Environmental Microclimate', fontsize=14, fontweight='bold')
ax1.grid(True, linestyle='--', alpha=0.3)

# Highlight Zones A and B
ax1.axvspan(start_A, end_A, color='green', alpha=0.1)
ax1.text(start_A + (end_A - start_A)/2, 22, "Scenario A\n(Outdoor)", ha='center', color='green', fontweight='bold')
ax1.axvspan(start_B, end_B, color='orange', alpha=0.1)
ax1.text(start_B + (end_B - start_B)/2, 22, "Scenario B\n(Indoor)", ha='center', color='orange', fontweight='bold')

# --- Subplot 2: Stress (VPD) ---
color_vpd = 'purple'
ax2.plot(df_plot['full_time'], df_plot['vpd'], color=color_vpd, linewidth=2, label='VPD')
ax2.fill_between(df_plot['full_time'], df_plot['vpd'], color=color_vpd, alpha=0.1)
ax2.set_ylabel('VPD (kPa)', color=color_vpd, fontweight='bold', fontsize=12)
ax2.tick_params(axis='y', labelcolor=color_vpd)
ax2.set_title('B. Atmospheric Demand (VPD)', fontsize=14, fontweight='bold')
ax2.grid(True, linestyle='--', alpha=0.3)
ax2.axvspan(start_A, end_A, color='green', alpha=0.1)
ax2.axvspan(start_B, end_B, color='orange', alpha=0.1)

# Annotate VPD values
mean_vpd_A = df_plot[(df_plot['full_time'] >= start_A) & (df_plot['full_time'] <= end_A)]['vpd'].mean()
mean_vpd_B = df_plot[(df_plot['full_time'] >= start_B) & (df_plot['full_time'] <= end_B)]['vpd'].mean()
ax2.text(start_A + (end_A - start_A)/2, mean_vpd_A + 0.1, f"~{mean_vpd_A:.2f} kPa", ha='center', color='purple')
ax2.text(start_B + (end_B - start_B)/2, mean_vpd_B + 0.1, f"~{mean_vpd_B:.2f} kPa", ha='center', color='purple')

# --- Subplot 3: Response (Effective Rate & ETA) ---
color_rate = 'teal'
ax3.plot(df_plot['full_time'], df_plot['effective_rate'], color=color_rate, linewidth=2, label='Algorithmic Drying Rate')
ax3.set_ylabel('Effective Drying Rate', color=color_rate, fontweight='bold', fontsize=12)
ax3.tick_params(axis='y', labelcolor=color_rate)

# Overlay ETA dashed line
ax3b = ax3.twinx()
ax3b.plot(df_plot['full_time'], df_plot['eta'], color='gray', linestyle=':', linewidth=1.5, alpha=0.7, label='Raw ETA')
ax3b.set_ylabel('Raw ETA (Hours)', color='gray', fontsize=10)
ax3b.tick_params(axis='y', labelcolor='gray')

ax3.set_title('C. System Response (Algorithmic Adjustment)', fontsize=14, fontweight='bold')
ax3.grid(True, linestyle='--', alpha=0.3)
ax3.axvspan(start_A, end_A, color='green', alpha=0.1)
ax3.axvspan(start_B, end_B, color='orange', alpha=0.1)

# Format X-axis
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax3.set_xlabel('Time of Day', fontsize=12)

plt.tight_layout()
plt.show()