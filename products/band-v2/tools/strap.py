"""
Band V2 strap: modelled in Blender (it isn't in CAD) and animated without cloth simulation.

Run inside Blender with band_explode.blend open (build_band.build() calls it):
    exec(open(r"C:\\Users\\Travis\\Scroll Sequence\\products\\band-v2\\tools\\strap.py", encoding="utf-8").read())
    strap()

How the real strap is put together (from photos of the product)
  One elastic strap forms the wrist loop. Each end comes UP through its slot from underneath,
  folds out over the slot's outer bar, and comes back down the outside, where its
  hook-and-loop patch grips the outside of the strap. Both patches carry the S logo.

How it's animated
  - BAND_StrapPath: a dense poly curve along the strap, from the -X tip to the +X tip:
        -X tail (outside, hooked on) -> over the -X bar -> down through the -X slot ->
        down the -X side -> round the bottom of the wrist -> up the +X side ->
        up through the +X slot -> over the +X bar -> +X tail (outside, hooked on)
    The curve has two shape keys:
        "Peel": both tails swing out from under their bar (the hook-and-loop lets go)
        "Drop": the wrist loop is DROP_MAX lower. The sides get DROP_MAX longer and the
                bottom arc moves down rigidly, so no point moves off the strap's line.
  - BAND_Strap: a flat ribbon bent onto the path by a Curve modifier. While the loop drops
    by d, the ribbon slides d along the path. Path length grows by 2d (both sides), so both
    tips retreat by the same d: the ends pull back over the bars and down out of the slots,
    exactly like a strap whose loop is dropping as one piece. The drop key and the slide
    use identical keyframes, so they stay in step on every frame.
  - The path is built in the curve object's local XY plane (a flat curve's normal = the
    strap's width axis); the object is rotated 90 deg about X so that plane = device XZ.

Measured from the Bottom shell (device cm): strap slots are through-holes at |x| 2.85-3.35,
|y| < 1.85; the outer bar spans |x| 3.35-3.6, z -0.52..0.08.
"""
import bpy, math
from mathutils import Vector, Matrix

STRAP_W = 3.5           # cm, webbing width (slot is 3.7 long)
STRAP_T = 0.16          # cm, webbing thickness
TAB_LEN = 1.7           # cm, hook-and-loop patch at each end
LAYER = STRAP_T + 0.03  # centreline gap where a tail lies on the outside of the strap

SLOT_X = 3.1            # strap centreline through the slot
BAR_OUT_X = 3.69        # centreline just outside the bar
OVER_C = ((BAR_OUT_X + SLOT_X) / 2, -0.05)     # arc over the bar (top z 0.245, bar top 0.08)
OVER_R = (BAR_OUT_X - SLOT_X) / 2
SIDE_TOP = -0.05        # where the strap leaves the slot downward
LOOP_C = -3.0           # centre of the bottom arc (worn): wrist ~6.2 cm wide, ~6 cm deep
LOOP_R = SLOT_X         # bottom arc radius (sides come straight down out of the slots)
TAIL_TOP = -0.6         # tail tucks in right under the bar (bar bottom -0.52)...
TAIL_IN = -0.9          # ...and lies flat on the strap from here
TAIL_LEN = 1.7          # cm of tail below TAIL_IN (tip at z ~ -2.6)

PEEL_DEG = 55           # how far the tails swing out when the hook-and-loop lets go
BEND_LEN = 0.45         # the peel hinges over this much tail, right where it leaves the bar
DROP_MAX = 26.0         # cm the loop drops: ends clear the slots at ~6, then it falls out of frame

# Timeline (the pod's own sequence starts after this; see build_band.py)
WORN_END, PEEL_END, DROP_END = 20, 32, 80
# ...and at the end it comes back the way it left (exact reverse), once the pod has closed
RISE_START, RISE_END, HOOK_END = 236, 284, 296

# point counts per segment are fixed, so every shape key has the same number of points
N_TAIL, N_TUCK, N_DOWN, N_OVER, N_SIDE, N_ARC = 30, 14, 10, 24, 80, 90


