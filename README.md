# Odyssey Trailer OLED — IMAX Framing

This version supports both common IMAX aspect ratios.

## Recommended setting

Use **IMAX 1.90:1** on the 128×64 OLED:

```
py convert_video.py odyssey_trailer.mp4 --fps 5 --aspect imax190
```

The OLED is 2.00:1, so a 1.90:1 image uses approximately 122×64 pixels and
leaves only about three black pixels on each side.

## IMAX 70mm framing

Use this only when the input video really contains a 1.43:1 expanded image:

```
py convert_video.py odyssey_trailer.mp4 --fps 5 --aspect imax143
```

On the OLED, this produces an image approximately 92×64 pixels with large black
bars on the left and right. It preserves the tall IMAX shape but uses less of
the tiny display.

## Completely fill the screen

```
py convert_video.py odyssey_trailer.mp4 --fps 5 --aspect fill
```

This crops the input to the OLED's exact 2.00:1 ratio. It fills every pixel but
is not an official IMAX aspect ratio.

## Keep the video's original shape

```
py convert_video.py odyssey_trailer.mp4 --fps 5 --aspect source
```

## Setup

Install the converter dependencies:

```
py -m pip install opencv-python numpy
```

Then run one of the conversion commands above. The converter replaces:

- `odyssey_frames.h`
- `odyssey_frames.cpp`

Open `OdysseyTrailerOLED.ino` in Arduino IDE and upload normally.

## Controls

- Short press: pause/resume
- Hold for 1.2 seconds: restart
- The trailer repeats automatically

## Hardware

OLED SDA to GPIO9
OLED SCK to GPIO8
Button to GPIO4 and GND
OLED power to 3V3 and GND

Personal Note

Watching Christopher Nolan's The Odyssey in IMAX was one of those rare cinematic experiences that genuinely captivated me — the visuals the storytelling the sheer scale of it all. This project is an homage to that film's production specifically the use of IMAX cameras. There's something poetic about a movie designed specifically for the IMAX format and seeing that same IMAX ratio recreated on a tiny 128×64 monochrome OLED feels like a creative way to connect my technical skills with the things I love. It's a playful nod to the idea that the medium matters even when you're pushing it to its absolute limits