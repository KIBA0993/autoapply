#!/usr/bin/env python3
"""ATS keyword-coverage check for a tailored resume.

The mechanical half of the check the ai-job-search project runs on its compiled PDF,
adapted for this setup: DOCX resumes + US Greenhouse/Lever/Ashby JDs.

Split of labor:
  - The AGENT extracts the keyword list from the JD (judgment) and passes it in.
  - THIS TOOL does the mechanical part: pull the resume's real text, match each
    keyword (verbatim + synonyms), and classify covered / synonym-only / missing.
  - The AGENT then annotates each `missing` as "have it" (add it) or "gap"
    (leave it, acknowledge in the cover note) using candidate_profile.json.

Never keyword-stuff. A gap gets acknowledged in framing, never faked in the resume.

Usage:
  python tools/ats_check.py <resume.docx> <keywords.json>

keywords.json:
  [
    {"term": "authentication", "priority": "required", "synonyms": ["authn", "auth"]},
    {"term": "A/B testing", "priority": "preferred", "synonyms": ["experimentation", "split test"]},
    ...
  ]
"""
import sys, re, json, zipfile, html


def resume_text(path):
    """Extract the resume's text the way an ATS parser sees it — from the docx XML,
    not textutil (which inserts spacing artifacts; see playbooks/tailoring.md)."""
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    # keep paragraph/tab boundaries so multi-word phrases survive
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", " ", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    # decode XML entities AFTER stripping tags, else "Trust &amp; Safety" never
    # matches the keyword "trust & safety" (silently undercounts every '&' term)
    text = html.unescape(text)
    # normalize whitespace and unicode punctuation
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)
    return text


def found(term, text_low):
    """Word-boundary match, tolerant of internal punctuation/spacing (A/B, ML-ops)."""
    t = term.lower().strip()
    # exact word-boundary first
    if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text_low):
        return True
    # flexible: collapse non-alphanumerics in both sides (matches "a/b testing" ~ "a b testing")
    flat_term = re.sub(r"[^a-z0-9]+", "", t)
    flat_text = re.sub(r"[^a-z0-9]+", "", text_low)
    return len(flat_term) >= 4 and flat_term in flat_text


def check(resume_path, keywords):
    text = resume_text(resume_path)
    low = text.lower()
    rows = []
    for kw in keywords:
        term = kw["term"]
        prio = kw.get("priority", "preferred")
        syns = kw.get("synonyms", [])
        if found(term, low):
            status, note = "covered", f'"{term}" present'
        else:
            hit = next((s for s in syns if found(s, low)), None)
            if hit:
                status, note = "synonym-only", f'has "{hit}" — prefer the posting term "{term}" if truthful'
            else:
                status, note = "missing", "agent: classify have-it vs gap against profile"
        rows.append({"term": term, "priority": prio, "status": status, "note": note})
    return rows


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    resume_path, kw_path = sys.argv[1], sys.argv[2]
    keywords = json.load(open(kw_path))
    rows = check(resume_path, keywords)

    order = {"covered": 0, "synonym-only": 1, "missing": 2}
    rows.sort(key=lambda r: (r["priority"] != "required", order[r["status"]], r["term"]))

    req = [r for r in rows if r["priority"] == "required"]
    req_cov = sum(1 for r in req if r["status"] == "covered")
    print(f"\nATS keyword coverage — {resume_path.split('/')[-1]}")
    print(f"Required covered verbatim: {req_cov}/{len(req)}" if req else "No required terms given")
    print("=" * 78)
    print(f"{'KEYWORD':30} {'PRIORITY':10} {'STATUS':13} NOTE")
    print("-" * 78)
    for r in rows:
        print(f"{r['term'][:29]:30} {r['priority']:10} {r['status']:13} {r['note'][:60]}")

    missing_req = [r["term"] for r in req if r["status"] == "missing"]
    if missing_req:
        print("\n⚠ Missing REQUIRED terms — agent must classify each:")
        for t in missing_req:
            print(f"   - {t}: is it 'missing (have it)' → add, or 'missing (gap)' → acknowledge?")


if __name__ == "__main__":
    main()
