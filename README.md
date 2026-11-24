# Beacon V3 — Exploded-View Scroll Sequence

Scroll-driven product page for the Beacon V3: a Blender-rendered explode/reassemble animation (180 WebP frames) scrubbed on a canvas as you scroll.

- **Live page:** https://leftoverjacksons.github.io/scrollSequence/
- **Page:** `index.html` + `frames/`
- **Scene:** `beacon_explode.blend` (Blender 5.1, via Git LFS)
- **Source model:** `source/*.usdz` (Fusion USD export, via Git LFS)
- **Rebuild script:** `tools/build_from_usd.py`
- **Design decisions:** [DESIGN.md](DESIGN.md)

Preview locally with `python -m http.server 8766`, then open http://localhost:8766.
