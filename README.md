# sf3

An interactive Street Fighter 3 demo against an RL-trained LLM in a sandboxed game engine.

## Installation

```bash
# Clone repository
git clone https://github.com/modal-labs/sf3.git
cd sf3

# Install dependencies
uv sync

# Set up Modal
modal setup
```

### Diambra

Sign up for a [Diambra account](https://www.diambra.ai/),
then store the token in a file named `assets/engine/credentials`.

Download the [ROM file](https://wowroms.com/en/roms/mame-0.139u1/street-fighter-iii-3rd-strike-fight-for-the-future-japan-990608-no-cd/7073.html),
then store it as `assets/engine/sfiii3n.zip`.

## Quickstart

```bash
# Test the LLM
modal run -m src.llm

# Test the YOLO model
modal run -m src.yolo

# Serve the web app
modal serve -m src.app

# Deploy the web app
modal deploy -m src.app
```

## Credit

### Icons

- [Feathericons](https://feathericons.com/)

### LLM

- [Qwen3 chat template](https://qwen.readthedocs.io/en/latest/_downloads/c101120b5bebcc2f12ec504fc93a965e/qwen3_nonthinking.jinja)

### Logos

- [Capcom](https://logos.fandom.com/wiki/Capcom?file=Capcom.svg)
- [Favicon](https://images.app.goo.gl/Dx3mLrW8dorr92Uq7)
- [Modal](https://live.standards.site/modal)

### Characters

- [Outfits](https://www.zytor.com/~johannax/jigsaw/sf/3s.html)
- [Moves/portraits](https://streetfighter.fandom.com/wiki/List_of_moves_in_Street_Fighter_III:_3rd_Strike)

### Sounds

- [Button click](https://freesound.org/people/orginaljun/sounds/157871/)
- [Button/link hover](https://freesound.org/people/steaq/sounds/757328/)
- [Coin insert](https://www.myinstants.com/en/instant/street-fighter-ii-coin/)
- [Original SF3](https://downloads.khinsider.com/game-soundtracks/album/street-fighter-iii-third-strike)
