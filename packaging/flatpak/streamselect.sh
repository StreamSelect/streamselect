#!/bin/sh
# Flatpak entry point: run StreamSelect from the source tree installed under
# /app/share/streamselect (see io.github.streamselect.StreamSelect.yml).
export PYTHONPATH="/app/share/streamselect${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m streamselect "$@"
