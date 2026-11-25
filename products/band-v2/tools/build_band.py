"""
Build the Band V2 exploded-view rig from a Fusion USD export.

Run inside Blender with band_explode.blend open:
    exec(open(r"C:\\Users\\Travis\\Scroll Sequence\\products\\band-v2\\tools\\build_band.py", encoding="utf-8").read())
    build()            # or run the steps one by one

Adapted from products/beacon-v3/tools/build_from_usd.py. The scene (camera rig, lights, world,
bloom, render settings) started as a copy of beacon_explode.blend with Beacon's parts removed.

Prerequisites
  - source/BAND V2.usdz imported into a collection named "USD_import" (wm.usd_import).
    Fusion's USD export only writes *visible* bodies.
  - fusion_bodies.json: every Fusion body with component path, bbox (cm), appearance, visibility.

Spaces
  Device space = Fusion space in cm: X across the pod (strap slots at +-X), Y along it (pogo
  pins/magnets at +-Y), Z = thickness, +Z = top (faceted face + logo). USD is Fusion in metres.
"""
import bpy, json, math, os, re
from mathutils import Matrix, Vector

PROJECT = os.path.dirname(bpy.data.filepath)
FUSION_BODIES = os.path.join(PROJECT, "fusion_bodies.json")
ROOT_COLLECTION = "BAND V2"
ROOT_NAME, SPIN_NAME = "BAND_root", "BAND_spin"
M_USD_TO_DEVICE = Matrix.Scale(100, 4)

# ---------------------------------------------------------------- explode rules
# First match wins, against "<fusion/path>::<body>". offset in device cm; L = stagger rank
# (higher = leaves earlier, comes back later). ("hide", pattern, None, 0) drops a part.
RULES = [
    ("Top shell",        r"^Top:1",                       (0, 0, 5.8), 5.2),
    # The whole main board (board + every component under it) always moves as one unit
    ("Main board",       r"^mainBoard_Delta:1",           (0, 0, 3.8), 3.6),
    ("Clear middle",     r"^Clear Middle:1",              (0, 0, 2.3), 2.4),
    ("Battery",          r"^803032 Batt:1",               (0, 0, 1.25), 1.8),
    ("Vibe motor",       r"^Large Vibe Motor:1",          (0, 0, 0.6), 1.2),
    ("Magnets",          r"Magnet \d:1",                  (0, 0, 0.0), 0),
    # Pogo pins poke through the Bottom shell's end walls along Y: they back in, rise, then
    # move out along their axis (see POGO and animate()), so they never pass through a wall.
    ("Pogo targets",     r"^Pogo Charge Target",          "pogo", 0),
    # The plate the +Y pins pass through: rides with them as their retainer
    ("Pogo targets",     r"^Component187:1",              "pogo", 0),
    ("Flex",             r"^flex_rev2 v3:1",              (0, 0, -1.0), 1.6),
    ("Sensor board",     r"^SlateSafety Sensor REV B:1",  (0, 0, -1.9), 2.8),
    ("Bottom shell",     r"^Bottom:1",                    (0, 0, -3.6), 5.2),
    ("Default",          r".*",                           (0, 0, 0.0), 0),
]


def usd_meshes():
    return [o for o in bpy.data.collections["USD_import"].all_objects if o.type == 'MESH']

def meshes_in_root():
    # Fusion parts only (the strap lives in the same collection but isn't from CAD)
    return [o for o in bpy.data.collections[ROOT_COLLECTION].all_objects if o.type == 'MESH' and "fusion_path" in o]


# ---------------------------------------------------------------- 1. bake
def bake():
    meshes = usd_meshes()
    empties = [o for o in bpy.data.collections["USD_import"].all_objects if o.type == 'EMPTY']
    for o in meshes:
        o.data.transform(M_USD_TO_DEVICE @ o.matrix_world)
        vs = o.data.vertices
        lo = Vector((min(v.co.x for v in vs), min(v.co.y for v in vs), min(v.co.z for v in vs)))
        hi = Vector((max(v.co.x for v in vs), max(v.co.y for v in vs), max(v.co.z for v in vs)))
        c = (lo + hi) / 2
        o.data.transform(Matrix.Translation(-c))
        o.parent = None
        o.matrix_world = Matrix.Translation(c)
        o["dev_min"] = list(lo); o["dev_max"] = list(hi)
    for e in empties:
        bpy.data.objects.remove(e, do_unlink=True)
    return len(meshes)


