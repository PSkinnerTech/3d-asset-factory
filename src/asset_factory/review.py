from __future__ import annotations

import html
import http.server
import json
import socketserver
from functools import partial
from pathlib import Path


def build_review_html(
    *,
    asset_id: str,
    concept_image: str,
    glb_path: str,
    thumbnail: str,
    qa_passed: bool,
    warnings: list[str],
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
    glb_url = json.dumps(f"../{glb_path}")

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
    #viewer {{
      min-height: 560px;
      background: #111827;
      border-radius: 8px;
      overflow: hidden;
    }}
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
    </aside>
    <section class="panel">
      <h2>3D Preview</h2>
      <div id="viewer"></div>
      <p class="path">GLB: {escaped_glb_path}</p>
      <p class="path">Thumbnail: {escaped_thumbnail}</p>
    </section>
  </main>
  <script type="module">
    import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js';
    import {{ GLTFLoader }} from 'https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/loaders/GLTFLoader.js';

    const viewer = document.getElementById('viewer');
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

    scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 3));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2);
    keyLight.position.set(3, 4, 2);
    scene.add(keyLight);

    const loader = new GLTFLoader();
    loader.load({glb_url}, (gltf) => {{
      scene.add(gltf.scene);
      renderer.setAnimationLoop(() => {{
        gltf.scene.rotation.y += 0.01;
        renderer.render(scene, camera);
      }});
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
    warnings: list[str],
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
        ),
        encoding="utf-8",
    )
    return path


def serve_review(run_dir: Path, port: int) -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=run_dir)
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving review for {run_dir} at http://localhost:{port}/reports/review.html")
        httpd.serve_forever()
