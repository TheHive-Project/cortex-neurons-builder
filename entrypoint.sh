#!/bin/bash

echo "Starting Docker daemon ..."
dockerd --host=unix:///var/run/docker.sock \
		--host=tcp://0.0.0.0:2375 &> /dev/null &
DOCKER_PID=$!

while ! docker info > /dev/null
do sleep 1
done

chmod u+x /usr/local/bin/*.py
/usr/local/bin/build.py $@
R=$?
kill ${DOCKER_PID}
exit $R