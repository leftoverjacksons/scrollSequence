# Beacon V3 — Exploded-View Scroll Sequence

Design notes for the explode/reassemble animation of the Beacon V3 and the scroll page built from it.
This is the source of truth for decisions. Add notes anywhere; the **Notes & requests** section at the bottom is for open ideas.

---

## 1. Files

| File | What it is |
|---|---|
| `beacon_explode.blend` | Blender 5.1 scene: parts, animation, camera, lights, materials, render settings |
| `source/BEACON V3 - Main.usdz` | **Current source.** USD export from Fusion via the Fusion MCP (16.4 MB, 640 bodies, 2026-11-24 v2) |
| `source/BEACON V3 - Main (2026-11-24 v1).usdz`, `source/fusion_bodies_v1.json` | Previous export (632 bodies) and its body dump, kept for reference |
| `tools/build_from_usd.py` | Rebuilds the whole rig from a fresh USD export (see §2) |
| `fusion_bodies.json` | Dump from Fusion: every body's component path, bounding box (cm) and appearance |
| `fusion_map_usd.json` / `fusion_map.json` | USD mesh / OBJ group → Fusion component mappings |
| `frames/frame_001.webp … frame_180.webp` | Rendered image sequence (1920×1080, WebP q82) |
| `index.html` | Scroll-sequence page (canvas scrubbing through `frames/`) |
| `C:\Users\Travis\Downloads\BEACON V3 - Main.obj` | Original OBJ export (retired, 108 MB, outside the project) |

## 2. Source model & hierarchy

- **Source is now the USD export** (`source/BEACON V3 - Main.usdz`), made from the open Fusion design through the Fusion MCP's `exportManager.createUSDExportOptions`. It has about twice the mesh detail of the OBJ (845k vertices vs 402k) and 632 bodies.
- **Fusion's exporters flatten the component tree** — both OBJ and USD write bodies only (`Body1`, `Body1.001`, …). The hierarchy is rebuilt from Fusion itself:
  1. A read-only Fusion script dumps every body's component path and bounding box to `fusion_bodies.json`.
  2. Each USD mesh is matched to a Fusion body by bounding box (630 within 0.15 cm, worst 0.27 cm on curved connector parts).
  3. Blender collections under **`BEACON V3`** mirror the Fusion assembly tree (Rear Assembly → Rear - Substrate & Overmold → Rear Substrate w/ Inserts → …). A component only gets its own collection when it holds more than one body.
  4. Objects are renamed after their component, e.g. `7588N72_Mold-in Inserts for Plastic:13`, or `Component · Body` when a component has several bodies. Every object keeps `fusion_path`, `fusion_body`, `fusion_appearance` and `usd_name` as custom properties.
- **Last rebuild:** 2026-11-24 from export v2 (640 bodies, worst match 0.27 cm).
- **To rebuild from a new export:** first move the current parts out of `BEACON V3` (as was done into `BEACON_usd_v1`), then export USD from Fusion → import it into a collection named `USD_import` → re-run the Fusion body dump → in Blender run `exec(open(r"…\tools\build_from_usd.py").read()); build()`. The explode rules live in `RULES` at the top of that script.
- Parts are baked into "device space": cm, X along the long side, **Z = thickness** (+Z = rear), origin at each part's bounding-box centre.
- **Retired (kept, not rendered):**
  - `BEACON_usd_v1`, the 632 parts from the first USD export (names prefixed `v1`), is excluded from the view layer.
  - `BEACON_parts`, the 622 OBJ parts, is excluded from the view layer.
  - `BEACON V3 - Main`, the very first merged import, is hidden.
- **Faceted pattern on the grey face panel:** intentional (confirmed).

