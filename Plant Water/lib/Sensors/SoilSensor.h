#pragma once
#include <Arduino.h>
#include "Config.h"

class SoilSensor {
public:
  bool begin() { pinMode(CFG::PIN_SOIL_ADC, INPUT); return true; }
  
  float read();
};
