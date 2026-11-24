"""
Rebuild the Beacon V3 exploded-view rig from a Fusion USD export.

Run inside Blender (Scripting tab, or via the MCP) with beacon_explode.blend open:
    exec(open(r"C:\\Users\\Travis\\Scroll Sequence\\tools\\build_from_usd.py").read())
    build()            # or run the steps one by one

Prerequisites
  - The USD is imported into a collection named "USD_import" (wm.usd_import).
  - fusion_bodies.json exists (dump of every Fusion body: component path + bbox in cm).
  - The scene already has BEACON_root (pitch animation), CamRig/Camera, lights, and the
    tuned materials from the OBJ version (BEACON_* plus the *.001 imported materials).

What it does
  1. bake      - bakes each USD mesh into the same space/scale as the old OBJ parts
                 (cm, Z = device thickness), origin at bbox centre, unparents, drops the
                 USD MeshInstance empties.
  2. identify  - matches each mesh to its Fusion component by bounding box.
  3. organise  - nested collections mirroring Fusion's assembly tree + readable names.
  4. offsets   - explode offsets from Fusion component paths (RULES below).
  5. materials - maps USD materials onto the tuned materials.
  6. animate   - parents to BEACON_root, keys explode/reassemble, retires the OBJ parts.
"""
import bpy, json, math, os, re
from mathutils import Matrix, Vector

PROJECT = r"C:\Users\Travis\Scroll Sequence"
FUSION_BODIES = os.path.join(PROJECT, "fusion_bodies.json")
ROOT_COLLECTION = "BEACON V3"
ROOT_REST = Vector((3.4, -2.85, 0.0))      # BEACON_root location (rest rotation = identity)
STEP = 0.92
BRACKET_TRAVEL = 4.8   # cm the wall bracket slides off the M8 end

# ---------------------------------------------------------------- explode rules
# First match wins. Matched against "<fusion/path/of/component>::<body name>".
# offset = (x, y, z) in device space (Z = thickness, + = back/rear side). L = stagger rank.
RULES = [
    # Note: the USD holds a single board mesh, which Fusion reports under
    # "_autosave-BEACON V3 REV C PCB" - it is the real board, so it falls through to "Main PCB".
    # Use ("hide", <pattern>, None, 0) to drop a part from the render.
    ("Housing A (rear)", r"Rear - Substrate & Overmold", (0, 0, 5.0), 5.2),
    ("Housing B (front/face)", r"Front - Substrate & Overmold", (0, 0, -5.0), 5.2),
    # Louver screens stay seated in their housings (same offset + timing as the housing)
    ("Louver screen rear", r"Louver Screen:5", (0, 0, 5.0), 5.2),
    ("Louver screen front", r"Louver Screen:1", (0, 0, -5.0), 5.2),
    # Light pipe slides off its LEDs diagonally (45 deg in the board plane, out of its corner)
    ("Light pipe", r"PCB Assembly:2/Light Pipe:1", "pipe", 2.0),
    # The rest of the PCB assembly is one rigid unit: main board + every component, the cell
    # module, shield can, WiFi module and sensor flex.
    ("PCB assembly", r"PCB Assembly:2(/|::)", (0, 0, 0), 0),
    # M8 stack shares one axis along device Y (X~0, Z~0); the connector is at the -Y end.
    # Bushing + 54-00323 pin assembly + M8 flex stay together with the PCB; the connector
    # pulls straight out of them along the axis (-Y), early, so the bracket can slide off after.
    ("M8 bushing + 54-00323", r"M8 Bushing|54-00323|^::M8 Flex$", (0, 0, 0), 0),
    ("M8 connector", r"854203M-DC", (0, -3.0, 0), 6.2),
    # Screws travel head-first along their axis until clear of every part they pass through
    # (see screws()). L is the stagger rank only.
    ("Screws 91290A015", r"91290A015", "screw", 2.0),
    ("Screws 91290A012", r"91290A012", "screw", 2.0),
    # Wall bracket clips over the M8 end (-X). The thumb screw (axis = device Y, head at +Y)
    # backs straight out along its axis first (clears the bracket's top arm at Y 0.61);
    # the bracket + magnets slide off -X later (low rank = starts later, after the connector).
    ("Bracket thumb screw", r"Wall Bracket:1/91746A421", (0, 2.0, 0), 6.5),
    ("Wall bracket", r"^Wall Bracket:1", (-BRACKET_TRAVEL, 0, 0), 2.0),
    ("Antenna", r"::New Antennae$", (0, 0, 2.4 * STEP), 2.4),
    ("LTE cord", r"::LTE Ant Cord$", (0, 0, 1.6 * STEP), 1.6),
    ("Default", r".*", "auto", 0),
]

