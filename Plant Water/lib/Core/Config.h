#pragma once
#include <Arduino.h>
// ======== Plant Thresholds ========

// Temperature (°C)
constexpr float T_HOT  = 30.0f;
constexpr float T_HOT2 = 32.0f;
constexpr float T_COLD = 15.0f;

// air humidity (%)
constexpr float RH_LOW  = 35.0f;
constexpr float RH_HIGH = 80.0f;

// light (ADC value)
constexpr int LIGHT_DARK = 300;
constexpr int LIGHT_LOW  = 800;

// soil moisture (0~1)
constexpr float SOIL_VERY_DRY = 0.25f;
constexpr float SOIL_DRY      = 0.45f;
constexpr float SOIL_TOO_WET  = 0.95f;


namespace CFG {
  // sampling interval & history capacity
  constexpr uint32_t SAMPLE_MS   = 300000;
  constexpr size_t   HISTORY_CAP = 600;              // 24h @10min

   // dry edge for ETA calculation (0~1)
  constexpr float SOIL_DRY_CRIT = 0.35f;   
    // A watering event is considered to have occurred if the humidity rises by more than 0.15% (15%) between two sampling periods
  constexpr float WATERING_THRESHOLD = 0.15f;


  // soil moisture (analog)
  constexpr int PIN_SOIL_ADC = 6;   
  constexpr int SOIL_ADC_DRY = 3400; // dry soil ADC
  constexpr int SOIL_ADC_WET = 2000; // wet soil ADC

  // light (analog)
  constexpr int PIN_LIGHT_ADC = 2; 

  // I2C（SHT3x）
  constexpr int I2C_SDA = 8;        //  GPIO8
  constexpr int I2C_SCL = 9;        //  GPIO9
  constexpr uint8_t I2C_ADDR_SHT = 0x44;

  // soil moisture threshold for watering detection
  constexpr float SOIL_THRESHOLD = 0.25f;

  // number of points used to calculate slope
  constexpr size_t SLOPE_WINDOW_POINTS = 12; // 6 hours
  // ETA will only start displaying after at least this many points have been saved
  constexpr size_t MIN_POINTS_FOR_ETA = 6; 
}
