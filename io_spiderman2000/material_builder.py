# Spider-Man 2000 PC — Blender material and texture creation

import bpy
from .psx_parser import PSXSceneData, PSXTextureInfo, PSXPalette
from .texture_decoder import (
    decode_4bit_texture, decode_8bit_texture, decode_16bit_texture,
    create_blender_image,
)


def build_materials(scene_data: PSXSceneData, obj: bpy.types.Object) -> list:
    """Create Blender materials from PSX scene texture data and assign to object.

    For v6 files, face.texture_index is an index into texture_names[].
    The correct texture is found by matching texture.name_index == face.texture_index.
    Materials are created so slot N = texture whose name_index == N.

    Returns list of created materials.
    """
    materials = []

    if not scene_data.textures:
        return materials

    # Build palette lookup by CRC name
    pal4_lookup = {p.name: p for p in scene_data.palettes_4bit}
    pal8_lookup = {p.name: p for p in scene_data.palettes_8bit}

    # Build lookup: name_index -> texture object
    # face.texture_index matches against texture.name_index (confirmed by thps2-tools)
    name_index_to_tex = {}
    for tex_info in scene_data.textures:
        name_index_to_tex[tex_info.name_index] = tex_info

    # Material slots: slot N = texture with name_index == N
    max_slot = max(name_index_to_tex.keys()) if name_index_to_tex else -1
    slot_count = max_slot + 1

    for slot in range(slot_count):
        tex_info = name_index_to_tex.get(slot)

        if tex_info is None:
            mat = _create_solid_material(f"SM2000_empty_{slot:03d}", (0.3, 0.3, 0.3, 1.0))
            obj.data.materials.append(mat)
            materials.append(mat)
            continue

        # Name material with slot index to guarantee unique names per slot.
        # CRC hash is included for readability but slot number prevents
        # collisions when two different textures share the same CRC.
        if slot < len(scene_data.texture_names):
            tex_name = f"SM2000_s{slot:03d}_{scene_data.texture_names[slot]:08X}"
        else:
            tex_name = f"SM2000_s{slot:03d}"

        # Decode texture pixels
        rgba_pixels = _decode_texture(tex_info, pal4_lookup, pal8_lookup)

        if not rgba_pixels or tex_info.width <= 0 or tex_info.height <= 0:
            mat = _create_solid_material(tex_name, (0.5, 0.5, 0.5, 1.0))
            obj.data.materials.append(mat)
            materials.append(mat)
            continue

        # Create Blender image and textured material
        image = create_blender_image(tex_name, tex_info.width, tex_info.height, rgba_pixels)
        mat = _create_textured_material(tex_name, image)
        obj.data.materials.append(mat)
        materials.append(mat)

    return materials


def _decode_texture(tex_info: PSXTextureInfo,
                    pal4_lookup: dict, pal8_lookup: dict) -> list:
    """Decode a PSX texture to RGBA pixels."""
    if not tex_info.pixel_data:
        return []

    if tex_info.color_count == 16:
        palette = pal4_lookup.get(tex_info.palette_name)
        if not palette:
            return []
        return decode_4bit_texture(
            tex_info.pixel_data, palette.colors,
            tex_info.width, tex_info.height,
        )
    elif tex_info.color_count == 256:
        palette = pal8_lookup.get(tex_info.palette_name)
        if not palette:
            return []
        return decode_8bit_texture(
            tex_info.pixel_data, palette.colors,
            tex_info.width, tex_info.height,
        )
    elif tex_info.color_count == 65536:
        return decode_16bit_texture(
            tex_info.pixel_data,
            tex_info.width, tex_info.height,
            palette_id=tex_info.flags,
        )
    return []


def _create_textured_material(name: str, image: bpy.types.Image) -> bpy.types.Material:
    """Create a Blender material with an image texture connected to Principled BSDF."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.blend_method = 'CLIP'
    mat.use_backface_culling = False

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Output node
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)

    # Principled BSDF
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Specular IOR Level'].default_value = 0.0
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Image Texture
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.location = (-300, 0)
    tex_node.image = image
    tex_node.interpolation = 'Closest'  # Pixel art / retro style

    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])

    return mat


def _create_solid_material(name: str, color: tuple) -> bpy.types.Material:
    """Create a simple solid-color material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.use_backface_culling = False

    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = 1.0
        bsdf.inputs['Specular IOR Level'].default_value = 0.0

    return mat