M_USD_TO_DEVICE = Matrix.Rotation(math.radians(90), 4, 'X') @ Matrix.Scale(100, 4)


def usd_meshes():
    return [o for o in bpy.data.collections["USD_import"].all_objects if o.type == 'MESH']


# ---------------------------------------------------------------- 1. bake
def bake():
    meshes = usd_meshes()
    empties = [o for o in bpy.data.collections["USD_import"].all_objects if o.type == 'EMPTY']
    for o in meshes:
        W = M_USD_TO_DEVICE @ o.matrix_world
        o.data.transform(W)
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
    fus = json.load(open(FUSION_BODIES, encoding="utf-8"))
    worst = 0
    for o in usd_meshes():
        lo, hi = Vector(o["dev_min"]), Vector(o["dev_max"])
        # device space -> Fusion cm: x = x, y = z, z = -y
        fmin = (lo.x, lo.z, -hi.y); fmax = (hi.x, hi.z, -lo.y)
        best = min((sum(abs(a - b) for a, b in zip(fmin, f["min"])) +
                    sum(abs(a - b) for a, b in zip(fmax, f["max"])), i) for i, f in enumerate(fus))
        f = fus[best[1]]
        o["fusion_path"] = "/".join(f["path"]); o["fusion_body"] = f["body"]
        o["fusion_path_json"] = json.dumps(f["path"])   # component names can contain "/"
        o["fusion_appearance"] = f["app"] or ""; o["fusion_match_err"] = round(best[0], 4)
        o["usd_name"] = o.name
        worst = max(worst, best[0])
    return worst


# ---------------------------------------------------------------- 3. organise
def _short(name, n=40):
    return name if len(name) <= n else name[:n - 1] + "…"

def _clear_tree(root):
    """Move every object back to the root collection and delete the sub-collections."""
    for o in list(root.all_objects):
        for c in list(o.users_collection): c.objects.unlink(o)
        root.objects.link(o)
    def drop(c):
        for ch in list(c.children): drop(ch); bpy.data.collections.remove(ch)
    drop(root)

def organise(meshes=None):
    root = bpy.data.collections.get(ROOT_COLLECTION) or bpy.data.collections.new(ROOT_COLLECTION)
    if root.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(root)
    if meshes is None:
        meshes = usd_meshes() if "USD_import" in bpy.data.collections else []
        if not meshes:                                   # re-organising an existing build
            _clear_tree(root); meshes = [o for o in root.objects if o.type == 'MESH']
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
        # deepest ancestor component that groups more than one body
        k = max((i for i in range(len(p) + 1) if i == 0 or count[p[:i]] > 1), default=0)
        target = coll_for(p[:k])
        for c in list(o.users_collection): c.objects.unlink(o)
        target.objects.link(o)
        comp = p[-1] if p else "Root"
        multi = count.get(p, 1) > 1
        o.name = _short(f"{_short(comp, 44)} · {o['fusion_body']}" if multi or not p else comp, 63)
    return len(made)


# ---------------------------------------------------------------- 4. offsets
def _auto_groups(objs):
    """'auto' parts move as whole components: group by the first two path levels."""
    groups = {}
    for o in objs:
        p = json.loads(o["fusion_path_json"])
        key = "/".join(p[:2]) if p else "::" + o["fusion_body"]
        lo, hi = Vector(o["dev_min"]), Vector(o["dev_max"])
        g = groups.setdefault(key, [lo.copy(), hi.copy()])
        g[0] = Vector(map(min, g[0], lo)); g[1] = Vector(map(max, g[1], hi))
    return groups

