#pragma once
#include <Arduino.h>
#include "Types.h"

class History {
public:
  void init(size_t cap);
  void reset();
  void push(const Sample& s, const Derived& d);
  size_t size() const { return _cnt; }

  // Get the k-th most recent sample (k=0: latest). Returns false if out of range.
  bool getSampleFromEnd(size_t k, Sample &out) const;

private:
  Sample*  _s = nullptr;
  Derived* _d = nullptr;
  size_t _cap = 0, _cnt = 0, _idx = 0;
};
