// Host-side tests for control.h against a simple lumped thermal model of the block.
// Build & run:  g++ -std=c++17 -O2 -I../lamp_dx test_control.cpp -o test_control && ./test_control
#include <cstdio>
#include <cstdlib>
#include "control.h"

using namespace lampdx;

static int failures = 0;
#define CHECK(cond, ...) do { if (!(cond)) { std::printf("FAIL %s:%d: ", __FILE__, __LINE__); \
  std::printf(__VA_ARGS__); std::printf("\n"); ++failures; } } while (0)

// Aluminium block for 8 x 0.2 mL tubes (~30 J/K incl. tubes), 20 W heater,
// 0.15 W/K loss to 25 °C ambient, 2 s sensor lag. Lid: 15 J/K, 10 W, 0.1 W/K.
struct Plant {
  float block = 25, lid = 25, block_sensor = 25, amb = 25;
  float block_watts = 20, lid_watts = 10;
  bool heater_connected = true;
  void step(float dt, float bd, float ld) {
    float pb = heater_connected ? bd * block_watts : 0;
    block += dt * (pb - 0.15f * (block - amb)) / 30.0f;
    lid += dt * (ld * lid_watts - 0.1f * (lid - amb)) / 15.0f;
    block_sensor += dt * (block - block_sensor) / 2.0f;
  }
};

static void test_thermistor() {
  Thermistor th;
  CHECK(fabsf(th.celsius_from_mv(1650) - 25.0f) < 0.01f, "25C midpoint: %f", th.celsius_from_mv(1650));
  // At 65 °C a B3950 100k reads ~20.9 kΩ → ~570 mV
  float t = th.celsius_from_mv(3300.0f * 20870 / (100000 + 20870));
  CHECK(fabsf(t - 65.0f) < 1.0f, "65C point: %f", t);
  CHECK(isnan(th.celsius_from_mv(0)), "short reads NAN");
  CHECK(isnan(th.celsius_from_mv(3300)), "open reads NAN");
}

static void test_reaches_and_holds_65() {
  Assay a; Plant p; a.start(65, 75, 30);
  float dt = 0.1f, max_t = 0, worst_hold_err = 0, t_to_hold = -1;
  for (int i = 0; i < 40 * 60 * 10 && a.state != State::Done; ++i) {
    a.step(dt, p.block_sensor, p.lid);
    p.step(dt, a.block_duty, a.lid_duty);
    if (p.block > max_t) max_t = p.block;
    if (a.state == State::Hold) {
      if (t_to_hold < 0) t_to_hold = a.elapsed_s;
      if (a.hold_elapsed_s > 120) worst_hold_err = fmaxf(worst_hold_err, fabsf(p.block - 65));
    }
  }
  CHECK(a.state == State::Done, "run should finish, state=%s fault=%s", state_name(a.state), fault_name(a.fault));
  CHECK(t_to_hold > 0 && t_to_hold < 300, "reach 65C in <5 min, took %.0fs", t_to_hold);
  CHECK(max_t < 66.5f, "overshoot under 1.5C, peak %.2f", max_t);
  CHECK(worst_hold_err < 0.5f, "hold within ±0.5C after settling, worst %.2f", worst_hold_err);
  CHECK(a.block_duty == 0 && a.lid_duty == 0, "heaters off when done");
  std::printf("  ramp %.0fs, peak %.2fC, hold error %.2fC\n", t_to_hold, max_t, worst_hold_err);
}

static void test_fault(const char* name, Fault expect, void (*setup)(Plant&), float (*sensor)(const Plant&, float)) {
  Assay a; Plant p; setup(p); a.start(65, 75, 30);
  for (int i = 0; i < 20 * 60 * 10 && a.state != State::Fault; ++i) {
    a.step(0.1f, sensor(p, a.elapsed_s), p.lid);
    p.step(0.1f, a.block_duty, a.lid_duty);
  }
  CHECK(a.state == State::Fault && a.fault == expect, "%s: got %s/%s", name, state_name(a.state), fault_name(a.fault));
  CHECK(a.block_duty == 0 && a.lid_duty == 0, "%s: heaters off on fault", name);
}

int main() {
  test_thermistor();
  test_reaches_and_holds_65();
  test_fault("detached heater", Fault::Runaway,
             [](Plant& p) { p.heater_connected = false; },
             [](const Plant& p, float) { return p.block_sensor; });
  test_fault("sensor unplugged mid-run", Fault::SensorBlock, [](Plant&) {},
             [](const Plant& p, float t) { return t > 60 ? NAN : p.block_sensor; });
  test_fault("undersized heater stalls below setpoint", Fault::Runaway,
             [](Plant& p) { p.block_watts = 4; },   // plateaus ~52 C, never reaches 65 C
             [](const Plant& p, float) { return p.block_sensor; });
  test_fault("over-temperature", Fault::OverTemp, [](Plant&) {},
             [](const Plant& p, float t) { return t > 30 ? 80.0f : p.block_sensor; });
  if (failures) { std::printf("%d check(s) failed\n", failures); return 1; }
  std::printf("all control tests passed\n");
  return 0;
}
