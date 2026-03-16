FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Install the small Linux toolchain the repository scripts expect.
# This keeps the devcontainer aligned with the bash/curl/python-based helpers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    jq \
    python3 \
    python3-pip \
    ripgrep \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Run as the non-root vscode user provided by the base image.
USER vscode
