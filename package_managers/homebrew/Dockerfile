FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Install git for Homebrew since it uses the GitFetcher
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy everything from the root directory (build context)
COPY . .

# Install core requirements using uv
WORKDIR /core
RUN uv pip install --system -r requirements.txt

WORKDIR /

# Run the main application
CMD ["python", "/package_managers/homebrew/main.py"]
