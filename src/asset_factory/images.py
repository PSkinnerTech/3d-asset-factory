from __future__ import annotations

import base64
from binascii import Error as BinasciiError
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from openai import OpenAI
from PIL import Image, UnidentifiedImageError


class ImagesClient(Protocol):
    def generate(self, **kwargs: object) -> object:
        pass


class OpenAIClient(Protocol):
    images: ImagesClient


@dataclass(frozen=True)
class GeneratedImage:
    image_path: Path
    prompt_path: Path
    model: str


class OpenAIImageGenerator:
    def __init__(self, client: OpenAIClient | None = None, model: str = "gpt-image-2"):
        self.client = client or OpenAI()
        self.model = model

    def generate(self, prompt: str, image_path: Path, prompt_path: Path) -> GeneratedImage:
        response = self.client.images.generate(
            model=self.model,
            prompt=prompt,
            size="1024x1024",
        )
        data = getattr(response, "data", None)
        if not data:
            raise RuntimeError("OpenAI image generation returned no image data")
        b64_json = getattr(data[0], "b64_json", None)
        if not b64_json:
            raise RuntimeError("OpenAI image generation returned no b64_json image")
        try:
            raw = base64.b64decode(b64_json, validate=True)
        except (BinasciiError, ValueError) as exc:
            raise RuntimeError(
                "OpenAI image generation returned malformed base64 image data"
            ) from exc
        try:
            with Image.open(BytesIO(raw)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise RuntimeError("OpenAI image generation returned non-image bytes") from exc
        image_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(raw)
        prompt_path.write_text(prompt, encoding="utf-8")
        return GeneratedImage(image_path=image_path, prompt_path=prompt_path, model=self.model)
