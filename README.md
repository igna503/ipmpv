# ipmpv

## Introduction

This Python script is designed to turn your Linux machine into an IPTV player, using MPV for video playback, Pygame for an OSD, and Flask as a remote controllable GUI.

It was designed with a Raspberry Pi using composite output in mind, some features may not work in all devices, but it's otherwise functional.

## Setup

You must provide your own IPTV list in the form of an M3U URL. Set the IPMPV_M3U_URL variable, run the "run.sh" script in an graphical session, access http://[your-machine-ip]:5000 in a web browser, and you're ready to go!

I recommend using a Raspberry Pi 4, and transcoding the video streams to 480p, as video acceleration support does not seem to play well with this app yet.

Video is stretched to fill the screen by default. Feel free to tweak the MPV settings in the script itself, a better way to change them is Coming Soon™

## Features

- TV channel selection

- Deinterlacing (can be slow in older Pis)

- Low latency mode

- Support for custom URL playback

- Support for starting RetroArch, pairs well with the Pi for CRT retro gaming

- Resolution switching for the Raspberry Pi's composite output

## Requirements

This application will only run on Linux under an X11 session.

A Bash script is included to install the following in a virtual environment:

- PyQT5

- Flask

- Regex

- Pillow

- Requests

- Python-MPV

- PyAlsaAudio

Additionally, the following applications and libraries are required to be installed in the host system:

- Python >= 3.10

- Alsa

- libmpv

- wmctl

- (Optional) yt-dlp, for YouTube video playback

- (RPI Specific) python3-pyqt5, it won't install via pip due to RAM constraints

## Environment variables

- IPMPV_M3U_URL: The URL of your M3U playlist. Default: None
- IPMPV_CORNER_RADIUS: Corner radius of the OSD. Set to 0 for sharp edges. Default: 15
- IPMPV_RETROARCH_CMD: Your custom RetroArch command, if any. Default: 'retroarch'

## Coming Soon

### Short term

- A way to change MPV settings without editing the script

- Better support for the Pi's HDMI output, more resolution support

### Long term

- A recommended environment, perhaps in the form of a Pi .img

- Docker image???

## License

This software is licensed under the GNU General Public License v3. See COPYING.

The Fira Sans font is licensed under the SIL Open Font License. See OFL.txt. Fira is a trademark of The Mozilla Corporation.
