"""
Band V2 strap: modelled in Blender (it isn't in CAD) and animated without cloth simulation.

Run inside Blender with band_explode.blend open (build_band.build() calls it):
    exec(open(r"C:\\Users\\Travis\\Scroll Sequence\\products\\band-v2\\tools\\strap.py", encoding="utf-8").read())
    strap()

How the real strap is put together
  One woven elastic strap forms the wrist loop. Each end is thin webbing that comes UP through
  its slot from underneath, wraps out over the slot's outer bar and tucks back in under it,
  ending in a RIGID padded tab that lies flat on the outside of the strap. The tab's back is
  hook-and-loop; its front is a faux-leather patch, stitched on, printed with the S logo
  (lying sideways: roof piece orange, lower piece grey). The tab never bends; only the thin
  webbing does.

How it's animated
  - BAND_StrapPath: a dense poly curve along the strap, from the -X tip to the +X tip.
    Each end is a turning-angle profile (_tab_profile): webbing up through the slot, a half
    turn over the bar, down the outside, an S-bend in, then the tab (zero turning, so rigid).
    Multiplying every turn by u (1 = worn, 0 = straight) unfolds it without stretching; the
    curve stores u = 0.875 ... 0 as shape keys "Fold_875" ... "Fold_000", blended in pairs.
    "Drop" lowers the wrist loop DROP_MAX (the sides get longer).
  - BAND_Strap: a flat ribbon bent onto the path by a Curve modifier. Solidify gives it
    thickness; the "Tab" vertex group makes the tabs THICK_T and the rest STRAP_T.
  - Off: the webbing unbends so each tab swings up, rigid, until it stands straight up in line
    with the strap (u 1 -> 0). Then the loop drops by d while the ribbon slides d along the
    path, so the whole strap moves straight down and the tabs pass down through the slots.
  - On (end of the sequence): the exact reverse. The strap rises with the tabs pointing up;
    once each tab is fully through its slot, the webbing bends over the bar and lays the tab
    flat onto the strap.
  - The path is built in the curve object's local XY plane (a flat curve's normal = the
    strap's width axis); the object is rotated 90 deg about X so that plane = device XZ.

Measured from the Bottom shell (device cm): strap slots are through-holes at |x| 2.85-3.35,
|y| < 1.85; the outer bar spans |x| 3.35-3.6, z -0.52..0.08.
"""
import bpy, math
from mathutils import Vector, Matrix

STRAP_W = 3.5           # cm, webbing width (slot is 3.7 long)
STRAP_T = 0.16          # cm, webbing thickness
THICK_T = 0.36          # cm, padded tab thickness (slot is 0.5 wide)
RAMP = 0.2              # cm over which the webbing thickens into the tab (on the webbing side)
TAB_LEN = 2.2           # cm, the rigid padded tab at each end (never bends)

SLOT_X = 3.1            # strap centreline through the slot
UP_START = -0.6         # the end profile starts here, just under the slot
WRAP_Z = 0.03           # centre of the webbing's wrap: the bar top (z 0.084) sits inside its inner radius
WRAP_R = (3.6 + STRAP_T / 2 + 0.03 - SLOT_X) / 2    # webbing clears the bar's outer face (x 3.6)
DOWN_Z = -0.65          # webbing runs down the outside of the bar to just under it (bar bottom -0.52)
TUCK_DZ = 0.5           # S-bend in, so the tab lands flat on the strap
LOOP_C = -3.0           # centre of the bottom arc (worn): wrist ~6.2 cm wide, ~6 cm deep
LOOP_R = SLOT_X         # bottom arc radius (sides come straight down out of the slots)

DROP_MAX = 26.0         # cm the strap pulls down: tabs clear the slots at ~4, then out of frame
FOLD_LEVELS = (1.0, 0.875, 0.75, 0.625, 0.5, 0.375, 0.25, 0.125, 0.0)   # basis + 8 keys

# Timeline (the pod's own sequence runs in between; see build_band.py)
WORN_END, FOLD_END, DROP_END = 20, 36, 80          # off: unfold, then pull down
RISE_START, RISE_END, HOOK_END = 236, 282, 296     # on: rise, then fold over

N_SIDE, N_ARC = 80, 90
DS = 0.025              # cm between path points on the tab profile


