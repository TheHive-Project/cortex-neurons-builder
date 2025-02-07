FROM python:3-slim

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy & install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python scripts to /usr/local/bin
COPY *.py /usr/local/bin/

# Env variables for Docker binary download
ENV DOCKER_CHANNEL=stable
ENV DOCKER_VERSION=24.0.9

# Install required packages and Docker CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        iptables \
        wget \
        ca-certificates \
        git && \
    update-alternatives --set iptables /usr/sbin/iptables-legacy && \
    rm -rf /var/lib/apt/lists/* && \
    wget -q -O - "https://download.docker.com/linux/static/${DOCKER_CHANNEL}/x86_64/docker-${DOCKER_VERSION}.tgz" | \
    tar -xzC /usr/local/bin/ --strip-components 1 && \
    addgroup --system dockremap && \
    adduser --system --ingroup dockremap dockremap && \
    echo 'dockremap:165536:65536' >> /etc/subuid && \
    echo 'dockremap:165536:65536' >> /etc/subgid

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/

# volume declaration for Docker data
VOLUME ["/var/lib/docker"]

# Set the container entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
