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
