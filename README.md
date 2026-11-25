# Scroll Sequences

Scroll-driven exploded-view product pages: Blender-rendered explode/reassemble animations, scrubbed on a canvas as you scroll. One repo, one GitHub Pages site, a picker page to choose the product.

- **Live site:** https://leftoverjacksons.github.io/scrollSequence/
- **Products:** listed in `products.json`, each in `products/<slug>/`
  - [Beacon V3](products/beacon-v3/) — [design notes](products/beacon-v3/DESIGN.md)
  - [Band V2](products/band-v2/) (draft) — [design notes](products/band-v2/DESIGN.md)
- **Shared player:** `shared/player.js` + `shared/player.css`
- **Conventions, pipeline, adding a product:** [DESIGN.md](DESIGN.md)

Preview locally from this folder with `python -m http.server 8766`, then open http://localhost:8766.
