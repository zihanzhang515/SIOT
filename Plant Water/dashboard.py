import dash
from dash import html, dcc, dash_table, Input, Output, State, callback_context
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import serial
import threading
import time
from collections import deque
import statistics
import requests
import random
import math
from flask import request

# ==========================================
# 1. Core Configuration
# ==========================================
SERIAL_PORT = "COM3"   # Please confirm port
BAUD_RATE = 9600
SERVER_PORT = 8050 

# 🔑 Telegram Configuration
TELEGRAM_TOKEN = "7507833046:AAFWv9bFPnWoaz-mSOjJ4142itB8I37NRXQ"
TELEGRAM_CHAT_ID = "8414366426"

# Global variables
data_rows = []
event_records = []
slope_buffer = deque(maxlen=12)
ser = None

# Status tracking
last_health_reasons = set()
last_message_time = datetime.min 
last_status = "Init"
last_smart_msg = "Init"

# Connection status monitoring
last_serial_update = datetime.min 
last_wifi_update = datetime.min

# Slope calculation auxiliary variables
prev_soil_val = None
prev_calc_time = None

# Pre-fill data
data_rows.append({
    "timestamp": datetime.now().strftime("%H:%M:%S"),
    "full_time": datetime.now(),
    "temp": 0, "hum": 0, "light": 0, "soil": 0,
    "status": "Waiting...", 
    "vpd": 0.0,      
    "slopeh": 0.0,   
    "eta": -1, "health": 0,
    "smart_msg": "System Initializing...", "mood_state": "Happy"
})

# ==========================================
# 2. Helper Functions
# ==========================================

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    
    def _send():
        try:
            print(f"📤 [Telegram] Sending: {message}")
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                print(f"✅ [Telegram] Success!")
            else:
                print(f"❌ [Telegram] Failed: {r.text}")
        except Exception as e:
            print(f"❌ [Telegram Error] {e}")
    
    threading.Thread(target=_send).start()

def calculate_python_slope(current_soil, current_time):
    global prev_soil_val, prev_calc_time
    if prev_soil_val is None or prev_calc_time is None:
        prev_soil_val = current_soil; prev_calc_time = current_time
        return 0.0
    dt_hours = (current_time - prev_calc_time).total_seconds() / 3600.0
    if dt_hours < 0.0001: return 0.0
    raw_slope = (current_soil - prev_soil_val) / dt_hours
    prev_soil_val = current_soil; prev_calc_time = current_time
    return raw_slope

def calculate_vpd(temp, hum):
    if temp == 0 or hum == 0: return 0
    try:
        es = 0.6108 * math.exp((17.27 * temp) / (temp + 237.3))
        return round(es * (1 - (hum / 100.0)), 3)
    except:
        return 0

def get_smart_advice(soil, light, status, eta, temp):
    current_hour = datetime.now().hour
    is_night = light < 100 or (current_hour >= 22 or current_hour < 7)
    
    # 🔥 For testing: Alarm directly if temp > 30
    if temp > 30: 
        return f"🔥 Heat Wave! Temp is {temp:.1f}°C", "Critical"

    # 🔥 For testing: Trigger thirsty alarm easier (originally 0.20)
    if soil < 0.30: 
        return "CRITICAL: Water NOW! 🩸", "Critical"
    
    if soil < 0.40 or (eta > 0 and eta < 24):
        if is_night: return "Wait until morning 🌙", "Sleepy"
        else: return "Time to water! 💧", "Thirsty"
        
    if soil > 0.90: return "Fully Hydrated 🌊", "Happy"
    if is_night: return "Plantie is sleeping 💤", "Sleepy"
    return "Plantie is growing 🌱", "Happy"

