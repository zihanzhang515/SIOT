#include "History.h"
#include <stdlib.h>

void History::reset() {
  _cnt = 0;  
  _idx = 0; 
}

void History::init(size_t cap){
  _cap = cap; _cnt = 0; _idx = 0;
  _s = (Sample*)  malloc(sizeof(Sample)*_cap);
  _d = (Derived*) malloc(sizeof(Derived)*_cap);
}

void History::push(const Sample& s, const Derived& d){
  _s[_idx] = s; _d[_idx] = d;
  _idx = (_idx + 1) % _cap;
  if (_cnt < _cap) _cnt++;
}

bool History::getSampleFromEnd(size_t k, Sample &out) const {
  if (k >= _cnt) return false;
  size_t pos = (_idx + _cap - 1 - k) % _cap;
  out = _s[pos];
  return true;
}