def offsets():
    stats = {}
    objs = usd_meshes_in_root()
    groups = _auto_groups(objs)
    for o in objs:
        key = f"{o['fusion_path']}::{o['fusion_body']}"
        c = (Vector(o["dev_min"]) + Vector(o["dev_max"])) / 2
        for label, pat, off, L in RULES:
            if re.search(pat, key):
                break
        if off is None:
            o.hide_render = True; o.hide_set(True); o["explode_group"] = "hidden duplicate"
            o["explode_off"] = [0, 0, 0]; o["explode_L"] = 0; stats[label] = stats.get(label, 0) + 1
            continue
        if off == "auto":
            p = json.loads(o["fusion_path_json"])
            g = groups["/".join(p[:2]) if p else "::" + o["fusion_body"]]
            gz = (g[0].z + g[1].z) / 2
            L = max(-3, min(3, gz * 2.5)); off = (0, 0, L * STEP); L = abs(L)
        elif off == "screw":
            off = (0, 0, 0)                     # filled in by screws(), which needs every other offset
        elif off == "pipe":
            off = _pipe_offset(objs, c)
        off = Vector(off)
        o["explode_group"] = label
        o["explode_off"] = list(off)
        o["explode_L"] = L if L else off.length / STEP
        stats[label] = stats.get(label, 0) + 1
    stats["screws"] = screws()
    return stats


PIPE_TRAVEL = 1.6   # cm, how far the light pipe slides off the LEDs

def _pipe_offset(objs, pipe_c):
    """45 deg diagonal in the board (XY) plane, pointing out of the corner the pipe sits in."""
    pcb = [o for o in objs if "PCB Assembly:2" in o["fusion_path"] and "Light Pipe" not in o["fusion_path"]]
    lo = Vector(map(min, *[Vector(o["dev_min"]) for o in pcb])) if len(pcb) > 1 else Vector(pcb[0]["dev_min"])
    hi = Vector(map(max, *[Vector(o["dev_max"]) for o in pcb])) if len(pcb) > 1 else Vector(pcb[0]["dev_max"])
    c = (lo + hi) / 2
    sx = 1 if pipe_c.x >= c.x else -1; sy = 1 if pipe_c.y >= c.y else -1
    return Vector((sx, sy, 0)).normalized() * PIPE_TRAVEL

def _head_dir(o):
    """+1 if the screw head is at the +Z end (device space), -1 if at the -Z end."""
    vs = [v.co for v in o.data.vertices]
    z0 = min(v.z for v in vs); z1 = max(v.z for v in vs); band = (z1 - z0) * 0.12
    def radius(sel):
        pts = [v for v in vs if sel(v.z)]
        cx = sum(v.x for v in pts) / len(pts); cy = sum(v.y for v in pts) / len(pts)
        return max(((v.x - cx) ** 2 + (v.y - cy) ** 2) ** 0.5 for v in pts)
    return 1 if radius(lambda z: z > z1 - band) > radius(lambda z: z < z0 + band) else -1

def screws(gap=0.35):
    """Each screw moves toward its head until its tail clears every part it passes through,
    measured in the exploded pose. Hosts = parts with geometry within the screw's radius of
    its axis, inside its length."""
    from mathutils.kdtree import KDTree
    objs = usd_meshes_in_root()
    scr = [o for o in objs if o.get("explode_group", "").startswith("Screws")]
    others = [o for o in objs if o not in scr and o.get("explode_group") != "hidden duplicate"]
    trees = {}
    def tree(o):
        if o.name not in trees:
            vs = o.data.vertices; t = KDTree(len(vs)); base = Vector(o["base_loc"]) if "base_loc" in o else o.matrix_world.to_translation()
            for i, v in enumerate(vs): t.insert(v.co + base, i)
            t.balance(); trees[o.name] = (t, base)
        return trees[o.name]
    report = {}
    for s in scr:
        lo, hi = Vector(s["dev_min"]), Vector(s["dev_max"]); axis = (lo + hi) / 2
        r = max(hi.x - lo.x, hi.y - lo.y) / 2 + 0.03
        hd = _head_dir(s); far_face = -1e9; hosts = []
        for o in others:
            olo, ohi = Vector(o["dev_min"]), Vector(o["dev_max"])
            if ohi.z < lo.z or olo.z > hi.z or not (olo.x - r <= axis.x <= ohi.x + r and olo.y - r <= axis.y <= ohi.y + r):
                continue
            t, base = tree(o)
            # sample the shank only (tail -> 70% of the length); geometry around the head
            # (counterbores, ribs) doesn't count as something the screw passes through
            L_ = hi.z - lo.z
            zs = [lo.z + L_ * 0.7 * k / 8 for k in range(9)] if hd > 0 else [hi.z - L_ * 0.7 * k / 8 for k in range(9)]
            hit = any(t.find_range(Vector((axis.x, axis.y, z)), r) for z in zs)
            if not hit: continue
            hosts.append(o.name)
            oz = Vector(o["explode_off"]).z
            far_face = max(far_face, (ohi.z + oz) * hd if hd > 0 else -(olo.z + oz))
        tail = lo.z if hd > 0 else hi.z            # end opposite the head
        need = (far_face + gap) - tail * hd if hosts else 1.2 * STEP
        dz = max(need, 0.6) * hd
        # explode_L 6.5 (> housings' 5.2): screws come out first and go back in last
        s["explode_off"] = [0, 0, dz]; s["explode_L"] = 6.5; s["screw_head"] = hd
        report[s.name] = {"head": "+Z" if hd > 0 else "-Z", "dz": round(dz, 2), "hosts": hosts[:6]}
    return report


