
#include "SoilSensor.h"

float SoilSensor::read() {
  // Multiple reads → Median filtering
  const int N = 9;
  int buf[N];
  for (int i=0; i<N; i++) {
    buf[i] = analogRead(CFG::PIN_SOIL_ADC);
    delay(3);
  }

  // Sort to find median
  for (int i=0; i<N-1; i++)
    for (int j=i+1; j<N; j++)
      if(buf[j] < buf[i]) std::swap(buf[i], buf[j]);

  int raw = buf[N/2]; // median

  // Normalize to 0~1
  int span = max(1, CFG::SOIL_ADC_DRY - CFG::SOIL_ADC_WET);
  float norm = float(CFG::SOIL_ADC_DRY - raw) / float(span);
  norm = constrain(norm, 0.0f, 1.0f);

  // EMA smoothing
  static float ema = norm;
  ema = 0.85f * ema + 0.15f * norm;

  // Ignore large jumps (>0.3)
  if (abs(norm - ema) > 0.3f) return ema;

  return ema;
}
