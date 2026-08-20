#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title Speaking Status
# @raycast.mode inline
# @raycast.icon ℹ️
# @raycast.packageName Speak
# @raycast.description playing, paused or idle

SPEAK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/speak"
"$SPEAK" --status
