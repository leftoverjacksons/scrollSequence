"""
Export per-frame 2D anchor positions for the scroll page's callouts.

Run inside Blender with beacon_explode.blend open:
    exec(open(r"C:\\Users\\Travis\\Scroll Sequence\\products\\beacon-v3\\tools\\callouts.py", encoding="utf-8").read())
    export_callouts()

Each anchor is a point fixed on a part (stored in the part's local space), so the label's
leader line follows the part through the pitch, explode, spin and reassembly. For every
frame in the anchor's window it writes the normalized image position (x right, y down,
0..1 of the 1920x1080 render) and whether the point is visible (not hidden behind
another part). Output: callouts.json next to index.html. The page owns the label text.

Anchor kinds
  pick : (frame, u, v)  -> ray-cast through that image position at that frame; the hit
                           point on `obj` becomes the anchor (use for spots on big parts)
  auto : frame          -> the visible surface point of `obj` nearest its projected
                           centre at that frame
"""
import bpy, json, os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

PROJECT = os.path.dirname(bpy.data.filepath)  # this product's folder (where the .blend lives)
OUT = os.path.join(PROJECT, "callouts.json")
W, H = 1920, 1080

# id: (object name, anchor kind, kind arg, (first frame, last frame))
ANCHORS = {
    # windows chosen from a visibility scan: each part is in view (not occluded) there
    "asa":     ("Front Substrate:1 · Body7347", "pick", (1, 820 / W, 520 / H), (1, 24)),
    "tpe":     ("Front OVermold:1",            "pick", (1, 700 / W, 772 / H), (1, 24)),
    "buttons": ("Rear Overmold:1",             "pick", (1, 960 / W, 778 / H), (12, 40)),
    "led":     ("Light Pipe:1",                "pick", (1, 1345 / W, 600 / H), (12, 40)),
    "sensor":  ("Louver Screen:5",             "pick", (1, 1180 / W, 390 / H), (12, 40)),
    "mount":   ("7588N66_Mold-in Inserts for Plastic:1", "auto", 66, (58, 76)),
    "antenna": ("Rear Assembly:1 · New Antennae", "auto", 80, (70, 90)),
    "m8":      ("M8 Bushing:1",                "auto", 92, (78, 98)),   # the port (bushing + pins), not the plug
    "magnet":  ("2494N54_Multi-Pole Neodymium Magnet v1:1", "auto", 100, (90, 110)),
    "battery": ("HCP433438 front :1 · Foam",   "auto", 112, (100, 124)),
}


def _scene():
    return bpy.context.scene

def _ray_from_image(s, u, v):
    cam = s.camera
    tr, br, bl, tl = [cam.matrix_world @ p for p in cam.data.view_frame(scene=s)]
    pt = tl.lerp(tr, u).lerp(bl.lerp(br, u), v)
    o = cam.matrix_world.translation
    return o, (pt - o).normalized()

def _hit(s, o, d):
    dg = bpy.context.evaluated_depsgraph_get()
    ok, loc, n, i, ob, m = s.ray_cast(dg, o, d)
    return (loc, ob.original if ok else None) if ok else (None, None)

def _local(obj, world):
    return obj.matrix_world.inverted() @ world

def _anchor_local(name, kind, arg):
    s = _scene(); obj = bpy.data.objects[name]
    if kind == "pick":
        f, u, v = arg; s.frame_set(f)
        loc, ob = _hit(s, *_ray_from_image(s, u, v))
        if ob is not obj:
            raise RuntimeError(f"{name}: pick at frame {f} hit {ob.name if ob else None}")
        return _local(obj, loc)
    s.frame_set(arg)
    cam = s.camera; eye = cam.matrix_world.translation
    mw = obj.matrix_world
    centre = mw @ (sum((Vector(c) for c in obj.bound_box), Vector()) / 8)
    c2 = world_to_camera_view(s, cam, centre).xy
    polys = sorted(obj.data.polygons, key=lambda p: (world_to_camera_view(s, cam, mw @ p.center).xy - c2).length)
    for p in polys:
        w = mw @ p.center
        d = (w - eye); dist = d.length
        loc, ob = _hit(s, eye, d.normalized())
        if ob is obj and (loc - eye).length > dist - 0.05:
            return p.center.copy()
    return _local(obj, centre)          # fallback: centre (will mostly read as hidden)

def _visible(s, world):
    eye = s.camera.matrix_world.translation; d = world - eye
    loc, ob = _hit(s, eye, d.normalized())
    return loc is None or (loc - eye).length > d.length - 0.05

MASK_COLS, MASK_ROWS = 80, 45          # 24 px cells on the 1920x1080 render

def model_mask(frames_dir=os.path.join(PROJECT, "frames"), bg=(0x17, 0x18, 0x1C), thresh=10):
    """Per-frame occupancy grid from the rendered frames: a cell is 'model' if any sampled
    pixel differs from the background by more than `thresh` (0-255). Glow halos count too,
    so labels keep clear of them. Returns base64 bitmaps, one per frame, row-major."""
    import numpy as np, base64, glob
    files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.webp")))
    bgv = np.array(bg, dtype=np.float32) / 255; out = []
    for fp in files:
        img = bpy.data.images.load(fp, check_existing=False)
        w, h = img.size; a = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(a)
        bpy.data.images.remove(img)
        a = a.reshape(h, w, 4)[::-1, :, :3]                  # top row first
        diff = np.abs(a[::3, ::3] - bgv).max(axis=2) > thresh / 255
        ch, cw = diff.shape[0] // MASK_ROWS, diff.shape[1] // MASK_COLS
        grid = diff[:ch * MASK_ROWS, :cw * MASK_COLS].reshape(MASK_ROWS, ch, MASK_COLS, cw).any(axis=(1, 3))
        out.append(base64.b64encode(np.packbits(grid.ravel()).tobytes()).decode())
    return out

def export_callouts(with_mask=True):
    s = _scene(); f0 = s.frame_current
    out = {"width": W, "height": H, "frames": s.frame_end - s.frame_start + 1, "anchors": {}}
    for key, (name, kind, arg, (a, b)) in ANCHORS.items():
        local = _anchor_local(name, kind, arg)
        obj = bpy.data.objects[name]; pts = []
        for f in range(a, b + 1):
            s.frame_set(f)
            w = obj.matrix_world @ local
            p = world_to_camera_view(s, s.camera, w)
            vis = 0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0 and p.z > 0 and _visible(s, w)
            pts.append([round(p.x, 4), round(1 - p.y, 4), 1 if vis else 0])
        out["anchors"][key] = {"from": a, "to": b, "pts": pts}
    s.frame_set(f0)
    if with_mask:
        out["mask"] = {"cols": MASK_COLS, "rows": MASK_ROWS, "frames": model_mask()}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return {k: f"{sum(p[2] for p in v['pts'])}/{len(v['pts'])} visible" for k, v in out["anchors"].items()}
