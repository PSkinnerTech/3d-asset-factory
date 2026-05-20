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
