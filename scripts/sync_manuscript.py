#!/usr/bin/env python3
"""Read a LaTeX source tree; never write to the manuscript or its bibliography."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def clean_tex(text):
    text = re.sub(r"(?<!\\)%[^\n]*", "", text)
    # This reader supports literal disabled blocks, not arbitrary TeX conditionals.
    while re.search(r"\\iffalse\b", text):
        m = re.search(r"\\iffalse\b", text)
        depth, end = 1, None
        for token in re.finditer(r"\\if\w*\b|\\fi\b", text[m.end():]):
            depth += -1 if token.group() == r"\fi" else 1
            if depth == 0:
                end = m.end() + token.end()
                break
        if end is None:
            raise ValueError("Unclosed literal \\iffalse block")
        text = text[:m.start()] + text[end:]
    return text


def active_sources(folder, main):
    folder = folder.resolve()
    seen, records = set(), []
    def visit(path):
        path = path.resolve()
        if not path.is_relative_to(folder.resolve()):
            raise ValueError(f"Input outside manuscript: {path.name}")
        if path in seen:
            return
        seen.add(path)
        raw = path.read_text()
        text = clean_tex(raw)
        records.append((path.relative_to(folder).as_posix(), text, hashlib.sha256(raw.encode()).hexdigest()))
        for match in re.finditer(r"\\(?:input|include)\s*\{([^}]+)\}", text):
            name = match.group(1)
            if "#" in name:
                continue
            child = folder / name
            if not child.suffix:
                child = child.with_suffix(".tex")
            if not child.resolve().is_relative_to(folder):
                raise ValueError(f"Input outside manuscript: {name}")
            if not child.exists():
                raise ValueError(f"Missing active input: {name}")
            visit(child)
    visit(folder / main)
    return records


def citation_contexts(records):
    citations = {}
    for name, text, _ in records:
        events = list(re.finditer(r"\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}|\\cite\w*\*?(?:\s*\[[^\]]*\])*\s*\{([^}]+)\}", text))
        section = "Overview" if name.startswith("neurips") else "Taxonomy" if name.startswith("Figures") else ""
        for m in events:
            if m.group(1):
                section = m.group(1)
            else:
                context = re.sub(r"\s+", " ", text[max(0, m.start()-400):min(len(text), m.end()+180)])
                for key in m.group(2).split(","):
                    citations.setdefault(key.strip(), []).append({"file": name, "section": section, "context": context})
    return citations


def balanced(text, start):
    opening = text[start]
    if opening == '"':
        end = start + 1
        while end < len(text):
            if text[end] == '"' and text[end-1] != "\\":
                return text[start+1:end], end+1
            end += 1
    depth = 1
    for end in range(start+1, len(text)):
        if text[end-1] == "\\":
            continue
        depth += (text[end] == "{") - (text[end] == "}")
        if depth == 0:
            return text[start+1:end], end+1
    raise ValueError("Unbalanced BibTeX field")


def read_bib(text):
    entries, offset = {}, 0
    while m := re.search(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text[offset:]):
        kind, key = m.group(1).lower(), m.group(2)
        start = offset + m.start()
        brace = text.index("{", start)
        body, end = balanced(text, brace)
        body = body[body.index(",")+1:]
        fields, pos = {}, 0
        while f := re.search(r"(\w+)\s*=\s*", body[pos:]):
            name = f.group(1).lower()
            vstart = pos + f.end()
            if body[vstart] in '{"':
                value, pos = balanced(body, vstart)
            else:
                stop = body.find(",", vstart)
                pos = len(body) if stop == -1 else stop
                value = body[vstart:pos].strip()
            fields[name] = value
        if key in entries:
            raise ValueError(f"Duplicate bibliography key: {key}")
        entries[key] = {"entry_type": kind, **fields}
        offset = end
    return entries


def plain(value):
    value = value.replace(r"\&", "&").replace(r"\_", "_").replace(r"\%", "%")
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", value).strip()


def load_source(folder, main):
    records = active_sources(folder, main)
    citations = citation_contexts(records)
    bib_path = folder / "Reference.bib"
    bib = read_bib(bib_path.read_text())
    missing = set(citations) - set(bib)
    if missing:
        raise ValueError(f"Citations missing from bibliography: {sorted(missing)}")
    try:
        commit = subprocess.check_output(["git", "-C", str(folder), "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "-C", str(folder), "status", "--porcelain"], text=True).strip())
    except subprocess.CalledProcessError:
        commit, dirty = None, None
    info = {"repository": "https://github.com/Junzhou-Chen/Phy_RSI_Survey", "commit": commit,
            "working_tree_dirty": dirty, "main_file": main, "cited_count": len(citations),
            "bibliography_count": len(bib), "bib_sha256": hashlib.sha256(bib_path.read_bytes()).hexdigest(),
            "active_files": [{"path": n, "sha256": h} for n, _, h in records]}
    return bib, citations, info


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manuscript", type=Path, required=True)
    ap.add_argument("--main", default="neurips_2026.tex")
    ap.add_argument("--check", action="store_true", help="Report coverage and metadata drift without writing")
    args = ap.parse_args()
    bib, contexts, info = load_source(args.manuscript.resolve(), args.main)
    exclusions_path = ROOT / "data/excluded_papers.json"
    exclusions = set(json.loads(exclusions_path.read_text())) if exclusions_path.exists() else set()
    info["excluded_citation_keys"] = sorted(exclusions & contexts.keys())
    contexts = {key: value for key, value in contexts.items() if key not in exclusions}
    info["catalog_cited_count"] = len(contexts)
    dest = ROOT / "data/papers.json"
    old = json.loads(dest.read_text()) if dest.exists() else []
    excluded_present = sorted(p["id"] for p in old if p["id"] in exclusions)
    old = [p for p in old if p["id"] not in exclusions]
    by_key = {p["id"]: p for p in old}
    if args.check:
        cited = {p["id"] for p in old if p.get("in_manuscript", True)}
        drift = [k for k in contexts if k in by_key and any(by_key[k].get(f) != plain(bib[k].get(f, "")) for f in ("title", "year"))]
        report = {"manuscript_count": info["cited_count"], "eligible_count": len(contexts), "catalog_count": len(cited),
                  "excluded_citations": info["excluded_citation_keys"], "excluded_present": excluded_present,
                  "missing": sorted(set(contexts)-cited), "no_longer_cited": sorted(cited-set(contexts)), "metadata_changed": drift}
        print(json.dumps(report, indent=2))
        raise SystemExit(bool(report["missing"] or report["no_longer_cited"] or excluded_present or drift))
    result = []
    for key, b in bib.items():
        if key not in contexts:
            continue
        p = by_key.get(key, {"id": key, "category": "", "focus": "", "resources": [], "verification_notes": []})
        raw_venue = plain(b.get("booktitle", b.get("journal", "")))
        p.update(title=plain(b.get("title", "")), year=plain(b.get("year", "")),
                 venue_raw=raw_venue, in_manuscript=True,
                 manuscript_sections=sorted({c["section"] for c in contexts[key]}))
        if "paper_url" not in p:
            arxiv = re.search(r"(?:arXiv:|preprint\s+)([a-zA-Z.-]+/\d{7}|\d{4}\.\d{4,5})", raw_venue, re.I)
            p["paper_url"] = "https://arxiv.org/abs/" + arxiv.group(1) if arxiv else ""
            p["paper_url_source"] = "manuscript bibliography (arXiv identifier)" if arxiv else ""
        result.append(p)
    # Keep community additions and retired citations for deliberate review.
    for p in old:
        if p["id"] not in contexts:
            p["in_manuscript"] = False
            result.append(p)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    (ROOT / "data/manuscript_snapshot.json").write_text(json.dumps(info, indent=2)+"\n")
    print(f"Synced {len(contexts)} included citations; {len(info['excluded_citation_keys'])} editorial exclusions; bibliography left unchanged.")


if __name__ == "__main__":
    main()
