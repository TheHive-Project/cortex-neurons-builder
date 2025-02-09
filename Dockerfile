FROM python:3-alpine

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy & install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python scripts to /usr/local/bin
COPY *.py /usr/local/bin/

# Env variables for Docker binary download
ENV DOCKER_CHANNEL=stable
ENV DOCKER_VERSION=27.5.1

# Install required packages and Docker CLI
RUN apk add --no-cache \
        iptables \
        wget \
        ca-certificates \
        git \
        bash && \
    update-ca-certificates && \
    wget -q -O - "https://download.docker.com/linux/static/${DOCKER_CHANNEL}/x86_64/docker-${DOCKER_VERSION}.tgz" | \
    tar -xzC /usr/local/bin/ --strip-components 1 && \
    addgroup -S dockremap && \
    adduser -S -G dockremap dockremap && \
    echo 'dockremap:165536:65536' >> /etc/subuid && \
    echo 'dockremap:165536:65536' >> /etc/subgid

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# volume declaration for Docker data
VOLUME ["/var/lib/docker"]

# Set the container entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