# ---------------------------------------------------------------- 2. identify
def identify():
    fus = [f for f in json.load(open(FUSION_BODIES, encoding="utf-8")) if f.get("visible", True)]
    worst = 0
    for o in usd_meshes():
        lo, hi = Vector(o["dev_min"]), Vector(o["dev_max"])
        best = min((sum(abs(a - b) for a, b in zip(lo, f["min"])) +
                    sum(abs(a - b) for a, b in zip(hi, f["max"])), i) for i, f in enumerate(fus))
        f = fus[best[1]]
        o["fusion_path"] = "/".join(f["path"]); o["fusion_body"] = f["body"]
        o["fusion_path_json"] = json.dumps(f["path"])
        o["fusion_appearance"] = f["app"] or ""; o["fusion_match_err"] = round(best[0], 4)
        o["usd_name"] = o.name
        worst = max(worst, best[0])
    return round(worst, 4)


# ---------------------------------------------------------------- 3. organise
def _short(name, n=40):
    return name if len(name) <= n else name[:n - 1] + "…"

def organise():
    root = bpy.data.collections.get(ROOT_COLLECTION) or bpy.data.collections.new(ROOT_COLLECTION)
    if root.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(root)
    meshes = usd_meshes()
    paths = [tuple(json.loads(o["fusion_path_json"])) for o in meshes]
    count = {}
    for p in paths:
        for i in range(1, len(p) + 1):
            count[p[:i]] = count.get(p[:i], 0) + 1
    made = {(): root}
    def coll_for(prefix):
        if prefix in made: return made[prefix]
        parent = coll_for(prefix[:-1])
        c = bpy.data.collections.new(_short(prefix[-1], 60)); parent.children.link(c)
        made[prefix] = c; return c
    for o, p in zip(meshes, paths):
        k = max((i for i in range(len(p) + 1) if i == 0 or count[p[:i]] > 1), default=0)
        target = coll_for(p[:k])
        for c in list(o.users_collection): c.objects.unlink(o)
        target.objects.link(o)
        comp = p[-1] if p else "Root"
        multi = count.get(p, 1) > 1
        o.name = _short(f"{_short(comp, 44)} · {o['fusion_body']}" if multi or not p else comp, 63)
    usd = bpy.data.collections.get("USD_import")
    if usd and not usd.all_objects:
        bpy.data.collections.remove(usd)
    return len(made)


# ---------------------------------------------------------------- 4. offsets
def offsets():
    stats = {}
    for o in meshes_in_root():
        key = f"{o['fusion_path']}::{o['fusion_body']}"
        for label, pat, off, L in RULES:
            if re.search(pat, key): break
        if off is None:
            o.hide_render = True; o.hide_set(True); o["explode_group"] = "hidden"
            o["explode_off"] = [0, 0, 0]; o["explode_L"] = 0
        elif off == "pogo":
            sy = 1 if (o["dev_min"][1] + o["dev_max"][1]) > 0 else -1     # which end (+Y / -Y)
            i, u, x = POGO["in"], POGO["up"], POGO["out"]
            if o["fusion_path"].startswith("Component187"):
                i = POGO["retainer_in"]               # sits in a ribbed groove: 0.3 clears it (more hits the bottom rib + flex)
            path = [(0, -sy * i, 0), (0, -sy * i, u), (0, sy * x, u)]     # in, up, axially out
            o["explode_group"] = label; o["explode_path"] = [list(p) for p in path]
            o["explode_off"] = list(path[-1]); o["explode_L"] = 0
        else:
            o["explode_group"] = label; o["explode_off"] = list(off); o["explode_L"] = L
        stats[label] = stats.get(label, 0) + 1
    return stats


