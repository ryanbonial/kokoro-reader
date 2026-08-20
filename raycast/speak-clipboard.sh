#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title Speak Clipboard
# @raycast.mode silent
# @raycast.icon 🔊
# @raycast.packageName Speak
# @raycast.description Read the clipboard aloud with Kokoro

SPEAK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/speak"
pbpaste | "$SPEAK"
