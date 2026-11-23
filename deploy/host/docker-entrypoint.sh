#!/bin/sh
# A bind mount arrives owned by whoever created it — usually root — while the service
# runs as uid 10001. Creating a case then fails with "Permission denied", which the
# analyst sees as a modal on "New case". Take ownership once, then drop the privilege.
set -e

if [ "$(id -u)" = "0" ]; then
  for dir in /data/cases /data/plugins; do
    mkdir -p "$dir" 2>/dev/null || true
    owner="$(stat -c %u "$dir" 2>/dev/null || echo 0)"
    if [ "$owner" != "10001" ]; then
      echo "fireblade: $dir belonged to uid $owner; handing it to 10001 (once)" >&2
      chown -R 10001:10001 "$dir" 2>/dev/null \
        || echo "fireblade: could not take ownership of $dir; the service may not be able to write there" >&2
    fi
  done
  # Drop to the image's own user and become the command itself: no shell in between,
  # so a signal reaches the service rather than this script.
  exec python3 -c 'import os, sys
os.setgroups([])
os.setgid(10001)
os.setuid(10001)
os.execvp(sys.argv[1], sys.argv[1:])' "$@"
fi

exec "$@"
