import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sync_manuscript import active_sources, citation_contexts, read_bib
from build_readme import validate, valid_url, venue


class SourceReaderTests(unittest.TestCase):
    def test_active_graph_excludes_comments_and_disabled_supplement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tex").write_text(r"""
% \citep{commented} \input{missing}
\citep[see][p. 2]{front}
\input{Content/section}
\iffalse
\citep{disabled}
\input{also-missing}
\iffalse \citep{nested} \fi
\fi
""")
            (root / "Content").mkdir()
            (root / "Figures").mkdir()
            (root / "Content/section.tex").write_text(r"\section{Learning}\citep{robot,meta}\input{Figures/tree}")
            (root / "Figures/tree.tex").write_text(r"\citet{taxonomy}")
            records = active_sources(root, "main.tex")
            self.assertEqual(set(citation_contexts(records)), {"front", "robot", "meta", "taxonomy"})
            self.assertEqual(len(records), 3)

    def test_inline_bib_and_nested_fields(self):
        entries = read_bib(r'''@article{one, title={A {Nested} Title}, year={2026}, journal={arXiv preprint arXiv:2607.07663}}
@inproceedings{two,
title="Quoted title", year=2025, booktitle={Proceedings}}
''')
        self.assertEqual(entries["one"]["title"], "A {Nested} Title")
        self.assertEqual(entries["two"]["year"], "2025")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_bib("@article{same,title={A}}\n@article{same,title={B}}")

    def test_escaping_input_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tex").write_text(r"\input{../outside}")
            with self.assertRaisesRegex(ValueError, "outside manuscript"):
                active_sources(root, "main.tex")


class CatalogValidationTests(unittest.TestCase):
    def test_robotics_letters_is_not_the_icra_conference(self):
        self.assertEqual(venue({"venue_raw": "IEEE Robotics and Automation Letters"}), "RA-L")
        self.assertEqual(venue({"venue_raw": "2024 IEEE International Conference on Robotics and Automation (ICRA)"}), "ICRA")

    def test_resource_requires_association_evidence(self):
        paper = {"id": "one", "title": "Title", "year": "2026", "focus": "Specific mechanism",
                 "category": "policy_updates", "in_manuscript": True,
                 "resources": [{"type": "code", "url": "https://github.com/author/code"}]}
        with self.assertRaisesRegex(ValueError, "missing evidence"):
            validate([paper], [{"id": "policy_updates"}], {"cited_count": 1})
        paper["resources"][0]["source_url"] = "https://author.example/paper"
        validate([paper], [{"id": "policy_updates"}], {"cited_count": 1})

    def test_http_and_credentials_are_rejected(self):
        self.assertFalse(valid_url("http://example.org"))
        self.assertFalse(valid_url("https://user:secret@example.org"))
        self.assertTrue(valid_url("https://arxiv.org/abs/2607.07663"))


if __name__ == "__main__":
    unittest.main()
