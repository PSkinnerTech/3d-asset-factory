import base64
from pathlib import Path

from PIL import Image

from asset_factory.images import OpenAIImageGenerator


class FakeImageData:
    def __init__(self, b64_json: str):
        self.b64_json = b64_json


class FakeImageResponse:
    def __init__(self, b64_json: str):
        self.data = [FakeImageData(b64_json)]


class FakeImages:
    def __init__(self, b64_json: str):
        self.b64_json = b64_json
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return FakeImageResponse(self.b64_json)


class FakeClient:
    def __init__(self, b64_json: str):
        self.images = FakeImages(b64_json)


def tiny_png_b64() -> str:
    image = Image.new("RGB", (4, 4), color=(40, 80, 120))
    data = Path("tiny.png")
    image.save(data)
    raw = data.read_bytes()
    data.unlink()
    return base64.b64encode(raw).decode("ascii")


def test_generate_image_writes_prompt_and_png(tmp_path: Path):
    client = FakeClient(tiny_png_b64())
    generator = OpenAIImageGenerator(client=client)

    output = generator.generate(
        prompt="single isolated lever",
        image_path=tmp_path / "concept.png",
        prompt_path=tmp_path / "prompt.txt",
    )

    assert output.image_path == tmp_path / "concept.png"
    assert output.prompt_path == tmp_path / "prompt.txt"
    assert output.model == "gpt-image-2"
    assert (tmp_path / "concept.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "prompt.txt").read_text(encoding="utf-8") == "single isolated lever"
    assert client.images.calls[0]["model"] == "gpt-image-2"
    assert client.images.calls[0]["prompt"] == "single isolated lever"
