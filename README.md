# sf3

An interactive Street Fighter 3 demo against an RL-trained LLM in a sandboxed game engine

## Installation

```bash
# Clone repository
git clone https://github.com/modal-labs/sf3.git
cd sf3

# Install dependencies
uv sync

# Set up Modal
modal setup

# Sign up for a diambra account at https://old.dev.diambra.ai/register
# then store token as `assets/credentials`

# Download the ROM file from https://wowroms.com/en/roms/mame-0.139u1/street-fighter-iii-3rd-strike-fight-for-the-future-japan-990608-no-cd/7073.html
# then store ROM file as `assets/sfiii3n.zip`
```

## Quickstart

```bash
# Serve the web app
modal serve -m src.app

# Deploy the web app
modal deploy -m src.app
```
