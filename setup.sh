#!/bin/bash
# One-shot setup. Apple Silicon only (mlx-audio requires Metal).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

[ "$(uname -m)" = "arm64" ] || { echo "Apple Silicon required (mlx-audio has no Intel build)"; exit 1; }
command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }

python3 -m venv .venv-mlx
./.venv-mlx/bin/pip install -q --upgrade pip
./.venv-mlx/bin/pip install -q -r requirements.txt
chmod +x speak raycast/*.sh

echo "Downloading and warming the model (one time, ~300MB)..."
./.venv-mlx/bin/python -c "
from mlx_audio.tts.utils import load_model
m = load_model('prince-canuma/Kokoro-82M')
for _ in m.generate(text='Setup complete.', voice='af_heart', speed=1.3, lang_code='a'): pass
print('model ready')
"
echo
echo "Done. Try:  ./speak 'hello there'"
echo "Raycast: Settings -> Script Commands -> Add Script Directory -> $(pwd)/raycast"
