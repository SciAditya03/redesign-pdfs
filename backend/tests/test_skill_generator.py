import zipfile

import pytest

from app.schemas.analysis import (
    AnalysisResult,
    GenerationMetadata,
    ProjectInfo,
    SourceDocument,
)
from app.services.skill_generator import (
    REQUIRED_FILES,
    SKILL_DESCRIPTION,
    SKILL_NAME,
    SkillGenerationError,
    _pages,
    build_outputs,
    parse_frontmatter,
    render_files,
    validate_skill_md,
    verify_zip,
)
from tests import factories


def analysis() -> AnalysisResult:
    return AnalysisResult(
        project=ProjectInfo(
            id="a" * 32,
            depth="deep",
            created_at="2026-11-18T00:00:00+00:00",
            documents=[
                SourceDocument(role="content_authority", filename="catalogue|v2.pdf", page_count=2, size_bytes=1000),
                SourceDocument(role="design_authority", filename="brand.pdf", page_count=3, size_bytes=2000),
            ],
        ),
        content_analysis=factories.content_analysis(),
        design_analysis=factories.design_analysis(),
        comparative_analysis=factories.comparative_analysis(),
        generation_metadata=GenerationMetadata(model="m", sdk="s", started_at="t0", completed_at="t1", stages=[]),
    )


def test_skill_md_frontmatter_exact():
    files = render_files(analysis())
    fm = parse_frontmatter(files["SKILL.md"])
    assert fm == {"name": SKILL_NAME, "description": SKILL_DESCRIPTION}


def test_skill_md_contains_required_guidance():
    md = render_files(analysis())["SKILL.md"]
    for phrase in ("Content authority", "Design authority", "Do not summarise", "Validate the result", "Deliver",
                   "quality-control report", "does not assume", "#191F5B", "catalogue\\|v2.pdf"):
        assert phrase in md, phrase
    # Architecture is rendered in order, regardless of model output order.
    assert md.index("| 1 | Cover") < md.index("| 2 | Introduction")


def test_markdown_tables_escape_pipes():
    md = render_files(analysis())["CONTENT_STRUCTURE.md"]
    assert "Proteomics \\| Mass Spec" in md
    for line in md.splitlines():
        if line.startswith("| 1 | Proteomics"):
            # 8 columns → 9 unescaped pipes
            assert line.replace("\\|", "").count("|") == 9


def test_supporting_files_have_content():
    files = render_files(analysis())
    assert set(files) == set(REQUIRED_FILES)
    assert "not inferable" in files["DESIGN_ANALYSIS.md"]  # null HEX is not invented
    assert "- [ ] **LOD values** (high)" in files["QUALITY_CHECKLIST.md"]
    assert "Footnote marker" in files["QUALITY_CHECKLIST.md"]
    assert "Content denser than reference" in files["REDESIGN_STRATEGY.md"]


def test_build_outputs_zip(tmp_path):
    written = build_outputs(analysis(), ["skill_zip", "skill_md", "analysis_json"], tmp_path)
    assert written["skill_zip"] == f"{SKILL_NAME}.zip"
    with zipfile.ZipFile(tmp_path / written["skill_zip"]) as zf:
        assert all(n.startswith(f"{SKILL_NAME}/") for n in zf.namelist())
        assert len(zf.namelist()) == len(REQUIRED_FILES)
    verify_zip(tmp_path / written["skill_zip"])
    assert (tmp_path / written["skill_md"]).is_file()


def test_build_outputs_rejects_unknown(tmp_path):
    with pytest.raises(SkillGenerationError):
        build_outputs(analysis(), ["pptx"], tmp_path)
    with pytest.raises(SkillGenerationError):
        build_outputs(analysis(), [], tmp_path)


@pytest.mark.parametrize("bad", [
    "no frontmatter",
    "---\nname: x\n",
    "---\nname: Bad Name\ndescription: d\n---\n",
    "---\nname: ok\ndescription: has: colon\n---\n",
    "---\nname: ok\ndescription: d\nextra: 1\n---\n",
])
def test_validate_skill_md_rejects(bad):
    with pytest.raises(SkillGenerationError):
        validate_skill_md(bad)


def test_page_ranges():
    assert _pages([5, 1, 2, 3, 7, 8]) == "1–3, 5, 7–8"
    assert _pages([]) == "—"
