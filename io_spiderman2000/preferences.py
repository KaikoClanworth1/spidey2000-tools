# Spider-Man 2000 PC — Addon preferences

import bpy
from bpy.props import FloatProperty, BoolProperty

from .constants import DEFAULT_IMPORT_SCALE


class SM2000Preferences(bpy.types.AddonPreferences):
    bl_idname = "io_spiderman2000"

    default_scale: FloatProperty(
        name="Default Import Scale",
        description="Default scale factor for imported models",
        default=DEFAULT_IMPORT_SCALE,
        min=0.0001, max=100.0,
    )

    import_textures: BoolProperty(
        name="Import Textures",
        description="Decode and apply embedded textures",
        default=True,
    )

    import_vertex_colors: BoolProperty(
        name="Import Vertex Colors",
        description="Import gouraud shading as vertex colors",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "default_scale")
        layout.prop(self, "import_textures")
        layout.prop(self, "import_vertex_colors")


classes = (SM2000Preferences,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
