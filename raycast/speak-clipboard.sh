#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title Speak Clipboard
# @raycast.mode silent
# @raycast.icon 🔊
# @raycast.packageName Speak
# @raycast.description Read the clipboard aloud with Kokoro

# Raycast gives scripts a bare environment; without this pbpaste emits
# Mac OS Roman and every curly apostrophe arrives as an invalid byte.
export LC_CTYPE=UTF-8

SPEAK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/speak"
pbpaste | "$SPEAK"