def _arc(c, r, a0, a1, n):
    return [Vector((c[0] + r * math.cos(a0 + (a1 - a0) * k / n), c[1] + r * math.sin(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]

def _line(p, q, n):
    return [p.lerp(q, k / n) for k in range(n + 1)]

def _tab_profile():
    """(length, curvature) segments of the +X end from UP_START, heading up: thin webbing up
    through the slot, over the bar, down the outside and in, then the rigid tab (curvature 0,
    so it never bends at any fold). Positive
    curvature turns clockwise (toward +X when heading up)."""
    dx = (SLOT_X + 2 * WRAP_R) - (SLOT_X + STRAP_T / 2 + THICK_T / 2 + 0.01)   # outside -> onto strap
    beta = 2 * math.atan(dx / TUCK_DZ)
    R = TUCK_DZ / (2 * math.sin(beta))
    return [(WRAP_Z - UP_START, 0.0),            # up through the slot
            (math.pi * WRAP_R, 1 / WRAP_R),       # over the bar
            (WRAP_Z - DOWN_Z, 0.0),               # down the outside
            (R * beta, 1 / R), (R * beta, -1 / R),  # S-bend in onto the strap
            (TAB_LEN, 0.0)]                       # the rigid padded tab, flat on the strap

def _tab_len():
    return sum(l for l, _ in _tab_profile())

def _right_upper(u):
    """+X tab from UP_START to the tip. u = 1 folded over the bar, 0 straight up."""
    p = Vector((SLOT_X, UP_START)); th = 0.0; P = [p.copy()]
    for length, k in _tab_profile():
        n = max(1, round(length / DS)); ds = length / n
        for _ in range(n):
            dth = u * k * ds
            mid = th + dth / 2
            chord = ds if abs(dth) < 1e-9 else 2 * math.sin(dth / 2) / dth * ds    # exact on arcs
            p = p + Vector((math.sin(mid), math.cos(mid))) * chord
            th += dth; P.append(p.copy())
    return P

def path_points(drop=0.0, u=1.0):
    """Ordered 2D points (x, z) from the -X tip to the +X tip. Same point count for any
    drop/u, so the results can be used as curve shape keys."""
    right_up = _right_upper(u)
    left_up = [Vector((-q.x, q.y)) for q in right_up]
    c = LOOP_C - drop
    left_side = _line(Vector((-SLOT_X, UP_START)), Vector((-SLOT_X, c)), N_SIDE)
    arc = _arc((0, c), LOOP_R, math.pi, 2 * math.pi, N_ARC)
    right_side = _line(Vector((SLOT_X, c)), Vector((SLOT_X, UP_START)), N_SIDE)
    return left_up[::-1] + left_side[1:] + arc[1:] + right_side[1:] + right_up[1:]

def _length(P):
    return sum((P[k + 1] - P[k]).length for k in range(len(P) - 1))


# ---------------------------------------------------------------- materials
def _nodes(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled"); p.location = (600, 0)
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, p

def _math(nt, op, a, b=None, loc=(0, 0)):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = op; n.location = loc
    for i, v in enumerate((a, b)):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = v
        else: nt.links.new(v, n.inputs[i])
    return n.outputs[0]

def _uv(nt, name, loc):
    n = nt.nodes.new("ShaderNodeUVMap"); n.uv_map = name; n.location = loc
    s = nt.nodes.new("ShaderNodeSeparateXYZ"); s.location = (loc[0] + 180, loc[1])
    nt.links.new(n.outputs["UV"], s.inputs[0])
    return n.outputs["UV"], s.outputs[0], s.outputs[1]

def _wave(nt, vec, scale, direction, loc, rot_deg=0.0):
    src = vec
    if rot_deg:
        mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (loc[0] - 200, loc[1])
        mp.inputs["Rotation"].default_value = (0, 0, math.radians(rot_deg))
        nt.links.new(vec, mp.inputs["Vector"]); src = mp.outputs["Vector"]
    w = nt.nodes.new("ShaderNodeTexWave"); w.location = loc
    w.wave_type = 'BANDS'; w.bands_direction = direction; w.wave_profile = 'SIN'
    w.inputs["Scale"].default_value = scale
    nt.links.new(src, w.inputs["Vector"])
    return w.outputs["Fac"]

def fabric_material():
    """Black woven elastic webbing: a twill of diagonal ribs over a fine cross weave, visible
    at render size (Wave period = 0.314 / scale cm). UVs are in cm."""
    m, nt, p = _nodes("BAND_Strap_Webbing")
    p.inputs["Roughness"].default_value = 0.85
    p.inputs["Sheen Weight"].default_value = 0.35; p.inputs["Sheen Roughness"].default_value = 0.45
    p.inputs["Sheen Tint"].default_value = (0.1, 0.1, 0.11, 1)
    p.inputs["Specular IOR Level"].default_value = 0.2
    uv, _, _ = _uv(nt, "UVMap", (-900, 0))
    twill = _wave(nt, uv, 2.6, 'X', (-400, 200), rot_deg=40)       # 0.12 cm diagonal ribs
    cross = _wave(nt, uv, 6.0, 'Y', (-400, -100))                  # 0.05 cm weave
    h = _math(nt, 'MULTIPLY_ADD', twill, 0.75, (-150, 50)); nt.links.new(cross, h.node.inputs[2])   # 0..1.75
    col = nt.nodes.new("ShaderNodeMapRange"); col.location = (100, 250)
    col.inputs["To Min"].default_value = 0.006; col.inputs["To Max"].default_value = 0.022
    col.inputs["From Max"].default_value = 1.75
    nt.links.new(h, col.inputs["Value"])
    rgb = nt.nodes.new("ShaderNodeCombineColor"); rgb.location = (350, 250)
    for i in range(3): nt.links.new(col.outputs["Result"], rgb.inputs[i])
    nt.links.new(rgb.outputs[0], p.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.location = (350, -200)
    bump.inputs["Strength"].default_value = 0.6; bump.inputs["Distance"].default_value = 0.02
    nt.links.new(h, bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m

def velcro_material():
    """Hook-and-loop on the back of each tab: dark, fuzzy, very rough."""
    m, nt, p = _nodes("BAND_Strap_Velcro")
    p.inputs["Base Color"].default_value = (0.014, 0.014, 0.015, 1)
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Sheen Weight"].default_value = 0.6; p.inputs["Sheen Roughness"].default_value = 0.3
    p.inputs["Sheen Tint"].default_value = (0.12, 0.12, 0.13, 1)
    p.inputs["Specular IOR Level"].default_value = 0.1
    uv, _, _ = _uv(nt, "UVMap", (-900, 0))
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.location = (-400, 100)
    nz.inputs["Scale"].default_value = 45.0; nz.inputs["Detail"].default_value = 6.0
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.location = (-400, -150)
    vo.inputs["Scale"].default_value = 30.0
    nt.links.new(uv, nz.inputs["Vector"]); nt.links.new(uv, vo.inputs["Vector"])
    h = _math(nt, 'ADD', nz.outputs["Fac"], vo.outputs["Distance"], (-150, 0))
    bump = nt.nodes.new("ShaderNodeBump"); bump.location = (300, -200)
    bump.inputs["Strength"].default_value = 0.8; bump.inputs["Distance"].default_value = 0.015
    nt.links.new(h, bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m

def leather_material(tab_len):
    """Faux-leather patch on the front of each tab: fine pebble grain, satin, with a dashed
    stitch line inset STITCH_IN from the patch edge. Uses the "Patch" UVs: U = cm from the
    tip, V = cm across the width."""
    STITCH_IN, STITCH_W, DASH = 0.13, 0.022, 0.11
    m, nt, p = _nodes("BAND_Strap_Leather")
    p.inputs["Roughness"].default_value = 0.5
    p.inputs["Specular IOR Level"].default_value = 0.35
    uv, U, V = _uv(nt, "Patch", (-1400, 0))
    # grain
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.location = (-900, 400)
    vo.inputs["Scale"].default_value = 55.0; nt.links.new(uv, vo.inputs["Vector"])
    # stitch mask: long edges (|V| near W/2 - in) and the two ends (U near in, tab_len - in)
    half = STRAP_W / 2 - STITCH_IN
    absV = _math(nt, 'ABSOLUTE', V, None, (-1000, 0))
    eV = _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', absV, half, (-850, 0)), None, (-700, 0))
    onV = _math(nt, 'LESS_THAN', eV, STITCH_W, (-550, 0))
    inU = _math(nt, 'MULTIPLY', _math(nt, 'GREATER_THAN', U, STITCH_IN - STITCH_W, (-850, -150)),
                _math(nt, 'LESS_THAN', U, tab_len - STITCH_IN + STITCH_W, (-850, -250)), (-700, -200))
    dashU = _math(nt, 'GREATER_THAN', _math(nt, 'SINE', _math(nt, 'MULTIPLY', U, 2 * math.pi / DASH, (-850, -350)), None, (-700, -350)), 0.0, (-550, -350))
    longs = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', onV, inU, (-400, -50)), dashU, (-250, -50))
    eU0 = _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', U, STITCH_IN, (-850, -500)), None, (-700, -500))
    eU1 = _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', U, tab_len - STITCH_IN, (-850, -600)), None, (-700, -600))
    onU = _math(nt, 'LESS_THAN', _math(nt, 'MINIMUM', eU0, eU1, (-550, -550)), STITCH_W, (-400, -550))
    inV = _math(nt, 'LESS_THAN', absV, half + STITCH_W, (-400, -650))
    dashV = _math(nt, 'GREATER_THAN', _math(nt, 'SINE', _math(nt, 'MULTIPLY', V, 2 * math.pi / DASH, (-700, -750)), None, (-550, -750)), 0.0, (-400, -750))
    ends = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', onU, inV, (-250, -600)), dashV, (-100, -600))
    stitch = _math(nt, 'MAXIMUM', longs, ends, (50, -300))
    col = nt.nodes.new("ShaderNodeMix"); col.data_type = 'RGBA'; col.location = (300, 200)
    col.inputs["A"].default_value = (0.018, 0.018, 0.02, 1)
    col.inputs["B"].default_value = (0.09, 0.09, 0.095, 1)      # dark grey thread
    nt.links.new(stitch, col.inputs["Factor"]); nt.links.new(col.outputs["Result"], p.inputs["Base Color"])
    h = _math(nt, 'MULTIPLY_ADD', stitch, 1.5, (200, -200)); nt.links.new(vo.outputs["Distance"], h.node.inputs[2])
    bump = nt.nodes.new("ShaderNodeBump"); bump.location = (400, -300)
    bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.01
    nt.links.new(h, bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m

def logo_grey_material():
    """Grey for the lower piece of the S on the strap patches."""
    m, nt, p = _nodes("BAND_Logo_Grey")
    p.inputs["Base Color"].default_value = (0.21, 0.21, 0.22, 1)
    p.inputs["Roughness"].default_value = 0.45
    return m


# ---------------------------------------------------------------- logo
LOGO_ENDS = (+1, -1)    # both tabs carry the S logo
LOGO_H = 1.0            # cm, height of the S on the patch

def tab_logo(path, L, end):
    """The S logo printed on a tab's leather patch: the logo faces copied from the Top shell
    (two pieces: the upper "roof" piece Pantone orange, the lower one grey), laid on the patch over
    the wrap and bent by the same Curve modifier as the strap."""
    import bmesh
    top = bpy.data.objects["Top:1"]; pan = bpy.data.materials["BEACON_Pantone165C"]
    idx = {i for i, sl in enumerate(top.material_slots) if sl.material == pan}
    bpy.context.scene.frame_set(1)
    M = top.matrix_world.copy()
    bm = bmesh.new(); bm.from_mesh(top.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in idx], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    pts = {v: M @ v.co for v in bm.verts}
    # split into connected pieces; the one highest in the logo's Y is the upper part
    left, pieces = set(bm.faces), []
    while left:
        stack = [left.pop()]; piece = set(stack)
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in left: left.discard(g); piece.add(g); stack.append(g)
        pieces.append(piece)
    upper = max(pieces, key=lambda pc: sum(pts[v].y for f in pc for v in f.verts) / sum(len(f.verts) for f in pc))
    for f in bm.faces: f.material_index = 0 if f in upper else 1     # upper (roof) orange, lower grey
    ys = [q.y for q in pts.values()]; xs = [q.x for q in pts.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    k = LOGO_H / (max(ys) - min(ys))
    # centre: on the outside of the wrap, from its top down the outer face
    prof = _tab_profile()
    from_tip = TAB_LEN / 2                        # centred on the tab
    xc = L - from_tip if end > 0 else from_tip
    lift = THICK_T / 2 + 0.004
    # Ribbon +Y is the outside of the wrap. As on the real patch, the S lies sideways: seen from
    # outside with the bar at the top, its roof points to the viewer's right (ribbon -end*Z) and
    # its right-hand side points down toward the tip (ribbon +end*X). The signs flip per end
    # because the two tabs are mirror images, so neither S is mirrored.
    for v in bm.verts:
        lx, ly = (pts[v].x - cx) * k, (pts[v].y - cy) * k
        v.co = Vector((xc + end * lx, lift, -end * ly))
    # The logo faces are large concave n-gons. Triangulate them while still flat, then split
    # long edges so the print follows the wrap instead of cutting chords through it.
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    for _ in range(6):
        long_edges = [e for e in bm.edges if e.calc_length() > 0.04]
        if not long_edges: break
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    name = "BAND_StrapLogo_" + ("+X" if end > 0 else "-X")
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(pan); me.materials.append(logo_grey_material())
    for poly in me.polygons: poly.use_smooth = False
    ob = bpy.data.objects.new(name, me); path.users_collection[0].objects.link(ob)
    ob.parent = path; ob.matrix_parent_inverse = Matrix.Identity(4)
    cm = ob.modifiers.new("FollowPath", 'CURVE'); cm.object = path; cm.deform_axis = 'POS_X'
    return ob


# ---------------------------------------------------------------- build
def _fold_weights(u):
    """Shape-key weights that put the tabs at fold u, blending the two nearest levels."""
    w = {lv: 0.0 for lv in FOLD_LEVELS[1:]}
    for a, b in zip(FOLD_LEVELS, FOLD_LEVELS[1:]):
        if a >= u >= b:
            t = (a - u) / (a - b)
            if a != 1.0: w[a] = 1 - t
            w[b] = t
            break
    return w

def _ease(t):
    t = min(1.0, max(0.0, t)); return t * t * (3 - 2 * t)

def strap():
    import bmesh
    rc = bpy.data.collections["BAND V2"]
    for n in ("BAND_Strap", "BAND_StrapPath", "BAND_StrapLogo", "BAND_StrapLogo_+X", "BAND_StrapLogo_-X"):
        o = bpy.data.objects.get(n)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    cu = bpy.data.curves.get("BAND_StrapPath")
    if cu: bpy.data.curves.remove(cu)
    for n in ("BAND_Strap", "BAND_StrapLogo", "BAND_StrapLogo_+X", "BAND_StrapLogo_-X"):
        me_old = bpy.data.meshes.get(n)
        if me_old: bpy.data.meshes.remove(me_old)

    P0 = path_points(0, 1)
    L = _length(P0)                                  # strap length = worn path, tip to tip
    tab = TAB_LEN                                    # padded length at each end

    # --- path curve + shape keys
    cu = bpy.data.curves.new("BAND_StrapPath", 'CURVE')
    cu.dimensions = '3D'; cu.twist_mode = 'Z_UP'
    sp = cu.splines.new('POLY'); sp.points.add(len(P0) - 1)
    for k, q in enumerate(P0): sp.points[k].co = (q.x, q.y, 0, 1)
    path = bpy.data.objects.new("BAND_StrapPath", cu); rc.objects.link(path)
    path.matrix_world = Matrix.Rotation(math.radians(90), 4, 'X')
    path.hide_render = True
    path.shape_key_add(name="Basis", from_mix=False)
    for lv in FOLD_LEVELS[1:]:
        kb = path.shape_key_add(name=f"Fold_{round(lv * 1000):03d}", from_mix=False)
        for k, q in enumerate(path_points(0, lv)): kb.data[k].co = (q.x, q.y, 0)
    kb = path.shape_key_add(name="Drop", from_mix=False)
    for k, q in enumerate(path_points(DROP_MAX, 1)): kb.data[k].co = (q.x, q.y, 0)
    keys = cu.shape_keys.key_blocks

    # --- ribbon: X = length (0..L), Z = width, Y = thickness (Solidify); UVs in cm
    me = bpy.data.meshes.new("BAND_Strap"); bm = bmesh.new()
    nx = max(2, int(L / 0.05)); nz = 8
    uvl = bm.loops.layers.uv.new("UVMap"); uvp = bm.loops.layers.uv.new("Patch")
    dfl = bm.verts.layers.deform.verify()
    verts = []
    for i in range(nx + 1):
        x = L * i / nx; d = min(x, L - x)
        wgt = 1.0 - _ease((d - tab) / RAMP)                       # 1 on the tabs, 0 on the strap
        row = []
        for j in range(nz + 1):
            v = bm.verts.new((x, 0, -STRAP_W / 2 + STRAP_W * j / nz)); v[dfl][0] = wgt; row.append(v)
        verts.append(row)
    for i in range(nx):
        x = L * (i + 0.5) / nx
        for j in range(nz):
            f = bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))
            f.material_index = 1 if min(x, L - x) < tab else 0
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.x, lp.vert.co.z)
                lp[uvp].uv = (min(lp.vert.co.x, L - lp.vert.co.x), lp.vert.co.z)
    bm.to_mesh(me); bm.free()
    # material slots: Solidify puts the +Y (outer) shell at index + 2 and rims at index + 4
    fab, vel, lea = fabric_material(), velcro_material(), leather_material(tab)
    for mat in (fab, vel, fab, lea, fab, fab): me.materials.append(mat)
    for poly in me.polygons: poly.use_smooth = True
    st = bpy.data.objects.new("BAND_Strap", me); rc.objects.link(st)
    vg = st.vertex_groups.new(name="Tab")
    # (bmesh deform layer index 0 -> this group)
    st.parent = path; st.matrix_parent_inverse = Matrix.Identity(4); st.location = (0, 0, 0)
    so = st.modifiers.new("Thickness", 'SOLIDIFY'); so.thickness = THICK_T; so.offset = 0
    so.use_even_offset = True; so.use_rim = True
    so.vertex_group = "Tab"; so.thickness_vertex_group = STRAP_T / THICK_T
    so.material_offset = 2; so.material_offset_rim = 4
    bv = st.modifiers.new("SoftEdges", 'BEVEL'); bv.width = 0.04; bv.segments = 3; bv.limit_method = 'ANGLE'
    cm = st.modifiers.new("FollowPath", 'CURVE'); cm.object = path; cm.deform_axis = 'POS_X'

    logos = [tab_logo(path, L, e) for e in LOGO_ENDS]

    # --- animation
    # 1. fold: tabs unfold to straight up (WORN_END -> FOLD_END), refold at the end
    #    (RISE_END -> HOOK_END). Keyed every frame so the unfold follows the true profile.
    def key_fold(f, u):
        for lv, w in _fold_weights(u).items():
            kbk = keys[f"Fold_{round(lv * 1000):03d}"]; kbk.value = w; kbk.keyframe_insert("value", frame=f)
    key_fold(1, 1.0)
    for f in range(WORN_END, FOLD_END + 1):
        key_fold(f, 1 - _ease((f - WORN_END) / (FOLD_END - WORN_END)))
    for f in range(RISE_END, HOOK_END + 1):
        key_fold(f, _ease((f - RISE_END) / (HOOK_END - RISE_END)))
    # 2. drop: the loop drops DROP_MAX while the ribbon slides DROP_MAX along the path with
    #    identical keyframes, so the whole strap moves straight down (and back up) as one piece
    for f, v in ((1, 0.0), (FOLD_END, 0.0), (DROP_END, 1.0), (RISE_START, 1.0), (RISE_END, 0.0)):
        keys["Drop"].value = v; keys["Drop"].keyframe_insert("value", frame=f)
        for o in [st] + logos:
            o.location.x = v * DROP_MAX; o.keyframe_insert("location", index=0, frame=f)
    for kbk in keys[1:]: kbk.value = 0.0
    for o in [st] + logos: o.location.x = 0
    # 3. hidden while it's out of frame
    for f, h in ((1, False), (DROP_END, False), (DROP_END + 1, True), (RISE_START, False)):
        for o in [st] + logos:
            o.hide_render = h; o.keyframe_insert("hide_render", frame=f)
            o.hide_viewport = h; o.keyframe_insert("hide_viewport", frame=f)
    return {"strap_length_cm": round(L, 2), "tab_cm": round(tab, 2), "path_points": len(P0), "segments": nx}
