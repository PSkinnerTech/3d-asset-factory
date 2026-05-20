import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from asset_factory.images import OpenAIImageGenerator


class FakeImageData:
    def __init__(self, b64_json: str | None):
        self.b64_json = b64_json


class FakeImageDataWithoutB64:
    pass


class FakeImageResponse:
    def __init__(self, data: list[object]):
        self.data = data


class FakeImages:
    def __init__(self, response: FakeImageResponse):
        self.response = response
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: FakeImageResponse):
        self.images = FakeImages(response)


def fake_client_with_b64(b64_json: str) -> FakeClient:
    return FakeClient(FakeImageResponse([FakeImageData(b64_json)]))


def tiny_png_b64() -> str:
    image = Image.new("RGB", (4, 4), color=(40, 80, 120))
    data = BytesIO()
    image.save(data, format="PNG")
    return base64.b64encode(data.getvalue()).decode("ascii")


def test_generate_image_writes_prompt_and_png(tmp_path: Path):
    client = fake_client_with_b64(tiny_png_b64())
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
    assert client.images.calls[0]["size"] == "1024x1024"


def test_generate_image_rejects_empty_data(tmp_path: Path):
    client = FakeClient(FakeImageResponse([]))
    generator = OpenAIImageGenerator(client=client)

    with pytest.raises(RuntimeError, match="returned no image data"):
        generator.generate(
            prompt="single isolated lever",
            image_path=tmp_path / "concept.png",
            prompt_path=tmp_path / "prompt.txt",
        )


@pytest.mark.parametrize("data_item", [FakeImageDataWithoutB64(), FakeImageData("")])
def test_generate_image_rejects_missing_b64_json(tmp_path: Path, data_item: object):
    client = FakeClient(FakeImageResponse([data_item]))
    generator = OpenAIImageGenerator(client=client)

    with pytest.raises(RuntimeError, match="returned no b64_json image"):
        generator.generate(
            prompt="single isolated lever",
            image_path=tmp_path / "concept.png",
            prompt_path=tmp_path / "prompt.txt",
        )


def test_generate_image_rejects_malformed_base64_without_writing_image(tmp_path: Path):
    client = fake_client_with_b64("not valid base64")
    generator = OpenAIImageGenerator(client=client)
    image_path = tmp_path / "concept.png"

    with pytest.raises(RuntimeError, match="malformed base64"):
        generator.generate(
            prompt="single isolated lever",
            image_path=image_path,
            prompt_path=tmp_path / "prompt.txt",
        )

    assert not image_path.exists()


def test_generate_image_rejects_non_image_bytes_without_writing_image(tmp_path: Path):
    client = fake_client_with_b64(base64.b64encode(b"not an image").decode("ascii"))
    generator = OpenAIImageGenerator(client=client)
    image_path = tmp_path / "concept.png"

    with pytest.raises(RuntimeError, match="returned non-image bytes"):
        generator.generate(
            prompt="single isolated lever",
            image_path=image_path,
            prompt_path=tmp_path / "prompt.txt",
        )

    assert not image_path.exists()
