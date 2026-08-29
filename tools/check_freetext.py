#!/usr/bin/env python3
"""Gate a generated free-text answer (e.g. "Why [company]?") before it can auto-send.

Résumé text goes through presubmit_gate.py (deai_lint + claim_trace against MASTER).
A free-text FORM answer has no MASTER to diff against, so this is its equivalent gate —
the check a drafted paragraph must pass before Mode B is allowed to submit it unattended.
Two things, both drawn from the SAME source files a human would check against:

  1. NEVER-CLAIM terms — parsed from profile/answer_bank.md's "NEVER CLAIM" table
     (confirmed-false claims like OAuth, hands-on legal-tech). A generated answer that
     reintroduces one is a factual misstatement going out under the user's legal name.
  2. Banned AI-tell vocabulary — parsed from playbooks/why-this-company.md's
     "Banned vocabulary" list (passionate, thrilled, proven track record, ...).

Reads the lists live so it never drifts from the source of truth. Input is the answer
text: a file path, --text "...", or stdin. Prints each hit with its category; exit 0 =
clean (eligible to auto-send), exit 1 = a hit (park it for the user), exit 64 = bad usage.

  python tools/check_freetext.py answer.txt
  echo "...draft..." | python tools/check_freetext.py -
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEF_BANK = os.path.join(ROOT, "profile", "answer_bank.md")
DEF_BANNED = os.path.join(ROOT, "playbooks", "why-this-company.md")


def _section(md, header_regex):
    """Return the lines of the markdown section whose header matches, up to the next
    header of the same-or-higher level (or EOF)."""
    lines = md.splitlines()
    out, in_sec, sec_level = [], False, 99
    for ln in lines:
        m = re.match(r"^(#{1,6})\s", ln)
        if m and in_sec and len(m.group(1)) <= sec_level:
            break
        if m and re.search(header_regex, ln, re.I):
            in_sec, sec_level = True, len(m.group(1))
            continue
        if in_sec:
            out.append(ln)
    return out


def never_claim_terms(bank_path):
    if not os.path.exists(bank_path):
        return []
    sec = "\n".join(_section(open(bank_path, encoding="utf-8").read(), r"NEVER CLAIM"))
    terms = set()
    # table rows: first cell holds the bolded term, often with a parenthetical of sub-terms
    for row in re.findall(r"^\|(.+?)\|", sec, re.M):
        for bold in re.findall(r"\*\*(.+?)\*\*", row):
            terms.add(bold.strip())
        for paren in re.findall(r"\(([^)]+)\)", row):
            for sub in re.split(r"[,/]", paren):
                sub = sub.strip()
                if len(sub) >= 3:
                    terms.add(sub)
    return sorted(terms)


def banned_vocab(banned_path):
    if not os.path.exists(banned_path):
        return []
    sec = "\n".join(_section(open(banned_path, encoding="utf-8").read(), r"Banned vocabulary"))
    return sorted({t.strip() for t in re.findall(r"`([^`]+)`", sec) if t.strip()})


def hits(text, terms):
    low = text.lower()
    found = []
    for t in terms:
        # word-ish boundary so "GRC" doesn't fire inside "GRCsomething"; phrases match literally
        pat = r"(?<![A-Za-z0-9])" + re.escape(t.lower()) + r"(?![A-Za-z0-9])"
        if re.search(pat, low):
            found.append(t)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", help="text file, or '-' for stdin")
    ap.add_argument("--text", help="answer text inline (instead of a file)")
    ap.add_argument("--answer-bank", default=DEF_BANK)
    ap.add_argument("--banned-from", default=DEF_BANNED)
    a = ap.parse_args()

    if a.text is not None:
        text = a.text
    elif a.input == "-" or (a.input is None and not sys.stdin.isatty()):
        text = sys.stdin.read()
    elif a.input:
        if not os.path.exists(a.input):
            print(f"input not found: {a.input}", file=sys.stderr)
            sys.exit(64)
        text = open(a.input, encoding="utf-8").read()
    else:
        print("need an input file, --text, or piped stdin", file=sys.stderr)
        sys.exit(64)

    nc = hits(text, never_claim_terms(a.answer_bank))
    tell = hits(text, banned_vocab(a.banned_from))

    if nc:
        print("NEVER-CLAIM (factual — hard stop): " + ", ".join(nc))
    if tell:
        print("AI-tell vocabulary (voice): " + ", ".join(tell))
    if nc or tell:
        print("PARK — fix before it can auto-send.")
        sys.exit(1)
    print("clean — no never-claim term, no AI tell.")
    sys.exit(0)


if __name__ == "__main__":
    main()