# ---------------------------------------------------------------- 5. materials
def _lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def _principled(m):
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m and m.use_nodes else None

# Fusion appearance -> tuned material already in the scene (carried over from Beacon), or a
# new one made by _make(). Unlisted Opaque(r,g,b) colours get the same class rules as Beacon.
APPEARANCE = {
    "Plastic - Matte (Black)": "BAND_Black_Plastic",
    "Phenolic (Amber)":        "BAND_LightPipe_Ring",        # Clear Middle = light pipe (see leds())
    "Polymide (Kapton)":       "BAND_Polyimide",             # flex: translucent amber polyimide
    "Brass - Matte":           "Brass_-_Polished.001",
    # "Steel - Satin" is Fusion's default on the board's STEP components: use their USD colour
    "Silver - Polished":       "Steel_-_Satin.001",
    "ABS (White)":             "Nylon_6-6_(White).001",
}

def _make(name):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; p = _principled(m)
    if name == "BAND_Black_Plastic":
        # matte black housing: not pure black, so form still reads under the studio lights
        p.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1)
        p.inputs["Roughness"].default_value = 0.6
        p.inputs["Specular IOR Level"].default_value = 0.4
    elif name == "BAND_Window":
        # optical windows in the bottom shell (photodiode / LED): dark clear glass
        p.inputs["Base Color"].default_value = (0.25, 0.27, 0.3, 1)
        p.inputs["Roughness"].default_value = 0.04
        p.inputs["Transmission Weight"].default_value = 0.9
        p.inputs["IOR"].default_value = 1.5
        m.surface_render_method = 'BLENDED'
    elif name == "BAND_Polyimide":
        # same recipe as Beacon's flex PCBs
        p.inputs["Base Color"].default_value = (0.78, 0.36, 0.05, 1)
        p.inputs["Roughness"].default_value = 0.22
        p.inputs["Transmission Weight"].default_value = 0.75
        p.inputs["IOR"].default_value = 1.7
        p.inputs["Coat Weight"].default_value = 0.5; p.inputs["Coat Roughness"].default_value = 0.06
    elif name == "BAND_Magnet_Nickel":
        p.inputs["Base Color"].default_value = (0.75, 0.74, 0.72, 1)
        p.inputs["Metallic"].default_value = 1.0
        p.inputs["Roughness"].default_value = 0.25
    return m

# Per-part overrides (pattern on the Fusion path) win over the appearance table
PART_OVERRIDE = [
    (r"Magnet \d:1", "BAND_Magnet_Nickel"),
    (r"(PhotoDiode|LED) Window:1", "BAND_Window"),
]

def _auto(usd_mat):
    p = _principled(usd_mat)
    if not p: return None
    raw = tuple(round(x * 255) for x in p.inputs["Base Color"].default_value[:3])
    cand = bpy.data.materials.get(f"Opaque({raw[0]},{raw[1]},{raw[2]}).001")
    if cand: return cand
    m = bpy.data.materials.get(f"BAND_auto_{raw[0]}_{raw[1]}_{raw[2]}")
    if m: return m
    m = usd_mat.copy(); m.name = f"BAND_auto_{raw[0]}_{raw[1]}_{raw[2]}"
    q = _principled(m); c = [_lin(x / 255) for x in raw]
    gold = raw[0] > 200 and 150 < raw[1] < 235 and raw[2] < 170
    grey_metal = raw in ((172, 172, 172), (185, 185, 185), (192, 192, 192), (202, 209, 238), (203, 210, 239))
    q.inputs["Base Color"].default_value = (*((1.0, 0.72, 0.32) if gold else c), 1)
    q.inputs["Metallic"].default_value = 1.0 if (gold or grey_metal) else 0.0
    q.inputs["Roughness"].default_value = 0.22 if gold else (0.3 if grey_metal else (0.42 if max(c) < 0.08 else 0.5))
    return m

