#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title Stop Speaking
# @raycast.mode silent
# @raycast.icon ⏹
# @raycast.packageName Speak
# @raycast.description Stop playback and clear

SPEAK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/speak"
"$SPEAK" --stop
