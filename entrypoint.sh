#!/bin/bash

dockerd --host=unix:///var/run/docker.sock \
		--host=tcp://0.0.0.0:2375 &> /dev/null &
DOCKER_PID=$!

/usr/local/bin/build.py $@
kill ${DOCKER_PID}