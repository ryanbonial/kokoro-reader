#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title Pause / Resume Speaking
# @raycast.mode silent
# @raycast.icon ⏯
# @raycast.packageName Speak
# @raycast.description Suspend or resume playback where it is

SPEAK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/speak"
"$SPEAK" --toggle