def calculate_health_detailed(soil, temp, hum, light):
    # Safety checks
    if math.isnan(temp): temp = 0
    if math.isnan(hum): hum = 0
    if math.isnan(light): light = 0

    reasons = [] # 🚀 FIX: Initialize list to store reasons

    # Soil scoring
    if 0.45 <= soil <= 0.65: 
        soil_score = 100
    elif soil < 0.20: 
        soil_score = 10
        reasons.append("Critical Dry")
    elif soil < 0.35: 
        soil_score = 40
        reasons.append("Soil Dry")
    elif soil < 0.45: 
        soil_score = 70
        reasons.append("Soil Low")
    elif soil > 0.90: 
        soil_score = 50
        reasons.append("Too Wet")
    else: 
        soil_score = 80

    # Temperature scoring
    if 22 <= temp <= 25: 
        temp_score = 100
    else:
        diff = abs(temp - 23.5)
        temp_score = max(20, 100 - diff * 12) 
        
        # 🚀 FIX: Explicitly add Temperature Warnings
        if temp > 30:
            reasons.append(f"High Temp ({temp:.1f}°C)")
        elif temp < 15:
            reasons.append(f"Low Temp ({temp:.1f}°C)")

    # Light scoring
    hour = datetime.now().hour
    is_day = 8 <= hour <= 18
    if is_day:
        if light < 300: 
            light_score = 50
            reasons.append("Low Light")
        elif light > 3000: 
            light_score = 60
        else: 
            light_score = 100
    else:
        light_score = 100 if light < 50 else 60

    total = (soil_score * 0.5 + temp_score * 0.3 + light_score * 0.2)
    jitter = random.uniform(-2, 2)
    total = max(0, min(100, total + jitter))

    # 🚀 FIX: Return 'reasons' list instead of empty []
    return int(total), soil_score, int(temp_score), light_score, reasons

# ==========================================
# 3. App Initialization
# ==========================================
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Plant Monitor IoT"
server = app.server

@server.route('/update_sensor', methods=['GET'])
def update_sensor_data():
    global data_rows, event_records, slope_buffer, last_health_reasons, last_message_time, last_status, last_wifi_update

    try:
        def safe_float(val):
            try: return 0 if math.isnan(float(val)) else float(val)
            except: return 0

        t_val = safe_float(request.args.get('temp', 0))
        h_val = safe_float(request.args.get('hum', 0))
        s_val = safe_float(request.args.get('soil', 0))
        l_val = safe_float(request.args.get('light', 0))
        
        last_wifi_update = datetime.now()
        now = datetime.now()

        if s_val < 0.35: status = "Thirsty"
        elif s_val > 0.85: status = "Too Wet"
        else: status = "OK"
        
        vpd_val = calculate_vpd(t_val, h_val)
        raw_slope = calculate_python_slope(s_val, now)
        slope_buffer.append(raw_slope)
        avg_slope = statistics.mean(slope_buffer) if len(slope_buffer) > 0 else 0
        
        dry_factor = 1.0 + (vpd_val * 0.2)
        if avg_slope < -0.0005: 
            raw_eta = (s_val - 0.25) / abs(avg_slope)
            smooth_eta = raw_eta / dry_factor
        else: 
            smooth_eta = -1

        # Pass t_val (temperature) for judgment
        smart_msg, mood_state = get_smart_advice(s_val, l_val, status, smooth_eta, t_val)
        h_total, h_s, h_e, h_l, current_reasons = calculate_health_detailed(s_val, t_val, h_val, l_val)

        # 🚀 LOGIC FIX: Log updates when reasons change
        current_reasons_set = set(current_reasons)
        if current_reasons_set != last_health_reasons:
            if len(current_reasons) > 0:
                # Log new issues
                new_issues = current_reasons_set - last_health_reasons
                # If it's a completely new set (e.g. from perfect to bad), log all
                if not new_issues and len(current_reasons) > 0:
                     new_issues = current_reasons_set

                for issue in new_issues:
                     event_records.insert(0, {"time": now.strftime("%H:%M"), "msg": f"⚠️ {issue}", "color": "#FF4B4B"})
            elif h_total > 90:
                event_records.insert(0, {"time": now.strftime("%H:%M"), "msg": "✅ Restored", "color": "#00D188"})
            last_health_reasons = current_reasons_set

        # Telegram Trigger
        time_since_last_msg = (datetime.now() - last_message_time).total_seconds()
        if mood_state == "Critical":
            if time_since_last_msg > 30: 
                send_telegram_message(f"🚨 ALERT (WiFi): {smart_msg}")
                last_message_time = datetime.now()
            else:
                print(f"⏳ [Telegram] Cooling down... ({int(30-time_since_last_msg)}s)")

        if status != last_status: last_status = status

        row = {
            "timestamp": now.strftime("%H:%M:%S"), "full_time": now,
            "temp": t_val, "hum": h_val, "light": l_val, "soil": s_val,
            "status": status, "slopeh": avg_slope, "vpd": vpd_val, "eta": smooth_eta, 
            "health": h_total, "h_soil": h_s, "h_temp": h_e, "h_light": h_l, 
            "reasons": ", ".join(current_reasons), "smart_msg": smart_msg, "mood_state": mood_state
        }
        data_rows.append(row)
        if len(data_rows) > 8000: data_rows.pop(0)
        print(f"📡 [WiFi] T:{t_val} S:{s_val} | Msg: {smart_msg}")
        return "OK"

    except Exception as e:
        print(f"❌ [WiFi Error] {e}")
        return "Error", 400