def usd_meshes_in_root():
    return [o for o in bpy.data.collections[ROOT_COLLECTION].all_objects if o.type == 'MESH']


# ---------------------------------------------------------------- 5. materials
def _lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def _principled(m):
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m and m.use_nodes else None

NAMED = {  # USD material name key -> tuned material
    "BrassPolished": "Brass_-_Polished.001", "SteelSatin": "Steel_-_Satin.001",
    "CoatingBlackOxide": "Coating_-_Black_Oxide.001", "PaintMetallicSilver": "Paint_-_Metallic_(Silver).001",
    "LightPipe": "Light_Pipe.001", "PhenolicAmber": "Phenolic_(Amber).001", "Nylon66White": "Nylon_6-6_(White).001",
    "MojaveDesertASA": "Mojave_Desert_ASA.001", "SandyOvermolding": "Sandy_Overmolding.001",
    "SlateCoolGrey": "BEACON_DarkGrey_Plastic", "MojaveDesertUnisoft": "BEACON_DesertTan_TPE",
}

def _tuned_for(usd_mat):
    name = usd_mat.name
    for k, v in NAMED.items():
        if k in name and v in bpy.data.materials:
            return bpy.data.materials[v]
    p = _principled(usd_mat)
    if not p: return None
    raw = tuple(round(x * 255) for x in p.inputs["Base Color"].default_value[:3])
    cand = bpy.data.materials.get(f"Opaque({raw[0]},{raw[1]},{raw[2]}).001")
    if cand: return cand
    # new colour: build a tuned material with the same class rules as the OBJ pass
    m = bpy.data.materials.get(f"BEACON_auto_{raw[0]}_{raw[1]}_{raw[2]}")
    if m: return m
    m = usd_mat.copy(); m.name = f"BEACON_auto_{raw[0]}_{raw[1]}_{raw[2]}"
    q = _principled(m); c = [_lin(x / 255) for x in raw]
    gold = raw[0] > 200 and 150 < raw[1] < 235 and raw[2] < 170
    grey_metal = raw in ((172, 172, 172), (185, 185, 185), (192, 192, 192))
    q.inputs["Base Color"].default_value = (*((1.0, 0.72, 0.32) if gold else c), 1)
    q.inputs["Metallic"].default_value = 1.0 if (gold or grey_metal) else 0.0
    q.inputs["Roughness"].default_value = 0.22 if gold else (0.3 if grey_metal else (0.42 if max(c) < 0.08 else 0.5))
    return m

# Fusion appearance wins over the USD material name (the USD names some bodies' materials
# after a different appearance, e.g. the M8 Flex came through as Nylon White)
APPEARANCE_OVERRIDE = {"Phenolic (Amber)": "Phenolic_(Amber).001"}

def materials():
    swapped = 0
    for o in usd_meshes_in_root():
        for sl in o.material_slots:
            if not sl.material: continue
            t = bpy.data.materials.get(APPEARANCE_OVERRIDE.get(o["fusion_appearance"], "")) or _tuned_for(sl.material)
            if t:
                sl.link = 'OBJECT'; sl.material = t; swapped += 1
    brand_colours()
    return swapped


