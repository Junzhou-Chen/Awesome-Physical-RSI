# Contributing

Contributions can correct paper metadata, add official code or project links, improve classifications, or propose related papers. Open an issue with the paper title and source links, or edit the catalog in a pull request.

## Source requirements

- Match the paper's title and identity using its publisher page, arXiv record, or author project.
- Link code, data, and models only when a paper, author project, or repository README connects the resource to the work. Record this evidence in `source_url`.
- Distinguish third-party implementations explicitly; do not label them as official code. The initial catalog lists associated author/project resources.
- Use a concise description of what the paper contributes. Do not treat a paper's use of “self-improving” as proof of RSI.
- Preserve publication/version uncertainty. Do not guess venue, acceptance status, DOI, dates, or missing links.

## Catalog entry

`data/papers.json` is the canonical catalog. Each paper has a stable `id`, one category from `data/categories.json`, a title, year, focus, and resource records. The `id` for a manuscript citation is its exact BibTeX key.

```json
{
  "id": "stable_citation_key",
  "title": "Paper title",
  "year": "2026",
  "category": "policy_updates",
  "focus": "A concise description of the learning mechanism",
  "paper_url": "https://original-paper-source.example/paper",
  "paper_url_source": "https://original-paper-source.example/paper",
  "resources": [
    {
      "type": "code",
      "url": "https://github.com/author/project",
      "source_url": "https://author-project.example/paper"
    }
  ],
  "verified_sources": ["https://author-project.example/paper"],
  "verification_notes": [],
  "in_manuscript": false
}
```

The example URLs illustrate the schema; replace them with verified sources. Resource types are `code`, `project`, `data`, and `model`. `label` can disambiguate multiple links of the same type. `venue` is an optional display override supported by a primary source; `venue_raw` preserves the bibliography metadata. `publication_status` and `verification_notes` record version questions. New community additions use `in_manuscript: false` until cited by the survey.

## Check a change

```bash
python3 scripts/build_readme.py
python3 scripts/build_readme.py --check
python3 -m unittest discover -s tests
```

Commit catalog changes together with the regenerated README and coverage report. Preserve source records when replacing links.