# ==========================================
# 4. Serial Thread
# ==========================================
def read_serial_thread():
    global ser, data_rows, event_records, slope_buffer, last_health_reasons, last_message_time, last_status, last_serial_update
    print(f"[System] Attempting to connect to serial {SERIAL_PORT}...")

    while True:
        try:
            if ser is None or not ser.is_open:
                try:
                    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                    print(f"✅ [System] Serial Connected Success on {SERIAL_PORT}")
                    ser.reset_input_buffer()
                except Exception as e:
                    time.sleep(2); continue

            if ser.in_waiting:
                try: line = ser.readline().decode("utf-8", errors="replace").strip()
                except: continue
                if not line: continue
                
                parts = line.split(",")
                if len(parts) != 9: continue
                
                last_serial_update = datetime.now()
                now = datetime.now()
                _, T_str, RH_str, light_str, soil_str, status, _, _, _ = parts

                try:
                    s_val = float(soil_str) if soil_str != 'nan' else 0
                    l_val = int(float(light_str)) if light_str != 'nan' else 0
                    t_val = float(T_str) if T_str != 'nan' else 0
                    h_val = float(RH_str) if RH_str != 'nan' else 0
                except ValueError: continue

                vpd_val = calculate_vpd(t_val, h_val)
                raw_slope = calculate_python_slope(s_val, now)
                slope_buffer.append(raw_slope)
                avg_slope = statistics.mean(slope_buffer) if len(slope_buffer) > 0 else 0
                
                dry_factor = 1.0 + (vpd_val * 0.2)
                if avg_slope < -0.0005: 
                    raw_eta = (s_val - 0.25) / abs(avg_slope)
                    smooth_eta = raw_eta / dry_factor
                else: smooth_eta = -1

                # Pass t_val (temperature)
                smart_msg, mood_state = get_smart_advice(s_val, l_val, status, smooth_eta, t_val)
                h_total, h_s, h_e, h_l, current_reasons = calculate_health_detailed(s_val, t_val, h_val, l_val)

                # 🚀 LOGIC FIX: Log updates
                current_reasons_set = set(current_reasons)
                if current_reasons_set != last_health_reasons:
                    if len(current_reasons) > 0:
                        new_issues = current_reasons_set - last_health_reasons
                        if not new_issues and len(current_reasons) > 0: new_issues = current_reasons_set
                        for issue in new_issues: event_records.insert(0, {"time": now.strftime("%H:%M"), "msg": f"⚠️ {issue}", "color": "#FF4B4B"})
                    elif h_total > 90:
                        event_records.insert(0, {"time": now.strftime("%H:%M"), "msg": "✅ Restored", "color": "#00D188"})
                    last_health_reasons = current_reasons_set

                # Telegram Trigger
                time_since_last_msg = (datetime.now() - last_message_time).total_seconds()
                if mood_state == "Critical":
                    if time_since_last_msg > 30:
                        send_telegram_message(f"🚨 ALERT (USB): {smart_msg}")
                        last_message_time = datetime.now()
                    else:
                        print(f"⏳ [Telegram] Cooling down... ({int(30-time_since_last_msg)}s)")

                if status != last_status: last_status = status

                row = {
                    "timestamp": now.strftime("%H:%M:%S"), "full_time": now,
                    "temp": t_val, "hum": h_val, "light": l_val, "soil": s_val,
                    "status": status, "slopeh": avg_slope, "vpd": vpd_val, "eta": smooth_eta, 
                    "health": h_total, "h_soil": h_s, "h_temp": h_e, "h_light": h_l,
                    "reasons": ", ".join(current_reasons), "smart_msg": smart_msg, "mood_state": mood_state
                }
                data_rows.append(row)
                if len(data_rows) > 8000: data_rows.pop(0)
                print(f"🔌 [Serial] T:{t_val} S:{s_val} | Msg: {smart_msg}")

        except Exception as e:
            print(f"[Serial Error] {e}"); time.sleep(1)