### What the parts actually are (from Fusion)
| Was called | Fusion component |
|---|---|
| "Standoffs" (black oxide) | `91290A015` socket head screws (×4), plus 3 × `91290A012` screws (new in the USD) |
| Brass inserts | `7588N72` mold-in inserts: 4 in the Rear Substrate, 4 in the Front Substrate |
| Steel "hinge cap" | `7588N66` mold-in insert (Rear Substrate) |
| "Hinge barrel" | `M8 Bushing` (overmold) + `854203M-DC` connector (2 bodies) |
| "Sub-board" | `ME310M1` cellular module |
| White plate | `SiWx917` module |
| Module + lid | Würth shield can `3600213120S` + cover `3610213126S` |
| Amber flex | `BEACON V3 Sensor Flex REV E` |
| Grilles (Ring / Ring:1) | `Louver Screen:5` (rear) and `Louver Screen:1` (front) |
| — | New in the USD: `54-00323` assembly (9 bodies, near the M8 end), `M8 Flex` (at the design root) |
| — | New in export v2: **`Wall Bracket`** (bracket + 2 × `2494N54` magnets + `91746A421` knurled thumb screw) clipping over the M8 end, and **`HCP433438 front`** (silver-painted part + polyurethane foam) inside the front assembly |

## 3. Orientation

- All parts are parented to the empty **`BEACON_root`** at the device centre (3.4, −2.85, 0), which now lives in the `BEACON V3` collection.
- **Hero face** = vent grille + hex "S" logo, on the **Front Substrate** (formerly Body7347). It was the model's underside, so `BEACON_root` flips the assembly (180° about X) in the 3/4 "pitched" pose.
- Explode offsets are in device space and follow the device as it rotates.

## 4. What moves together

Rules are matched against `<Fusion component path>::<body>`. **Every body inside a matched component moves with it**, so inserts, screws and SMD parts stay with their parent. `STEP = 0.92`.