# Brand colours (sRGB), from the user
MOJAVE_DESERT = (199, 181, 149)     # Pantone Mojave Desert #C7B595 - every tan part
COOL_GRAY_11C = (83, 86, 90)        # Pantone Cool Gray 11 C #53565A - every grey housing part
TAN_MATERIALS = ("BEACON_DesertTan_TPE", "Mojave_Desert_ASA.001", "Sandy_Overmolding.001")
GREY_MATERIALS = ("BEACON_DarkGrey_Plastic",)
FLEX_MATERIALS = ("Phenolic_(Amber).001",)  # flex PCBs -> translucent polyimide

# Linear base colours tuned so the face-on render measures the Pantone value under AgX
# (Medium High Contrast, +0.3 exposure) + this lighting. A straight sRGB->linear conversion
# renders the grey too light (110,116,121) and the tan washed out. Measured after tuning:
# grey face (84,86,90), tan ~(200,184,159). Re-tune if lighting/exposure changes.
TUNED_BASE = {MOJAVE_DESERT: (0.5744, 0.4221, 0.2175), COOL_GRAY_11C: (0.048, 0.0496, 0.0547)}

def _base(mat, srgb):
    p = _principled(bpy.data.materials.get(mat))
    if not p: return False
    p.inputs["Base Color"].default_value = (*TUNED_BASE.get(srgb, [_lin(c / 255) for c in srgb]), 1)
    return True

def polyimide_material(m):
    p = _principled(m)
    for l in list(p.inputs["Base Color"].links): m.node_tree.links.remove(l)
    p.inputs["Base Color"].default_value = (0.78, 0.36, 0.05, 1)     # amber polyimide (Kapton)
    p.inputs["Roughness"].default_value = 0.22
    p.inputs["Transmission Weight"].default_value = 0.75
    p.inputs["IOR"].default_value = 1.7
    p.inputs["Coat Weight"].default_value = 0.5; p.inputs["Coat Roughness"].default_value = 0.06
    p.inputs["Metallic"].default_value = 0.0

def brand_colours():
    out = {}
    for m in TAN_MATERIALS: out[m] = _base(m, MOJAVE_DESERT)
    for m in GREY_MATERIALS: out[m] = _base(m, COOL_GRAY_11C)
    for m in FLEX_MATERIALS:
        if m in bpy.data.materials: polyimide_material(bpy.data.materials[m]); out[m] = "polyimide"
    return out


# ---------------------------------------------------------------- 5b. logo colour
LOGO_FACES = os.path.join(PROJECT, "logo_faces.json")   # faces picked in Fusion (see DESIGN.md)
PANTONE_165C = (255, 103, 31)                            # Pantone 165 C, sRGB approximation (#FF671F)

def logo_material():
    m = bpy.data.materials.get("BEACON_Pantone165C")
    if m: return m
    m = bpy.data.materials.new("BEACON_Pantone165C"); m.use_nodes = True
    p = _principled(m)
    # Tuned so the face-on render measures ~(233,98,45) under AgX + this lighting.
    # Plain sRGB->linear of PANTONE_165C renders salmon (~239,159,134): AgX desaturates
    # bright saturated colours and specular adds white, hence the darker base + low specular.
    p.inputs["Base Color"].default_value = (0.7, 0.058, 0.0, 1)
    p.inputs["Roughness"].default_value = 0.7
    p.inputs["Specular IOR Level"].default_value = 0.05
    return m

def logo(tol=0.003):
    """Colour the mesh faces lying on the Fusion faces listed in logo_faces.json."""
    return paint_faces(LOGO_FACES, logo_material(), tol)

