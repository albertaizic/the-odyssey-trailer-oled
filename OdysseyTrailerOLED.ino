/*
  Odyssey Trailer Player for ESP32-S3 + SSD1306 128x64 OLED

  Existing wiring:
    OLED GND -> ESP32 GND
    OLED VDD -> ESP32 3V3
    OLED SCK -> ESP32 GPIO8
    OLED SDA -> ESP32 GPIO9
    Button one side -> ESP32 GPIO4
    Button other side -> ESP32 GND

  Controls:
    Short press: pause/resume
    Hold 1.2 seconds: restart trailer
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "odyssey_frames.h"

constexpr uint8_t OLED_SDA = 9;
constexpr uint8_t OLED_SCL = 8;
constexpr uint8_t BUTTON_PIN = 4;
constexpr uint8_t OLED_ADDRESS = 0x3C;
constexpr int8_t OLED_RESET = -1;

constexpr uint32_t BUTTON_DEBOUNCE_MS = 35;
constexpr uint32_t BUTTON_LONG_PRESS_MS = 1200;

Adafruit_SSD1306 display(128, 64, &Wire, OLED_RESET);

uint32_t currentFrame = 0;
uint32_t nextFrameAt = 0;
bool paused = false;

bool lastRawButton = false;
bool stableButton = false;
bool longPressHandled = false;
uint32_t lastButtonChangeAt = 0;
uint32_t buttonPressedAt = 0;

void showMessage(const __FlashStringHelper* line1,
                 const __FlashStringHelper* line2 = nullptr) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 18);
  display.println(line1);

  if (line2 != nullptr) {
    display.setCursor(0, 34);
    display.println(line2);
  }

  display.display();
}

void drawCurrentFrame() {
  display.clearDisplay();

  display.drawBitmap(
    0,
    0,
    ODYSSEY_FRAMES[currentFrame],
    ODYSSEY_WIDTH,
    ODYSSEY_HEIGHT,
    SSD1306_WHITE
  );

  display.display();
}

void restartTrailer() {
  currentFrame = 0;
  paused = false;
  nextFrameAt = millis();
}

void updateButton() {
  const uint32_t now = millis();
  const bool rawPressed = digitalRead(BUTTON_PIN) == LOW;

  if (rawPressed != lastRawButton) {
    lastRawButton = rawPressed;
    lastButtonChangeAt = now;
  }

  if ((now - lastButtonChangeAt) >= BUTTON_DEBOUNCE_MS &&
      rawPressed != stableButton) {
    stableButton = rawPressed;

    if (stableButton) {
      buttonPressedAt = now;
      longPressHandled = false;
    } else {
      const uint32_t heldFor = now - buttonPressedAt;

      if (!longPressHandled && heldFor >= BUTTON_DEBOUNCE_MS) {
        paused = !paused;

        if (!paused) {
          nextFrameAt = now;
        }
      }
    }
  }

  if (stableButton &&
      !longPressHandled &&
      (now - buttonPressedAt) >= BUTTON_LONG_PRESS_MS) {
    longPressHandled = true;
    restartTrailer();
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  Wire.begin(OLED_SDA, OLED_SCL);
  Wire.setClock(400000);

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println(F("ERROR: SSD1306 display not found."));
    while (true) {
      delay(1000);
    }
  }

  display.clearDisplay();
  display.display();

  if (ODYSSEY_WIDTH != 128 || ODYSSEY_HEIGHT != 64 ||
      ODYSSEY_FRAME_COUNT == 0 || ODYSSEY_FPS == 0) {
    showMessage(F("Invalid frame file"), F("Run converter again"));
    while (true) {
      delay(1000);
    }
  }

  showMessage(F("THE ODYSSEY"), F("Starting trailer..."));
  delay(1200);

  Serial.printf(
    "Playing %lu frames at %u FPS\n",
    static_cast<unsigned long>(ODYSSEY_FRAME_COUNT),
    ODYSSEY_FPS
  );

  restartTrailer();
}

void loop() {
  updateButton();

  if (paused) {
    delay(1);
    return;
  }

  const uint32_t now = millis();
  const uint32_t frameIntervalMs = 1000UL / ODYSSEY_FPS;

  if (static_cast<int32_t>(now - nextFrameAt) >= 0) {
    drawCurrentFrame();

    currentFrame++;
    if (currentFrame >= ODYSSEY_FRAME_COUNT) {
      currentFrame = 0;
    }

    nextFrameAt += frameIntervalMs;

    // Recover cleanly if display transfer or another operation made us late.
    if (static_cast<int32_t>(now - nextFrameAt) >
        static_cast<int32_t>(frameIntervalMs * 2UL)) {
      nextFrameAt = now + frameIntervalMs;
    }
  }
}
