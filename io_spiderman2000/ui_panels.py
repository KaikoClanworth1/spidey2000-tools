# Spider-Man 2000 PC — Blender UI panels for asset browsing

import re
import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty, IntProperty

from .constants import LEVEL_NAMES, DEFAULT_IMPORT_SCALE


class SM2000_UL_asset_list(bpy.types.UIList):
    """UIList for displaying PKR assets."""
    bl_idname = "SM2000_UL_asset_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='MESH_DATA')
            layout.label(text=f"{item.size // 1024}KB")
        elif self.layout_type == 'GRID':
            layout.label(text="", icon='MESH_DATA')


class SM2000_OT_import_asset(bpy.types.Operator):
    """Import the selected asset from the PKR archive"""
    bl_idname = "sm2000.import_asset"
    bl_label = "Import Asset"
    bl_options = {'REGISTER', 'UNDO'}

    asset_name: StringProperty()
    asset_index: IntProperty()

    def execute(self, context):
        pkr_path = context.scene.get("sm2000_pkr_path", "")
        if not pkr_path:
            self.report({'ERROR'}, "No PKR archive loaded")
            return {'CANCELLED'}

        from .pkr_parser import PKRArchive
        from .psx_parser import PSXParser
        from .mesh_builder import build_scene, link_object_to_scene
        from .material_builder import build_materials

        try:
            pkr = PKRArchive(pkr_path)
            entry = pkr.find_file(self.asset_name)
            if not entry:
                self.report({'ERROR'}, f"Asset not found: {self.asset_name}")
                pkr.close()
                return {'CANCELLED'}

            data = pkr.read_file(entry)
            pkr.close()

            import os
            name = os.path.splitext(entry.name)[0]
            scene_data = PSXParser(data).parse()

            scale = context.scene.get("sm2000_import_scale", DEFAULT_IMPORT_SCALE)
            objects = build_scene(scene_data, name, scale=scale)

            for obj in objects:
                link_object_to_scene(obj)
                build_materials(scene_data, obj)

            total_verts = sum(len(o.data.vertices) for o in objects)
            self.report({'INFO'}, f"Imported {name}: {total_verts} vertices")

        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


