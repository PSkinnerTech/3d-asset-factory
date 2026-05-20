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
