#!/usr/bin/env python3
"""Conservatively check public catalog URLs; access restrictions require review."""
import argparse
import concurrent.futures
import datetime
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "Awesome-Physical-RSI link checker (+https://github.com/Junzhou-Chen/Awesome-Physical-RSI)", "Range": "bytes=0-4095"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            sample = response.read(4096).decode("utf-8", errors="ignore").lower()
            challenge = any(x in sample for x in ("verify you are human", "<title>just a moment", "<title>captcha"))
            return {"url": url, "status": "review" if challenge else "reachable", "http_status": response.status,
                    "final_url": response.url, "note": "Possible access challenge" if challenge else ""}
    except urllib.error.HTTPError as e:
        return {"url": url, "status": "review", "http_status": e.code,
                "note": "HTTP response requires manual review; not proof of unavailability"}
    except Exception as e:
        return {"url": url, "status": "review", "http_status": None, "note": str(e)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=ROOT / "reports/link-check.json")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=12)
    ap.add_argument("--paper-only", action="store_true")
    args = ap.parse_args()
    if not 1 <= args.workers <= 8 or not 1 <= args.timeout <= 30:
        ap.error("workers must be 1–8 and timeout 1–30 seconds")
    papers = json.loads((ROOT / "data/papers.json").read_text())
    urls = {p["paper_url"] for p in papers if p.get("paper_url")}
    if not args.paper_only:
        urls |= {r["url"] for p in papers for r in p.get("resources", [])}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(lambda url: check(url, args.timeout), sorted(urls)))
    report = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "links": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(f"Checked {len(results)} URLs; {sum(r['status']=='reachable' for r in results)} reachable; "
          f"{sum(r['status']=='review' for r in results)} need review. Report: {args.output}")


if __name__ == "__main__":
    main()
