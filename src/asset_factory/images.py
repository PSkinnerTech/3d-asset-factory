from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import OpenAI


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
        image_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(base64.b64decode(b64_json))
        prompt_path.write_text(prompt, encoding="utf-8")
        return GeneratedImage(image_path=image_path, prompt_path=prompt_path, model=self.model)
