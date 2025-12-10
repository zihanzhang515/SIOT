#include "EnvSensor.h"
#include "Config.h"
#include <Wire.h>
#include <Adafruit_SHT31.h>

static Adafruit_SHT31 sht;

bool EnvSensor::begin() {
  Wire.begin(CFG::I2C_SDA, CFG::I2C_SCL);
  return sht.begin(CFG::I2C_ADDR_SHT);
}

bool EnvSensor::read(float &T, float &RH) {
  float t = sht.readTemperature();
  float h = sht.readHumidity();
  if (!isnan(t) && !isnan(h)) { T=t; RH=h; return true; }
  return false;
}
