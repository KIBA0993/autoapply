#!/usr/bin/env python3
"""Tamper-evident snapshots of the PII profile files that drive submitted-application content.

These files (`profile/answer_bank.md`, `profile/candidate_profile.json`) are gitignored — so
there is normally NO history to diff against when something looks off (this is exactly why the
2026-08-20 "was answer_bank.md tampered with?" question could not be answered from git). This
tool makes a **sealed copy + SHA-256 fingerprint** of each, so any later change is provable and
diffable in seconds.

Costs ~zero model tokens: it hashes/copies on disk and prints one line per file. It never loads
file *contents* into an agent's context — only `--check` diffs do, and only when you ask.

Usage:
  python tools/integrity_snapshot.py                 # take a snapshot (run this at run-start)
  python tools/integrity_snapshot.py --check         # compare current files to the last snapshot
  python tools/integrity_snapshot.py --list          # list stored snapshots

Exit: --check exits non-zero if any tracked file differs from the last snapshot.
Snapshots live in sources/integrity/<UTC-ts>/ (gitignored) with a manifest; latest.json points
at the newest. This is a local audit trail — never published (the sanitizer excludes sources/).
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INTEG_DIR = os.path.join(ROOT, "sources", "integrity")

# The files whose integrity is worth sealing before each run — the ones that decide what goes
# out under the user's legal name. Add here if a new PII source starts driving submitted content.
TRACKED = [
    "profile/answer_bank.md",
    "profile/candidate_profile.json",
]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def snapshot():
    ts = _now_ts()
    dest = os.path.join(INTEG_DIR, ts)
    os.makedirs(dest, exist_ok=True)
    manifest = {"created": ts, "files": {}}
    for rel in TRACKED:
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            print(f"  WARN: tracked file missing, skipped: {rel}", file=sys.stderr)
            continue
        digest = _sha256(src)
        st = os.stat(src)
        # copy the sealed content under a flattened name so the diff has a "before" to show
        shutil.copy2(src, os.path.join(dest, rel.replace("/", "__")))
        manifest["files"][rel] = {"sha256": digest, "size": st.st_size,
                                  "mtime": datetime.datetime.fromtimestamp(
                                      st.st_mtime, datetime.timezone.utc).isoformat()}
        print(f"  sealed {rel}  sha256={digest[:16]}…  ({st.st_size} bytes)")
    # write manifest atomically
    _atomic_json(os.path.join(dest, "manifest.json"), manifest)
    _atomic_json(os.path.join(INTEG_DIR, "latest.json"), {"latest": ts})
    print(f"snapshot {ts} -> {os.path.relpath(dest, ROOT)}")
    return ts


def _atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _latest_ts():
    p = os.path.join(INTEG_DIR, "latest.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("latest")


def check(max_diff_lines=200):
    ts = _latest_ts()
    if not ts:
        print("no snapshot yet — run `python tools/integrity_snapshot.py` first", file=sys.stderr)
        sys.exit(2)
    dest = os.path.join(INTEG_DIR, ts)
    with open(os.path.join(dest, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    print(f"comparing against snapshot {ts}")
    changed = False
    for rel, meta in manifest["files"].items():
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            print(f"  MISSING NOW: {rel} (was present at snapshot)")
            changed = True
            continue
        now = _sha256(src)
        if now == meta["sha256"]:
            print(f"  OK        {rel}  sha256={now[:16]}…")
            continue
        changed = True
        print(f"  CHANGED   {rel}  {meta['sha256'][:16]}… -> {now[:16]}…")
        sealed = os.path.join(dest, rel.replace("/", "__"))
        if os.path.exists(sealed) and rel.endswith((".md", ".json", ".csv", ".txt")):
            before = open(sealed, encoding="utf-8").read().splitlines(keepends=True)
            after = open(src, encoding="utf-8").read().splitlines(keepends=True)
            diff = list(difflib.unified_diff(before, after,
                        fromfile=f"snapshot/{rel}", tofile=f"current/{rel}"))
            if len(diff) > max_diff_lines:
                diff = diff[:max_diff_lines] + [f"... (+{len(diff) - max_diff_lines} more diff lines; "
                                                f"open the sealed copy in {os.path.relpath(dest, ROOT)})\n"]
            sys.stdout.writelines(diff)
    if changed:
        print("\nRESULT: files differ from the last snapshot — review the diff above. "
              "If the change was expected (your edits / the run's own writes), take a fresh "
              "snapshot; if not, investigate before submitting anything.")
        sys.exit(1)
    print("RESULT: all tracked files match the last snapshot.")


def list_snaps():
    if not os.path.isdir(INTEG_DIR):
        print("no snapshots yet")
        return
    latest = _latest_ts()
    for name in sorted(os.listdir(INTEG_DIR)):
        d = os.path.join(INTEG_DIR, name)
        if not os.path.isdir(d):
            continue
        tag = "  <- latest" if name == latest else ""
        print(f"  {name}{tag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare current files to the last snapshot")
    ap.add_argument("--list", action="store_true", help="list stored snapshots")
    a = ap.parse_args()
    if a.list:
        list_snaps()
    elif a.check:
        check()
    else:
        snapshot()


if __name__ == "__main__":
    main()
