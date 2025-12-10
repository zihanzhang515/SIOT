#include <Arduino.h>
#include "Estimation.h"
#include "Config.h"

void setup() {
  Serial.begin(9600);
  delay(500);

  Serial.println("=== ETA Prediction Model Test ===");
  Serial.println("soil_now, slope_h, T, RH, VPD, ETA(h)");
}

void loop() {

  
  // Case A: Normal decrease of 0.03/hour, high temperature, low humidity → ETA should decrease.
  {
    float s_now = 0.45;  
    float slope_h = -0.03;
    float T = 28.0;
    float RH = 35.0;
    float vpd = Estimation::vpd_kPa(T, RH);

    float eta = Estimation::etaHours(s_now, CFG::SOIL_DRY_CRIT, slope_h, vpd);

    Serial.printf("A: soil=%.2f slope=%.3f T=%.1f RH=%.1f VPD=%.2f ETA=%.2f h\n",
                  s_now, slope_h, T, RH, vpd, eta);
  }

  // Case B: Normal decrease of 0.03/hour, moderate temperature and humidity → ETA moderate.
  {
    float s_now = 0.45;
    float slope_h = -0.03;
    float T = 20.0;
    float RH = 70.0;
    float vpd = Estimation::vpd_kPa(T, RH);

    float eta = Estimation::etaHours(s_now, CFG::SOIL_DRY_CRIT, slope_h, vpd);

    Serial.printf("B: soil=%.2f slope=%.3f T=%.1f RH=%.1f VPD=%.2f ETA=%.2f h\n",
                  s_now, slope_h, T, RH, vpd, eta);
  }

  // Case C: Very slow decrease of 0.001/hour, moderate temperature and humidity → ETA should be very large (near infinity).
  {
    float s_now = 0.45;
    float slope_h = -0.001;   // 非常慢
    float T = 25.0;
    float RH = 50.0;
    float vpd = Estimation::vpd_kPa(T, RH);

    float eta = Estimation::etaHours(s_now, CFG::SOIL_DRY_CRIT, slope_h, vpd);

    Serial.printf("C: soil=%.2f slope=%.3f T=%.1f RH=%.1f VPD=%.2f ETA=%s\n",
                  s_now, slope_h, T, RH, vpd,
                  (eta == INFINITY ? "INF" : String(eta,2).c_str()));
  }

  Serial.println("-----------------------------------");
  delay(3000);
}
