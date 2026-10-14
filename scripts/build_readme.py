#!/usr/bin/env python3
"""Generate the public README and coverage report from the curated catalog."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPO = "Junzhou-Chen/Awesome-Physical-RSI"
DATE = "2026-10-13"


def load():
    return (json.loads((ROOT / "data/papers.json").read_text()),
            json.loads((ROOT / "data/categories.json").read_text()),
            json.loads((ROOT / "data/manuscript_snapshot.json").read_text()))


def valid_url(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not re.search(r"[\s<>]", url)


def validate(papers, categories, snapshot):
    errors, ids = [], set()
    category_ids = {c["id"] for c in categories}
    for p in papers:
        key = p.get("id", "")
        if not key or key in ids:
            errors.append(f"Missing/duplicate id: {key}")
        ids.add(key)
        for field in ("title", "year", "focus"):
            if not p.get(field):
                errors.append(f"{key}: missing {field}")
        if p.get("category") not in category_ids:
            errors.append(f"{key}: unknown category {p.get('category')}")
        if p.get("paper_url") and (not valid_url(p["paper_url"]) or not p.get("paper_url_source")):
            errors.append(f"{key}: invalid paper URL or missing provenance")
        seen = set()
        for resource in p.get("resources", []):
            if resource.get("type") not in {"code", "project", "data", "model"}:
                errors.append(f"{key}: unsupported resource type")
            if not valid_url(resource.get("url", "")) or not valid_url(resource.get("source_url", "")):
                errors.append(f"{key}: invalid resource URL or missing evidence URL")
            pair = (resource.get("type"), resource.get("url"))
            if pair in seen:
                errors.append(f"{key}: duplicate resource {pair}")
            seen.add(pair)
        for url in p.get("verified_sources", []):
            if not valid_url(url):
                errors.append(f"{key}: invalid verification source")
    cited = [p for p in papers if p.get("in_manuscript")]
    expected_count = snapshot.get("catalog_cited_count", snapshot["cited_count"])
    if ids & set(snapshot.get("excluded_citation_keys", [])):
        errors.append("Catalog contains editorially excluded citations")
    if len(cited) != expected_count:
        errors.append(f"Snapshot/catalog coverage differs: {expected_count} vs {len(cited)}")
    if errors:
        raise ValueError("\n".join(errors))


def venue(p):
    if p.get("venue"):
        return p["venue"]
    text = p.get("venue_raw", "")
    if not text:
        return "Venue pending"
    if "arxiv" in text.lower():
        return "arXiv preprint"
    aliases = [("neural information processing", "NeurIPS"),
               ("learning representations", "ICLR"), ("robot learning", "CoRL"),
               ("international conference on machine learning", "ICML"),
               ("26th annual international conference on machine learning", "ICML"),
               ("robotics and automation letters", "RA-L"),
               ("robotics and automation", "ICRA"), ("intelligent robots and systems", "IROS"),
               ("computer vision and pattern recognition", "CVPR"),
               ("international conference on computer vision", "ICCV"),
               ("robotics: science and systems", "RSS"), ("robotics science and systems", "RSS"),
               ("transactions on robotics", "T-RO"), ("international journal of robotics research", "IJRR"),
               ("transactions on machine learning research", "TMLR")]
    for pattern, alias in aliases:
        if pattern in text.lower():
            return alias
    return text


def esc(value):
    return str(value).replace("|", "&#124;").replace("\n", " ").replace("[", "&#91;").replace("]", "&#93;")


def publication(p):
    text = venue(p)
    return text if re.search(r"\b(?:19|20)\d{2}\b", text) else f"{p['year']} · {text}"


def publication_year(p):
    years = re.findall(r"\b((?:19|20)\d{2})\b", p.get("venue", ""))
    return int(years[-1] if years else p["year"])


def anchor(title):
    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", title.lower()))


def stats(papers, categories, snapshot):
    types = Counter(r["type"] for p in papers for r in p.get("resources", []))
    return {"updated": DATE, "source_commit": snapshot["commit"], "papers": len(papers),
            "manuscript_citations": sum(p.get("in_manuscript", False) for p in papers),
            "source_manuscript_citations": snapshot["cited_count"],
            "excluded_citation_keys": snapshot.get("excluded_citation_keys", []),
            "paper_links": sum(bool(p.get("paper_url")) for p in papers),
            "papers_with_resources": sum(bool(p.get("resources")) for p in papers),
            "papers_with_code": sum(any(r["type"] == "code" for r in p.get("resources", [])) for p in papers),
            "resource_links": dict(sorted(types.items())),
            "source_reviewed_papers": sum(bool(p.get("verified_sources")) for p in papers),
            "category_counts": {c["id"]: sum(p["category"] == c["id"] for p in papers) for c in categories},
            "paper_links_pending": [p["id"] for p in papers if not p.get("paper_url")],
            "resource_links_pending": [p["id"] for p in papers if not p.get("resources")]}


def render(papers, categories, snapshot):
    s = stats(papers, categories, snapshot)
    lines = ["# Awesome Physical RSI", "",
             "**From Self-Improvement to Recursive Self-Improvement in Physical AI: A Survey**", "",
             "[![Paper](https://img.shields.io/badge/Paper-PDF-b31b1b)](paper/physical-rsi-survey.pdf) "
             f"[![Papers](https://img.shields.io/badge/papers-{s['papers']}-2563eb)](#paper-catalog) "
             f"[![Code](https://img.shields.io/badge/papers_with_code-{s['papers_with_code']}-0d9488)](#paper-catalog) "
             f"[![Stars](https://img.shields.io/github/stars/{REPO}?style=social)](https://github.com/{REPO}/stargazers)", "",
             "A companion reading list on how embodied systems acquire experience, construct feedback, and retain improvements to policies, memories, predictive models, and learning procedures. The catalog follows the survey's functional taxonomy and includes its foundational and digital precedents.", "",
             "[![Figure 1: Acting in the world, physical self-improvement, and toward physical RSI](assets/figure-1.png)](assets/figure-1.png)", "",
             "**Physical self-improvement (SI)** retains improvements to an embodied system. **Recursive self-improvement (RSI)** uses earlier improvement outcomes to revise the process that produces later gains. The survey proposes evaluating a revised process against its saved predecessor through subsequent learning under matched conditions and resources.", "",
             "## Updates", "",
             f"- **{DATE}** — Catalog: **{s['manuscript_citations']} / {snapshot['cited_count']}** manuscript citations indexed"
             + f", **{s['paper_links']}** paper links, and **{s['papers_with_resources']}** papers with linked resources (**{s['papers_with_code']}** with code).", "",
             "## Contents", "",
             "- [How to read the catalog](#how-to-read-the-catalog)", "- [Paper catalog](#paper-catalog)"]
    groups = list(dict.fromkeys(c["group"] for c in categories))
    for group in groups:
        lines.append(f"  - [{group}](#{anchor(group)})")
        for c in categories:
            if c["group"] == group:
                lines.append(f"    - [{c['title']} ({s['category_counts'][c['id']]})](#{anchor(c['title'])})")
    lines += ["- [Contributing](#contributing)", "- [Citation](#citation)", "- [Acknowledgments](#acknowledgments)", "",
              "## How to read the catalog", "",
              "- Each paper appears once under its primary contribution. Many papers support several functions; section-level cross-references are retained in the [machine-readable catalog](data/papers.json).", 
              "- **Paper titles** link to an original paper, publisher page, or author-hosted manuscript. **Code**, **Project**, **Data**, and **Models** link to associated resources supported by a source record. A code link does not imply that experiments have been reproduced.",
              "- **—** means that no associated resource link has been verified in this catalog. It does not mean that code or data is unavailable.",
              "- Publication labels come from the manuscript bibliography unless a primary source has been checked. **arXiv preprint** describes the version indexed here; it is not a claim about all later publication history. Link evidence and any metadata questions are recorded with each entry.",
              "- Inclusion records relevance to the survey. Digital agents, simulated methods, datasets, and runtime planners have distinct roles in this literature; inclusion alone does not establish physical RSI.", "",
              "## Paper catalog", ""]
    for group in groups:
        lines += [f"## {group}", ""]
        for c in categories:
            if c["group"] != group:
                continue
            entries = [p for p in papers if p["category"] == c["id"]]
            lines += [f"### {c['title']}", "", c["description"], "",
                      "| Paper | Year · venue / version | Focus | Resources |", "|:---|:---|:---|:---|"]
            for p in sorted(entries, key=lambda p: (-publication_year(p), p["title"].lower())):
                title = f"**{esc(p.get('display_title', p['title']))}**"
                if p.get("paper_url"):
                    title = f"[{title}]({p['paper_url']})"
                else:
                    title += "<br>Paper link pending"
                label = {"code": "Code", "project": "Project", "data": "Data", "model": "Models"}
                links = " · ".join(f"[{esc(r.get('label') or label[r['type']])}]({r['url']})" for r in sorted(p.get("resources", []), key=lambda r: (list(label).index(r["type"]), r["url"]))) or "—"
                lines.append(f"| {title} | {esc(publication(p))} | {esc(p['focus'])} | {links} |")
            lines += ["", "[↑ Contents](#contents)", ""]
    lines += ["## Contributing", "",
              "Corrections, official resource links, and relevant new papers are welcome through issues or pull requests. See [CONTRIBUTING.md](CONTRIBUTING.md) for the catalog schema and source requirements.", "",
              "## Citation", "",
              "Read the [survey PDF](paper/physical-rsi-survey.pdf). A formal citation will be added when available. Please cite the original papers for their methods and results.", "",
              "## Acknowledgments", "",
              "Original catalog text and maintenance scripts are released under the [MIT license](LICENSE). Linked papers, code, models, and datasets retain their respective licenses.", ""]
    return "\n".join(lines), s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="Fail if generated files are stale")
    args = ap.parse_args()
    papers, categories, snapshot = load()
    validate(papers, categories, snapshot)
    readme, coverage = render(papers, categories, snapshot)
    outputs = {ROOT / "README.md": readme, ROOT / "data/coverage.json": json.dumps(coverage, indent=2)+"\n"}
    stale = []
    for path, text in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(text)
    if stale:
        raise SystemExit("Generated files are stale: " + ", ".join(stale))
    print(f"Validated {len(papers)} papers across {len(categories)} categories; {coverage['paper_links']} paper links, {coverage['papers_with_code']} papers with code.")


if __name__ == "__main__":
    main()
