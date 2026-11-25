# Band V2 — Exploded-View Scroll Sequence

Design notes for the Band V2 strap-off + explode/reassemble animation and its scroll page.
All paths are relative to this folder (`products/band-v2/`). Shared conventions (player, pipeline, hosting) are in the [repo-level DESIGN.md](../../DESIGN.md).
**Status: second pass (2026-11-25).** Added: battery, LED-lit light-pipe ring, collision-free pogo pin moves, and the strap. Add notes anywhere; the **Notes & requests** section at the bottom is for open ideas.

---

## 1. Files

| File | What it is |
|---|---|
| `band_explode.blend` | Blender 5.1 scene. Started as a copy of `beacon_explode.blend` (camera rig, lights, world, bloom, render settings) with Beacon's parts removed |
| `source/BAND V2.usdz` | USD export from Fusion via the Fusion MCP, document **"BAND V2 - 2026 Cleanup for Renders"** (245 visible bodies) |
| `fusion_bodies.json` | Dump of every Fusion body (810, incl. hidden): component path, bbox (cm), appearance, `visible` |
| `logo_faces.json` | The 2 Top-shell faces painted "Enamel Glossy (Yellow)" in Fusion = the S logo |
| `tools/build_band.py` | Builds the whole rig from the USD: `reimport(); build()`. Also `check_collisions()` |
| `tools/strap.py` | Models and animates the strap (called by `build()`) |
| `tools/render_white.py` | White-background render (copy of Beacon's) |
| `frames/`, `frames_white/` | 300 frames each, 1920×1080 WebP |
| `index.html` | Page config for the shared player |

## 2. Source model

- **Fusion's USD export only writes visible bodies**, so what's shown in Fusion is what gets rendered. `identify()` matches only against `visible` bodies in the dump. All 245 matched by bounding box (worst 0.002 cm).
- **Hidden in Fusion, so not in the render:** `STRAP ADJUSTOR` + the CAD strap pieces (the rendered strap is modelled in Blender, §5), older board revisions (`mainBoard`, `mainBoard Beta`, `mainBoard_charlieRevision`), `Valencell Sensor`, `pogoPinPads`, and the hidden root bodies.
- **Device space = Fusion space in cm** (no axis swap, unlike Beacon): X across the pod (strap slots at ±X), Y along it (pogo pins and magnets at ±Y), **Z = thickness, +Z = top** (faceted face + logo). USD is the same axes in metres, so `M_USD_TO_DEVICE` is just ×100.
- Collections under **`BAND V2`** mirror the Fusion tree; objects keep `fusion_path`, `fusion_body`, `fusion_appearance`, `usd_name`.

## 3. What moves together

Rules (`RULES` in `tools/build_band.py`) match `<Fusion path>::<body>`; everything under a matched component moves together.

| Group | Fusion component | Move (cm) | Frames out / back |
|---|---|---|---|
| Top shell | `Top:1` | Z +5.8 | 92–128 / 208–236 |
| Main board | `mainBoard_Delta:1`: **always one unit** (133 bodies, never split) | Z +3.8 | 95–131 / 206–232 |
| Clear middle (light pipe) | `Clear Middle:1` | Z +2.3 | 98–134 / 204–230 |
| Battery | `803032 Batt:1` | Z +1.25 | 100–136 / 202–228 |
| Vibe motor | `Large Vibe Motor:1` | Z +0.6 | 102–136 / 200–226 |
| Magnets ×4 | | stay | |
| **Pogo pins ×4** | `Pogo Charge Target*` | **in along Y 0.45 → up 0.75 → out along Y 1.6** | 112–120–128–142 / 182–190–198–206 |
| Pin retainer | `Component187:1` (the plate the +Y pins pass through) | Same path as the +Y pins, but in 0.3 | same |
| Bottom shell | `Bottom:1` + `PhotoDiode Window` + `LED Window` | Z −3.6 | 132–158 / 166–190 |
| Flex | `flex_rev2 v3:1` | Z −1.0 | 132–158 / 166–190 |
| Sensor board | `SlateSafety Sensor REV B:1` | Z −1.9 | 132–158 / 166–190 |

**Why this order:** the pins sit in holes through the bottom shell's end walls (wall |y| 3.005–3.39, pin tips at 3.38).
- **Out:**
  1. The pins only back in once the battery has lifted clear of the +Y pins.
  2. They rise once the board and ring are above them.
  3. They slide out over the still-seated end wall.
  4. Only then does the bottom shell drop.
- **Back:** the exact reverse.

**Collisions are checked, not eyeballed:** `check_collisions()` tests the moving parts against every other part, per frame, ignoring contacts that already exist when assembled.
- **Current result:** no new contacts for the pins (every frame, 100–215) or the stack (every 3rd frame, 90–237).
- **Retainer limit:** retracting the retainer more than 0.3 cm hits the bottom shell's rib and the flex.

## 4. Timeline (300 frames @ 30 fps)

| Frames | What happens |
|---|---|
| 1–20 | Worn: strap looped as if around a wrist, camera pulled back and lower |
| 20–32 | Both strap ends peel off the hook-and-loop (§5) |
| 32–80 | Strap loop drops as one piece; the ends back out over the bars and down out of the slots; camera pushes in to the pod |
| 80–92 | Pod alone, assembled, ring glowing |
| 92–158 | Opens (order in §3); 360° spin 118–198 |
| 158–166 | Hold, fully exploded |
| 166–236 | Closes (exact reverse) |
| 236–284 | Strap comes back the way it left: the loop rises and the ends feed up through the slots and over the bars; camera pulls back out |
| 284–296 | The tails fold down and hook on |
| 296–300 | Worn again (matches frame 1) |

- **`BAND_root`** at the device centre (0.005, 0, 0.448); **`BAND_spin`** under it carries every part.
- **Camera** (`camera()`, `CAM_KEYS`): CamRig scale 1.45 and framing height z −2.4 while worn → 0.8 on the pod by frame 80 → 1.32 for the exploded stack (140–190) → 0.8 by 234 → back to the worn framing by 296.
- **View angle** (`camera_view()`, `VIEW_KEYS`):
  - **Head-on** (the Fusion view: from above the +Y pin end, 45° up, top logo upright) while worn, frames 1–20.
  - Eases on a sphere to the **3/4 view** by frame 80, while the strap comes off. That view is 28° up, between the +Y pin end and the +X slot, with the logo facing forward as in Fusion. It's only a ~30° turn from head-on, so the pod never swings round the back.
  - Holds the 3/4 view through the explode.
  - Eases back to head-on over 236–296 while the strap returns, and ends there.

## 5. Strap (`tools/strap.py`)

Not in CAD, so it's modelled in Blender: black woven elastic webbing, 3.5 cm × 0.16 cm, 23 cm long, with a 1.7 cm hook-and-loop patch at each end. Both patches carry the S logo (`BAND_StrapLogo_+X`, `BAND_StrapLogo_-X`: the Pantone S faces copied from the Top shell, 1.15 cm tall, bent by the same Curve modifier).
- The S's "up" points back toward the bar, so both read upright in the head-on camera once the tabs peel open.
- The two tails are mirror images, so the lateral sign flips per end. Both were checked against the strap's outward normal, so neither S is mirrored.

**How the real strap goes together** (from product photos): it's one strap. The wrist loop hangs below the pod; each end comes **up through its slot from underneath**, folds out over the slot's outer bar, and comes back down the outside, where its hook-and-loop patch grips the strap.

- **No cloth simulation.** The strap is a ribbon bent onto a path curve (`BAND_StrapPath`, hidden) by a Curve modifier. That keeps it exact and identical on every render.
- **The path follows the real geometry** measured from the bottom shell: slots are through-holes at |x| 2.85–3.35, |y| < 1.85, and the outer bar is at |x| 3.35–3.6, z −0.52…0.08. From the −X tip, the route goes over the −X bar, down through the slot, down the side, round a 6.2 cm-wide bottom arc, then up the +X side, through its slot, over its bar and onto the +X tail.
- **Animation** uses two curve shape keys plus a slide:
  1. **Peel** (20–32): both tails straighten and swing out 55° (`PEEL_DEG`). They hinge right where they come over the bar, with the bend spread over 0.45 cm (`BEND_LEN`), so the hook-and-loop lets go. When worn, each tail tucks in tight under its bar and ends about 2.6 cm down.
  2. **Drop** (32–80): the loop drops 26 cm (`DROP_MAX`). Its sides get longer, so the ribbon slides the same distance along the path using identical keyframes. Both ends therefore retreat back over the bars and down out of the slots in step, as one piece. The ends clear the slots after about 6 cm.
  3. Hidden 81–235.
  4. **Return** (236–296): the exact reverse. Drop goes back to 0 over 236–284, then Peel goes back to 0 over 284–296.
- **Checked:** no contact with any pod part, every 3rd frame over 1–55 and 240–300.
- **Tunables** at the top of `strap.py`: width, thickness, tab length, wrist size (`LOOP_C`, `LOOP_R`), tail length, `PEEL_DEG`, `BEND_LEN`, `DROP_MAX`, timing, `LOGO_ENDS`, `LOGO_H`.

## 6. Materials

| Material | Used for | Spec |
|---|---|---|
| `BAND_Black_Plastic` | Top, Bottom | Near-black (0.018), roughness 0.6 |
| `BEACON_Pantone165C` | S logo faces on Top | Same tuned Pantone 165 C as Beacon |
| **`BAND_LightPipe_Ring`** | Clear Middle | **Beacon's light-pipe recipe**: milky translucent PC whose emission (LED colour) is strongest at edges/grazing angles. Glow ×2.2 when assembled, ×0.45 while open |
| `BAND_LED_Emitter` | The 4 × `APFA2507` side-emitting LEDs, one mid-way along each main-board edge | Emission 30 in `LED_COLOR`. Each LED also has a small area light (`BAND_LED_Light_1–4`) facing outward into the ring |
| `BAND_Window` | Photodiode + LED windows | Dark clear glass |
| `BAND_Polyimide` | Flex | Translucent amber polyimide |
| `BAND_Magnet_Nickel` | Magnets | Nickel-plated metal |
| Brass | Pogo pins | Beacon's tuned brass |
| `BAND_Strap_Webbing`, `BAND_Strap_Tab` | Strap | Matte black fabric, dark sheen, ribbed weave bump (UVs in cm) |
| `BAND_auto_r_g_b` | Board components | From each part's USD colour by Beacon's class rules. Fusion tags most STEP parts "Steel - Satin", so that appearance is ignored |

- **`LED_COLOR`** = soft blue (linear 0.05, 0.38, 1.0), picked to match the edge glow in the product photo. Change it in `build_band.py` and rebuild.
- Bloom threshold 6 (as Beacon): the LEDs and ring edges bloom.

## 7. Render

From this folder (about 5–6 min per theme for 300 frames):
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b band_explode.blend -o "//frames/frame_###" -a
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b band_explode.blend --python tools/render_white.py -a
```

## 8. Scroll page (`index.html`)

- Shared player, 300 frames, light theme by default (`?theme=dark` for dark). `version` 7.
- **Pacing (`stops`):** a short worn hold, the strap removal over ~2 screens, then the explode, a linger on the hold, then reassembly.
- **No callouts yet.** Candidates:
  - optical sensor + windows (AFE4410 PPG front end)
  - LED light ring
  - vibe motor
  - battery
  - magnetic charging (magnets + pogo pins)
  - main board (nRF9160 LTE-M/GPS)

## 9. Open questions

- Is the LED colour right (soft blue), or should it match a specific status colour?
- Strap dimensions: 3.5 cm × 28.4 cm is a guess from the slot size and the photos.
- Tagline "Wearable physiological monitor" is a placeholder.

---

## Notes & requests

<!-- Add your notes here -->
