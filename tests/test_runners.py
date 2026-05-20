import json
from pathlib import Path

from PIL import Image

from asset_factory.runners.base import RunnerRequest
from asset_factory.runners.mock import MockRunner


def test_mock_runner_writes_raw_glb_and_report(tmp_path: Path):
    image_path = tmp_path / "concept.png"
    Image.new("RGB", (16, 16), color=(120, 80, 40)).save(image_path)
    output_dir = tmp_path / "trellis"

    result = MockRunner().run(
        RunnerRequest(concept_image=image_path, output_dir=output_dir, resolution=512)
    )

    assert result.raw_glb_path == output_dir / "raw.glb"
    assert result.report_path == output_dir / "raw_report.json"
    assert result.raw_glb_path.read_bytes()[:4] == b"glTF"
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["runner_type"] == "mock"
    assert report["runner_version"] == "0.1.0"
    assert report["resolution"] == 512
    assert report["concept_image"] == str(image_path)
    assert report["raw_glb"] == str(output_dir / "raw.glb")
    assert report["success"] is True
    assert result.runner_type == "mock"
    assert result.success is True
