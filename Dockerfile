# NVIDIA driver 580.x reports CUDA 13.0 support on host; a CUDA 12.4 runtime base is fine
# (driver >= container runtime). Sticking to Ubuntu 22.04 for compatibility.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

LABEL org.opencontainers.image.title="MaRNoW Dev GPU Base" \
      org.opencontainers.image.description="RTX 4070 (8GB) friendly base for resume/JD pipeline with Playwright, LaTeX, Ollama" \
      org.opencontainers.image.source="local"

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OLLAMA_HOST=0.0.0.0:11434

# 1) System packages (lean), LaTeX (not texlive-full), and Playwright deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git build-essential pkg-config \
    python3 python3-pip python3-venv python3-dev \
    # Playwright / headless Chromium runtime deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libatspi2.0-0 libwayland-client0 \
    fonts-liberation \
    # Minimal LaTeX set (extend later if templates need extras)
    latexmk texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
    # Optional utilities
    jq nano \
    && rm -rf /var/lib/apt/lists/*

# 2) Python deps (core only; your app's requirements can be added later)
RUN python3 -m pip install --upgrade pip && \
    pip install \
      playwright==1.48.* \
      pypdf \
      python-docx \
      beautifulsoup4 lxml \
      spacy==3.7.* \
      sqlite-utils \
      uvicorn fastapi

# Install Chromium for Playwright + OS deps
RUN python3 -m playwright install chromium && \
    python3 -m playwright install-deps

# 3) Ollama (GPU build inside container). Models pulled at runtime into a volume.
RUN curl -fsSL https://ollama.com/install.sh | sh
EXPOSE 11434

# 4) Workspace
WORKDIR /app
COPY . /app

# Copy entrypoint
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Healthcheck: container is healthy when Ollama answers
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://localhost:11434/api/tags >/dev/null || exit 1

# Default command: entrypoint starts Ollama then runs your CMD (bash by default)
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
