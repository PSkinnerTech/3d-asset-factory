import json
from pathlib import Path

from asset_factory.review import build_review_html, serve_review, write_review_html


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
    assert '<script type="importmap">' in html
    assert '"three"' in html
    assert '"three/addons/"' in html
    assert "import * as THREE from 'three';" in html
    assert "import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';" in html


def test_build_review_html_renders_export_links():
    from asset_factory.review import ReviewExportLink

    html = build_review_html(
        asset_id="chloroplast_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
        exports=[
            ReviewExportLink(
                profile="Web",
                glb_path="exports/web/asset.glb",
                stl_path="exports/web/asset.stl",
                stl_report_path="exports/web/stl_report.json",
                stl_warning_count=2,
            )
        ],
    )

    assert "<h2>Exports</h2>" in html
    assert "Web" in html
    assert 'href="../exports/web/asset.glb"' in html
    assert 'href="../exports/web/asset.stl"' in html
    assert 'download>GLB</a>' in html
    assert 'download>STL</a>' in html
    assert 'href="../exports/web/stl_report.json"' in html
    assert "2 STL warnings" in html
    assert "STL exports are geometry-only and may need repair before 3D printing." in html


def test_build_review_html_marks_missing_export_formats_unavailable():
    from asset_factory.review import ReviewExportLink

    html = build_review_html(
        asset_id="pulley_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
        exports=[
            ReviewExportLink(
                profile="Unity",
                glb_path=None,
                stl_path="exports/unity/asset.stl",
            )
        ],
    )

    assert "Unity" in html
    assert 'aria-label="GLB unavailable for Unity"' in html
    assert (
        '<span class="export-badge unavailable" aria-label="GLB unavailable for Unity">'
        "GLB</span>"
    ) in html
    assert 'href="../exports/unity/asset.stl"' in html


def test_build_review_html_renders_export_empty_state():
    html = build_review_html(
        asset_id="failed_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=False,
        warnings=["QA failed"],
        exports=[],
    )

    assert "<h2>Exports</h2>" in html
    assert "No export packages were created for this run." in html


def test_build_review_html_escapes_export_content():
    from asset_factory.review import ReviewExportLink

    html = build_review_html(
        asset_id="demo",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
        exports=[
            ReviewExportLink(
                profile='Web <script>',
                glb_path='exports/web/asset" onclick="alert(1).glb',
            )
        ],
    )

    assert "Web &lt;script&gt;" in html
    assert 'href="../exports/web/asset&quot; onclick=&quot;alert(1).glb"' in html
    assert 'href="../exports/web/asset" onclick="alert(1).glb"' not in html


def test_collect_review_exports_finds_package_files_and_warning_counts(tmp_path: Path):
    from asset_factory.models import ExportProfile
    from asset_factory.review import ReviewExportLink, collect_review_exports

    export_dir = tmp_path / "exports" / "web"
    export_dir.mkdir(parents=True)
    (export_dir / "asset.glb").write_bytes(b"glb")
    (export_dir / "asset.stl").write_bytes(b"stl")
    (export_dir / "stl_report.json").write_text(
        json.dumps({"warnings": ["not watertight", "many bodies"]}),
        encoding="utf-8",
    )

    exports = collect_review_exports(tmp_path, {ExportProfile.WEB: export_dir})

    assert exports == [
        ReviewExportLink(
            profile="Web",
            glb_path="exports/web/asset.glb",
            stl_path="exports/web/asset.stl",
            stl_report_path="exports/web/stl_report.json",
            stl_warning_count=2,
        )
    ]


def test_collect_review_exports_keeps_stl_link_when_report_is_unreadable(tmp_path: Path):
    from asset_factory.models import ExportProfile
    from asset_factory.review import ReviewExportLink, collect_review_exports

    export_dir = tmp_path / "exports" / "unity"
    export_dir.mkdir(parents=True)
    (export_dir / "asset.stl").write_bytes(b"stl")
    (export_dir / "stl_report.json").write_text("{not-json", encoding="utf-8")

    exports = collect_review_exports(tmp_path, {ExportProfile.UNITY: export_dir})

    assert exports == [
        ReviewExportLink(
            profile="Unity",
            glb_path=None,
            stl_path="exports/unity/asset.stl",
            stl_report_path="exports/unity/stl_report.json",
            stl_warning_count=1,
        )
    ]


def test_collect_review_exports_does_not_link_outside_run_dir(tmp_path: Path):
    from asset_factory.models import ExportProfile
    from asset_factory.review import ReviewExportLink, collect_review_exports

    outside_dir = tmp_path.parent / "outside-export"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "asset.glb").write_bytes(b"glb")

    exports = collect_review_exports(tmp_path, {ExportProfile.UNREAL: outside_dir})

    assert exports == [ReviewExportLink(profile="Unreal")]


def test_build_review_html_frames_loaded_model_in_preview():
    html = build_review_html(
        asset_id="chloroplast_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
    )

    assert "function frameObject(object)" in html
    assert "new THREE.Box3().setFromObject(object)" in html
    assert "box.getCenter(center)" in html
    assert "box.getSize(size)" in html
    assert "camera.lookAt(center)" in html
    assert "camera.near" in html
    assert "camera.far" in html
    assert "import { OrbitControls } from 'three/addons/controls/OrbitControls.js';" in html
    assert "controls.target.copy(center)" in html
    assert "controls.update()" in html
    assert "frameObject(gltf.scene)" in html


def test_build_review_html_escapes_visible_html_content():
    html = build_review_html(
        asset_id='cell<&>"',
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=["Review <b>shape</b> & color"],
    )

    assert "cell&lt;&amp;&gt;&quot;" in html
    assert "Review &lt;b&gt;shape&lt;/b&gt; &amp; color" in html
    assert '<b>shape</b>' not in html


def test_build_review_html_escapes_glb_url_for_script_context():
    html = build_review_html(
        asset_id="demo",
        concept_image="image/concept.png",
        glb_path="optimize/foo</script><script>alert(1)</script>.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
    )

    assert "</script><script>" not in html
    assert "\\u003c/script\\u003e\\u003cscript\\u003e" in html


def test_serve_review_binds_to_localhost(monkeypatch, tmp_path: Path):
    captured = {}

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, address, handler):
            captured["address"] = address
            captured["handler"] = handler
            self.server_address = address

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def serve_forever(self):
            captured["served"] = True

    monkeypatch.setattr("asset_factory.review.ReviewHTTPServer", FakeServer)

    serve_review(tmp_path, 4321)

    assert captured["address"] == ("127.0.0.1", 4321)
    assert captured["served"] is True


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