def materials():
    report = {}
    for o in meshes_in_root():
        app = o["fusion_appearance"]
        part = next((m for pat, m in PART_OVERRIDE if re.search(pat, o["fusion_path"])), None)
        for sl in o.material_slots:
            if not sl.material: continue
            name = part or APPEARANCE.get(app)
            t = (bpy.data.materials.get(name) or _make(name)) if name else _auto(sl.material)
            if t:
                sl.link = 'OBJECT'; sl.material = t
                report[t.name] = report.get(t.name, 0) + 1
    return report


# ---------------------------------------------------------------- 5b. logo (Pantone 165 C)
LOGO_FACES = os.path.join(PROJECT, "logo_faces.json")   # Top's "Enamel Glossy (Yellow)" faces in Fusion

def logo_material():
    """Same tuned Pantone 165 C as Beacon (measures ~(233,98,45) under this lighting)."""
    m = bpy.data.materials.get("BEACON_Pantone165C")
    if m: return m
    m = bpy.data.materials.new("BEACON_Pantone165C"); m.use_nodes = True; p = _principled(m)
    p.inputs["Base Color"].default_value = (0.7, 0.058, 0.0, 1)
    p.inputs["Roughness"].default_value = 0.7
    p.inputs["Specular IOR Level"].default_value = 0.05
    return m

def logo(tol=0.003):
    faces = json.load(open(LOGO_FACES, encoding="utf-8")); mat = logo_material(); hits = {}
    for o in meshes_in_root():
        mine = [f for f in faces if f["body"] == o["fusion_body"] and f["path"] == json.loads(o["fusion_path_json"])]
        if not mine: continue
        if mat.name not in [s.material.name for s in o.material_slots if s.material]:
            o.data.materials.append(None); o.material_slots[-1].link = 'OBJECT'; o.material_slots[-1].material = mat
        idx = [i for i, s in enumerate(o.material_slots) if s.material == mat][0]
        base = Vector(o["base_loc"]); n = 0
        for poly in o.data.polygons:
            fp = poly.center + base                      # device space == Fusion cm
            for f in mine:
                if all(f["min"][k] - tol <= fp[k] <= f["max"][k] + tol for k in range(3)) and \
                   poly.normal.dot(Vector(f["normal"])) > 0.95:
                    poly.material_index = idx; n += 1; break
        hits[o.name] = n
    return hits


# ---------------------------------------------------------------- 5c. LEDs + light-pipe ring
# The Clear Middle ring is a light pipe, like Beacon's: semi-clear polycarbonate carrying light
# from the 4 side-emitting APFA2507 LEDs, one at the middle of each main-board edge.
LED_COLOR = (0.05, 0.38, 1.0)          # linear; soft blue (the product photo's edge glow). Change here.
LED_PATTERN = r"APFA2507"
ASSEMBLED_GLOW = 2.2                     # ring glows brighter when closed (only its thin edge shows)
OPEN_GLOW = 0.45                         # ...and softer while opened up, so the bare ring doesn't wash out

def led_material():
    m = bpy.data.materials.get("BAND_LED_Emitter") or bpy.data.materials.new("BAND_LED_Emitter")
    m.use_nodes = True; p = _principled(m)
    p.inputs["Base Color"].default_value = (*LED_COLOR, 1)
    p.inputs["Emission Color"].default_value = (*LED_COLOR, 1)
    p.inputs["Emission Strength"].default_value = 30.0
    return m