def paint_faces(faces_json, mat, tol=0.003):
    """Assign `mat` to every mesh face lying on the Fusion faces in `faces_json`
    (a selection dump: body, path, bbox in cm, normal). Returns {object: face count}."""
    faces = json.load(open(faces_json, encoding="utf-8"))
    hits = {}
    for o in usd_meshes_in_root():
        mine = [f for f in faces if f.get("body") == o["fusion_body"] and f.get("path") == json.loads(o["fusion_path_json"])]
        if not mine: continue
        if mat.name not in [s.material.name for s in o.material_slots if s.material]:
            o.data.materials.append(None); o.material_slots[-1].link = 'OBJECT'; o.material_slots[-1].material = mat
        idx = [i for i, s in enumerate(o.material_slots) if s.material == mat][0]
        base = Vector(o["base_loc"]); n = 0
        for poly in o.data.polygons:
            d = poly.center + base                            # device space
            fp = (d.x, d.z, -d.y)                             # -> Fusion cm
            fn = (poly.normal.x, poly.normal.z, -poly.normal.y)
            for f in mine:
                if all(f["min"][k] - tol <= fp[k] <= f["max"][k] + tol for k in range(3)) and \
                   sum(a * b for a, b in zip(fn, f["normal"])) > 0.95:
                    poly.material_index = idx; n += 1; break
        hits[o.name] = n
    return hits


# ---------------------------------------------------------------- 5c. LEDs + light pipe
LED_FACES = os.path.join(PROJECT, "led_faces.json")      # QLS6A side-emitting faces picked in Fusion
LED_COLOR = (1.0, 0.02, 0.62)                             # magenta (linear); change here
LIGHT_PIPE_BODIES = ("Light Pipe", "Body172")             # bodies of Rear Assembly/PCB Assembly/Light Pipe:1

def led_material():
    m = bpy.data.materials.get("BEACON_LED_Emitter") or bpy.data.materials.new("BEACON_LED_Emitter")
    m.use_nodes = True; p = _principled(m)
    p.inputs["Base Color"].default_value = (*LED_COLOR, 1)
    p.inputs["Emission Color"].default_value = (*LED_COLOR, 1)
    p.inputs["Emission Strength"].default_value = 40.0
    return m

def light_pipe_material(glow=4.5):
    """Milky translucent polycarbonate that appears lit from the LEDs."""
    m = bpy.data.materials.get("BEACON_LightPipe_PC") or bpy.data.materials.new("BEACON_LightPipe_PC")
    m.use_nodes = True; p = _principled(m)
    p.inputs["Base Color"].default_value = (0.93, 0.95, 0.96, 1)
    p.inputs["Roughness"].default_value = 0.35
    p.inputs["IOR"].default_value = 1.585                  # polycarbonate
    p.inputs["Transmission Weight"].default_value = 0.85
    p.inputs["Subsurface Weight"].default_value = 0.35
    p.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0); p.inputs["Subsurface Scale"].default_value = 0.4
    p.inputs["Coat Weight"].default_value = 0.4; p.inputs["Coat Roughness"].default_value = 0.08
    p.inputs["Emission Color"].default_value = (*LED_COLOR, 1)
    # light pipes glow hardest at grazing angles / edges: drive strength by Layer Weight facing
    nt = m.node_tree
    for n in [n for n in nt.nodes if n.name.startswith("LP_")]: nt.nodes.remove(n)
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.name = "LP_facing"; lw.inputs["Blend"].default_value = 0.35
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.name = "LP_strength"
    mr.inputs["To Min"].default_value = glow * 0.35; mr.inputs["To Max"].default_value = glow * 2.0
    nt.links.new(lw.outputs["Facing"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], p.inputs["Emission Strength"])
    lw.location = (p.location.x - 500, p.location.y - 300); mr.location = (p.location.x - 250, p.location.y - 300)
    return m

