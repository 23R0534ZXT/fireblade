#!/bin/bash
# Timeline Explorer, one file at a time, inside the console session.
# Each measurement is appended as soon as it ends, so stopping the loop loses nothing.
set -u
HOST=23R@192.168.1.167
OUT=/root/fb/bench/tle-results.jsonl
: > "$OUT"
run_one() {
  local rows="$1" limit="$2" csv out
  csv="C:\\Users\\23R\\fb-bench\\size-${rows}-1\\auth.log.csv"
  out="C:\\Users\\23R\\fb-bench\\tle-${rows}.json"
  echo "=== $rows rows (limit ${limit}s) ==="
  timeout $((limit + 200)) ssh -o BatchMode=yes "$HOST" \
    "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\23R\\fb-bench\\te_drive.ps1 -Csv \"$csv\" -Limit $limit -Out \"$out\""
  # Keep the picture of what the tool displayed, for the report.
  timeout 120 scp -q -o BatchMode=yes "$HOST:C:/Users/23R/fb-bench/tle-${rows}.png" "/root/shots/tle-${rows}.png"
  echo
}
run_one 1000000 900   | tee -a "$OUT"
run_one 4000000 900   | tee -a "$OUT"
run_one 16000000 1800 | tee -a "$OUT"
run_one 32000000 1800 | tee -a "$OUT"
echo "DONE"