def light_pipe_material(glow=4.0):
    """Beacon's light-pipe recipe: milky translucent PC whose emission is strongest at grazing
    angles and edges (Layer Weight -> Map Range), which reads as carried light."""
    m = bpy.data.materials.get("BAND_LightPipe_Ring") or bpy.data.materials.new("BAND_LightPipe_Ring")
    m.use_nodes = True; p = _principled(m)
    p.inputs["Base Color"].default_value = (0.92, 0.94, 0.97, 1)
    p.inputs["Roughness"].default_value = 0.3
    p.inputs["IOR"].default_value = 1.585
    p.inputs["Transmission Weight"].default_value = 0.85
    p.inputs["Subsurface Weight"].default_value = 0.35
    p.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0); p.inputs["Subsurface Scale"].default_value = 0.4
    p.inputs["Coat Weight"].default_value = 0.4; p.inputs["Coat Roughness"].default_value = 0.08
    p.inputs["Emission Color"].default_value = (*LED_COLOR, 1)
    nt = m.node_tree
    for n in [n for n in nt.nodes if n.name.startswith("LP_")]: nt.nodes.remove(n)
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.name = "LP_facing"; lw.inputs["Blend"].default_value = 0.35
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.name = "LP_strength"
    mr.inputs["To Min"].default_value = glow * 0.35; mr.inputs["To Max"].default_value = glow * 2.0
    nt.links.new(lw.outputs["Facing"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], p.inputs["Emission Strength"])
    return m

def leds(light_energy=5.0, light_size=0.1):
    out = {}
    emit = led_material(); n = 0
    led_objs = [o for o in meshes_in_root() if re.search(LED_PATTERN, o["fusion_path"])]
    for o in led_objs:
        for sl in o.material_slots: sl.link = 'OBJECT'; sl.material = emit
        n += 1
    out["led_objects"] = n
    pipe = light_pipe_material()
    for o in meshes_in_root():
        if o["fusion_path"].startswith("Clear Middle:1"):
            for sl in o.material_slots: sl.link = 'OBJECT'; sl.material = pipe
    # a small area light on each LED facing outward (toward the ring), parented to the LED
    c, _, _ = device_centre()
    for old in [ob for ob in bpy.data.objects if ob.name.startswith("BAND_LED_Light")]:
        bpy.data.objects.remove(old, do_unlink=True)
    for i, led in enumerate(led_objs):
        b = Vector(led["base_loc"])
        d = Vector((b.x - c.x, b.y - c.y, 0)).normalized()
        dat = bpy.data.lights.new(f"BAND_LED_Light_{i + 1}", 'AREA')
        dat.energy = light_energy; dat.size = light_size; dat.color = LED_COLOR
        L = bpy.data.objects.new(dat.name, dat); bpy.data.collections[ROOT_COLLECTION].objects.link(L)
        L.parent = led; L.matrix_parent_inverse = Matrix.Identity(4)
        half = (Vector(led["dev_max"]) - Vector(led["dev_min"])) / 2
        L.matrix_basis = Matrix.Translation(d * (abs(half.dot(d)) + 0.02)) @ d.to_track_quat('-Z', 'Z').to_matrix().to_4x4()
    out["lights"] = len(led_objs)
    # glow: brighter while assembled, softer while opened up
    mr = pipe.node_tree.nodes["LP_strength"]; lo, hi = mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value
    if pipe.node_tree.animation_data: pipe.node_tree.animation_data_clear()
    for f, k in ((f, ASSEMBLED_GLOW if w == "A" else OPEN_GLOW) for f, w in GLOW_KEYS):
        mr.inputs["To Min"].default_value = lo * k; mr.inputs["To Max"].default_value = hi * k
        mr.inputs["To Min"].keyframe_insert("default_value", frame=f); mr.inputs["To Max"].keyframe_insert("default_value", frame=f)
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = lo, hi
    # bloom: emitters bloom, specular highlights don't
    g = bpy.context.scene.compositing_node_group
    gl = next((x for x in g.nodes if x.type == 'GLARE'), None) if g else None
    if gl: gl.inputs["Threshold"].default_value = 6.0
    return out


