from pathlib import Path

from PIL import Image

from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.pipeline import generate_asset
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
    assert (run_dir / "exports" / "web" / "asset.glb").exists()
    assert (run_dir / "exports" / "unity" / "asset.glb").exists()
    assert result.manifest.qa.passed is True
    assert result.manifest.provenance.openai_model == "fake-image-model"
    assert result.manifest.provenance.runner_type == "mock"
