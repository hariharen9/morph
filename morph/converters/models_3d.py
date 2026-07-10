"""
3D Model conversions using the native blender python module (`bpy`).
Provides format conversions (obj, stl, fbx, gltf, blend) and headless rendering (png).
"""
import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional

from ..registry import ConversionResult, register

def _run_bpy_script(script_content: str) -> None:
    """Run a bpy script in an isolated subprocess to prevent global state corruption/memory leaks."""
    import importlib.util
    if importlib.util.find_spec("bpy") is None:
        raise RuntimeError(f"3D conversion requires the 'bpy' package (not available on Python {sys.version_info.major}.{sys.version_info.minor}). Please use Python 3.13 or older, or install Blender.")

    code = f"""
import bpy
import sys
import os

def main():
    try:
        # Clear factory settings first if not loading a blend file
{script_content}
    except Exception as e:
        print(f"ERROR: {{e}}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"3D conversion failed.\nStdout: {result.stdout}\nStderr: {result.stderr}")

def _get_import_code(filepath: Path) -> str:
    ext = filepath.suffix.lower().lstrip('.')
    path_str = repr(str(filepath.absolute()))
    
    if ext == 'blend':
        return f"        bpy.ops.wm.open_mainfile(filepath={path_str})"
    elif ext == 'obj':
        return f"        bpy.ops.wm.obj_import(filepath={path_str})"
    elif ext == 'stl':
        return f"        bpy.ops.wm.stl_import(filepath={path_str})"
    elif ext == 'fbx':
        return f"        bpy.ops.import_scene.fbx(filepath={path_str})"
    elif ext in ('gltf', 'glb'):
        return f"        bpy.ops.import_scene.gltf(filepath={path_str})"
    else:
        raise ValueError(f"Unsupported 3D import format: {ext}")

def _get_export_code(filepath: Path) -> str:
    ext = filepath.suffix.lower().lstrip('.')
    path_str = repr(str(filepath.absolute()))
    
    if ext == 'blend':
        return f"        bpy.ops.wm.save_as_mainfile(filepath={path_str})"
    elif ext == 'obj':
        return f"        bpy.ops.wm.obj_export(filepath={path_str})"
    elif ext == 'stl':
        return f"        bpy.ops.wm.stl_export(filepath={path_str})"
    elif ext == 'fbx':
        return f"        bpy.ops.export_scene.fbx(filepath={path_str})"
    elif ext in ('gltf', 'glb'):
        return f"        bpy.ops.export_scene.gltf(filepath={path_str})"
    else:
        raise ValueError(f"Unsupported 3D export format: {ext}")

def _3d_to_3d(input_path: Path, output_path: Path, **kwargs) -> ConversionResult:
    """Converts a 3D model from one format to another."""
    import_cmd = _get_import_code(input_path)
    export_cmd = _get_export_code(output_path)
    
    # If the input isn't a blend file, we should clear the default scene first
    clear_scene_cmd = ""
    if input_path.suffix.lower() != '.blend':
        clear_scene_cmd = "        bpy.ops.wm.read_factory_settings(use_empty=True)"
        
    script = f"""
{clear_scene_cmd}
{import_cmd}
{export_cmd}
    """
    
    _run_bpy_script(script)
    return ConversionResult(output_path)

def _3d_to_image(input_path: Path, output_path: Path, **kwargs) -> ConversionResult:
    """Renders a 3D model into a PNG image headlessly."""
    import_cmd = _get_import_code(input_path)
    
    clear_scene_cmd = ""
    if input_path.suffix.lower() != '.blend':
        clear_scene_cmd = "        bpy.ops.wm.read_factory_settings(use_empty=True)"
        
    out_path_str = repr(str(output_path.absolute()))
    
    script = f"""
{clear_scene_cmd}
{import_cmd}

        # Select all objects to find bounding box center
        bpy.ops.object.select_all(action='SELECT')
        
        # Add a camera (if no camera exists)
        if not any(obj.type == 'CAMERA' for obj in bpy.context.scene.objects):
            bpy.ops.object.camera_add(location=(10, -10, 10))
            cam = bpy.context.active_object
            cam.rotation_euler = (0.9, 0, 0.785)
            bpy.context.scene.camera = cam
            
        # Add light (if no light exists)
        if not any(obj.type == 'LIGHT' for obj in bpy.context.scene.objects):
            bpy.ops.object.light_add(type='SUN', location=(5, 5, 5))
            
        # Setup render settings
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.render.filepath = {out_path_str}
        bpy.context.scene.render.resolution_x = 1024
        bpy.context.scene.render.resolution_y = 1024
        
        # Render
        bpy.ops.render.render(write_still=True)
    """
    
    _run_bpy_script(script)
    return ConversionResult(output_path)



# 3D to 3D conversions
formats_3d = ['obj', 'stl', 'fbx', 'gltf', 'glb', 'blend']
for in_ext in formats_3d:
    for out_ext in formats_3d:
        if in_ext != out_ext:
            register(
                in_ext, out_ext,
                backend="bpy",
                family="3d_model",
                description=f"{in_ext} → {out_ext} (blender/bpy)"
            )(_3d_to_3d)
            
# 3D to Image conversions
for in_ext in formats_3d:
    register(
        in_ext, 'png',
        backend="bpy",
        family="3d_model",
        description=f"{in_ext} → png (blender/bpy headless render)"
    )(_3d_to_image)
