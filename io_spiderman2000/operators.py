# Spider-Man 2000 PC — Blender import operators

import os
import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

from .constants import DEFAULT_IMPORT_SCALE, LEVEL_NAMES
from .pkr_parser import PKRArchive
from .psx_parser import PSXParser
from .mesh_builder import build_mesh_object, build_scene, link_object_to_scene
from .material_builder import build_materials


class IMPORT_OT_sm2000_psx(bpy.types.Operator, ImportHelper):
    """Import a Spider-Man 2000 PSX model file"""
    bl_idname = "import_scene.sm2000_psx"
    bl_label = "Import SM2000 Model"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".psx"
    filter_glob: StringProperty(
        default="*.psx;*.PSX",
        options={'HIDDEN'},
    )

    import_scale: FloatProperty(
        name="Scale",
        description="Import scale factor",
        default=DEFAULT_IMPORT_SCALE,
        min=0.0001, max=100.0,
    )

    merge_meshes: BoolProperty(
        name="Merge Meshes",
        description="Merge all meshes into a single object",
        default=True,
    )

    def execute(self, context):
        return self._import_psx_file(context, self.filepath)

    def _import_psx_file(self, context, filepath):
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
        except IOError as e:
            self.report({'ERROR'}, f"Failed to read file: {e}")
            return {'CANCELLED'}

        name = os.path.splitext(os.path.basename(filepath))[0]
        return self._import_psx_data(context, data, name)

    def _import_psx_data(self, context, data, name):
        try:
            scene_data = PSXParser(data).parse()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse PSX file: {e}")
            return {'CANCELLED'}

        objects = build_scene(
            scene_data, name,
            scale=self.import_scale,
            merge_meshes=self.merge_meshes,
        )

        for obj in objects:
            link_object_to_scene(obj)
            # Build and assign materials/textures
            import traceback
            try:
                build_materials(scene_data, obj)
            except Exception as e:
                traceback.print_exc()
                self.report({'WARNING'}, f"Texture import error: {e}")

        total_verts = sum(len(obj.data.vertices) for obj in objects)
        total_faces = sum(len(obj.data.polygons) for obj in objects)
        self.report({'INFO'}, f"Imported {name}: {len(objects)} objects, {total_verts} vertices, {total_faces} faces")
        return {'FINISHED'}


class IMPORT_OT_sm2000_pkr(bpy.types.Operator, ImportHelper):
    """Open a Spider-Man 2000 PKR archive and browse its contents"""
    bl_idname = "import_scene.sm2000_pkr"
    bl_label = "Import SM2000 Archive"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".pkr"
    filter_glob: StringProperty(
        default="*.pkr;*.PKR",
        options={'HIDDEN'},
    )

    import_scale: FloatProperty(
        name="Scale",
        description="Import scale factor",
        default=DEFAULT_IMPORT_SCALE,
        min=0.0001, max=100.0,
    )

    asset_name: StringProperty(
        name="Asset",
        description="Name of the asset to import (leave empty to open browser)",
        default="",
    )

    import_mode: EnumProperty(
        name="Mode",
        items=[
            ('BROWSE', "Browse", "Open the PKR and show the asset browser panel"),
            ('ASSET', "Single Asset", "Import a specific asset by name"),
            ('LEVEL', "Full Level", "Import a complete level (geometry + objects + lights)"),
        ],
        default='BROWSE',
    )

    def execute(self, context):
        try:
            pkr = PKRArchive(self.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open PKR: {e}")
            return {'CANCELLED'}

        # Store PKR path in scene for the panel to use
        context.scene["sm2000_pkr_path"] = self.filepath

        if self.import_mode == 'BROWSE':
            # Build asset list and store for the panel
            psx_files = pkr.list_files(ext='.psx')
            asset_list = []
            for entry in psx_files:
                asset_list.append({
                    'name': entry.name,
                    'dir': entry.directory,
                    'index': entry.index,
                    'size': entry.uncompressed_size,
                })
            context.scene["sm2000_assets"] = str(asset_list)
            pkr.close()
            self.report({'INFO'}, f"Loaded PKR: {len(psx_files)} PSX files found")
            return {'FINISHED'}

        elif self.import_mode == 'ASSET':
            return self._import_single_asset(context, pkr)

        elif self.import_mode == 'LEVEL':
            return self._import_level(context, pkr)

        pkr.close()
        return {'FINISHED'}

    def _import_single_asset(self, context, pkr):
        entry = pkr.find_file(self.asset_name)
        if not entry:
            self.report({'ERROR'}, f"Asset not found: {self.asset_name}")
            pkr.close()
            return {'CANCELLED'}

        data = pkr.read_file(entry)
        pkr.close()

        name = os.path.splitext(entry.name)[0]
        try:
            scene_data = PSXParser(data).parse()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse {entry.name}: {e}")
            return {'CANCELLED'}

        objects = build_scene(scene_data, name, scale=self.import_scale)
        for obj in objects:
            link_object_to_scene(obj)
            try:
                build_materials(scene_data, obj)
            except Exception:
                pass

        self.report({'INFO'}, f"Imported {name}")
        return {'FINISHED'}

    def _import_level(self, context, pkr):
        level_id = self.asset_name
        level_files = pkr.find_level_files(level_id)

        if 'G' not in level_files:
            self.report({'ERROR'}, f"No geometry file found for level {level_id}")
            pkr.close()
            return {'CANCELLED'}

        friendly_name = LEVEL_NAMES.get(level_id, level_id)
        collection_name = f"{level_id} - {friendly_name}"

        imported = []

        # Import geometry
        data = pkr.read_file(level_files['G'])
        scene_data = PSXParser(data).parse()
        objects = build_scene(scene_data, f"{level_id}_Geometry", scale=self.import_scale)
        for obj in objects:
            link_object_to_scene(obj, collection_name)
            try:
                build_materials(scene_data, obj)
            except Exception:
                pass
            imported.append(obj)

        # Import objects
        if 'O' in level_files:
            try:
                data = pkr.read_file(level_files['O'])
                scene_data = PSXParser(data).parse()
                objects = build_scene(
                    scene_data, f"{level_id}_Objects",
                    scale=self.import_scale, merge_meshes=False,
                )
                for obj in objects:
                    link_object_to_scene(obj, collection_name)
                    imported.append(obj)
            except Exception as e:
                self.report({'WARNING'}, f"Failed to import objects: {e}")

        pkr.close()

        total_verts = sum(len(o.data.vertices) for o in imported if o.data)
        self.report({'INFO'},
                    f"Imported level {level_id} ({friendly_name}): "
                    f"{len(imported)} objects, {total_verts} vertices")
        return {'FINISHED'}


# Registration
classes = (
    IMPORT_OT_sm2000_psx,
    IMPORT_OT_sm2000_pkr,
)


def menu_func_import_psx(self, context):
    self.layout.operator(IMPORT_OT_sm2000_psx.bl_idname,
                         text="Spider-Man 2000 Model (.psx)")


def menu_func_import_pkr(self, context):
    self.layout.operator(IMPORT_OT_sm2000_pkr.bl_idname,
                         text="Spider-Man 2000 Archive (.pkr)")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_psx)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_pkr)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_pkr)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_psx)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
