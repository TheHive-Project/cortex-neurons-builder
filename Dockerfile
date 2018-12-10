FROM python:3

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY build.py /usr/local/bin/

ENV DOCKER_CHANNEL stable
ENV DOCKER_VERSION 18.09.0

RUN apt update && \
    apt install -q -y iptables && \
    rm -rf /var/lib/apt/lists/* && \
    wget -q -O - "https://download.docker.com/linux/static/${DOCKER_CHANNEL}/x86_64/docker-${DOCKER_VERSION}.tgz" | \
    tar -xzC /usr/local/bin/ --strip-components 1 && \
    addgroup --system dockremap && \
    adduser --system --ingroup dockremap dockremap && \
    echo 'dockremap:165536:65536' >> /etc/subuid && \
    echo 'dockremap:165536:65536' >> /etc/subgid

COPY entrypoint.sh /usr/local/bin/

VOLUME /var/lib/docker

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