# ==========================================
# 5. UI Layout
# ==========================================
COLORS = {"bg_gradient": "radial-gradient(circle at 50% 0%, #1e1e24 0%, #0a0a0f 100%)", "card": "rgba(28, 28, 35, 0.7)", "card_border": "rgba(255,255,255,0.08)", "text": "#FFFFFF", "text_dim": "#888899", "accent": "#6366f1", "chart_fill": "rgba(99, 102, 241, 0.2)", "red_line": "#FF4B4B", "green": "#00d188", "yellow": "#f59e0b"}
CARD_STYLE = {"backgroundColor": COLORS["card"], "borderRadius": "24px", "padding": "24px", "border": f"1px solid {COLORS['card_border']}", "boxShadow": "0 15px 40px rgba(0,0,0,0.4)", "backdropFilter": "blur(15px)", "display": "flex", "flexDirection": "column", "position": "relative", "overflow": "hidden"}
def apply_chart_style(fig): fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False)); return fig

dashboard_layout = html.Div(style={"display": "grid", "gridTemplateColumns": "2fr 1fr 1fr", "gap": "25px", "maxWidth": "1800px", "margin": "0 auto", "alignItems": "start"}, children=[
    html.Div(style={"display": "flex", "flexDirection": "column", "gap": "25px"}, children=[
        html.Div(style={**CARD_STYLE, "padding": "15px", "flexDirection": "row", "alignItems": "center", "justifyContent": "space-between", "height": "auto"}, children=[html.Div("🔌 Connection Mode:", style={"color": COLORS["text_dim"], "fontSize": "12px"}), html.Div(id="conn-status-display", children="Waiting...", style={"fontWeight": "bold", "color": COLORS["accent"], "fontSize": "14px"})]),
        html.Div(style={"display": "grid", "gridTemplateColumns": "280px 1fr", "gap": "25px", "height": "300px"}, children=[
            html.Div(style={**CARD_STYLE, "padding": "0", "backgroundImage": "url('https://images.unsplash.com/photo-1485955900006-10f4d324d411?q=80&w=600')", "backgroundSize": "cover", "backgroundPosition": "center"}),
            html.Div(style={"display": "flex", "flexDirection": "column", "gap": "20px"}, children=[
                html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px", "flex": "1"}, children=[
                    html.Div(style={**CARD_STYLE, "justifyContent":"center", "alignItems":"center"}, children=[html.Div("Temperature", style={"fontSize":"12px", "color":COLORS["text_dim"]}), html.Div(id="val-temp", children="--", style={"fontSize":"32px", "fontWeight":"bold"})]),
                    html.Div(style={**CARD_STYLE, "justifyContent":"center", "alignItems":"center"}, children=[html.Div("Humidity", style={"fontSize":"12px", "color":COLORS["text_dim"]}), html.Div(id="val-hum", children="--", style={"fontSize":"32px", "fontWeight":"bold"})])
                ]),
                html.Div(style={**CARD_STYLE, "flex": "1.5"}, children=[html.Div([html.Span("Light Intensity"), html.Span(id="val-light", style={"float":"right", "fontWeight":"bold", "color": "#f59e0b"})], style={"fontSize":"12px", "color":COLORS["text_dim"], "marginBottom":"5px"}), dcc.Graph(id="light-graph", config={'displayModeBar': False}, style={"flex": "1"})])
            ])
        ]),
        html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-end", "padding": "0 10px"}, children=[html.Div([html.Div("HOURS", style={"fontSize":"10px", "color":COLORS["text_dim"]}), html.Div(id="eta-h", children="--", style={"fontSize":"64px", "fontWeight":"800", "lineHeight":"0.8"})]), html.Div([html.Div("MINUTES", style={"fontSize":"10px", "color":COLORS["text_dim"]}), html.Div(id="eta-m", children="--", style={"fontSize":"64px", "fontWeight":"800", "lineHeight":"0.8"})]), html.Div([html.Div("TO WATER", style={"fontSize":"10px", "color":COLORS["text_dim"], "textAlign":"right"}), html.Div("THE PLANTIE", style={"fontSize":"12px", "fontWeight":"bold", "textAlign":"right"})], style={"marginBottom": "8px"})]),
        html.Div(style={**CARD_STYLE, "height": "400px"}, children=[html.Div([html.Span("Soil Moisture Trend", style={"fontWeight":"bold", "fontSize":"16px"}), html.Div([html.Button("6H", id="btn-6h", n_clicks=0, style={"fontSize":"11px", "padding":"6px 12px", "borderRadius":"8px", "marginRight":"6px", "cursor":"pointer"}), html.Button("12H", id="btn-12h", n_clicks=0, style={"fontSize":"11px", "padding":"6px 12px", "borderRadius":"8px", "marginRight":"6px", "cursor":"pointer"}), html.Button("24H", id="btn-24h", n_clicks=0, style={"fontSize":"11px", "padding":"6px 12px", "borderRadius":"8px", "cursor":"pointer"})])], style={"display":"flex", "justifyContent":"space-between", "marginBottom":"20px", "alignItems":"center"}), dcc.Graph(id="soil-graph", config={'displayModeBar': False}, style={"flex": "1"})])
    ]),
    html.Div(style={"display": "flex", "flexDirection": "column", "gap": "20px"}, children=[
        html.Div(id="cal-widget", style={**CARD_STYLE, "height": "100px", "flexDirection":"row", "justifyContent":"space-around", "alignItems":"center", "padding":"0 10px"}),
        html.Div(style={**CARD_STYLE, "flex": "1", "minHeight": "300px", "justifyContent":"center", "alignItems":"center"}, children=[dcc.Graph(id="health-graph", config={'displayModeBar': False}, style={"height": "100%", "width": "100%"}), html.Div([html.Div(id="health-val", children="--", style={"fontSize":"56px", "fontWeight":"bold", "textAlign":"center"}), html.Div("Health Score", style={"fontSize":"12px", "color":COLORS["text_dim"], "textAlign":"center"})], style={"position":"absolute", "pointerEvents":"none"})])
    ]),
    html.Div(style={"display": "flex", "flexDirection": "column", "gap": "20px"}, children=[
        html.Div(style={**CARD_STYLE, "height": "340px", "justifyContent":"center", "alignItems":"center", "background":"linear-gradient(180deg, #1C1D26 0%, #15161E 100%)"}, children=[html.Div("Plant Mood", style={"position":"absolute", "top":"20px", "left":"20px", "fontSize":"14px", "color":COLORS["text_dim"]}), html.Div(id="mood-emoji", style={"fontSize": "80px", "marginBottom": "20px"}), html.Div(id="mood-text", children='"Waiting..."', style={"color":COLORS["text_dim"], "fontStyle":"italic", "textAlign":"center", "padding":"0 10px"})]),
        html.Div(style={**CARD_STYLE, "flex": "1", "minHeight": "300px"}, children=[html.Div("Event Log", style={"fontSize":"14px", "fontWeight":"bold", "marginBottom":"15px"}), html.Div(id="log-list", style={"overflowY":"auto", "flex":"1"})])
    ])
])