def leds(light_energy=6.0, light_size=0.12):
    out = {"emitter_faces": paint_faces(LED_FACES, led_material())}
    pipe = light_pipe_material(); n = 0
    for o in usd_meshes_in_root():
        if "Light Pipe:1" in o["fusion_path"] and o["fusion_body"] in LIGHT_PIPE_BODIES:
            for sl in o.material_slots: sl.link = 'OBJECT'; sl.material = pipe
            n += 1
    out["light_pipe_objects"] = n
    # a small area light on each emitter face, parented to its LED so it follows the PCB
    faces = json.load(open(LED_FACES, encoding="utf-8"))
    for i, f in enumerate(faces):
        led = next(o for o in usd_meshes_in_root() if o["fusion_body"] == f["body"] and json.loads(o["fusion_path_json"]) == f["path"])
        c = [(a + b) / 2 for a, b in zip(f["min"], f["max"])]
        dev_c = Vector((c[0], -c[2], c[1])); dev_n = Vector((f["normal"][0], -f["normal"][2], f["normal"][1]))
        name = f"LED_Light_{i + 1}"
        L = bpy.data.objects.get(name)
        if not L:
            d = bpy.data.lights.new(name, 'AREA'); L = bpy.data.objects.new(name, d)
            bpy.data.collections[ROOT_COLLECTION].objects.link(L)
        L.data.energy = light_energy; L.data.size = light_size; L.data.color = LED_COLOR
        # LED mesh vertices are relative to its origin (base_loc), so express the light the same way
        L.parent = led; L.matrix_parent_inverse = Matrix.Identity(4)
        L.matrix_basis = (Matrix.Translation(dev_c + dev_n * 0.02 - Vector(led["base_loc"]))
                          @ dev_n.to_track_quat('-Z', 'Y').to_matrix().to_4x4())
    out["lights"] = len(faces)
    # brighter when assembled (only the pipe's thin exit edge shows), softer while opened up
    mr = pipe.node_tree.nodes["LP_strength"]; lo, hi = mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value
    if pipe.node_tree.animation_data: pipe.node_tree.animation_data_clear()
    for f, k in ((1, ASSEMBLED_GLOW), (38, ASSEMBLED_GLOW), (56, 1.0), (150, 1.0), (166, ASSEMBLED_GLOW)):
        mr.inputs["To Min"].default_value = lo * k; mr.inputs["To Max"].default_value = hi * k
        mr.inputs["To Min"].keyframe_insert("default_value", frame=f); mr.inputs["To Max"].keyframe_insert("default_value", frame=f)
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = lo, hi
    out["bloom"] = bloom()
    return out


ASSEMBLED_GLOW = 2.2

def bloom(threshold=6.0, strength=0.7, size=0.4):
    """Compositor bloom: only emitters (LEDs, light pipe edges) exceed the threshold."""
    s = bpy.context.scene
    g = bpy.data.node_groups.get("BEACON_Bloom") or bpy.data.node_groups.new("BEACON_Bloom", "CompositorNodeTree")
    g.nodes.clear(); g.interface.clear()
    g.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = g.nodes.new("CompositorNodeRLayers"); rl.scene = s; rl.location = (-300, 0)
    gl = g.nodes.new("CompositorNodeGlare"); go = g.nodes.new("NodeGroupOutput"); go.location = (300, 0)
    gl.inputs["Type"].default_value = 'Bloom'; gl.inputs["Quality"].default_value = 'High'
    gl.inputs["Threshold"].default_value = threshold; gl.inputs["Strength"].default_value = strength
    gl.inputs["Size"].default_value = size
    g.links.new(rl.outputs["Image"], gl.inputs["Image"]); g.links.new(gl.outputs[0], go.inputs[0])
    s.compositing_node_group = g
    return g.name


# ---------------------------------------------------------------- 5d. mid-animation spin
SPIN_FRAMES = (60, 124)        # full 360 about the stack (device Z) axis, eased in/out

def spin():
    root = bpy.data.objects["BEACON_root"]
    sp = bpy.data.objects.get("BEACON_spin")
    if not sp:
        sp = bpy.data.objects.new("BEACON_spin", None); bpy.data.collections[ROOT_COLLECTION].objects.link(sp)
    sp.parent = root; sp.matrix_parent_inverse = Matrix.Identity(4)
    sp.location = (0, 0, 0); sp.rotation_mode = 'XYZ'; sp.empty_display_size = 1.5
    sp.animation_data_clear()
    for f, a in ((SPIN_FRAMES[0], 0.0), (SPIN_FRAMES[1], 2 * math.pi)):
        sp.rotation_euler = (0, 0, a); sp.keyframe_insert("rotation_euler", frame=f)
    return sp


# Explicit (out start, out end, in start, in end) frames where the stagger formula can't give
# the right order: the connector and thumb screw pass through the bracket's arms, so they
# come out before the bracket slides off and go back in only after it is back on.
TIMING = {
    "Bracket thumb screw": (36, 66, 130, 160),
    "M8 connector":        (38, 70, 128, 160),
    "Wall bracket":        (56, 90, 96, 126),
}

