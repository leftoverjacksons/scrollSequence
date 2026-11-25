"""
Render the sequence on a pure white background into frames_white/, without changing the
saved .blend (only the camera-ray background changes; lighting/reflections stay the same).

    & "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe" -b band_explode.blend `
        --python tools/render_white.py -a
"""
import bpy, os

PROJECT = os.path.dirname(bpy.data.filepath)  # this product's folder (where the .blend lives)
WHITE_STRENGTH = 8.0      # AgX (Medium High Contrast, +0.3 exposure) maps this to #FFFFFF; 4 -> 248

s = bpy.context.scene
bg = s.world.node_tree.nodes["Background.001"]      # what the camera sees directly
bg.inputs["Color"].default_value = (1, 1, 1, 1)
bg.inputs["Strength"].default_value = WHITE_STRENGTH
s.render.filepath = os.path.join(PROJECT, "frames_white", "frame_###")

# The white background (strength 8) is above the dark render's bloom threshold (6), so it
# would bloom over the whole model as a haze. Raise the threshold above the background;
# the LEDs (40) and light-pipe edges (~20 when assembled) still bloom.
glare = next(n for n in bpy.data.node_groups["BEACON_Bloom"].nodes if n.bl_idname == "CompositorNodeGlare")
glare.inputs["Threshold"].default_value = 12.0
