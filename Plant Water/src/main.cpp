#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

#include "Config.h"
#include "Types.h"

#include "SoilSensor.h"
#include "EnvSensor.h"
#include "LightSensor.h"

#include "History.h"
#include "Estimation.h"

// ==========================================
// Wifi settings
// ==========================================
const char* ssid     = "Home sweet home";      
const char* password = "zzhwzhImperial111";      
String serverIP      = "192.168.0.64";   
int serverPort       = 8050;              

// ===== Global objects =====
SoilSensor soil;
EnvSensor  env;
LightSensor light;
History    history;

uint32_t lastSample = 0;

// Wifi send control
uint32_t lastWiFiTime = 0;
// Set to 0 to send data every sample
const long wifiInterval = 0; 

// ===== Status Computation =====
const char* computeStatus(float soil, float lux, float T, float eta, size_t history_size) {
  if (!isfinite(soil) && !isfinite(T) && !isfinite(lux)) return "Unknown";

  if (history_size < CFG::MIN_POINTS_FOR_ETA) return "Calibrating";

  if (soil >= 0.80f) return "TooWet"; 
  if (soil >= 0.40f) return "OK";     

  if (eta < 0 || isinf(eta)) return "Stable"; 
  if (eta <= 6)  return "VeryDry";
  if (eta <= 12) return "Thirsty";
  
  return "OK"; 

  // Additional checks
  if (isfinite(T)) {
    if (T > T_HOT2) return "Hot";
    if (T > T_HOT)  return "Warm";
    if (T < T_COLD) return "Cold";
  }
  if (isfinite(lux)) {
    if ((int)lux < LIGHT_DARK) return "Dark";
  }
  return "OK";
}

// ===== Setup =====
void setup() {
  delay(500);
  Serial.begin(9600);
  delay(500);

  analogReadResolution(12);
  analogSetPinAttenuation(CFG::PIN_SOIL_ADC,  ADC_11db);
  analogSetPinAttenuation(CFG::PIN_LIGHT_ADC, ADC_11db);

  Serial.println();
  Serial.println("=== PlantWater IoT Boot ===");
  Serial.println("Init sensors...");

  bool ok1 = soil.begin();
  bool ok2 = env.begin();
  bool ok3 = light.begin();

  Serial.printf("SoilSensor: %s\n", ok1 ? "OK" : "FAIL");
  Serial.printf("EnvSensor (SHT31): %s\n", ok2 ? "OK" : "FAIL");
  Serial.printf("LightSensor (ADC): %s\n", ok3 ? "OK" : "FAIL");

  history.init(CFG::HISTORY_CAP);

  // ===== WiFi connection =====
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 20) { 
    delay(500);
    Serial.print(".");
    retry++;
  }
  Serial.println();
  if(WiFi.status() == WL_CONNECTED){
    Serial.print("WiFi Connected! IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi Failed! Running in Offline Mode.");
  }

  Serial.println("timestamp,temperature,humidity,light,soil,status,slope,ETA,health");
}

// ===== Loop =====
void loop() {
  uint32_t now = millis();

  // Sampling is performed according to the frequency specified in Config.h.
  if (lastSample == 0 || now - lastSample >= CFG::SAMPLE_MS) {
    lastSample = now;

    // ---- raw data ----
    Sample s{};
    s.ms   = now;
    s.soil = soil.read();

    float T = NAN, RH = NAN;
    if (env.read(T, RH)) {
      s.T = T; s.RH = RH;
    } else {
      s.T = NAN; s.RH = NAN;
    }
    s.luxRaw = light.readRaw();

    // ==== watering detection ====
    float minRecentSoil = s.soil;
    int lookBackCount = 5; 
    int limit = (history.size() < lookBackCount) ? history.size() : lookBackCount;

    for(int k=0; k < limit; k++) {
        Sample old;
        if(history.getSampleFromEnd(k, old)) {
           if(old.soil < minRecentSoil) {
               minRecentSoil = old.soil; 
           }
        }
    }

    float soilRise = s.soil - minRecentSoil;
    if (soilRise > CFG::WATERING_THRESHOLD) {
        Serial.printf(">>> WATERING DETECTED! Rise: %.3f. Resetting... <<<\n", soilRise);
        history.reset(); 
    }

    // derivation of data
    Derived d = Estimation::computeDerived(s, history);
    Health  h = Estimation::healthScore(history, d);

    // ---- status computation ----
    const char* status = computeStatus(s.soil, s.luxRaw, s.T, d.eta_h, history.size());

    // ---- store to history ----
    history.push(s, d);

    //  --- Serial output ----
    Serial.printf(
      "%lu,%.2f,%.2f,%d,%.3f,%s,%.5f,%.2f,%.0f\n",
      millis(), s.T, s.RH, (int)s.luxRaw, s.soil,
      status, d.slope_h, d.eta_h, h.score
    );

    // WiFi Transmission (Includes fixed logic)
    // Try sending as long as there is a sample.
    if (now - lastWiFiTime > wifiInterval) {
        lastWiFiTime = now; 
        
        // If the WiFi connection drops, try reconnecting; if that doesn't work, restart automatically.
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("⚠️ WiFi Lost! Reconnecting...");
            WiFi.disconnect();
            WiFi.reconnect();
            delay(3000); 
            
            if (WiFi.status() != WL_CONNECTED) {
                 Serial.println("❌ Stuck! Restarting System...");
                 ESP.restart(); 
            }
        }

        if (WiFi.status() == WL_CONNECTED) {
          HTTPClient http;
          String url = "http://" + serverIP + ":" + String(serverPort) + "/update_sensor";
          
          // Prepare data
          String strT = isfinite(s.T) ? String(s.T) : "0";
          String strH = isfinite(s.RH) ? String(s.RH) : "0";
          String strSoil = isfinite(s.soil) ? String(s.soil) : "0";
          String strLight = isfinite(s.luxRaw) ? String(s.luxRaw) : "0";
          
          
    
          String strSlope = isfinite(d.slope_h) ? String(d.slope_h, 6) : "-0.001";

          url += "?temp=" + strT;
          url += "&hum=" + strH;
          url += "&soil=" + strSoil;
          url += "&light=" + strLight;
          url += "&slope=" + strSlope; 

         
          http.setTimeout(2000); 
          
          http.begin(url);
          int httpCode = http.GET();
          
          if (httpCode > 0) {
              Serial.printf("WiFi Sent OK: %d\n", httpCode);
          } else {
              Serial.printf("WiFi Error: %d\n", httpCode);
          }
          http.end();
        }
    }
  }

  delay(5);
}