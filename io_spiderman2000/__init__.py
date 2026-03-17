# Spider-Man 2000 PC — Blender Import Addon
# Imports maps, models, textures, and animations from the PC game Spider-Man (2000)
# by Neversoft / LTI Gray Matter / Activision

bl_info = {
    "name": "Spider-Man 2000 Importer",
    "author": "SM2000 Community",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "File > Import > Spider-Man 2000",
    "description": "Import models, maps, and textures from Spider-Man 2000 PC (.pkr, .psx)",
    "category": "Import-Export",
}


def register():
    from . import operators
    from . import ui_panels
    from . import preferences

    preferences.register()
    operators.register()
    ui_panels.register()


def unregister():
    from . import operators
    from . import ui_panels
    from . import preferences

    ui_panels.unregister()
    operators.unregister()
    preferences.unregister()


if __name__ == "__main__":
    register()
