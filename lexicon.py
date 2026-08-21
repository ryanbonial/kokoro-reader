"""Pronunciation substitutions applied before text reaches the speech engine.

Rules live in lexicon.txt as `written = spoken`. They are plain text rewrites
rather than phonemes: "esbuild = e s build" is easier to read, edit, and reason
about than "[esbuild](/ˈiːɛsbɪld/)", and it survives an engine change.

Reloaded on every call, so editing lexicon.txt takes effect without restarting
the daemon.
"""
import re, pathlib

PATH = pathlib.Path(__file__).parent / "lexicon.txt"


def load():
    rules = []
    if not PATH.exists():
        return rules
    for line in PATH.read_text().splitlines():
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        written, spoken = line.split("=", 1)
        written, spoken = written.strip(), spoken.strip()
        if written:
            rules.append((written, spoken))
    rules.sort(key=lambda kv: -len(kv[0]))     # longest match wins
    return rules


def apply(text, rules=None):
    for written, spoken in (load() if rules is None else rules):
        # word-ish boundaries: don't fire inside a longer identifier
        text = re.sub(rf"(?<![\w-]){re.escape(written)}(?![\w-])", spoken, text, flags=re.I)
    return text