# ---------------------------------------------------------------- 6. rig + animation
# 240 frames. The strap comes off first (1-80, tools/strap.py), then the pod opens in an order
# that keeps every part clear of the others (checked frame by frame with check_collisions()):
#   1. top shell, board, clear ring, battery, motor lift      (92-136)
#   2. pogo pins back in, rise, slide out over the end wall   (112-142)
#   3. bottom shell drops, with the flex and sensor board     (132-158)
#   hold, then the exact reverse: bottom back, pins back, upper stack back (166-236).
FRAME_END = 300                # 236-296: the strap comes back on (tools/strap.py)
SPIN_FRAMES = (118, 198)
# (out start, out end, back start, back end) per group
TIMING = {
    "Top shell":    (92, 128, 208, 236),
    "Main board":   (95, 131, 206, 232),
    "Clear middle": (98, 134, 204, 230),
    "Battery":      (100, 136, 202, 228),
    "Vibe motor":   (102, 136, 200, 226),
    "Bottom shell": (132, 158, 166, 190),
    "Flex":         (132, 158, 166, 190),
    "Sensor board": (132, 158, 166, 190),
}
# Ring glow keys: assembled (bright) -> open (soft) -> assembled
GLOW_KEYS = ((1, "A"), (92, "A"), (110, "O"), (214, "O"), (232, "A"))

def device_centre():
    objs = meshes_in_root()
    lo = Vector(map(min, *[Vector(o["dev_min"]) for o in objs]))
    hi = Vector(map(max, *[Vector(o["dev_max"]) for o in objs]))
    return (lo + hi) / 2, lo, hi

def rig():
    """BAND_root at the device centre (pitch/idle pose lives here), BAND_spin under it."""
    c, lo, hi = device_centre()
    rc = bpy.data.collections[ROOT_COLLECTION]
    root = bpy.data.objects.get(ROOT_NAME) or bpy.data.objects.new(ROOT_NAME, None)
    if root.name not in rc.objects: rc.objects.link(root)
    root.location = c; root.rotation_mode = 'QUATERNION'; root.empty_display_size = 3
    sp = bpy.data.objects.get(SPIN_NAME) or bpy.data.objects.new(SPIN_NAME, None)
    if sp.name not in rc.objects: rc.objects.link(sp)
    sp.parent = root; sp.matrix_parent_inverse = Matrix.Identity(4)
    sp.location = (0, 0, 0); sp.rotation_mode = 'XYZ'; sp.empty_display_size = 1.5
    sp.animation_data_clear()
    for f, a in ((SPIN_FRAMES[0], 0.0), (SPIN_FRAMES[1], 2 * math.pi)):
        sp.rotation_euler = (0, 0, a); sp.keyframe_insert("rotation_euler", frame=f)
    # camera rig, target and lights move with the device centre (the scene came from Beacon's)
    t = bpy.data.objects.get("CamTarget")
    # only once, on the scene copied from Beacon (after camera() runs, CamTarget is animated)
    delta = c - t.location if (t and not t.animation_data) else Vector()
    if delta.length > 1e-4:
        for n in ("CamRig", "CamTarget", "Key", "Fill", "Rim", "Top"):
            if n in bpy.data.objects: bpy.data.objects[n].location += delta
    return {"centre": [round(x, 3) for x in c], "size": [round(x, 3) for x in hi - lo]}

# Pogo pin moves (cm): back in along the axis until the tip clears the end wall (pins span
# |Y| 2.64-3.38, wall outer face at |Y| 3.39), rise, then out along the axis past the wall.
# End wall measured at the pins: inner face |y| 3.005, outer 3.39; pin tips at 3.38 -> 0.45 clears.
POGO = {"in": 0.45, "up": 0.75, "out": 1.6, "retainer_in": 0.3}
# Pogo frames: out = (in start, in end / up start, up end / out start, out end),
# back = the same moves reversed. Out starts before the Bottom shell moves (42) and the
# return finishes after it is back (156), so the pins never cross a wall.
# Out: in 112-120 (the battery has lifted clear of the +Y pins), up 120-128 (board and ring
# are above), out 128-142 over the still-seated bottom wall. Back: in 182-190 over the
# returned bottom wall, down 190-198, out into the wall holes 198-206, before the battery returns.
POGO_OUT = (112, 120, 128, 142)
POGO_BACK = (182, 190, 198, 206)

