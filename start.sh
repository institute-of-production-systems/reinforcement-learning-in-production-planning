#!/bin/bash
# Start a virtual X server
Xvfb :0 -screen 0 1280x800x24 &

# Start a lightweight window manager
fluxbox &

# Start VNC server (passwordless for demo)
x11vnc -display :0 -nopw -forever -shared &

# Start noVNC (web client on port 6080)
websockify --web /usr/share/novnc/ 6080 localhost:5900 &

# Run your PyQt app inside the virtual display
export DISPLAY=:0
python3 user_interface.py