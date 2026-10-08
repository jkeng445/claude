// KJG-2026-002 LAMP-Dx: ESP32 firmware (Arduino core for ESP32 v3.x).
//
// Runs the 65 °C isothermal block and heated lid, switches the excitation LED,
// and streams telemetry to the host app over USB serial (115200 baud).
//
// Commands (one per line):
//   RUN <block_c> <lid_c> <minutes>   e.g. RUN 65 75 35
//   STOP
//   LED <0|1>
//   STATUS
// Telemetry (1 Hz, one JSON object per line):
//   {"ms":12000,"state":"HOLD","fault":"NONE","block":65.02,"lid":74.9,
//    "block_duty":0.31,"lid_duty":0.22,"hold_s":540,"led":1}
//
// All control/safety logic lives in control.h and is unit-tested on a PC.
#include "control.h"

// ---- Pin map (see docs/hardware.md for wiring) ----
constexpr int PIN_BLOCK_NTC = 34;   // ADC1, 100k NTC divider
constexpr int PIN_LID_NTC   = 35;   // ADC1, 100k NTC divider
constexpr int PIN_BLOCK_HTR = 25;   // logic-level MOSFET gate → 12 V block heater
constexpr int PIN_LID_HTR   = 26;   // logic-level MOSFET gate → 12 V lid heater
constexpr int PIN_LED       = 27;   // excitation / illumination LED driver
constexpr int PIN_FAN       = 14;   // optional cool-down fan
constexpr int PWM_FREQ = 1000, PWM_BITS = 10;

lampdx::Thermistor ntc;
lampdx::Assay assay;
bool led_on = false;

float read_celsius(int pin) {
  uint32_t mv = 0;
  for (int i = 0; i < 16; ++i) mv += analogReadMilliVolts(pin);   // factory-calibrated ADC
  return ntc.celsius_from_mv(mv / 16.0f);
}

void set_led(bool on) { led_on = on; digitalWrite(PIN_LED, on ? HIGH : LOW); }

void handle_line(String line) {
  line.trim();
  if (line.startsWith("RUN")) {
    float b = 65, l = 75, m = 35;
    sscanf(line.c_str(), "RUN %f %f %f", &b, &l, &m);
    if (b < 30 || b > 75 || l < b || l > 95 || m <= 0 || m > 120) {
      Serial.println("{\"error\":\"RUN out of range (block 30-75, lid >= block and <= 95, minutes 0-120]\"}");
      return;
    }
    assay.start(b, l, m);
    digitalWrite(PIN_FAN, LOW);
    Serial.printf("{\"ack\":\"RUN\",\"block\":%.1f,\"lid\":%.1f,\"minutes\":%.1f}\n", b, l, m);
  } else if (line == "STOP") {
    assay.stop();
    Serial.println("{\"ack\":\"STOP\"}");
  } else if (line.startsWith("LED")) {
    set_led(line.endsWith("1"));
    Serial.printf("{\"ack\":\"LED\",\"led\":%d}\n", led_on);
  } else if (line == "STATUS") {
    // telemetry line follows on the next tick
  } else if (line.length()) {
    Serial.println("{\"error\":\"unknown command\"}");
  }
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_BLOCK_NTC, ADC_11db);
  analogSetPinAttenuation(PIN_LID_NTC, ADC_11db);
  ledcAttach(PIN_BLOCK_HTR, PWM_FREQ, PWM_BITS);
  ledcAttach(PIN_LID_HTR, PWM_FREQ, PWM_BITS);
  ledcWrite(PIN_BLOCK_HTR, 0);
  ledcWrite(PIN_LID_HTR, 0);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_FAN, OUTPUT);
  set_led(false);
  Serial.println("{\"hello\":\"KJG-2026-002 LAMP-Dx\",\"fw\":\"0.1.0\"}");
}

void loop() {
  static uint32_t last_ctl = millis(), last_tel = 0;
  static String buf;

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { handle_line(buf); buf = ""; }
    else if (buf.length() < 64) buf += c;
  }

  uint32_t now = millis();
  if (now - last_ctl >= 100) {                       // 10 Hz control loop
    float dt = (now - last_ctl) / 1000.0f;
    last_ctl = now;
    float block = read_celsius(PIN_BLOCK_NTC), lid = read_celsius(PIN_LID_NTC);
    assay.step(dt, block, lid);
    const int full = (1 << PWM_BITS) - 1;
    ledcWrite(PIN_BLOCK_HTR, (int)(assay.block_duty * full));
    ledcWrite(PIN_LID_HTR, (int)(assay.lid_duty * full));
    // Fan helps cool the block after a run so the next run starts from ambient.
    digitalWrite(PIN_FAN, (assay.state == lampdx::State::Done && block > 40) ? HIGH : LOW);

    if (now - last_tel >= 1000) {
      last_tel = now;
      Serial.printf("{\"ms\":%lu,\"state\":\"%s\",\"fault\":\"%s\",\"block\":%.2f,\"lid\":%.2f,"
                    "\"block_duty\":%.3f,\"lid_duty\":%.3f,\"hold_s\":%.0f,\"led\":%d}\n",
                    (unsigned long)now, lampdx::state_name(assay.state), lampdx::fault_name(assay.fault),
                    block, lid, assay.block_duty, assay.lid_duty, assay.hold_elapsed_s, led_on);
    }
  }
}