def _arc(c, r, a0, a1, n):
    return [Vector((c[0] + r * math.cos(a0 + (a1 - a0) * k / n), c[1] + r * math.sin(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]

def _line(p, q, n):
    return [p.lerp(q, k / n) for k in range(n + 1)]

def _right_upper(peel):
    """+X side from the slot exit going up: slot -> over bar -> down outside -> tuck -> tail tip.
    Ordered slot-first. `peel` (0..1): the tail straightens and swings out, hinging right where
    it comes over the bar (the bend is spread over BEND_LEN so it reads as webbing, not a crease)."""
    P = _line(Vector((SLOT_X, SIDE_TOP - 0.25)), Vector((SLOT_X, OVER_C[1])), N_DOWN)          # up through the slot
    P += _arc(OVER_C, OVER_R, math.pi, 0, N_OVER)[1:]                                          # over the bar
    top = Vector((BAR_OUT_X, OVER_C[1]))
    # worn: down outside the bar, tight S-bend in under it, then flat on the strap
    rest = _line(top, Vector((BAR_OUT_X, TAIL_TOP)), N_DOWN)[1:]
    for k in range(1, N_TUCK + 1):
        t = k / N_TUCK; e = t * t * (3 - 2 * t)
        rest.append(Vector((BAR_OUT_X + (SLOT_X + LAYER - BAR_OUT_X) * e, TAIL_TOP + (TAIL_IN - TAIL_TOP) * t)))
    rest += _line(Vector((SLOT_X + LAYER, TAIL_IN)), Vector((SLOT_X + LAYER, TAIL_IN - TAIL_LEN)), N_TAIL)[1:]
    if peel <= 0:
        return P + rest
    # peeled: same length, straight down from the bar, then bent outward near the top
    seg = [(rest[0] - top).length] + [(rest[k + 1] - rest[k]).length for k in range(len(rest) - 1)]
    a = math.radians(PEEL_DEG) * peel
    q = top.copy(); s = 0.0; out = []
    for d in seg:
        s += d
        t = min(1.0, s / BEND_LEN); th = a * t * t * (3 - 2 * t)
        q = q + Vector((math.sin(th), -math.cos(th))) * d        # straight down, rotated outward (+X) by th
        out.append(q.copy())
    return P + out

def path_points(drop=0.0, peel=0.0):
    """Ordered 2D points (x, z) from the -X tip to the +X tip. Same point count for any
    drop/peel, so the results can be used as curve shape keys."""
    right_up = _right_upper(peel)
    left_up = [Vector((-q.x, q.y)) for q in _right_upper(peel)]
    c = LOOP_C - drop
    side_bot = c                                                  # sides run straight down to the arc
    left_side = _line(Vector((-SLOT_X, SIDE_TOP - 0.25)), Vector((-SLOT_X, side_bot)), N_SIDE)
    arc = _arc((0, c), LOOP_R, math.pi, 2 * math.pi, N_ARC)       # bottom half-circle, -X -> +X
    right_side = _line(Vector((SLOT_X, side_bot)), Vector((SLOT_X, SIDE_TOP - 0.25)), N_SIDE)
    P = left_up[::-1] + left_side[1:] + arc[1:] + right_side[1:] + right_up[1:]
    return P

def _length(P):
    return sum((P[k + 1] - P[k]).length for k in range(len(P) - 1))


# ---------------------------------------------------------------- materials
def strap_material():
    """Black woven elastic webbing: matte, dark sheen, ribbed weave bump."""
    m = bpy.data.materials.get("BAND_Strap_Webbing") or bpy.data.materials.new("BAND_Strap_Webbing")
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled"); p.location = (300, 0)
    p.inputs["Base Color"].default_value = (0.006, 0.006, 0.007, 1)
    p.inputs["Roughness"].default_value = 0.9
    p.inputs["Sheen Weight"].default_value = 0.25; p.inputs["Sheen Roughness"].default_value = 0.5
    p.inputs["Sheen Tint"].default_value = (0.08, 0.08, 0.09, 1)
    p.inputs["Specular IOR Level"].default_value = 0.15
    uv = nt.nodes.new("ShaderNodeTexCoord"); uv.location = (-500, 0)
    w1 = nt.nodes.new("ShaderNodeTexWave"); w1.location = (-250, 120)
    w1.wave_type = 'BANDS'; w1.bands_direction = 'X'; w1.inputs["Scale"].default_value = 18.0
    w2 = nt.nodes.new("ShaderNodeTexWave"); w2.location = (-250, -120)
    w2.wave_type = 'BANDS'; w2.bands_direction = 'Y'; w2.inputs["Scale"].default_value = 40.0
    mix = nt.nodes.new("ShaderNodeMath"); mix.operation = 'MULTIPLY'; mix.location = (-50, 0)
    bump = nt.nodes.new("ShaderNodeBump"); bump.location = (100, -200)
    bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.02
    nt.links.new(uv.outputs["UV"], w1.inputs["Vector"]); nt.links.new(uv.outputs["UV"], w2.inputs["Vector"])
    nt.links.new(w1.outputs["Fac"], mix.inputs[0]); nt.links.new(w2.outputs["Fac"], mix.inputs[1])
    nt.links.new(mix.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    return m

def tab_material():
    """Hook-and-loop patches at both ends: flatter, matte black."""
    m = bpy.data.materials.get("BAND_Strap_Tab") or bpy.data.materials.new("BAND_Strap_Tab")
    m.use_nodes = True; p = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    p.inputs["Base Color"].default_value = (0.012, 0.012, 0.013, 1)
    p.inputs["Roughness"].default_value = 0.95
    p.inputs["Specular IOR Level"].default_value = 0.1
    p.inputs["Sheen Weight"].default_value = 0.15
    p.inputs["Sheen Tint"].default_value = (0.08, 0.08, 0.09, 1)
    return m



LOGO_ENDS = (+1, -1)    # both patches carry the S logo
LOGO_H = 1.15           # cm, height of the S on the patch

def tab_logo(path, L, end):
    """The S logo on a hook-and-loop patch: the Pantone S faces copied from the Top shell,
    laid on the outside face of the tab and bent by the same Curve modifier as the strap."""
    import bmesh
    top = bpy.data.objects["Top:1"]; pan = bpy.data.materials["BEACON_Pantone165C"]
    idx = {i for i, sl in enumerate(top.material_slots) if sl.material == pan}
    bpy.context.scene.frame_set(1)
    M = top.matrix_world.copy()
    bm = bmesh.new(); bm.from_mesh(top.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in idx], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    pts = [M @ v.co for v in bm.verts]
    cx = (min(q.x for q in pts) + max(q.x for q in pts)) / 2
    cy = (min(q.y for q in pts) + max(q.y for q in pts)) / 2
    k = LOGO_H / (max(q.y for q in pts) - min(q.y for q in pts))
    xc = L - TAB_LEN / 2 if end > 0 else TAB_LEN / 2
    lift = STRAP_T / 2 + 0.006
    # Ribbon +Y is the outside face of both tails. Ribbon X runs from the -X tip (0) to the
    # +X tip (L). The S's "up" points back toward the bar, so it reads upright in the head-on
    # camera once the tabs peel open, matching the logo on the Top shell. The lateral sign
    # differs per end because the two tails are mirror images; both were checked against the
    # strap's outward normal so neither S is mirrored.
    for v, q in zip(bm.verts, pts):
        lx, ly = (q.x - cx) * k, (q.y - cy) * k
        v.co = Vector((xc - end * ly, lift, -end * lx))
    name = "BAND_StrapLogo_" + ("+X" if end > 0 else "-X")
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me); path.users_collection[0].objects.link(ob)
    ob.parent = path; ob.matrix_parent_inverse = Matrix.Identity(4)
    me.materials.append(pan)
    cm = ob.modifiers.new("FollowPath", 'CURVE'); cm.object = path; cm.deform_axis = 'POS_X'
    bm.to_mesh(me); me.update()
    bm.free()
    for poly in me.polygons: poly.use_smooth = False
    return ob

# ---------------------------------------------------------------- build
def strap():
    import bmesh
    rc = bpy.data.collections["BAND V2"]
    for n in ("BAND_Strap", "BAND_StrapPath", "BAND_StrapLogo", "BAND_StrapLogo_+X", "BAND_StrapLogo_-X"):
        o = bpy.data.objects.get(n)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    for n in ("BAND_StrapPath",):
        cu = bpy.data.curves.get(n)
        if cu: bpy.data.curves.remove(cu)
    for n in ("BAND_Strap", "BAND_StrapLogo", "BAND_StrapLogo_+X", "BAND_StrapLogo_-X"):
        me_old = bpy.data.meshes.get(n)
        if me_old: bpy.data.meshes.remove(me_old)

    P0 = path_points(0, 0)
    L = _length(P0)                                  # strap length = worn path, tip to tip

    # --- path curve + shape keys
    cu = bpy.data.curves.new("BAND_StrapPath", 'CURVE')
    cu.dimensions = '3D'; cu.twist_mode = 'Z_UP'
    sp = cu.splines.new('POLY'); sp.points.add(len(P0) - 1)
    for k, q in enumerate(P0): sp.points[k].co = (q.x, q.y, 0, 1)
    path = bpy.data.objects.new("BAND_StrapPath", cu); rc.objects.link(path)
    path.matrix_world = Matrix.Rotation(math.radians(90), 4, 'X')
    path.hide_render = True
    path.shape_key_add(name="Basis", from_mix=False)
    for name, pts in (("Peel", path_points(0, 1)), ("Drop", path_points(DROP_MAX, 0))):
        kb = path.shape_key_add(name=name, from_mix=False)
        for k, q in enumerate(pts): kb.data[k].co = (q.x, q.y, 0)
    keys = cu.shape_keys.key_blocks

    # --- ribbon: X = length (0..L), Z = width, Y = thickness (Solidify); UVs in cm
    me = bpy.data.meshes.new("BAND_Strap"); bm = bmesh.new()
    nx = max(2, int(L / 0.06)); nz = 6
    uvl = bm.loops.layers.uv.new("UVMap")
    verts = [[bm.verts.new((L * i / nx, 0, -STRAP_W / 2 + STRAP_W * j / nz)) for j in range(nz + 1)] for i in range(nx + 1)]
    for i in range(nx):
        x = L * (i + 0.5) / nx
        for j in range(nz):
            f = bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))
            f.material_index = 1 if (x < TAB_LEN or x > L - TAB_LEN) else 0
            for lp in f.loops: lp[uvl].uv = (lp.vert.co.x, lp.vert.co.z)
    bm.to_mesh(me); bm.free()
    me.materials.append(strap_material()); me.materials.append(tab_material())
    for poly in me.polygons: poly.use_smooth = True
    st = bpy.data.objects.new("BAND_Strap", me); rc.objects.link(st)
    st.parent = path; st.matrix_parent_inverse = Matrix.Identity(4); st.location = (0, 0, 0)
    so = st.modifiers.new("Thickness", 'SOLIDIFY'); so.thickness = STRAP_T; so.offset = 0
    so.use_even_offset = True; so.use_rim = True
    bv = st.modifiers.new("SoftEdges", 'BEVEL'); bv.width = 0.03; bv.segments = 2; bv.limit_method = 'ANGLE'
    cm = st.modifiers.new("FollowPath", 'CURVE'); cm.object = path; cm.deform_axis = 'POS_X'

    logos = [tab_logo(path, L, e) for e in LOGO_ENDS]

    # --- animation
    # 1. peel: hook-and-loop lets go, both tails swing out (WORN_END -> PEEL_END)
    for f, v in ((1, 0.0), (WORN_END, 0.0), (PEEL_END, 1.0), (RISE_END, 1.0), (HOOK_END, 0.0)):
        keys["Peel"].value = v; keys["Peel"].keyframe_insert("value", frame=f)
    # 2. drop: loop drops DROP_MAX while the ribbon slides DROP_MAX along the path, with
    #    identical keyframes so drop and slide stay in step (PEEL_END -> DROP_END)
    #    At the end: the loop rises back up and the ends feed up through the slots and over
    #    the bars (RISE_START -> RISE_END), then the tails fold down and hook on (-> HOOK_END).
    for f, v in ((1, 0.0), (PEEL_END, 0.0), (DROP_END, 1.0), (RISE_START, 1.0), (RISE_END, 0.0)):
        keys["Drop"].value = v; keys["Drop"].keyframe_insert("value", frame=f)
        for o in [st] + logos:
            o.location.x = v * DROP_MAX; o.keyframe_insert("location", index=0, frame=f)
    keys["Peel"].value = keys["Drop"].value = 0.0; st.location.x = 0
    for o in logos: o.location.x = 0
    # 3. gone: hidden while it's out of frame
    for f, h in ((1, False), (DROP_END, False), (DROP_END + 1, True), (RISE_START, False)):
        for o in [st] + logos:
            o.hide_render = h; o.keyframe_insert("hide_render", frame=f)
            o.hide_viewport = h; o.keyframe_insert("hide_viewport", frame=f)
    return {"strap_length_cm": round(L, 1), "path_points": len(P0), "segments": nx}
