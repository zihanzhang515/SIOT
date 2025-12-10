#pragma once
#include <Arduino.h>
#include "Types.h"
#include "Config.h"
#include "History.h"

namespace Estimation {
  float vpd_kPa(float T, float RH);
  float slopePerHourWithLatest(const History& hist, const Sample& latest,
                               size_t N = CFG::SLOPE_WINDOW_POINTS);
  float etaHours(float soil_now, float soil_thr, float slope_h, float vpd);
  Derived computeDerived(const Sample& latest, const History& hist);
  inline Health healthScore(const History&, const Derived&) {
    Health h; h.score = 80.0f; return h; 
  }
}