| Group | Fusion component(s) | Offset (device space) |
|---|---|---|
| **Housing A** (rear) | everything under `Rear - Substrate & Overmold` = Rear Substrate (dark grey) + Rear Overmold (tan TPE) + its 4 brass and 1 steel mold-in inserts | Z **+5.0** |
| **Housing B** (front/face) | everything under `Front - Substrate & Overmold` = Front Substrate (dark grey, plus Lower Ledge) + Front Overmold (tan TPE) + its 4 brass inserts | Z **−5.0** |
| Louver screens | `Louver Screen:5` (rear) / `Louver Screen:1` (front) | **Stay seated in their housings**: Z +5.0 / −5.0, same timing as the housing |
| **PCB assembly (rigid)** | everything under `PCB Assembly:2` except the light pipe: main board, cell module, shield can, WiFi module, sensor flex, LEDs (594 bodies) | 0. Stays at centre as one piece |
| **Light pipe** | `Light Pipe:1` | Slides off its LEDs at **45° in the board plane**, out of the corner it sits in (`PIPE_TRAVEL` = 1.6 cm, i.e. +1.13 X, +1.13 Y), so the magenta LEDs and the glowing pipe are both visible |
| **Wall bracket** | `Wall Bracket:1` + its 2 magnets | Slides off the M8 end: X −4.8 (`BRACKET_TRAVEL`) |
| Bracket thumb screw | `91746A421` | **Axially** out along its own axis toward the head: Y +2.0 (clears the bracket's top arm) |
| HCP433438 front | foam + silver part | Default rule: Z −1.18 |
| **M8 bushing + 54-00323** | `M8 Bushing` + the `54-00323` pin assembly + `M8 Flex` | Stay connected, at centre with the PCB (offset 0) |
| M8 connector | `854203M-DC` (2 bodies) | **Axially** out of the bushing along the M8 axis (device −Y): Y −3.0 |
| Screws | `91290A015` ×4, `91290A012` ×3 | **Toward the head** (see below) |

**Screws:** `screws()` in the build script works out each screw's head end and the parts it passes through, then moves the screw toward its head until its tip clears the far face of those parts in the exploded pose, plus 0.35 cm.
- **Head end:** whichever end has the wider vertex spread.
- **Hosts:** parts with geometry around the shank only, not the head.
- **Results:**
  - The 4 × `91290A015` are head +Z. They go up (+6.78) and end above Housing A.
  - The 3 × `91290A012` are head −Z. They go down (−0.85) and end just below the PCB.
- **Timing:** screws lead out first and go back in last (stagger rank `r` capped at 1.25).
| Antenna / LTE cord | `New Antennae` / `LTE Ant Cord` | Z +2.4 / +1.6 × STEP |
| Everything else | e.g. `54-00323`, `M8 Flex`, `20278 PLUG` | Whole component moves by its Z position × 2.5 (clamped ±3 × STEP) |

**Explicit timing (`TIMING` in the build script):** the connector and thumb screw pass through the bracket's arms, so the stagger formula is overridden for them:
- **Thumb screw:** out 36–66, back in 130–160.
- **M8 connector:** out 38–70, back in 128–160.
- **Wall bracket:** slides off 56–90 (after both are clear) and back on 96–126 (before they go back in).

Each part stores `base_loc`, `explode_off`, `explode_L` (stagger rank) and `explode_group`.

## 5. Animation timeline (180 frames @ 30 fps)

| Frames | What happens |
|---|---|
| 1–22 | **Idle, hero 3/4**: matched to the user's Fusion reference view. The face is toward the camera, tipped top-away so the bottom edge (pins, light-pipe exit) shows, the right end swung slightly toward camera, M8 end and bracket on the left |
| 22–62 | **Pitch down** into the 3/4 view |
| ~38–96 | **Explode**: screws first, then outer parts lead (start = 42 + (1 − r)·16, duration 38, r = min(1.25, explode_L / 5.2)) |
| 60–124 | **Full 360° spin** about the stack axis (device Z), eased in and out, on the empty `BEACON_spin` |
| ~96–104 | Hold, fully exploded |
| ~104–156 | **Reassemble**: inner parts settle first, outer housing closes last (start = 104 + r·14, duration 38) |
| 122–162 | **Pitch back up** to face-on |
| 162–180 | Idle, same hero 3/4 pose as the start |

- Pitch = quaternion keys on `BEACON_root`: idle pose at 1/22/162/180, 3/4 exploded pose at 62/122.
- **Idle pose** = the face-on orientation (`FACE_ON_QUAT`) plus a tilt in camera space, `IDLE_TILT` = pitch −17°, yaw −18°, roll +6°. To retune, run `idle_pose(pitch=…, yaw=…, roll=…)` in the build script, then update `IDLE_TILT`. The tilt makes the magenta light-pipe edge read as a halo in the opening and closing frames.
- Spin: `BEACON_spin` is a child of `BEACON_root` with an identity rest pose. All parts are parented to it (parent inverse = −root location), so the spin happens inside the pitched pose. Frames are set by `SPIN_FRAMES` in the build script.
- Easing = Blender's default Bezier keys (ease in and out).

## 6. Camera

- `Camera` is parented to **`CamRig`** (at the device centre) and tracks **`CamTarget`**.
- Camera local position (21, −30, 14), 50 mm lens. `CamRig` yaw is fixed at −12° (no orbit).
- **Dolly** via `CamRig` scale: 0.8 at frames 1–22 → 1.32 at 72–112 → 0.8 at 160–180, so the exploded stack never clips.

## 7. Lighting & world

All area lights track `CamTarget`:

| Light | Position | Power | Size | Notes |
|---|---|---|---|---|
| **Key** | (20, −20, 12) | 6500 W | 12 × 6 | Moved forward and softened so the matte face doesn't flare at peak explode |
| **Fill** | (−16, −18, 4) | 1800 W | 12 | Cool tint |
| **Rim** | (−6, 16, 10) | 6000 W | 6 | Warm tint, separates the parts from the background |
| **Top** | (3.4, −2.85, 22) | 2500 W | 16 | Broad softbox; gives the face a soft gradient |

- **World, split by ray type:**
  - What the camera sees directly: solid near-black (0.02, 0.022, 0.026), which renders as about **#17181C**. The page background must match this.
  - What lights the scene and shows in reflections: a studio gradient (dark floor → dim horizon → bright soft top), so metals have something to reflect.
- EEVEE raytracing is on (reflections and fast GI). Colour management: AgX, "Medium High Contrast", exposure +0.3.

## 8. Materials

### Logo — Pantone 165 C
- The raised hex "S" logo on the Front Substrate (Body7347) uses **`BEACON_Pantone165C`**. Its faces were picked in Fusion and saved to `logo_faces.json` (Fusion face bounding boxes + normals). `logo()` in the build script colours every mesh face lying on those Fusion faces, and runs automatically on a rebuild.
- **To change which surfaces are logo-coloured:** select the faces in Fusion, re-run the selection dump (it writes `logo_faces.json`), then run `logo()`.
- Target is Pantone 165 C ≈ sRGB **#FF671F** (255, 103, 31). A straight conversion renders salmon (~239/159/134), because AgX desaturates bright saturated colours and specular adds white. The material is tuned instead: linear base (0.7, 0.058, 0.0), roughness 0.7, specular 0.05. It measures **≈ (233, 98, 45)** on the face-on frames. For an exact match, the logo would need a different view transform (e.g. Standard) or a small compositor correction.

### LEDs & light pipe
- **LED emitters:** the side-emitting faces of the 3 × `QLS6A-FKW-CNSNSF043` LEDs on the PCB. They were picked in Fusion and saved to `led_faces.json`, and use **`BEACON_LED_Emitter`** (emission 40, colour `LED_COLOR` = **magenta**, linear (1.0, 0.02, 0.62)). The pipe's glow uses the same colour. Each LED also has a small area light (`LED_Light_1–3`, 6 W, 0.12 cm) parented to it, so the light travels with the PCB.
- **Light pipe:** **`BEACON_LightPipe_PC`**, milky translucent polycarbonate.
  - IOR 1.585, transmission 0.85, subsurface 0.35, roughness 0.35, light coat.
  - Emission in the LED colour, brighter at grazing angles and edges (Layer Weight → Map Range, base glow 4.5), which reads as carried light.
  - The glow is keyed **×2.2 when assembled** (frames 1–38 and 166–180) and ×1 while opened up.
- **Bloom:** the compositor group `BEACON_Bloom` (Glare, Bloom, threshold 6, strength 0.7, size 0.4). Only the emitters exceed the threshold.
- Face-on, only the pipe's thin exit edge (bottom edge, under the logo) is visible, so the assembled glow there is a bright line rather than a halo. The full glow shows during the 3/4 exploded section.
- **To change the LED colour:** set `LED_COLOR` in the build script and run `leds()`.

USD parts get the tuned materials below. `build_from_usd.py` maps them by Fusion appearance name (e.g. `XID_BrassPolished…` → brass), or by the original raw colour for `Opaque(r,g,b)` appearances. Colours that are new in the USD get an auto material (`BEACON_auto_r_g_b`) built by the same class rules. Assignment is per object (slot link = Object).

### Brand colours (from the user)
- **Tan, for everything tan:** Pantone **Mojave Desert #C7B595** (199, 181, 149). It's used for the overmold TPE (`BEACON_DesertTan_TPE`), the louver screens and wall bracket (`Mojave_Desert_ASA.001`), and the M8 bushing (`Sandy_Overmolding.001`).
- **Grey:** Pantone **Cool Gray 11 C #53565A** (83, 86, 90), on `BEACON_DarkGrey_Plastic`.
- Like the logo, the base colours are tuned so the render measures the Pantone value: the grey face measures (84, 86, 90) and the tan about (200, 184, 159). The values are in `TUNED_BASE` in the build script. Re-tune if the lighting or exposure changes.
- **Flex PCBs** (sensor flex and M8 flex, Fusion "Phenolic (Amber)") are **translucent amber polyimide**: transmission 0.75, IOR 1.7, roughness 0.22, glossy coat. `APPEARANCE_OVERRIDE` makes the Fusion appearance win over the USD material name, which had the M8 flex as white nylon.

### Housing
| Material | Fusion appearance | Spec |
|---|---|---|
| `BEACON_DarkGrey_Plastic` | Slate Cool Grey 11c (Rear/Front Substrate, Lower Ledge) | Cool Gray 11 C rigid plastic, lightly textured: noise bump (scale 180, strength 0.12) plus roughness varying 0.62–0.74, specular 0.32 |
| `BEACON_DesertTan_TPE` | Mojave Desert Unisoft (Rear/Front Overmold) | Mojave Desert TPE rubber, roughness ~0.78, specular 0.25, sheen 0.15, very subtle texture |

### Everything else
| Class | Fusion appearance / colour | Settings |
|---|---|---|
| Brass (mold-in inserts) | Brass - Polished | Metallic, roughness 0.22 |
| Satin steel (insert, M8 connector) | Steel - Satin | Metallic, roughness 0.32 |
| Black oxide (socket head screws) | Coating - Black Oxide | Metallic, near-black, roughness 0.42 |
| Silver paint (shell interior) | Paint - Metallic (Silver) | Metallic 0.9, roughness 0.45 |
| Gold contacts | Opaque 255/207/128, 255/206/127, 219/188,126 (and similar golds) | Metallic gold, roughness 0.22 |
| Tin / solder / nickel shields | Opaque 185/185/185, 192/192/192, 202/209/238, 172/172/172 | Metallic, roughness 0.3 |
| PCB solder mask | Opaque 80/124/105 (main), 0/128/0 (cell module) | Deep green, roughness 0.32, coat 0.5. *The module's pure #008000 is darkened.* |
| Light pipe | Light Pipe | **`BEACON_LightPipe_PC`**, milky polycarbonate that glows (see LEDs below) |
| Flex PCBs | Phenolic (Amber) | Translucent amber polyimide (see Brand colours) |
| Louver screens, wall bracket | Mojave Desert ASA | Mojave Desert, roughness 0.5 |
| M8 bushing | Sandy Overmolding | Matte, roughness 0.78 |
| Antenna | Nylon 6-6 (White) | Off-white, roughness 0.6 |
| Ceramic caps | Opaque 97/69/55 | Roughness 0.45 |
| Black IC packages / plastics | Any very dark Opaque | Roughness 0.42 |
| Other Opaque | Fallback | Own colour, roughness 0.5 |

The class mapping is a best guess from Fusion's appearance names and colours. Correct anything that reads wrong.

## 9. Render

- EEVEE (raytracing on), 64 samples, 1920×1080, WebP quality 82, RGB. Output: `frames/frame_###.webp`. Before a full render, check that the output path still points here (test renders can change it), and count only the frames written by *this* run.
- Render from the command line so the open Blender session stays usable:
  ```powershell
  & "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b "beacon_explode.blend" -a
  ```
  About 1 s per frame, so ~3–4 minutes for the full sequence.

## 10. Scroll page (`index.html`)

- Intro and outro sections, with a scroll track around a fixed (sticky) full-screen canvas. The track's height comes from `STOPS`: currently 1100vh, plus one screen.
- `FRAME_COUNT = 180`. **Bump `VERSION` after every re-render** so browsers don't show cached frames (currently `11`). Don't open the page while a render is running: the browser caches a mix of old and new frames under the same version.
- Preloads all frames, with a thin progress bar while loading. If you scroll faster than frames load, it shows the nearest loaded frame.
- Sizing: fits the whole frame on wide screens and crops to fill (up to 1.6× zoom) on tall or phone screens.
- **Scroll pacing (`STOPS`):** a list of [scroll position in vh, animation frame] pairs. Frames between stops are spread evenly, so a long scroll span covering few frames makes the page linger. That's how each callout gets roughly a screen of scroll.
- **Callouts** (the `CALLOUTS` array in `index.html`; text is first-draft copy, edit freely). Each is a label in a left or right column with a leader line to a dot on the part. The leader follows the part every frame through the pitch, explode and spin.

  | Frames | Callout | Points at |
  |---|---|---|
  | 2–13 | **Ruggedized construction** headline + **ASA substrate** + **TPE overmold** | Front Substrate face / Front Overmold edge |
  | 14–26 | **Buttons** + **LED indicator** + **Sensor tunnel** | Button pad on the Rear Overmold / light-pipe exit / rear louver (sensor tunnel) |
  | 57–65 | **¼"-20 standard mount** | `7588N66` insert in the rear housing (the thumb screw threads into it) |
  | 77–88 | **Cell antenna** | `New Antennae` (flat white flex antenna) |
  | 88–97 | **Auxiliary input** (M8 port) | `M8 Bushing` (the port: bushing + pins), not the plug that pulls out |
  | 97–109 | **Polymagnet bracket** | `2494N54` magnet in the wall bracket |
  | 109–123 | **LiPoly battery** | `HCP433438 front` pack |

- **Anchor tracking:** `tools/callouts.py` (run in Blender: `export_callouts()`) fixes each anchor to a point on its part. For every frame in its window it writes the 2D image position and whether that point is visible (a ray test, so a label hides when its part is behind something) to **`callouts.json`**. The windows were picked from a visibility scan:
  - The ¼"-20 insert is only exposed at frames 58–65, while the housings separate and before the spin turns it away.
  - The sensor tunnel is hidden from about frame 25 as the device pitches.
- **Text never covers the model:** `export_callouts()` also writes a per-frame **model mask** into `callouts.json`: an 80×45 grid (24 px cells), marking each cell that differs from the background in the dark frames, glow halos included.
- **Labels never move:** each label gets **one fixed screen position for its whole window**; only the leader line follows the part. (Per-frame placement made labels flutter.) The layout is computed once per viewport size, picking the spot nearest the anchor's average position, preferred side first, where the text box clears:
  - the model in **every** frame of the window, with a 14 px margin;
  - the labels and headline shown at the same time (labels sharing a window are placed top-to-bottom by anchor height);
  - the screen edges.

  Leaders that run through another label or cross another leader are heavily penalised (this is what separates ASA and TPE). On very narrow screens with no clear spot, a label falls back to its preferred side. The headline tries top-left, bottom-left, top-right, bottom-right and then top-centre, clear of the model across its window.
- **Re-run `export_callouts()` after any change to the animation or camera** (it re-reads `frames/` for the mask, so render first), then bump `VERSION`.
- **Later idea from the user:** an "x-ray" view on the buttons callout, to see the button on the other side through the housing.
- **Themes:**
  - **Light (default):** for the Slate Safety site, which is a white page with Pantone 165 C orange accents. It shows `frames_white/` on `#ffffff`, with dark text and orange eyebrow labels and dots.
  - **Dark:** `?theme=dark` shows `frames/` on `#17181c`.
- **White frames:** `tools/render_white.py` swaps only the camera-ray background to white. Strength 8 is what AgX needs to reach #FFFFFF; strength 4 gives #F8F8F8. Lighting and reflections are unchanged, and the saved .blend isn't touched. It also raises the bloom threshold from 6 to 12: the white background (strength 8) is above 6, and at that threshold it bloomed over the whole model as a haze. The LEDs and pipe edges are well above 12, so they still bloom. Render with:
  `blender -b beacon_explode.blend --python tools/render_white.py -a`
- The magenta glow halos read much more softly on white than on dark.
- Preview: the page needs a local web server (it won't load frames from `file://`). From this folder run `python -m http.server 8766`, then open http://localhost:8766.

## 11. Known issues / open questions

- **New parts in the USD:** `54-00323` (9 bodies, the M8 connector's pin assembly), `M8 Flex` and 3 × `91290A012` screws weren't in the OBJ. **Confirmed: keep them in the animation.**
- The USD holds one PCB board mesh, which Fusion reports under `_autosave-BEACON V3 REV C PCB`. It's the real board, now named `Main PCB · Body1`.
- Louver screens are tan (confirmed).
- Black IC packages read a little dark against the background. A stronger rim light, or slightly lighter epoxy, would help if needed.

## 12. Repo / storage

- **Repo:** https://github.com/leftoverjacksons/scrollSequence (branch `main`). Local working copy: `C:\Users\Travis\Scroll Sequence`.
- **Hosted page:** GitHub Pages from `main` / root → https://leftoverjacksons.github.io/scrollSequence/. `.nojekyll` makes Pages serve the files as-is.
- **Git LFS** holds `*.blend` and `*.usdz` (see `.gitattributes`). The frames are **not** in LFS on purpose: GitHub Pages doesn't serve LFS files, so `frames/*.webp` must stay as normal git files.
- **Ignored:** `*.blend1`, `render_log.txt`, `.claude/`. The retired 108 MB OBJ lives outside the project and isn't in the repo.
- Commits use the GitHub noreply address `leftoverjacksons@users.noreply.github.com` (repo-local git config).
- **Workflow after a re-render:** bump `VERSION` in `index.html`, then commit `frames/`, `index.html` and the `.blend`, and push. Pages redeploys in about a minute.

---

## Notes & requests

<!-- Add your notes here -->

