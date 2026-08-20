#!/usr/bin/env python3
"""speakd - a warm Kokoro daemon that speaks text sent to a unix socket.

Keeps the model, the phonemizer, and one audio output stream open, so a request
costs generation time only. Sentences are appended to a single stream rather
than played as separate processes: spawning `afplay` per sentence cost ~1.3s of
dead air at every boundary.

Protocol: one connection, one message, one short reply.
    <utf-8 text>   speak it, cancelling anything already playing
    __STOP__       stop and clear
    __PAUSE__      halt the stream, keeping the queued audio
    __RESUME__     carry on
    __TOGGLE__     pause if playing, resume if paused
    __STATUS__     -> playing | paused | idle

Run:  ./.venv-mlx/bin/python speakd.py
"""
import os, re, sys, queue, socket, signal, threading
import numpy as np, sounddevice as sd

SOCK = os.path.expanduser("~/.cache/speakd/speakd.sock")
SR = 24000
VOICE = os.environ.get("SPEAK_VOICE", "af_heart")
SPEED = float(os.environ.get("SPEAK_SPEED", "1.3"))
JOIN_MS = int(os.environ.get("SPEAK_JOIN_MS", "350"))   # breath between sentences


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def trim(a, thresh=0.005, keep_ms=15):
    """Strip Kokoro's ~600ms of leading/trailing padding."""
    loud = np.where(np.abs(a) > thresh)[0]
    if loud.size == 0:
        return a[:0]
    keep = int(SR * keep_ms / 1000)
    return a[max(0, loud[0] - keep) : min(len(a), loud[-1] + keep)]


class Player:
    """One persistent output stream fed from a growing buffer."""

    def __init__(self):
        self._buf = np.zeros(0, dtype=np.float32)
        self._lock = threading.Lock()
        self.paused = False
        self.stream = sd.OutputStream(samplerate=SR, channels=1, dtype="float32",
                                      blocksize=1024, callback=self._cb)
        self.stream.start()

    def _cb(self, outdata, frames, _time, _status):
        with self._lock:
            n = min(frames, len(self._buf))
            outdata[:n, 0] = self._buf[:n]
            outdata[n:, 0] = 0
            self._buf = self._buf[n:]

    def add(self, audio):
        with self._lock:
            self._buf = np.concatenate([self._buf, audio])

    def clear(self):
        with self._lock:
            self._buf = self._buf[:0]

    def pending(self):
        with self._lock:
            return len(self._buf)

    def pause(self):
        if not self.paused and self.pending():
            self.stream.stop()
            self.paused = True
        return self.status()

    def resume(self):
        if self.paused:
            self.stream.start()
            self.paused = False
        return self.status()

    def status(self):
        if not self.pending():
            return "idle"
        return "paused" if self.paused else "playing"


_lock = threading.Lock()
_job = 0
player: Player | None = None


def cancel():
    global _job
    with _lock:
        _job += 1
        jid = _job
    player.clear()
    if player.paused:
        player.stream.start()
        player.paused = False
    return jid


def stale(jid):
    with _lock:
        return jid != _job


def sentences(text):
    text = " ".join(text.split())
    out = []
    for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text):
        p = p.strip()
        if not p:
            continue
        while len(p) > 300:                 # long sentences stall first audio
            cut = p.rfind(", ", 0, 300)
            if cut < 60:
                break
            out.append(p[: cut + 1])
            p = p[cut + 2 :]
        out.append(p)
    return out


def speak(model, text, jid):
    join = np.zeros(int(SR * JOIN_MS / 1000), dtype=np.float32)
    for s in sentences(text):
        if stale(jid):
            return
        try:
            audio = trim(np.concatenate([
                np.asarray(r.audio, dtype=np.float32).reshape(-1)
                for r in model.generate(text=s, voice=VOICE, speed=SPEED, lang_code="a")
            ]))
        except Exception as e:
            log(f"generate failed: {e!r}")
            continue
        if stale(jid) or audio.size == 0:
            continue
        player.add(np.concatenate([audio, join]))
        # don't run far ahead of the ear: wait until under ~6s is queued
        while player.pending() > SR * 6 and not stale(jid):
            threading.Event().wait(0.1)


def main():
    global player
    os.makedirs(os.path.dirname(SOCK), exist_ok=True)
    if os.path.exists(SOCK):
        os.unlink(SOCK)

    from mlx_audio.tts.utils import load_model
    model = load_model("prince-canuma/Kokoro-82M")
    for _ in model.generate(text="Ready.", voice=VOICE, speed=SPEED, lang_code="a"):
        pass
    player = Player()
    log("speakd: warm")

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    os.chmod(SOCK, 0o600)
    srv.listen(8)
    signal.signal(signal.SIGTERM, lambda *_: (cancel(), sys.exit(0)))

    COMMANDS = {
        "__PAUSE__": lambda: player.pause(),
        "__RESUME__": lambda: player.resume(),
        "__TOGGLE__": lambda: player.resume() if player.paused else player.pause(),
        "__STATUS__": lambda: player.status(),
    }

    while True:
        conn, _ = srv.accept()
        try:
            buf = b""
            while chunk := conn.recv(65536):
                buf += chunk
            text = buf.decode("utf-8", "replace").strip()
            reply = ""
            if not text:
                pass
            elif text in COMMANDS:
                reply = COMMANDS[text]()
            elif text == "__STOP__":
                cancel()
                reply = "idle"
            else:
                jid = cancel()
                threading.Thread(target=speak, args=(model, text, jid), daemon=True).start()
                reply = "playing"
            conn.sendall(reply.encode())
        except Exception as e:
            log(f"request failed: {e!r}")
        finally:
            conn.close()


if __name__ == "__main__":
    main()
