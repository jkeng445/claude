// KJG-2026-002 LAMP-Dx: hardware-independent thermal control and safety logic.
//
// Everything here is plain C++ with no Arduino dependency, so the exact code
// that runs on the ESP32 is also compiled and tested on a PC
// (see firmware/test/test_control.cpp).
#pragma once
#include <math.h>
#include <stdint.h>

namespace lampdx {

// ---------- Thermistor (100k NTC, B=3950, to GND; 100k fixed resistor to Vref) ----------
struct Thermistor {
  float r_fixed = 100000.0f, r0 = 100000.0f, t0_c = 25.0f, beta = 3950.0f, vref_mv = 3300.0f;

  // Returns NAN when the reading is outside the physically possible range,
  // which the safety monitor treats as an open or shorted sensor.
  float celsius_from_mv(float mv) const {
    if (mv <= 5.0f || mv >= vref_mv - 5.0f) return NAN;
    float r = r_fixed * mv / (vref_mv - mv);
    float inv_t = 1.0f / (t0_c + 273.15f) + logf(r / r0) / beta;
    return 1.0f / inv_t - 273.15f;
  }
};

// ---------- PID with derivative-on-measurement and conditional-integration anti-windup ----------
struct Pid {
  float kp, ki, kd;
  float integral = 0, last_meas = NAN, d_filt = 0;

  Pid(float p, float i, float d) : kp(p), ki(i), kd(d) {}
  void reset() { integral = 0; last_meas = NAN; d_filt = 0; }

  float step(float setpoint, float meas, float dt) {
    float err = setpoint - meas;
    float d = isnan(last_meas) ? 0 : -(meas - last_meas) / dt;
    last_meas = meas;
    d_filt += 0.2f * (d - d_filt);                     // low-pass the derivative
    float unclamped = kp * err + integral + ki * err * dt + kd * d_filt;
    // Only integrate when the output is not saturated in the direction of the error.
    if (!((unclamped >= 1.0f && err > 0) || (unclamped <= 0.0f && err < 0))) integral += ki * err * dt;
    float out = kp * err + integral + kd * d_filt;
    return out < 0 ? 0 : (out > 1 ? 1 : out);
  }
};

enum class State : uint8_t { Idle, Ramp, Hold, Done, Fault };
enum class Fault : uint8_t { None, SensorBlock, SensorLid, OverTemp, Runaway, RampTimeout };

inline const char* state_name(State s) {
  switch (s) { case State::Idle: return "IDLE"; case State::Ramp: return "RAMP";
    case State::Hold: return "HOLD"; case State::Done: return "DONE"; default: return "FAULT"; }
}
inline const char* fault_name(Fault f) {
  switch (f) { case Fault::None: return "NONE"; case Fault::SensorBlock: return "SENSOR_BLOCK";
    case Fault::SensorLid: return "SENSOR_LID"; case Fault::OverTemp: return "OVER_TEMP";
    case Fault::Runaway: return "THERMAL_RUNAWAY"; default: return "RAMP_TIMEOUT"; }
}

struct Limits {
  float block_abs_max = 85.0f;     // hardware thermal fuse should sit just above this
  float lid_abs_max = 100.0f;
  float over_setpoint = 8.0f;      // fault if block exceeds setpoint by this much
  float hold_band = 0.5f;          // HOLD timer starts once within ±band
  float ramp_timeout_s = 600.0f;
  float runaway_window_s = 90.0f;  // full power for this long with < runaway_min_rise °C → fault
  float runaway_min_rise = 2.0f;
};

// One isothermal run: heat block to setpoint (65 °C for LAMP), hold for N minutes,
// keep the heated lid above block temperature to stop condensation, then switch off.
class Assay {
 public:
  Limits lim;
  Pid block_pid{0.25f, 0.004f, 1.5f};
  Pid lid_pid{0.15f, 0.002f, 0.5f};

  State state = State::Idle;
  Fault fault = Fault::None;
  float block_sp = 65.0f, lid_sp = 75.0f, hold_s = 30 * 60.0f;
  float elapsed_s = 0, hold_elapsed_s = 0;
  float block_duty = 0, lid_duty = 0;

  void start(float block_c, float lid_c, float minutes) {
    block_sp = block_c; lid_sp = lid_c; hold_s = minutes * 60.0f;
    elapsed_s = hold_elapsed_s = 0; fault = Fault::None; state = State::Ramp;
    block_pid.reset(); lid_pid.reset(); runaway_t_ = 0; runaway_ref_ = NAN;
  }
  void stop() { if (state != State::Fault) state = State::Idle; off(); }

  // Call at a fixed rate (e.g. 10 Hz). Temperatures may be NAN on sensor failure.
  void step(float dt, float block_c, float lid_c) {
    if (state == State::Idle || state == State::Done || state == State::Fault) { off(); return; }
    elapsed_s += dt;

    if (isnan(block_c) || block_c < -20 || block_c > 150) return trip(Fault::SensorBlock);
    if (isnan(lid_c) || lid_c < -20 || lid_c > 150) return trip(Fault::SensorLid);
    if (block_c > lim.block_abs_max || block_c > block_sp + lim.over_setpoint || lid_c > lim.lid_abs_max)
      return trip(Fault::OverTemp);

    block_duty = block_pid.step(block_sp, block_c, dt);
    lid_duty = lid_pid.step(lid_sp, lid_c, dt);

    // Runaway: heater driven hard but the block isn't warming (detached heater,
    // dead MOSFET, sensor fallen out of the block).
    if (block_duty > 0.9f && block_c < block_sp - 5) {
      if (isnan(runaway_ref_)) { runaway_ref_ = block_c; runaway_t_ = 0; }
      runaway_t_ += dt;
      if (runaway_t_ >= lim.runaway_window_s) {
        if (block_c - runaway_ref_ < lim.runaway_min_rise) return trip(Fault::Runaway);
        runaway_ref_ = block_c; runaway_t_ = 0;
      }
    } else { runaway_ref_ = NAN; }

    if (state == State::Ramp) {
      if (fabsf(block_c - block_sp) <= lim.hold_band) state = State::Hold;
      else if (elapsed_s > lim.ramp_timeout_s) return trip(Fault::RampTimeout);
    }
    if (state == State::Hold) {
      hold_elapsed_s += dt;
      if (hold_elapsed_s >= hold_s) { state = State::Done; off(); }
    }
  }

 private:
  float runaway_t_ = 0, runaway_ref_ = NAN;
  void off() { block_duty = lid_duty = 0; }
  void trip(Fault f) { fault = f; state = State::Fault; off(); }
};

}  // namespace lampdx