table_layout = html.Div(style={"padding": "40px", "maxWidth": "1600px", "margin": "0 auto"}, children=[
    html.H3("Raw Data Logs", style={"color": "white"}),
    html.Button("Download CSV", id="btn-download", style={"marginBottom": "10px", "padding": "10px", "background": COLORS["accent"], "color": "white", "border": "none", "borderRadius": "5px", "cursor": "pointer"}),
    dcc.Download(id="download-dataframe-csv"),
    dash_table.DataTable(id='raw-data-table', columns=[{"name": i, "id": i} for i in ["timestamp","status","soil","temp","hum","vpd","light","health","eta","smart_msg"]], data=[], style_header={'backgroundColor': '#2c2d3e','color':'white','border':'none'}, style_data={'backgroundColor':'#1e1e26','color':'#ccc','border':'1px solid #333'}, page_size=20)
])

app.layout = html.Div(style={"background": COLORS["bg_gradient"], "minHeight": "100vh", "fontFamily": "Inter, sans-serif", "color": COLORS["text"]}, children=[
    dcc.Interval(id="interval-fast", interval=2000, n_intervals=0),
    dcc.Tabs(colors={"border": "#333", "primary": COLORS["accent"], "background": "transparent"}, children=[
        dcc.Tab(label="DASHBOARD", children=dashboard_layout, style={'padding':'15px', 'backgroundColor':'rgba(0,0,0,0)', 'color':'#888'}, selected_style={'padding':'15px', 'backgroundColor':'rgba(0,0,0,0)', 'color':'white', 'borderTop':f'3px solid {COLORS["accent"]}'}),
        dcc.Tab(label="DATA LOGS", children=table_layout, style={'padding':'15px', 'backgroundColor':'rgba(0,0,0,0)', 'color':'#888'}, selected_style={'padding':'15px', 'backgroundColor':'rgba(0,0,0,0)', 'color':'white', 'borderTop':f'3px solid {COLORS["accent"]}'})
    ])
])

