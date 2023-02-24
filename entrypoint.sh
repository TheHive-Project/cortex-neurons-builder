#!/bin/bash
if [ ! -S /var/run/docker.sock ]; then 
	echo "Starting Docker daemon ..."
	dockerd --host=unix:///var/run/docker.sock \
			--host=tcp://0.0.0.0:2375 &> /dev/null &
	DOCKER_PID=$!

	while ! docker info > /dev/null
	do sleep 1
	done
fi

# Avoid issues with git
git config --global --add safe.directory '*'

chmod u+x /usr/local/bin/*.py
/usr/local/bin/build.py $@
R=$?
if [ -n "$DOCKER_PID" ]; then
	kill ${DOCKER_PID}
fi
exit $R
