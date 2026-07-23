# Odyssey Trailer on ESP32-S3 + 128×64 SSD1306

This project converts a video trailer into a tiny black-and-white animation and
stores all frames directly in the ESP32-S3 flash.

## What it does

- Resolution: 128×64
- Color: monochrome
- Default speed: 5 FPS
- Audio: not supported
- Short button press: pause/resume
- Hold button for 1.2 seconds: restart
- Trailer repeats automatically

## Existing wiring

| Part | ESP32-S3 |
|---|---|
| OLED GND | GND |
| OLED VDD | 3V3 |
| OLED SCK | GPIO8 |
| OLED SDA | GPIO9 |
| Button side 1 | GPIO4 |
| Button side 2 | GND |

## 1. Install Arduino libraries

In Arduino IDE Library Manager, install:

- Adafruit GFX Library
- Adafruit SSD1306

## 2. Put the trailer in this folder

Use a trailer video you obtained legally. A normal MP4 file is easiest.

Example filename:

    odyssey_trailer.mp4

## 3. Install the converter requirements

Open Command Prompt inside this project folder:

    py -m pip install opencv-python numpy

## 4. Convert the trailer

For a trailer up to 150 seconds at 5 FPS:

    py convert_video.py odyssey_trailer.mp4 --fps 5 --duration 150

This replaces:

- odyssey_frames.h
- odyssey_frames.cpp

Each second at 5 FPS uses 5,120 bytes. A 150-second trailer uses about 750 KiB
for frame data.

For a smaller upload, use 4 FPS:

    py convert_video.py odyssey_trailer.mp4 --fps 4 --duration 150

## 5. Open and upload

Open:

    OdysseyTrailerOLED.ino

Use the same ESP32-S3 board settings that worked for your Wi-Fi mapper.

Important Arduino settings:

- Flash Size: 16 MB
- Partition Scheme: choose one with enough application space
- Upload Speed: use the speed that already works for your board

If Arduino says the sketch is too large, select a partition scheme such as
"Huge APP" or convert at 4 FPS.

## Notes

The generated `odyssey_frames.cpp` can be several megabytes as text. This is
normal. The actual packed movie data uses only 1,024 bytes per frame in flash.

The screen cannot show real color. Ordered dithering creates black-and-white
patterns that imitate brightness and preserve more detail than a plain threshold.
