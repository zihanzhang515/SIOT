#pragma once
#include <Arduino.h>

class EnvSensor {
public:
  bool begin();
  bool read(float &T, float &RH); 
};