# Camera: CamRig scale = dolly (Beacon's rig), CamRig/CamTarget z = framing height.
# Worn (strap on, loop hangs ~6.5 cm below the pod): pulled back and aimed lower. Then the
# Beacon-style dolly out for the exploded stack and back.
WORN_FRAME = {"scale": 1.45, "z": -2.4}
CAM_KEYS = [  # (frame, dolly scale, worn framing 1/0)
    (1, WORN_FRAME["scale"], 1), (20, WORN_FRAME["scale"], 1), (80, 0.8, 0), (96, 0.8, 0),
    (140, 1.32, 0), (190, 1.32, 0), (234, 0.8, 0), (240, 0.8, 0),
    (296, WORN_FRAME["scale"], 1), (FRAME_END, WORN_FRAME["scale"], 1),   # pulls back out as the strap returns
]

# Viewing angle, in CamRig space (the rig is turned -12 deg about Z). "Head-on" is the
# Fusion-style view from above the pin end, used while worn and when it settles at the end.
CAM_DIST = 39.205                  # camera distance from the rig centre (original (21, -30, 14))
VIEW_34 = (62.0, 28.0)             # (azimuth, elevation) deg: 3/4 from the +Y pin end and +X slot, logo forward (as in Fusion)
VIEW_HEAD_ON = (96.0, 45.0)        # from the +Y end: matches the Fusion view (logo upright)
VIEW_KEYS = [(1, 1), (20, 1), (80, 0), (236, 0), (296, 1), (FRAME_END, 1)]   # (frame, 1 = head-on)

def camera_view():
    """Keys the camera's position on its rig every frame, easing on a sphere between the
    3/4 and head-on views (the Track To constraint keeps it aimed at CamTarget)."""
    cam = bpy.data.objects["Camera"]
    r = CAM_DIST
    cam.animation_data_clear()
    for (f0, v0), (f1, v1) in zip(VIEW_KEYS, VIEW_KEYS[1:]):
        for f in range(f0, f1 + 1):
            t = (f - f0) / (f1 - f0); t = t * t * (3 - 2 * t); h = v0 + (v1 - v0) * t
            az = math.radians(VIEW_34[0] + (VIEW_HEAD_ON[0] - VIEW_34[0]) * h)
            el = math.radians(VIEW_34[1] + (VIEW_HEAD_ON[1] - VIEW_34[1]) * h)
            cam.location = (r * math.cos(el) * math.cos(az), r * math.cos(el) * math.sin(az), r * math.sin(el))
            cam.keyframe_insert("location", frame=f)
    return len(VIEW_KEYS)

def camera():
    camera_view()
    rigo, tgt = bpy.data.objects["CamRig"], bpy.data.objects["CamTarget"]
    c, _, _ = device_centre()
    for o in (rigo, tgt): o.animation_data_clear()
    for f, sc, worn in CAM_KEYS:
        z = WORN_FRAME["z"] if worn else c.z
        rigo.scale = (sc, sc, sc); rigo.keyframe_insert("scale", frame=f)
        for o in (rigo, tgt):
            o.location = (c.x, c.y, z); o.keyframe_insert("location", frame=f)
    bpy.context.scene.frame_set(1)
    return len(CAM_KEYS)

def animate():
    s = bpy.context.scene
    root = bpy.data.objects[ROOT_NAME]; sp = bpy.data.objects[SPIN_NAME]
    inv = Matrix.Translation(-root.location)
    Lmax = 5.2
    for o in meshes_in_root():
        o.animation_data_clear()
        base = Vector(o["base_loc"]) if "base_loc" in o else o.matrix_world.to_translation()
        o.parent = sp; o.matrix_parent_inverse = inv
        o["base_loc"] = list(base); o.location = base
        off = Vector(o["explode_off"])
        if "explode_path" in o:                       # multi-leg move (pogo pins)
            p1, p2, p3 = [base + Vector(p) for p in o["explode_path"]]
            out = zip(POGO_OUT, (base, p1, p2, p3))
            back = zip(POGO_BACK, (p3, p2, p1, base))
            for f, p in list(out) + list(back):
                o.location = p; o.keyframe_insert("location", frame=f)
            continue
        if off.length < 1e-6: continue
        if o.get("explode_group") in TIMING:
            a, b, c, d = TIMING[o["explode_group"]]
        else:                                          # Beacon's stagger formula
            r = min(1.25, o["explode_L"] / Lmax)
            a = 92 + (1 - r) * 16; b = a + 38
            c = 166 + r * 14; d = c + 38
        for f, p in ((a, base), (b, base + off), (c, base + off), (d, base)):
            o.location = p; o.keyframe_insert("location", frame=f)
    s.frame_set(1)


