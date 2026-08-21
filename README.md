# kokoro-reader

A local text-to-speech reader for macOS. Highlight text anywhere, hit a hotkey, listen.
Runs [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) on Apple Silicon via MLX.
Nothing leaves the machine, which matters if you read internal documents.

Two things live here:

- **`speak`** — a prose reader. Send it text, it reads it aloud. Driven from Raycast.
- **`render_mlx.py`** — a two-voice dialogue renderer. Feed it a script, get a wav.

## Requirements

- Apple Silicon Mac. `mlx-audio` is Metal-only; there is no Intel build.
- Python 3.9 or newer.
- Raycast, if you want the hotkey. Optional, the CLI works alone.

Roughly 300MB of model download and about 500MB resident while the daemon runs.

## Setup

```bash
git clone https://github.com/<YOUR_USER>/kokoro-reader
cd kokoro-reader
./setup.sh
```

`setup.sh` creates a venv, installs dependencies, and downloads plus warms the model.
Verify with:

```bash
./speak "if you can hear this, it works"
```

### Raycast

Raycast Settings → **Script Commands** → **Add Script Directory** → pick this repo's
`raycast/` folder. Four commands appear: Speak Clipboard, Pause / Resume, Stop, Status.
Assign hotkeys if you like, or just search for them.

Usage is ⌘C then the speak command. It reads the **clipboard**, not the selection,
deliberately — see *Why the clipboard* below.

## CLI

```bash
./speak "some text"      # speak an argument
pbpaste | ./speak        # speak stdin
./speak --toggle         # pause / resume
./speak --pause
./speak --resume
./speak --stop
./speak --status         # playing | paused | idle
```

The daemon starts on first use, which costs about 15 seconds while the model loads,
then stays warm until reboot. Every call after that is roughly half a second to first
sound. To make it survive reboots, add a launchd agent running
`.venv-mlx/bin/python speakd.py` with `RunAtLoad` and `KeepAlive`; that trades a
resident process for zero cold start.

## Dialogue renderer

For scripts with two speakers, one turn per line:

```
A|First speaker's line.
B|Second speaker's line.
```

```bash
./.venv-mlx/bin/python render_mlx.py script.txt
./.venv-mlx/bin/python render_mlx.py script.txt --speed 1.3 --gap 0.4
```

Writes `<script-basename>.wav` alongside. Non-default settings get suffixed into the
filename so you can bracket values without overwriting.

## Tuning

| Setting | Where | Default | What it does |
|---|---|---|---|
| `SPEED` | top of `speakd.py`, or `SPEAK_SPEED` env | 1.3 | prose pace; 1.0 is Kokoro's native rate |
| `JOIN_MS` | top of `speakd.py`, or `SPEAK_JOIN_MS` | 350 | silence between sentences |
| `VOICE` | top of `speakd.py`, or `SPEAK_VOICE` | `af_heart` | any Kokoro voice (`am_michael`, `bf_emma`, …) |
| `--speed` | `render_mlx.py` | 1.2 | dialogue pace, slower than prose on purpose |
| `--gap` | `render_mlx.py` | 0.5 | silence between speaker turns |

After editing `speakd.py`, run `pkill -f speakd.py`. The next call restarts it.

## Pronunciation hints

Technical vocabulary is the main thing the engine gets wrong: it reads "esbuild"
phonetically and "yml" as a word. Fix those in `lexicon.txt`, one `written = spoken`
rule per line:

```
esbuild = e s build
yml     = yamel
nginx   = engine x
```

Matching is case-insensitive and whole-word, so `esbuilder` and `myyml` are left
alone. Longest rule wins. The file is reloaded on every utterance, so edits take
effect immediately with no daemon restart.

These are plain text rewrites rather than phonemes. `esbuild = e s build` is easier to
read and edit than `[esbuild](/ˈiːɛsbɪld/)`, and it survives swapping the engine out.
Both `speak` and `render_mlx.py` apply the same file.

## Four non-obvious things this works around

Both were measured on an M3 Pro and cost real time to find. If you build something
similar, you will hit them.