# ---------------------------------------------------------------- 5e. idle (start/end) pose
# Face-on base orientation of BEACON_root (hero face square to the camera), then a tilt in
# *camera* space: pitch < 0 tips the top away (shows the bottom edge / light-pipe exit),
# yaw < 0 swings the right end toward camera, roll > 0 lifts the right end on screen.
FACE_ON_QUAT = (0.5538, -0.8085, -0.1644, 0.1126)
IDLE_TILT = {"pitch": -17.0, "yaw": -18.0, "roll": 6.0}     # degrees, matched to the user's Fusion view
IDLE_FRAMES = (1, 22, 162, 180)

def idle_pose(pitch=None, yaw=None, roll=None):
    from mathutils import Quaternion, Euler
    t = dict(IDLE_TILT)
    for k, v in (("pitch", pitch), ("yaw", yaw), ("roll", roll)):
        if v is not None: t[k] = v
    s = bpy.context.scene; f0 = s.frame_current; s.frame_set(IDLE_FRAMES[0])
    cam = s.camera.matrix_world.to_quaternion()            # rotation only (rig scale dropped)
    local = Euler((math.radians(t["pitch"]), math.radians(t["yaw"]), math.radians(t["roll"])), 'XYZ').to_quaternion()
    q = cam @ local @ cam.inverted() @ Quaternion(FACE_ON_QUAT)
    root = bpy.data.objects["BEACON_root"]
    s.frame_set(62); mid = root.rotation_quaternion.copy()
    if q.dot(mid) < 0: q.negate()                            # keep the shortest path into the 3/4 pose
    for f in IDLE_FRAMES:
        root.rotation_quaternion = q; root.keyframe_insert("rotation_quaternion", frame=f)
    s.frame_set(f0)
    return [round(x, 4) for x in q]


# ---------------------------------------------------------------- 6. animate
def animate(retire_obj_parts=True):
    s = bpy.context.scene
    root = bpy.data.objects["BEACON_root"]
    rc = bpy.data.collections[ROOT_COLLECTION]
    if root.name not in rc.objects:
        for c in list(root.users_collection): c.objects.unlink(root)
        rc.objects.link(root)
    inv = Matrix.Translation(-ROOT_REST)
    Lmax = 5.2
    sp = spin()                                  # child of root, identity rest: parts ride the spin
    for o in usd_meshes_in_root():
        o.animation_data_clear()
        base = o.matrix_world.to_translation() if o.parent is None else Vector(o["base_loc"])
        o.parent = sp; o.matrix_parent_inverse = inv
        o["base_loc"] = list(base); o.location = base
        off = Vector(o["explode_off"])
        if off.length < 1e-6: continue
        r = min(1.25, o["explode_L"] / Lmax)     # >1 = leads the housings out, follows them back
        a = 42 + (1 - r) * 16; b = a + 38
        c = 104 + r * 14; d = c + 38
        if o.get("explode_group") in TIMING:
            a, b, c, d = TIMING[o["explode_group"]]
        for f, p in ((a, base), (b, base + off), (c, base + off), (d, base)):
            o.location = p; o.keyframe_insert("location", frame=f)
    if retire_obj_parts and "BEACON_parts" in bpy.data.collections:
        old = bpy.data.collections["BEACON_parts"]
        old.hide_render = True
        lc = bpy.context.view_layer.layer_collection.children.get("BEACON_parts")
        if lc: lc.exclude = True
    usd = bpy.context.view_layer.layer_collection.children.get("USD_import")
    if usd and not bpy.data.collections["USD_import"].all_objects:
        bpy.data.collections.remove(bpy.data.collections["USD_import"])
    s.frame_set(1)


def build():
    s = bpy.context.scene
    keep = (s.frame_start, s.frame_end, s.render.fps, s.render.fps_base)
    out = {"baked": bake(), "worst_match_cm": identify(), "collections": organise(),
           "groups": offsets(), "material_slots": materials()}
    animate()                                   # sets base_loc, which logo() needs
    if os.path.exists(LOGO_FACES): out["logo_faces"] = logo()
    if os.path.exists(LED_FACES): out["leds"] = leds()
    # usd_import resets the scene frame range/fps to the USD stage's: restore ours
    s.frame_start, s.frame_end, s.render.fps, s.render.fps_base = 1, 180, 30, 1.0
    out["frame_range_before"] = keep
    bpy.ops.wm.save_mainfile()
    return out
