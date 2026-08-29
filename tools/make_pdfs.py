#!/usr/bin/env python3
"""Regenerate PDFs for the résumé variants — run this whenever the .docx change,
so the .docx and .pdf never drift apart.

Converter, most-reliable first:
  1. LibreOffice `soffice --headless` if installed — batch, no GUI state, rock solid.
  2. docx2pdf (drives Microsoft Word) — works but flaky: Word's AppleScript bridge
     wedges after an error and cascades. We isolate each file in its OWN subprocess
     and convert a temp COPY (so a variant left open in Word doesn't lock it).

If Word is wedged (its automation stops responding), some files will FAIL — quit
Word and re-run, or install LibreOffice (`brew install --cask libreoffice`) for a
converter that never wedges.

Usage:
  python tools/make_pdfs.py                 # all 9 category variants
  python tools/make_pdfs.py Fraud Risk ...  # only these
"""
import sys, os, shutil, subprocess, tempfile

RESUME_DIR = os.path.expanduser("~/Documents/Resume")
CATS = ["Fraud","Risk","Identity","Analytics","Pricing","Monetization",
        "Payments","Platform","AI_ML"]
NAME = "Candidate_Resume_%s"

SOFFICE_PATHS = ["soffice", "libreoffice",
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice"]


def find_soffice():
    for p in SOFFICE_PATHS:
        if os.path.isabs(p) and os.path.exists(p):
            return p
        if shutil.which(p):
            return p
    return None


def via_soffice(soffice, docx_paths):
    ok = []
    for src in docx_paths:
        r = subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                            "--outdir", RESUME_DIR, src],
                           capture_output=True, text=True, timeout=120)
        pdf = os.path.splitext(src)[0] + ".pdf"
        ok.append(os.path.exists(pdf) and os.path.getsize(pdf) > 1000)
    return ok


_W = (
 "import sys,os,shutil,tempfile\n"
 "from docx2pdf import convert\n"
 "src=sys.argv[1]; dst=sys.argv[2]\n"
 "d=tempfile.mkdtemp(); ts=os.path.join(d,'x.docx'); tp=os.path.join(d,'x.pdf')\n"
 "shutil.copy(src,ts)\n"
 "convert(ts,tp)\n"
 "ok=os.path.exists(tp) and os.path.getsize(tp)>1000\n"
 "if ok: shutil.move(tp,dst)\n"
 "shutil.rmtree(d,ignore_errors=True)\n"
 "sys.exit(0 if ok else 1)\n"
)

def via_word(docx_paths, retries=3):
    ok = []
    for src in docx_paths:
        dst = os.path.splitext(src)[0] + ".pdf"
        done = False
        for _ in range(retries):
            # fresh subprocess per attempt: a wedged Word can't cascade into the next
            p = subprocess.run([sys.executable, "-c", _W, src, dst],
                               capture_output=True, text=True)
            if p.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 1000:
                done = True
                break
        ok.append(done)
    return ok


def main():
    cats = sys.argv[1:] or CATS
    docx = [os.path.join(RESUME_DIR, NAME % c + ".docx") for c in cats]
    missing = [d for d in docx if not os.path.exists(d)]
    if missing:
        print("missing .docx:", *[os.path.basename(m) for m in missing]);
    docx = [d for d in docx if os.path.exists(d)]

    soffice = find_soffice()
    if soffice:
        print(f"converter: LibreOffice ({soffice})")
        results = via_soffice(soffice, docx)
    else:
        print("converter: docx2pdf / Microsoft Word (isolated subprocess per file)")
        results = via_word(docx)

    npass = sum(results)
    for d, ok in zip(docx, results):
        print(f"  {'OK ' if ok else 'FAIL'} {os.path.basename(os.path.splitext(d)[0])}.pdf")
    print(f"\n{npass}/{len(docx)} PDFs generated")
    if npass < len(docx):
        print("Some failed — if using Word, quit Word and re-run, or install LibreOffice.")
    sys.exit(0 if npass == len(docx) else 1)


if __name__ == "__main__":
    main()
