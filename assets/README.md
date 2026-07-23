# Place your demo GIF here as `demo.gif`

Record a short video of the OLED playing the animation and convert to GIF:
```
ffmpeg -i oled_video.mp4 -vf "fps=10,scale=320:-1:flags=lanczos" -loop 0 demo.gif
```

Recommended: 5-10 second clip showing the animation playing.