@app.callback(
    [Output("val-temp", "children"), Output("val-hum", "children"), Output("val-light", "children"),
     Output("light-graph", "figure"), Output("soil-graph", "figure"), Output("health-graph", "figure"), 
     Output("eta-h", "children"), Output("eta-m", "children"),
     Output("health-val", "children"), Output("mood-text", "children"), Output("mood-emoji", "children"),
     Output("log-list", "children"), Output("cal-widget", "children"), Output("raw-data-table", "data"),
     Output("btn-6h", "style"), Output("btn-12h", "style"), Output("btn-24h", "style"), Output("conn-status-display", "children")], 
    [Input("interval-fast", "n_intervals"), Input("btn-6h", "n_clicks"), Input("btn-12h", "n_clicks"), Input("btn-24h", "n_clicks")]
)
def update_view(n, btn6, btn12, btn24):
    base = {"fontSize":"11px","padding":"6px 12px","background":"transparent","border":"1px solid #555","color":"white","borderRadius":"8px","marginRight":"6px","cursor":"pointer"}
    active = {**base, "background": COLORS["accent"], "border": "none"}
    s6, s12, s24 = base.copy(), base.copy(), active.copy()
    win_hrs = 24
    
    ctx = callback_context
    if ctx.triggered:
        btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if btn_id == "btn-6h": win_hrs = 6; s6=active; s12=base; s24=base
        elif btn_id == "btn-12h": win_hrs = 12; s6=base; s12=active; s24=base
        elif btn_id == "btn-24h": win_hrs = 24; s6=base; s12=base; s24=active

    if len(data_rows) <= 1:
        e = apply_chart_style(go.Figure())
        return "--", "--", "--", e, e, e, "--", "--", "--", "Waiting...", "⏳", [], [], [], s6, s12, s24, "Waiting..."

    latest = data_rows[-1]
    df = pd.DataFrame(data_rows)
    now = datetime.now()
    
    timeout_limit = 310
    if (now - last_serial_update).total_seconds() < timeout_limit:
        seconds_ago = int((now - last_serial_update).total_seconds())
        display_mode = f"USB Active (Last: {seconds_ago}s ago)"
    elif (now - last_wifi_update).total_seconds() < timeout_limit:
        seconds_ago = int((now - last_wifi_update).total_seconds())
        display_mode = f"WiFi Active (Last: {seconds_ago}s ago)"
    else: display_mode = "Waiting for Data..."

    fig_light = apply_chart_style(go.Figure(go.Scatter(x=df.index[-30:], y=df['light'][-30:], fill='tozeroy', line=dict(color="#F59E0B", width=2), fillcolor="rgba(245,158,11,0.1)")))
    fig_light.update_layout(margin=dict(l=0,r=0,t=10,b=20), xaxis=dict(visible=False), yaxis=dict(visible=False))

    cutoff = df['full_time'].iloc[-1] - timedelta(hours=win_hrs)
    df_soil = df[df['full_time'] >= cutoff]
    if df_soil.empty: df_soil = df
    fig_soil = go.Figure()
    fig_soil.add_trace(go.Scatter(x=df_soil['full_time'], y=df_soil['soil'], fill='tozeroy', mode='lines', line=dict(color=COLORS["accent"], width=3), fillcolor=COLORS["chart_fill"]))
    fig_soil.add_trace(go.Scatter(x=[df_soil['full_time'].min(), df_soil['full_time'].max()], y=[0.35, 0.35], mode='lines', line=dict(color=COLORS["red_line"], width=2, dash='dash'), name='Dry'))
    fig_soil = apply_chart_style(fig_soil)
    fig_soil.update_layout(margin=dict(l=30, r=10, t=10, b=30), xaxis=dict(visible=True, showgrid=False, color="#666", tickformat="%H:%M"), yaxis=dict(visible=True, gridcolor='rgba(255,255,255,0.05)', range=[0, 1.05]), showlegend=False)

    h = int(latest.get('health', 0))
    gauge_color = COLORS["green"]
    if h < 60: gauge_color = COLORS["yellow"]
    if h < 40: gauge_color = COLORS["red_line"]
    fig_health = apply_chart_style(go.Figure(go.Pie(values=[h, 100-h], hole=0.9, sort=False, marker_colors=[gauge_color, '#252630'], textinfo='none', hoverinfo='none')))
    fig_health.update_layout(showlegend=False)

    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    cal = []
    for i, d in enumerate(days):
        is_today = (i == datetime.now().weekday())
        s = {"textAlign":"center", "padding":"5px", "borderRadius":"8px", "minWidth": "30px"}
        if is_today: s.update({"background":COLORS["accent"], "color":"white", "boxShadow":f"0 4px 10px {COLORS['accent']}66"})
        else: s.update({"color":"#666"})
        cal.append(html.Div(style=s, children=[html.Div(d, style={"fontSize":"8px"}), html.Div(str((datetime.now()-timedelta(days=datetime.now().weekday()-i)).day), style={"fontSize":"12px", "fontWeight":"bold"})]))

    logs = []
    for ev in event_records[:5]:
        color = ev.get("color", COLORS['accent'])
        logs.append(html.Div(style={"borderLeft": f"3px solid {color}", "paddingLeft": "10px", "marginBottom": "10px"}, children=[html.Div(ev["msg"], style={"fontWeight":"bold", "fontSize":"13px"}), html.Div(ev["time"], style={"fontSize":"10px", "color": COLORS["text_dim"]})]))

    eta = latest['eta']
    mood_emoji = "😊"; ms = latest.get('mood_state', 'Happy')
    if ms == "Thirsty": mood_emoji = "😰"
    elif ms == "Critical": mood_emoji = "🥵"
    elif ms == "Sleepy": mood_emoji = "😴"

    if eta != -1 and eta != float('inf') and eta < 240 and eta > 0: eta_h, eta_m = f"{int(eta):02d}", f"{int((eta%1)*60):02d}"
    else: eta_h, eta_m = "--", "--"

    return f"{latest['temp']:.1f}°", f"{latest['hum']:.0f}%", f"{latest['light']} Lx", fig_light, fig_soil, fig_health, eta_h, eta_m, f"{h}", f'"{latest.get("smart_msg", "")}"', mood_emoji, logs, cal, df.sort_values("timestamp", ascending=False).to_dict('records'), s6, s12, s24, display_mode

@app.callback(Output("download-dataframe-csv", "data"), Input("btn-download", "n_clicks"), prevent_initial_call=True)
def download(n): return dcc.send_data_frame(pd.DataFrame(data_rows).to_csv, "plant_data.csv")

if __name__ == "__main__":
    t = threading.Thread(target=read_serial_thread)
    t.daemon = True; t.start()
    print("[System] Background Serial Thread Started ✅")
    print(f"[System] Web Server Starting on port {SERVER_PORT}...")
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=True, use_reloader=False)