# ──────────────────────────────────────────────
# Java 11 → 21 Migration Agent
# Python 3.11 + Java 21 JDK + Maven + Git
# ──────────────────────────────────────────────
FROM python:3.11-slim

# Install basic tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    unzip \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Java 21 via Adoptium apt repo
RUN wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public \
        | gpg --dearmor > /etc/apt/trusted.gpg.d/adoptium.gpg \
    && echo "deb https://packages.adoptium.net/artifactory/deb bookworm main" \
       > /etc/apt/sources.list.d/adoptium.list \
    && apt-get update \
    && apt-get install -y temurin-21-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install Maven via apt
RUN apt-get update && apt-get install -y maven && rm -rf /var/lib/apt/lists/*

# ── App ──
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

# Workspace for cloned repos
RUN mkdir -p /workspace
WORKDIR /workspace

ENTRYPOINT ["python", "/app/agent.py"]
CMD ["--help"]
