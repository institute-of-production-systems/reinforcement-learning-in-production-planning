# syntax=docker/dockerfile:1

# Base Python image for custom image
FROM python:3.12.7-bullseye

# Create working directory and install pip dependencies
WORKDIR /propplan-py

#RUN apt-get update && apt install -y qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools libnss3 libasound2 '^libxcb.*-dev' libx11-xcb-dev libglu1-mesa-dev libxrender-dev libxi-dev libxkbcommon-dev libxkbcommon-x11-dev

RUN apt-get update && apt-get install -y \
    x11vnc xvfb fluxbox \
    websockify novnc \
    qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools \
    libnss3 libasound2 \
    libx11-xcb1 libxrender1 libxi6 \
    libxcb1 libxcb-render0 libxcb-shape0 libxcb-xfixes0 \
    libxkbcommon0 libxkbcommon-x11-0 \
    libglu1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Copy Python project files from local to /propplan-py image working directory
COPY . .

#RUN export QT_QPA_PLATFORM=offscreen

EXPOSE 5900 6080

# Start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD [ "/start.sh"]

# Run the application
#CMD [ "python3", "user_interface.py"]
