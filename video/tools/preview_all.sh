#!/bin/sh
# Preview-render every scene at 720p, no caching, into build/preview_v1 (parallel).
cd "$(dirname "$0")/.."
for f in scenes/s[0-9][0-9]_*.py; do
  c=$(grep -o -E '^class S[0-9]{2}[A-Za-z0-9]*\(SwarmScene\)' "$f" | sed -E 's/class ([A-Za-z0-9]+).*/\1/')
  ( .venv/bin/manim -qm --disable_caching --media_dir build/preview_v1 "$f" "$c" > "build/logs/v1_$(basename "$f" .py).log" 2>&1; echo "$c exit $?" ) &
done
wait
