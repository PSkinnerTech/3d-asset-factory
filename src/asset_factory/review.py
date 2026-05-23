from __future__ import annotations

import html
import http.server
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path


class ReviewHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


@dataclass(frozen=True)
class ReviewExportLink:
    profile: str
    glb_path: str | None = None
    stl_path: str | None = None
    stl_report_path: str | None = None
    stl_warning_count: int = 0


_PROFILE_ORDER = {
    "web": 0,
    "unity": 1,
    "unreal": 2,
}


def _profile_value(profile: object) -> str:
    value = getattr(profile, "value", profile)
    return str(value)


def _profile_sort_key(profile: object) -> tuple[int, str]:
    value = _profile_value(profile)
    return (_PROFILE_ORDER.get(value, len(_PROFILE_ORDER)), value)


def _profile_label(profile: object) -> str:
    return _profile_value(profile).replace("_", " ").title()


def _resolve_export_dir(run_dir: Path, export_path: str | Path) -> Path:
    path = Path(export_path)
    if path.is_absolute():
        return path
    if path.parts[:1] == ("exports",):
        return run_dir / path
    return path


def _relative_existing_file(run_dir: Path, path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        return None


def _stl_warning_count(report_path: Path) -> int:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1
    warnings = report.get("warnings") if isinstance(report, dict) else None
    if not isinstance(warnings, list):
        return 1
    return len(warnings)


def collect_review_exports(
    run_dir: Path,
    exports: Mapping[object, str | Path],
) -> list[ReviewExportLink]:
    if not exports:
        return []

    exports_by_profile = {
        _profile_value(profile): export_path for profile, export_path in exports.items()
    }
    unknown_profiles = sorted(
        (profile for profile in exports_by_profile if profile not in _PROFILE_ORDER),
        key=_profile_sort_key,
    )
    ordered_profiles = [*_PROFILE_ORDER, *unknown_profiles]

    collected: list[ReviewExportLink] = []
    for profile in ordered_profiles:
        export_path = exports_by_profile.get(profile)
        if export_path is None:
            collected.append(ReviewExportLink(profile=_profile_label(profile)))
            continue

        export_dir = _resolve_export_dir(run_dir, export_path)
        glb_path = _relative_existing_file(run_dir, export_dir / "asset.glb")
        stl_path = _relative_existing_file(run_dir, export_dir / "asset.stl")
        stl_report_path = _relative_existing_file(run_dir, export_dir / "stl_report.json")
        collected.append(
            ReviewExportLink(
                profile=_profile_label(profile),
                glb_path=glb_path,
                stl_path=stl_path,
                stl_report_path=stl_report_path,
                stl_warning_count=_stl_warning_count(export_dir / "stl_report.json")
                if stl_path
                else 0,
            )
        )
    return collected


def _script_json(value: str) -> str:
    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _href(path: str) -> str:
    return html.escape(f"../{path}", quote=True)


def _export_badge(profile: str, label: str, path: str | None) -> str:
    escaped_label = html.escape(label, quote=True)
    escaped_profile = html.escape(profile, quote=True)
    if path is None:
        return (
            f'<span class="export-badge unavailable" '
            f'aria-label="{escaped_label} unavailable for {escaped_profile}">{escaped_label}</span>'
        )
    return f'<a class="export-badge" href="{_href(path)}" download>{escaped_label}</a>'


def _stl_warning_badge(count: int) -> str:
    if count <= 0:
        return ""
    label = "warning" if count == 1 else "warnings"
    return f'<span class="export-warning">{count} STL {label}</span>'


def _render_exports_panel(exports: Sequence[ReviewExportLink]) -> str:
    if not exports:
        return (
            '<section class="panel export-panel">\n'
            "        <h2>Exports</h2>\n"
            '        <p class="muted">No export packages were created for this run.</p>\n'
            "      </section>"
        )

    rows = []
    show_stl_note = False
    for export in exports:
        escaped_profile = html.escape(export.profile, quote=True)
        glb_badge = _export_badge(export.profile, "GLB", export.glb_path)
        stl_badge = _export_badge(export.profile, "STL", export.stl_path)
        report_link = ""
        if export.stl_report_path is not None:
            report_link = (
                f'<a class="export-badge" href="{_href(export.stl_report_path)}" '
                "download>STL report</a>"
            )
        warning_badge = _stl_warning_badge(export.stl_warning_count)
        show_stl_note = show_stl_note or export.stl_path is not None
        rows.append(
            '<div class="export-row">'
            f"<strong>{escaped_profile}</strong>"
            f'<div class="export-actions">{glb_badge}{stl_badge}{report_link}{warning_badge}</div>'
            "</div>"
        )

    note = ""
    if show_stl_note:
        note = (
            '<p class="export-note">'
            "STL exports are geometry-only and may need repair before 3D printing."
            "</p>"
        )

    return (
        '<section class="panel export-panel">\n'
        "        <h2>Exports</h2>\n"
        f"        {''.join(rows)}\n"
        f"        {note}\n"
        "      </section>"
    )


def build_review_html(
    *,
    asset_id: str,
    concept_image: str,
    glb_path: str,
    thumbnail: str,
    qa_passed: bool,
    warnings: Sequence[str],
    exports: Sequence[ReviewExportLink] = (),
) -> str:
    escaped_asset_id = html.escape(asset_id, quote=True)
    escaped_concept_image = html.escape(concept_image, quote=True)
    escaped_glb_path = html.escape(glb_path, quote=True)
    escaped_thumbnail = html.escape(thumbnail, quote=True)
    warning_items = "".join(f"<li>{html.escape(warning, quote=True)}</li>" for warning in warnings)
    if not warning_items:
        warning_items = "<li>No warnings reported.</li>"
    status_label = "Passed" if qa_passed else "Needs review"
    status_class = "passed" if qa_passed else "failed"
    glb_url = _script_json(f"../{glb_path}")
    exports_panel = _render_exports_panel(exports)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Review {escaped_asset_id}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #18212f;
      --muted: #5f6b7a;
      --line: #d8dee8;
      --paper: #ffffff;
      --canvas: #f4f6f8;
      --accent: #1b6b8f;
      --passed: #047857;
      --failed: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      background: var(--canvas);
      color: var(--ink);
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 20px 28px;
      background: var(--paper);
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 0; font-size: 1.35rem; }}
    h2 {{ font-size: 0.95rem; }}
    .muted {{ color: var(--muted); }}
    main {{
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      gap: 20px;
      padding: 20px;
    }}
    img {{
      display: block;
      width: 100%;
      border: 1px solid var(--line);
      background: white;
    }}
    ul {{ padding-left: 20px; color: var(--muted); }}
    button {{
      min-height: 36px;
      margin: 0 8px 8px 0;
      padding: 8px 12px;
      border: 1px solid #a9b4c2;
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }}
    button.primary {{
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }}
    .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .stack {{ display: grid; gap: 16px; }}
    .status {{
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 0.86rem;
      font-weight: 700;
    }}
    .status.passed {{ background: #dff7ea; color: var(--passed); }}
    .status.failed {{ background: #fde8e4; color: var(--failed); }}
    .export-panel {{ display: grid; gap: 12px; }}
    .export-row {{
      display: grid;
      gap: 8px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }}
    .export-row:first-of-type {{ padding-top: 0; border-top: 0; }}
    .export-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .export-badge {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 5px 9px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      color: var(--accent);
      font-size: 0.82rem;
      font-weight: 700;
      text-decoration: none;
    }}
    .export-badge.unavailable {{
      border-color: var(--line);
      color: var(--muted);
      background: var(--canvas);
    }}
    .export-warning {{
      color: var(--failed);
      font-size: 0.82rem;
      font-weight: 700;
    }}
    .export-note {{
      margin-bottom: 0;
      color: var(--muted);
      font-size: 0.86rem;
    }}
    #viewer {{
      position: relative;
      min-height: 560px;
      background: #111827;
      border-radius: 8px;
      overflow: hidden;
    }}
    #viewer-status {{
      position: absolute;
      left: 16px;
      right: 16px;
      bottom: 16px;
      color: #f9fafb;
      font-size: 0.9rem;
    }}
    #viewer-status.error {{ color: #fecaca; }}
    .path {{
      overflow-wrap: anywhere;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.86rem;
    }}
    @media (max-width: 800px) {{
      header {{ align-items: flex-start; flex-direction: column; }}
      main {{ grid-template-columns: 1fr; }}
      #viewer {{ min-height: 420px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escaped_asset_id}</h1>
    <div class="status {status_class}">QA {status_label}</div>
  </header>
  <main>
    <aside class="stack">
      <section class="panel">
        <h2>Concept Image</h2>
        <img src="../{escaped_concept_image}" alt="Concept image for {escaped_asset_id}">
      </section>
      <section class="panel">
        <h2>Warnings</h2>
        <ul>{warning_items}</ul>
      </section>
      <section class="panel">
        <h2>Review</h2>
        <button class="primary" type="button">Approve</button>
        <button type="button">Needs changes</button>
        <button type="button">Reject</button>
      </section>
      {exports_panel}
    </aside>
    <section class="panel">
      <h2>3D Preview</h2>
      <div id="viewer"><div id="viewer-status">Loading GLB...</div></div>
      <p class="path">GLB: {escaped_glb_path}</p>
      <p class="path">Thumbnail: {escaped_thumbnail}</p>
    </section>
  </main>
  <script type="importmap">
    {{
      "imports": {{
        "three": "https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/"
      }}
    }}
  </script>
  <script type="module">
    import * as THREE from 'three';
    import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
    import {{ GLTFLoader }} from 'three/addons/loaders/GLTFLoader.js';

    const viewer = document.getElementById('viewer');
    const viewerStatus = document.getElementById('viewer-status');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111827);

    const camera = new THREE.PerspectiveCamera(
      45,
      viewer.clientWidth / viewer.clientHeight,
      0.1,
      100
    );
    camera.position.set(2.5, 2, 2.5);

    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(viewer.clientWidth, viewer.clientHeight);
    viewer.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 3));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2);
    keyLight.position.set(3, 4, 2);
    scene.add(keyLight);

    function frameObject(object) {{
      const box = new THREE.Box3().setFromObject(object);
      const center = new THREE.Vector3();
      const size = new THREE.Vector3();
      box.getCenter(center);
      box.getSize(size);

      const maxSize = Math.max(size.x, size.y, size.z, 1);
      const fitDistance = maxSize / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
      const viewDirection = new THREE.Vector3(1, 0.8, 1).normalize();

      camera.position.copy(center).add(viewDirection.multiplyScalar(fitDistance * 1.6));
      camera.near = Math.max(fitDistance / 100, 0.001);
      camera.far = Math.max(fitDistance * 100, maxSize * 10);
      camera.lookAt(center);
      camera.updateProjectionMatrix();

      controls.target.copy(center);
      controls.update();
    }}

    const loader = new GLTFLoader();
    loader.load({glb_url}, (gltf) => {{
      viewerStatus.hidden = true;
      scene.add(gltf.scene);
      frameObject(gltf.scene);
      renderer.setAnimationLoop(() => {{
        controls.update();
        renderer.render(scene, camera);
      }});
    }}, undefined, () => {{
      viewerStatus.textContent = 'GLB failed to load';
      viewerStatus.classList.add('error');
    }});

    window.addEventListener('resize', () => {{
      camera.aspect = viewer.clientWidth / viewer.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(viewer.clientWidth, viewer.clientHeight);
    }});
  </script>
</body>
</html>
"""


def write_review_html(
    run_dir: Path,
    *,
    asset_id: str,
    concept_image: str,
    glb_path: str,
    thumbnail: str,
    qa_passed: bool,
    warnings: Sequence[str],
    exports: Sequence[ReviewExportLink] = (),
) -> Path:
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "review.html"
    path.write_text(
        build_review_html(
            asset_id=asset_id,
            concept_image=concept_image,
            glb_path=glb_path,
            thumbnail=thumbnail,
            qa_passed=qa_passed,
            warnings=warnings,
            exports=exports,
        ),
        encoding="utf-8",
    )
    return path


def serve_review(run_dir: Path, port: int) -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=run_dir)
    with ReviewHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving review for {run_dir} at http://127.0.0.1:{port}/reports/review.html")
        httpd.serve_forever()