class SM2000_OT_import_level(bpy.types.Operator):
    """Import a complete level (geometry + objects + lights)"""
    bl_idname = "sm2000.import_level"
    bl_label = "Import Level"
    bl_options = {'REGISTER', 'UNDO'}

    level_id: StringProperty()

    def execute(self, context):
        pkr_path = context.scene.get("sm2000_pkr_path", "")
        if not pkr_path:
            self.report({'ERROR'}, "No PKR archive loaded")
            return {'CANCELLED'}

        from .pkr_parser import PKRArchive
        from .psx_parser import PSXParser
        from .mesh_builder import build_scene, link_object_to_scene
        from .material_builder import build_materials

        try:
            pkr = PKRArchive(pkr_path)
            level_files = pkr.find_level_files(self.level_id)

            if 'G' not in level_files:
                self.report({'ERROR'}, f"No geometry for level {self.level_id}")
                pkr.close()
                return {'CANCELLED'}

            friendly = LEVEL_NAMES.get(self.level_id, self.level_id)
            col_name = f"{self.level_id} - {friendly}"

            scale = context.scene.get("sm2000_import_scale", DEFAULT_IMPORT_SCALE)
            imported = []

            # Geometry
            data = pkr.read_file(level_files['G'])
            scene_data = PSXParser(data).parse()
            objects = build_scene(scene_data, f"{self.level_id}_Geometry", scale=scale)
            for obj in objects:
                link_object_to_scene(obj, col_name)
                build_materials(scene_data, obj)
                imported.append(obj)

            # Objects
            if 'O' in level_files:
                try:
                    data = pkr.read_file(level_files['O'])
                    obj_scene_data = PSXParser(data).parse()
                    objects = build_scene(obj_scene_data, f"{self.level_id}_Objects",
                                         scale=scale, merge_meshes=False)
                    for obj in objects:
                        link_object_to_scene(obj, col_name)
                        build_materials(obj_scene_data, obj)
                        imported.append(obj)
                except Exception:
                    pass

            pkr.close()

            total_verts = sum(len(o.data.vertices) for o in imported if o.data)
            self.report({'INFO'}, f"Imported {self.level_id}: {len(imported)} objects, {total_verts} verts")

        except Exception as e:
            self.report({'ERROR'}, f"Level import failed: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


class SM2000_PT_main_panel(bpy.types.Panel):
    """Spider-Man 2000 asset browser panel"""
    bl_label = "Spider-Man 2000"
    bl_idname = "SM2000_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SM2000"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        pkr_path = scene.get("sm2000_pkr_path", "")

        if not pkr_path:
            layout.label(text="No PKR loaded", icon='INFO')
            layout.operator("import_scene.sm2000_pkr", text="Open PKR Archive", icon='FILE_FOLDER')
            layout.separator()
            layout.operator("import_scene.sm2000_psx", text="Import PSX File", icon='IMPORT')
            return

        # Show loaded PKR
        import os
        layout.label(text=f"PKR: {os.path.basename(pkr_path)}", icon='PACKAGE')
        layout.operator("import_scene.sm2000_pkr", text="Change PKR", icon='FILE_FOLDER')

        layout.separator()

        # Import scale
        box = layout.box()
        box.label(text="Import Options", icon='PREFERENCES')
        row = box.row()
        row.prop(scene, '["sm2000_import_scale"]', text="Scale")

        layout.separator()

        # Parse the asset list
        assets_str = scene.get("sm2000_assets", "")
        if not assets_str:
            layout.label(text="Loading assets...")
            return

        try:
            import ast
            assets = ast.literal_eval(assets_str)
        except Exception:
            layout.label(text="Failed to parse asset list")
            return

        # Categorize assets
        levels = {}
        characters = []
        objects_list = []
        lowres = []

        level_pattern = re.compile(r'^(L\w+\d+\w*)_G\.psx$', re.IGNORECASE)

        for asset in assets:
            name = asset['name']
            directory = asset['dir']
            size = asset['size']

            if 'lowres' in directory.lower():
                lowres.append(asset)
                continue

            m = level_pattern.match(name)
            if m:
                lid = m.group(1).upper()
                if lid not in levels:
                    levels[lid] = asset
                continue

            # Skip _O, _L files (they're imported as part of levels)
            if re.match(r'^L\w+\d+\w*_[OL]\.psx$', name, re.IGNORECASE):
                continue

            if size > 100000:
                characters.append(asset)
            else:
                objects_list.append(asset)

        # Levels section
        if levels:
            box = layout.box()
            box.label(text=f"Levels ({len(levels)})", icon='WORLD')
            for lid in sorted(levels.keys()):
                friendly = LEVEL_NAMES.get(lid, lid)
                row = box.row(align=True)
                row.label(text=f"{lid} - {friendly}")
                op = row.operator("sm2000.import_level", text="", icon='IMPORT')
                op.level_id = lid

        # Characters section
        if characters:
            box = layout.box()
            box.label(text=f"Characters ({len(characters)})", icon='ARMATURE_DATA')
            for asset in sorted(characters, key=lambda a: a['name'].lower()):
                row = box.row(align=True)
                row.label(text=f"{asset['name']} ({asset['size']//1024}KB)")
                op = row.operator("sm2000.import_asset", text="", icon='IMPORT')
                op.asset_name = asset['name']

        # Objects section
        if objects_list:
            box = layout.box()
            box.label(text=f"Objects ({len(objects_list)})", icon='OBJECT_DATA')
            for asset in sorted(objects_list, key=lambda a: a['name'].lower()):
                row = box.row(align=True)
                row.label(text=f"{asset['name']} ({asset['size']//1024}KB)")
                op = row.operator("sm2000.import_asset", text="", icon='IMPORT')
                op.asset_name = asset['name']


# Registration
classes = (
    SM2000_OT_import_asset,
    SM2000_OT_import_level,
    SM2000_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
