from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.prompts import build_image_prompt


def make_spec(style: StyleMode) -> AssetSpec:
    return AssetSpec(
        id="chloroplast_001",
        subject=ScienceSubject.BIOLOGY,
        object="chloroplast",
        grade_band="6-8",
        style=style,
        learning_goal="Identify the outer membrane, stroma, thylakoids, and grana.",
        exports=[ExportProfile.WEB],
        qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
    )


def test_conceptual_prompt_prioritizes_readable_structure():
    prompt = build_image_prompt(make_spec(StyleMode.CONCEPTUAL))

    assert "single isolated chloroplast" in prompt
    assert "conceptual educational 3D asset reference" in prompt
    assert "simplified readable parts" in prompt
    assert "no labels" in prompt
    assert "plain neutral background" in prompt


def test_realistic_prompt_prioritizes_recognition():
    prompt = build_image_prompt(make_spec(StyleMode.REALISTIC))

    assert "single isolated chloroplast" in prompt
    assert "realistic educational 3D asset reference" in prompt
    assert "recognizable natural form" in prompt
    assert "no labels" in prompt
    assert "plain neutral background" in prompt
