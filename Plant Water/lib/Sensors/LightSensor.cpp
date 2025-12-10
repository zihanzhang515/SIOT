#include "LightSensor.h"

int LightSensor::readRaw() {
  return analogRead(CFG::PIN_LIGHT_ADC);
}