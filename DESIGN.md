# Scroll Sequences — Shared Design

How this repo is laid out, the conventions every product follows, and how to add a new one.
Product-specific decisions (parts, explode rules, materials, timeline, callouts) live in each product's own `DESIGN.md`:

| Product | Folder | Design notes | Live page |
|---|---|---|---|
| Beacon V3 | `products/beacon-v3/` | [DESIGN.md](products/beacon-v3/DESIGN.md) | https://leftoverjacksons.github.io/scrollSequence/products/beacon-v3/ |
| Band V2 (draft) | `products/band-v2/` | [DESIGN.md](products/band-v2/DESIGN.md) | https://leftoverjacksons.github.io/scrollSequence/products/band-v2/ |

Add notes anywhere; the **Notes & requests** section at the bottom is for open ideas.

---

## 1. Repo layout

```
index.html              Product picker (landing page). Reads products.json.
products.json           The product list shown on the picker.
shared/
  player.js             Scroll-sequence player: frame preload, scroll → frame, callout placement
  player.css            Shared page styles + light/dark theme tokens
products/
  _template/index.html  Starting point for a new product page
  <slug>/
    index.html          Markup + window.SEQUENCE config (frame count, stops, callouts)
    DESIGN.md           That product's design notes
    <name>.blend        Blender scene (Git LFS)
    source/             Fusion exports (*.usdz, Git LFS) and dumps
    tools/              Blender scripts for this product (build, callouts, white render)
    frames/             Dark-background frames  frame_001.webp …
    frames_white/       White-background frames (optional)
    callouts.json       Anchor tracks + model mask from tools/callouts.py (optional)
```

Everything a product needs sits in its own folder, so products never collide and one can be removed by deleting its folder and its `products.json` entry.

## 2. The shared player

- A product page defines `window.SEQUENCE` and loads `../../shared/player.js` + `player.css`. The full config is documented at the top of `shared/player.js`; the short version:

  | Field | Meaning |
  |---|---|
  | `frameCount` | Frames per folder (`frame_001.webp` … ) |
  | `version` | Cache-buster. **Bump after every re-render** |
  | `renderSize` | Render resolution, e.g. `[1920, 1080]` |
  | `frameDirs` | `{ light: "frames_white", dark: "frames" }`; list only the themes you rendered |
  | `defaultTheme` | Theme without a `?theme=` param |
  | `stops` | Scroll pacing, `[scroll vh, frame]` pairs. Long spans over few frames make the page linger |
  | `callouts`, `calloutsFile`, `headlineFrames` | Optional labels with leader lines that track parts (see Beacon §10 for how placement works) |

- **Theme tokens** (`--bg`, `--accent`, …) are in `player.css`. A product with a different brand colour overrides them in a `<style>` in its own page. `--bg` must match the render background exactly, or the frame edges show.
- **Changing the player changes every product.** After editing `shared/`, check each product page, not just the one you were working on.

## 3. Pipeline (same for every product)

1. **Fusion → USD:** export the design as USD via the Fusion MCP, and dump every body's component path + bounding box (Fusion's exporters flatten the component tree; the dump rebuilds it). See Beacon §2.
   Fusion's USD export only writes **visible** bodies: hide what shouldn't be rendered before exporting.
2. **Blender rig:** the quickest start is a copy of an existing product's `.blend` with its parts deleted (keeps camera rig, lights, world, bloom and render settings). Band V2 was made this way. Copy `products/band-v2/tools/build_band.py` as the build script: it's the leaner of the two, with `reimport()` and `build()`. `RULES`, materials and timing are per product.
3. **Render** from the command line, from the product folder, with a relative output path:
   ```powershell
   & "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b "<name>.blend" -o "//frames/frame_###" -a
   ```
   EEVEE, 1920×1080, WebP q82 has worked well (~1 s/frame). Optionally render white frames with a copy of `tools/render_white.py`.
4. **Callouts (optional):** copy `tools/callouts.py`, define anchors, run `export_callouts()` in Blender → `callouts.json`.
5. **Page:** fill in `window.SEQUENCE` in the product's `index.html`.

Tool scripts find their files relative to the open `.blend` (`PROJECT = os.path.dirname(bpy.data.filepath)`), so copies work in any product folder without editing paths.

## 4. Adding a product

1. Create `products/<slug>/` (lowercase, dashes; it becomes the URL).
2. Copy `products/_template/index.html` into it and set the title, tagline and `SEQUENCE` config.
3. Add a `DESIGN.md` there (Beacon's is a good outline: files, source, what moves together, timeline, camera, lighting, materials, render, page).
4. Add an entry to `products.json`:
   ```json
   { "slug": "<slug>", "name": "Product Name", "tagline": "…", "poster": "frames_white/frame_090.webp", "status": "draft", "updated": "YYYY-MM-DD" }
   ```
   `poster` is a path inside the product folder (a mid-explode frame reads best). `status` is shown as a badge: `live` or `draft`.
5. Add a row to the product table at the top of this file.

## 5. Preview

Serve the **repo root** (pages load `../../shared/`):
```powershell
python -m http.server 8766
```
Then open http://localhost:8766 for the picker, or http://localhost:8766/products/<slug>/ directly. Don't open a page while its frames are rendering: the browser caches a mix of old and new frames under the same version.

## 6. Repo, storage & hosting

- **Repo:** https://github.com/leftoverjacksons/scrollSequence (branch `main`). Local working copy: `C:\Users\Travis\Scroll Sequence`.
- **Hosting:** GitHub Pages from `main` / root → https://leftoverjacksons.github.io/scrollSequence/ (the picker). Each product is at `/scrollSequence/products/<slug>/`. `.nojekyll` makes Pages serve files as-is.
- **Git LFS** holds `*.blend` and `*.usdz` (see `.gitattributes`). Frames are **not** in LFS on purpose: Pages doesn't serve LFS files, so `*.webp` must stay normal git files.
- **Size budget:** GitHub Pages sites are limited to about 1 GB, and the repo should stay under a few GB. Each 180-frame sequence is roughly 5–15 MB per theme, so dozens of products fit; the `.blend` and `.usdz` files (LFS) don't count toward the Pages site.
- **Ignored:** `*.blend1`, `render_log.txt`, `.claude/`.
- Commits use the GitHub noreply address `leftoverjacksons@users.noreply.github.com` (repo-local git config).
- **After a re-render:** bump `version` in that product's `index.html`, commit its frames, `callouts.json`, `index.html` and `.blend`, push. Pages redeploys in about a minute.

---

## Notes & requests

<!-- Add your notes here -->