**Kokoro pads every utterance with ~600ms of silence.** Leading and trailing. Generate
sentence by sentence and you get more than a second of dead air at each boundary before
any gap you configure. `trim()` in both scripts strips it, which is why `JOIN_MS` and
`--gap` mean what they say.

**`afplay` costs ~1.3s per invocation.** It takes 1.77 seconds to play a 0.5 second
file; the rest is process and audio-device startup. One `afplay` per sentence is
therefore unusable. `speakd.py` keeps a single `sounddevice` output stream open for the
life of the daemon and appends audio to it. Pause is a stream halt rather than a signal
to a child process, which is also more precise.

**A persistent output stream does not follow the default device.** The fix for the
previous problem causes this one. A `sounddevice` stream stays bound to whichever
output device was default when it opened, so connecting headphones mid-session sends
audio to the old device and you hear nothing. Everything reports healthy, because it
is: audio generates, buffers, and drains on schedule, just into the wrong place.
`Player.retarget()` checks the current default at the start of each utterance and
reopens if it changed.

The subtlety: PortAudio caches its device list when it initializes, so a long-lived
process keeps reporting the devices that existed at startup. `retarget()` calls
`sd._terminate()` and `sd._initialize()` before checking, or the check reads stale
data and never fires.

**GUI launchers run scripts without a locale, and `pbpaste` changes encoding.**
Raycast, Automator and friends give a script a bare environment with no `LC_CTYPE`.
`pbpaste` then emits Mac OS Roman instead of UTF-8, so a curly apostrophe arrives as
the single byte `0xD5`, which is not valid UTF-8. Decode that with
`errors="replace"` and "isn't" becomes `isn\ufffdt`; the phonemizer treats the unknown
character as a word break and reads it as "isn" plus the letter T, which sounds like
"isentee".

Fixed in two places, because either alone would do it and both are cheap:
`raycast/speak-clipboard.sh` exports `LC_CTYPE=UTF-8` so the bytes are right to begin
with, and `decode_request()` in `speakd.py` falls back to `mac_roman` rather than
substituting replacement characters. Anything that copies from a word processor,
Google Docs, Notion or Slack will hit this, since they all use typographic quotes.

## Why the clipboard

The obvious design is a macOS Service reading the current selection, and it does not
work. Two reasons, both dead ends:

- Automator Quick Actions installed by hand into `~/Library/Services` register with
  `pbs` but never appear in any app's Services menu. Survived a reboot. Never reached
  the script at all.
- Even working, Services cannot see Google Docs' selection, because Docs draws text in
  its own layer rather than a standard text view. Same for some Electron apps.

The clipboard costs one extra ⌘C and works everywhere. Don't spend an afternoon on
Services; this README is the record of that afternoon.

## Privacy

Everything runs on this machine. No network calls after the one-time model download,
so the text you read never leaves the Mac. That is the main reason to prefer this over
a hosted voice if you read anything confidential.

Nothing is written to disk by default. `SPEAK_DEBUG=1 speak "..."` appends a line per
call to `~/.cache/speakd/invocations.log` with a timestamp, a length, and the first 60
characters, which is useful when a hotkey silently does nothing or text arrives
mangled. Leave it off the rest of the time and delete the file when you are done:

```bash
rm -f ~/.cache/speakd/invocations.log
```

`~/.cache/speakd/speakd.log` holds the daemon's stderr (device changes, phonemizer
warnings, tracebacks). It does not record what you asked it to say.

## Known limitations

- **Heteronyms.** "lives", "read", "lead", "tear", "wind" and friends are disambiguated
  by part-of-speech tagging, which fails on unusual syntax. `lexicon.txt` cannot help:
  a rule has one spoken form, and these words have two depending on the sentence.
  Misaki supports inline overrides (`[lives](/lˈɪvz/)`) if you control the text, but
  you can't annotate something you just highlighted.
- **One voice for prose.** `speak` reads everything in `VOICE`. Two voices only apply
  to the dialogue renderer.
- **No speed change mid-playback.** Audio is generated ahead of the ear, so changing
  pace would mean discarding the buffer.
