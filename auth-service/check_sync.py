#!/usr/bin/env python3
"""Diff this repo's auth-service/ deployer files against
belchamber-plugins-private's copy, the sibling repo one level up.

wp-auth-service is the one plugin publish-plugin.ps1 explicitly does NOT
keep in sync automatically (see that script's own comment) -- it is a
deliberate bundled exception, not a per-plugin case like every other
plugin here. Nothing currently re-runs this on a schedule; it is a
lazy-man check, run by hand before or after touching deploy_plugin.py or
_credentials.py, the same spirit as db/backup_db.py's lazy staleness
check elsewhere on this drive -- cheap to run, costs nothing if nobody
asks for it.

Usage:
    python check_sync.py
"""
from __future__ import annotations

import filecmp
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIBLING = HERE.parent.parent / "belchamber-plugins-private" / "auth-service"

FILES_TO_CHECK = ["deploy_plugin.py", "_credentials.py"]


def main() -> int:
    if not SIBLING.is_dir():
        print(f"Sibling repo not found at {SIBLING} -- nothing to compare against.", file=sys.stderr)
        return 1

    drifted = []
    for name in FILES_TO_CHECK:
        mine = HERE / name
        theirs = SIBLING / name
        if not mine.is_file():
            print(f"MISSING here: {name}")
            drifted.append(name)
            continue
        if not theirs.is_file():
            print(f"MISSING in belchamber-plugins-private: {name}")
            drifted.append(name)
            continue
        if not filecmp.cmp(mine, theirs, shallow=False):
            print(f"DRIFTED: {name}")
            drifted.append(name)
        else:
            print(f"OK: {name}")

    if drifted:
        print(f"\n{len(drifted)} file(s) out of sync with {SIBLING}.")
        print("Copy the current version by hand in whichever direction is correct -- "
              "there is no automated sync for this pair.")
        return 1

    print(f"\nAll checked files match {SIBLING}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
