from pathlib import Path

import pytest
from PIL import Image

from asset_factory.manifest import read_manifest
from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.pipeline import generate_asset
from asset_factory.runners.base import RunnerRequest, RunnerResult
from asset_factory.runners.mock import MockRunner


class FakeImageGenerator:
    model = "fake-image-model"

    def generate(self, prompt: str, image_path: Path, prompt_path: Path):
        Image.new("RGB", (64, 64), color=(30, 90, 150)).save(image_path)
        prompt_path.write_text(prompt, encoding="utf-8")
        return type(
            "GeneratedImage",
            (),
            {"image_path": image_path, "prompt_path": prompt_path, "model": self.model},
        )()


class FailingRunner:
    def run(self, request: RunnerRequest) -> RunnerResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = request.output_dir / "failed_report.json"
        report_path.write_text('{"success": false}', encoding="utf-8")
        return RunnerResult(
            raw_glb_path=request.output_dir / "missing.glb",
            report_path=report_path,
            runner_type="fake",
            runner_version="0",
            success=False,
        )


def make_spec() -> AssetSpec:
    return AssetSpec(
        id="pulley_001",
        subject=ScienceSubject.PHYSICS,
        object="pulley",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Identify the wheel, axle, rope, and load.",
        exports=[ExportProfile.WEB, ExportProfile.UNITY],
        qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
    )


def test_generate_asset_creates_complete_run(tmp_path: Path):
    result = generate_asset(
        spec=make_spec(),
        root_dir=tmp_path,
        image_generator=FakeImageGenerator(),
        runner=MockRunner(),
        timestamp="20260520T120000Z",
    )

    run_dir = result.run_dir
    assert (run_dir / "image" / "concept.png").exists()
    assert (run_dir / "image" / "prompt.txt").exists()
    assert (run_dir / "trellis" / "raw.glb").exists()
    assert (run_dir / "optimize" / "asset.glb").exists()
    assert (run_dir / "previews" / "thumbnail.png").exists()
    assert (run_dir / "previews" / "turntable.webm").exists()
    assert (run_dir / "reports" / "review.html").exists()
    assert (run_dir / "exports" / "web" / "asset.glb").exists()
    assert (run_dir / "exports" / "unity" / "asset.glb").exists()
    assert read_manifest(run_dir / "manifest.json") == result.manifest
    assert result.manifest.qa.passed is True
    assert result.manifest.provenance.openai_model == "fake-image-model"
    assert result.manifest.provenance.runner_type == "mock"
    assert result.manifest.files.review_html == str(run_dir / "reports" / "review.html")
    assert result.manifest.files.exports == {
        ExportProfile.WEB: str(run_dir / "exports" / "web"),
        ExportProfile.UNITY: str(run_dir / "exports" / "unity"),
    }

    for profile in (ExportProfile.WEB, ExportProfile.UNITY):
        exported_manifest = read_manifest(run_dir / "exports" / profile.value / "manifest.json")
        assert exported_manifest.qa.passed is True
        assert exported_manifest.provenance.openai_model == "fake-image-model"
        assert exported_manifest.provenance.runner_type == "mock"
        assert exported_manifest.files.optimized_glb == "asset.glb"
        assert exported_manifest.files.thumbnail == "thumbnail.png"
        assert exported_manifest.files.turntable == "turntable.webm"
        assert exported_manifest.files.qa_report == "qa.json"
        assert exported_manifest.files.raw_glb is None
        assert exported_manifest.files.concept_image is None
        assert exported_manifest.files.review_html is None
        assert exported_manifest.files.exports == {profile: "."}


def test_generate_asset_skips_exports_when_qa_fails(tmp_path: Path):
    spec = make_spec().model_copy(update={"qa": QaThresholds(max_triangles=1, max_glb_mb=25)})

    result = generate_asset(
        spec=spec,
        root_dir=tmp_path,
        image_generator=FakeImageGenerator(),
        runner=MockRunner(),
        timestamp="20260520T120000Z",
    )

    assert result.manifest.qa.passed is False
    assert (result.run_dir / "reports" / "review.html").exists()
    assert result.manifest.files.exports == {}
    assert not (result.run_dir / "exports" / "web" / "asset.glb").exists()
    assert not (result.run_dir / "exports" / "unity" / "asset.glb").exists()


def test_generate_asset_raises_when_runner_fails(tmp_path: Path):
    with pytest.raises(RuntimeError, match="fake.*failed_report.json"):
        generate_asset(
            spec=make_spec(),
            root_dir=tmp_path,
            image_generator=FakeImageGenerator(),
            runner=FailingRunner(),
            timestamp="20260520T120000Z",
        )

    run_dir = tmp_path / "runs" / "pulley_001" / "20260520T120000Z"
    assert not (run_dir / "optimize" / "asset.glb").exists()
    assert not (run_dir / "exports" / "web" / "asset.glb").exists()
