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
| 20–36 | Both tabs come off the hook-and-loop and swing up, rigid, until they stand straight up in line with the strap (§5) |
| 36–80 | The whole strap pulls straight down out of the slots; camera pushes in to the pod |
| 80–92 | Pod alone, assembled, ring glowing |
| 92–158 | Opens (order in §3); 360° spin 118–198 |
| 158–166 | Hold, fully exploded |
| 166–236 | Closes (exact reverse) |
| 236–282 | Strap comes back the way it left: it rises straight up, tabs pointing up, until each tab has fully passed through its slot; camera pulls back out |
| 282–296 | The webbing bends over the bars and lays the tabs flat onto the strap |
| 296–300 | Worn again (matches frame 1) |

- **`BAND_root`** at the device centre (0.005, 0, 0.448); **`BAND_spin`** under it carries every part.
- **Camera** (`camera()`, `CAM_KEYS`): CamRig scale 1.45 and framing height z −2.4 while worn → 0.8 on the pod by frame 80 → 1.32 for the exploded stack (140–190) → 0.8 by 234 → back to the worn framing by 296.
- **View angle** (`camera_view()`, `VIEW_KEYS`):
  - **Head-on** (the Fusion view: from above the +Y pin end, 45° up, top logo upright) while worn, frames 1–20.
  - Eases on a sphere to the **3/4 view** by frame 80, while the strap comes off. That view is 28° up, between the +Y pin end and the +X slot, with the logo facing forward as in Fusion. It's only a ~30° turn from head-on, so the pod never swings round the back.
  - Holds the 3/4 view through the explode.
  - Eases back to head-on over 236–296 while the strap returns, and ends there.

## 5. Strap (`tools/strap.py`)

Not in CAD, so it's modelled in Blender.

**How the real strap goes together:**
- It's one strap of black woven elastic webbing, 3.5 × 0.16 cm and 24.8 cm long.
- Each end is thin webbing that comes up through its slot from underneath, wraps out over the slot's outer bar and tucks back in under it.
- It ends in a **rigid padded tab** (2.2 cm long, 0.36 cm thick) that lies flat on the outside of the strap.
  - The tab's back is **hook-and-loop**.
  - Its front is a **faux-leather patch, stitched on**, printed with the S logo.
  - As on the real patch, the S lies sideways: seen from outside with the bar at the top, the orange "roof" piece points right and the grey lower piece is on the left.
- **The tab never bends; only the thin webbing does.**

**How it's modelled:**
- **No cloth simulation.** The strap is a ribbon bent onto a path curve (`BAND_StrapPath`, hidden) by a Curve modifier. That keeps it exact and identical on every render.
- **Thickness:** Solidify uses the `Tab` vertex group. The tabs are `THICK_T` and the rest is `STRAP_T`, ramping over 0.2 cm on the webbing side.
- **Material slots:** Solidify puts the outer (+Y) shell at slot index + 2 and the rims at + 4. The slots are fabric, velcro, fabric, leather, fabric, fabric. The result is fabric everywhere, velcro on the tab backs and leather on the tab fronts.
- **The path follows the real geometry** measured from the bottom shell: slots are through-holes at |x| 2.85–3.35, |y| < 1.85, and the outer bar is at |x| 3.35–3.6, z −0.52…0.084.
  - The tab (0.36 cm) passes through the 0.5 cm slot.
  - The webbing's wrap centre (`WRAP_Z` 0.03) and radius are set so the bar top sits inside its inner radius.
- **End shape** is a turning-angle profile along its length (`_tab_profile()`): webbing straight up through the slot, a half turn over the bar, down the outside to `DOWN_Z`, an S-bend in, then the tab with zero turning, so it stays rigid.
  - Multiplying every turn by *u* (1 = worn, 0 = straight up) unfolds the webbing without stretching. The tab just swings, rigid.
  - The curve stores *u* = 0.875 … 0 as shape keys `Fold_875` … `Fold_000`. These are blended in neighbouring pairs and keyed every frame.
- **Logo** (`BAND_StrapLogo_+X`, `BAND_StrapLogo_-X`):
  - It's the logo faces copied from the Top shell, split into their two pieces (roof orange, lower piece grey).
  - It's 1 cm across the strap and centred on the tab. It's triangulated and subdivided while flat.
  - The lateral sign flips per end, so neither S is mirrored. Both ends were checked against a photo of the real patch.

**Animation:**
1. **Unfold** (20–36): the webbing unbends and each tab swings up, rigid, until it stands straight up in line with the strap.
2. **Pull down** (36–80): the loop's `Drop` shape key lowers it by 26 cm (`DROP_MAX`) while the ribbon slides the same distance along the path, using identical keyframes.
   - Above the slots the path is now straight, so the whole strap moves straight down as one piece.
   - The tabs pass down through the slots and clear them after about 4 cm.
3. Hidden 81–235.
4. **Return** (236–296): the exact reverse. The strap rises with the tabs pointing up (236–282). Once each tab has fully passed through its slot, the webbing bends over the bar and lays the tab flat onto the strap (282–296).

**Checked:** no contact with any pod part on every frame of 1–61 and 240–300.

**Tunables** at the top of `strap.py`: `STRAP_W`, `STRAP_T`, `THICK_T`, `RAMP`, `TAB_LEN`, the end profile (`WRAP_Z`, `WRAP_R`, `DOWN_Z`, `TUCK_DZ`), wrist size (`LOOP_C`, `LOOP_R`), `DROP_MAX`, timing, `LOGO_ENDS`, `LOGO_H`.

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
| `BAND_Strap_Webbing` | Whole strap | Black woven fabric: diagonal twill ribs (0.12 cm) over a fine cross weave, with sheen. UVs in cm |
| `BAND_Strap_Leather` | Front of each tab | Faux leather, pebble grain, satin. Dashed dark-grey stitching inset 0.13 cm from the patch edge ("Patch" UVs: cm from the tip) |
| `BAND_Strap_Velcro` | Back of each tab | Hook-and-loop: dark, fuzzy, rough |
| `BAND_Logo_Grey` | Lower piece of the S on the tabs (the roof is Pantone orange) | Grey 0.21 |
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

- Shared player, 300 frames, light theme by default (`?theme=dark` for dark). `version` 10.
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
