"""Render a two-speaker script to audio with Kokoro on MLX.

usage: render_mlx.py [script.txt] [--speed 1.2] [--gap 0.35]

Script format, one turn per line:
    A|first speaker's line
    B|second speaker's line

Writes <script-basename>.wav next to this file (speed-suffixed if not the default).
"""
import sys, time, pathlib, argparse, numpy as np, soundfile as sf
import lexicon
from mlx_audio.tts.utils import load_model

SR = 24000
VOICES = {"A": "af_heart", "B": "am_michael"}
DEFAULT_SPEED = 1.2   # 1.0 reads noticeably slower than podcast pace
DEFAULT_GAP = 0.5     # real silence now that Kokoro's ~600ms padding is trimmed off


def trim(a, thresh=0.005, keep_ms=15):
    """Strip Kokoro's ~600ms of leading/trailing padding so --gap means what it says."""
    loud = np.where(np.abs(a) > thresh)[0]
    if loud.size == 0:
        return a[:0]
    keep = int(SR * keep_ms / 1000)
    return a[max(0, loud[0] - keep) : min(len(a), loud[-1] + keep)]


here = pathlib.Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument("script", nargs="?", default="excerpt.txt")
ap.add_argument("--speed", type=float, default=DEFAULT_SPEED,
                help=f"speaking rate, 1.0 is Kokoro's native pace (default {DEFAULT_SPEED})")
ap.add_argument("--gap", type=float, default=DEFAULT_GAP,
                help=f"seconds of silence between turns (default {DEFAULT_GAP})")
args = ap.parse_args()

GAP = np.zeros(int(SR * args.gap), dtype=np.float32)

src = pathlib.Path(args.script)
if not src.is_absolute():
    src = here / src
if not src.exists():
    sys.exit(f"no such script: {src}")
suffix = "" if args.speed == DEFAULT_SPEED else f"-{args.speed:g}x"
if args.gap != DEFAULT_GAP:
    suffix += f"-gap{args.gap:g}"
out = here / f"{src.stem}{suffix}.wav"

model = load_model("prince-canuma/Kokoro-82M")

chunks, turns, audio_s = [], 0, 0.0
t0 = time.time()
for lineno, line in enumerate(src.read_text().splitlines(), 1):
    if not line.strip():
        continue
    if "|" not in line:
        sys.exit(f"{src}:{lineno}: expected 'A|text' or 'B|text', got: {line[:40]}")
    spk, text = line.split("|", 1)
    spk = spk.strip().upper()
    if spk not in VOICES:
        sys.exit(f"{src}:{lineno}: unknown speaker {spk!r}, expected A or B")
    turns += 1
    audio = trim(np.concatenate([
        np.asarray(r.audio, dtype=np.float32).reshape(-1)
        for r in model.generate(text=lexicon.apply(text.strip()), voice=VOICES[spk],
                                speed=args.speed, lang_code="a")
    ]))
    audio_s += len(audio) / SR
    chunks += [audio, GAP]
elapsed = time.time() - t0

if not chunks:
    sys.exit(f"{src}: no turns found")

full = np.concatenate(chunks)
sf.write(out, full, SR)
total_s = len(full) / SR          # speech plus the gaps between turns
mins, secs = divmod(int(total_s), 60)
print(f"{out}")
print(f"{turns} turns, {mins}m{secs:02d}s audio ({total_s - audio_s:.0f}s of it gaps), "
      f"{elapsed:.0f}s to generate ({total_s/elapsed:.1f}x realtime)")
print(f"afplay {out}")
