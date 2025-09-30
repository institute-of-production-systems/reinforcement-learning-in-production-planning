#!/bin/bash
# Allow local docker containers to use your X server
xhost +local:docker >/dev/null 2>&1

# Run the container with access to your display
docker run -it --rm \
    -e DISPLAY=$DISPLAY \
    -e QT_X11_NO_MITSHM=1 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    propplan-py "$@"

# Revoke the X server permission afterwards
xhost -local:docker >/dev/null 2>&1