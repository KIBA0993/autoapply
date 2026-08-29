#!/usr/bin/env python3
"""De-AI voice lint for a tailored resume — the style companion to claim_trace.py.

claim_trace guards truth (numbers + never-claim). This guards *voice*: it scans
the prose zones a tailoring run rewrites (Summary, Domain Expertise line, and
every bullet) for the tells that make text read as machine-written.

Grounded in two on-disk audits and 2025-26 web consensus:
  - gstack design-review: "No em dashes. No AI vocabulary: delve, crucial,
    robust, comprehensive, ... "
  - gstack money-content: 12-signal authenticity audit (vocabulary inflation,
    performative emotion, universal hedging).
  - Press/linguistics: em-dash overuse, the tricolon reflex, uniform sentences.

It does NOT touch titles, companies, dates, or section headers — those legitimately
use an en dash as a separator, which is not a prose tell.

Usage:  python tools/deai_lint.py <variant.docx>
Exit 1 if any banned token is found in a prose zone (CI-friendly).
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Tokens that read as AI. Em/en dash matched literally; the rest word-bounded so
# "at scale" never fires inside "that scaled".
BANNED = [
    "—", "–",
    "proven ability", "deep expertise", "at scale", "leverage", "robust",
    "seamless", "spanning", "delve", "showcase", "comprehensive", "crucial",
    "nuanced", "multifaceted", "pivotal", "landscape", "tapestry", "underscore",
    "foster", "intricate", "vibrant", "furthermore", "moreover", "additionally",
    "world-class", "cutting-edge", "state-of-the-art", "game-changer",
    "best-in-class", "track record", "spearhead", "driving ", "utilize",
]


def prose_zones(path):
    """Return (label, text) for every zone a tailoring run rewrites."""
    from docx import Document
    d = Document(path)
    out = []
    for i, p in enumerate(d.paragraphs):
        t = p.text.strip()
        if not t:
            continue
        if t.startswith("•"):
            out.append((f"bullet[{i}]", t))
        elif t.startswith("Domain Expertise"):
            out.append(("domain", t))
        elif i == 3:  # SUMMARY paragraph in this template
            out.append(("summary", t))
    return out


def scan(text):
    hits = []
    low = text.lower()
    for b in BANNED:
        if b in ("—", "–"):
            if b in text:
                hits.append(b)
        elif re.search(r"\b" + re.escape(b.strip()) + r"\b", low):
            hits.append(b.strip())
    return hits


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    print(f"\nDe-AI voice lint — {os.path.basename(path)}")
    print("=" * 78)
    fail = False
    for label, text in prose_zones(path):
        hits = scan(text)
        if hits:
            fail = True
            print(f"  ✗ {label:12} {', '.join(sorted(set(hits)))}")
            print(f"      …{text[:90]}…")
    if not fail:
        print("  ✓ clean — no em dashes, no AI-cliche vocabulary in any prose zone")
    print("=" * 78)
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
