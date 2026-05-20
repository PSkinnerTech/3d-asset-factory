# EdTech 3D Asset Factory

CLI-first developer tool for generating educational science 3D assets from checked-in specs.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## Commands

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml
asset-factory qa runs/chloroplast_001/<timestamp>
asset-factory export runs/chloroplast_001/<timestamp> --profile web
asset-factory review runs/chloroplast_001/<timestamp>
```

## Seed Specs

The `assets/seeds` directory contains 10 initial science specs:

- 5 conceptual assets for biology and physics.
- 5 realistic assets for biology and earth science.

Generate one with the mock runner:

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

Generate one with TRELLIS.2 once `TRELLIS2_COMMAND` and OpenAI credentials are configured:

```bash
TRELLIS2_COMMAND='python /path/to/trellis_generate.py {image} {output}' \
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

## Verified Local Workflow

Mock generation works without OpenAI credentials or TRELLIS.2:

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

Expected output:

```text
Generated run: runs/chloroplast_001/20260520T100148Z
```

The generated run contains:

```text
image/concept.png
image/prompt.txt
trellis/raw.glb
trellis/raw_report.json
optimize/asset.glb
previews/thumbnail.png
previews/turntable.webm
exports/web/asset.glb
exports/unity/asset.glb
exports/unreal/asset.glb
reports/qa.json
reports/review.html
manifest.json
```

Inspect the manifest:

```bash
python -m json.tool runs/chloroplast_001/20260520T100148Z/manifest.json | head -80
```

The manifest should include:

```json
{
  "asset": {
    "id": "chloroplast_001"
  },
  "education": {
    "style": "conceptual"
  },
  "provenance": {
    "runner_type": "mock"
  },
  "qa": {
    "passed": true
  }
}
```

OpenAI + TRELLIS.2 generation uses the same spec and run layout:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='python /path/to/trellis_generate.py {image} {output}'
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```
