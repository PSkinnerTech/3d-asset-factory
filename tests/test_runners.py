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
    assert '"runner_type": "mock"' in result.report_path.read_text(encoding="utf-8")
    assert result.runner_type == "mock"
    assert result.success is True
