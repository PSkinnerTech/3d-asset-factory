from pathlib import Path

from asset_factory.review import build_review_html, write_review_html


def test_build_review_html_contains_manifest_and_viewer():
    html = build_review_html(
        asset_id="chloroplast_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=["Science correctness needs review"],
    )

    assert "chloroplast_001" in html
    assert "image/concept.png" in html
    assert "optimize/asset.glb" in html
    assert "Science correctness needs review" in html
    assert "GLTFLoader" in html


def test_write_review_html(tmp_path: Path):
    path = write_review_html(
        tmp_path,
        asset_id="demo",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=False,
        warnings=["Bad silhouette"],
    )

    assert path == tmp_path / "reports" / "review.html"
    assert path.exists()
    assert "Bad silhouette" in path.read_text(encoding="utf-8")
