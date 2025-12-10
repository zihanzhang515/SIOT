#pragma once
#include <Arduino.h>
#include "Config.h"

class LightSensor {
public:
  bool begin() { pinMode(CFG::PIN_LIGHT_ADC, INPUT); return true; }
 
  int readRaw();
};
