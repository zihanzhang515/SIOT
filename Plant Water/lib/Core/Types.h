#pragma once
#include <Arduino.h>

struct Sample {
  float soil;    // 0~1
  float T;       // °C
  float RH;      // %
  float luxRaw;  // ADC value
  uint32_t ms;   // timestamp
};

struct Derived {
  float vpd_kPa;   // kPa
  float slope_h;   // Water content slope (per hour, negative value = decrease)
  float eta_h;     // Estimated time to dry (hours)
};

struct Health {
  float score;     // 0~100
};