def check_collisions(groups=("Pogo targets",), frames=range(100, 216, 2), margin=0.0):
    """Report parts of `groups` intersecting any other part at the given frames, ignoring
    pairs that already touch in the assembled pose (frame 1). Returns {frame: [(a, b), ...]}."""
    from mathutils.bvhtree import BVHTree
    s = bpy.context.scene
    movers = [o for o in meshes_in_root() if o.get("explode_group") in groups]
    others = [o for o in meshes_in_root() if o not in movers and o.visible_get()]
    local = {o.name: BVHTree.FromPolygons([v.co for v in o.data.vertices], [p.vertices for p in o.data.polygons]) for o in others}
    def hits(f):
        s.frame_set(f); out = set()
        for m in movers:
            Mw = m.matrix_world; mv = [Mw @ v.co for v in m.data.vertices]
            lo = Vector(map(min, *mv)) - Vector((margin,) * 3); hi = Vector(map(max, *mv)) + Vector((margin,) * 3)
            for o in others:
                ow = o.matrix_world
                c = [ow @ Vector(x) for x in (o.bound_box[0], o.bound_box[6])]
                olo = Vector(map(min, *c)); ohi = Vector(map(max, *c))
                if any(hi[k] < olo[k] or lo[k] > ohi[k] for k in range(3)): continue
                inv = ow.inverted()
                t = BVHTree.FromPolygons([inv @ p for p in mv], [p.vertices for p in m.data.polygons])
                if t.overlap(local[o.name]): out.add((m.name, o.name))
        return out
    rest = hits(1)
    report = {}
    for f in frames:
        h = hits(f) - rest
        if h: report[f] = sorted(h)
    s.frame_set(1)
    return report


USD_PATH = os.path.join(PROJECT, "source", "BAND V2.usdz")

def reimport():
    """Delete the current build and import the USD fresh into USD_import."""
    for cname in (ROOT_COLLECTION, "USD_import"):
        c = bpy.data.collections.get(cname)
        if not c: continue
        for o in list(c.all_objects):
            if o.name not in (ROOT_NAME, SPIN_NAME): bpy.data.objects.remove(o, do_unlink=True)
        def drop(cc):
            for ch in list(cc.children): drop(ch); bpy.data.collections.remove(ch)
        drop(c)
        if cname == "USD_import": bpy.data.collections.remove(c)
    for _ in range(3): bpy.data.orphans_purge(do_local_ids=True, do_recursive=True)
    s = bpy.context.scene
    c = bpy.data.collections.new("USD_import"); s.collection.children.link(c)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children["USD_import"]
    bpy.ops.wm.usd_import(filepath=USD_PATH)
    return len(c.all_objects)

def build():
    out = {"baked": bake(), "worst_match_cm": identify(), "collections": organise(),
           "groups": offsets(), "materials": materials(), "rig": rig()}
    animate()                                   # sets base_loc, which logo() needs
    if os.path.exists(LOGO_FACES): out["logo_faces"] = logo()
    out["leds"] = leds()
    out["camera_keys"] = camera()
    strap_py = os.path.join(PROJECT, "tools", "strap.py")
    if os.path.exists(strap_py):
        g = {}; exec(open(strap_py, encoding="utf-8").read(), g); out["strap"] = g["strap"]()
    s = bpy.context.scene
    s.frame_start, s.frame_end, s.render.fps, s.render.fps_base = 1, FRAME_END, 30, 1.0
    s.render.filepath = "//frames/frame_###"
    return out
