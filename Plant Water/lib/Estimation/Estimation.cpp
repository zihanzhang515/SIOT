#include "Estimation.h"
#include <math.h>

float Estimation::vpd_kPa(float T, float RH){
  if (isnan(T) || isnan(RH)) return NAN;
  float es = 0.6108f * expf(17.27f * T / (T + 237.3f)); // kPa
  float ea = es * (RH / 100.0f);
  float v  = es - ea;
  return v > 0 ? v : 0.0f;
}

float Estimation::slopePerHourWithLatest(const History& hist, const Sample& latest, size_t N)
{
    size_t count = hist.size();

    // 1. At the very beginning, with only 0 or 1 point, it's impossible to calculate the slope.
    if (count < 2) return 0.0f;

    // 2. Adaptive Strategy:
    // If there are not enough historical data points (N) (e.g., at startup), use all historical data (count).
    // If there are enough historical data points, use only the most recent N.
    size_t effective_N = (count < N) ? count : N;

    Sample old;
    // Take the oldest point (index is effective_N - 1)
    if (!hist.getSampleFromEnd(effective_N - 1, old)) return 0.0f;

    // 3. Calculate time difference in hours
    float dt_h = (latest.ms - old.ms) / 3600000.0f;
    
    // Avoid division by zero
    if (dt_h < 0.0001f) return 0.0f;

    // 4. Calculate soil moisture difference
    float ds = latest.soil - old.soil;

    // 5. Slope per hour
    return ds / dt_h; 
}

float Estimation::etaHours(float soil_now, float soil_dry,
                           float slope_h, float vpd)
{
    // 1. If the slope is positive (due to increased humidity/temperature drift), return a "Stable" signal (-1).
    if (slope_h > 0) return -1.0f;

    // 2. If the slope is extremely small, consider it stable and return infinity.
    if (fabsf(slope_h) < 0.001f) return INFINITY;

    // 3. If the current soil moisture is already below the dry threshold, return 0.
    if (soil_now <= soil_dry)
        return 0.0f;

    // Calculate the estimated time to dry (eta)
    float rem = soil_now - soil_dry;
    float eta = rem / fabsf(slope_h);

    // 4. Adjust eta based on VPD (Vapor Pressure Deficit)
    // High VPD (dry air) → faster drying → shorter eta
    // Low VPD (humid air) → slower drying → longer eta

    if (isfinite(vpd)) {
        float factor = 1.0f + 0.25f * (vpd - 1.0f);
        factor = constrain(factor, 0.5f, 1.8f);

        eta /= factor;
    }

    return eta;
}


Derived Estimation::computeDerived(const Sample& latest, const History& hist){
  Derived d{};
  d.vpd_kPa  = vpd_kPa(latest.T, latest.RH);
  d.slope_h  = slopePerHourWithLatest(hist, latest, CFG::SLOPE_WINDOW_POINTS);
  d.eta_h    = etaHours(latest.soil, CFG::SOIL_THRESHOLD, d.slope_h, d.vpd_kPa);
  return d;
}
