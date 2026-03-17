# Spider-Man 2000 PC — Blender mesh creation from parsed PSX data

import bpy
import bmesh
from .psx_parser import PSXSceneData, PSXMesh, PSXFace
from .constants import DEFAULT_IMPORT_SCALE, PSX_VERSION_6


def build_mesh_object(mesh_data: PSXMesh, name: str, scale: float = DEFAULT_IMPORT_SCALE,
                      version: int = PSX_VERSION_6) -> bpy.types.Object:
    """Create a Blender mesh object from parsed PSX mesh data."""

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    # v6 UVs are u16 in fixed-point where 512=1.0; v3/v4 UVs are u8 where 256=1.0
    uv_scale = 512.0 if version >= PSX_VERSION_6 else 256.0

    # Add vertices with axis remap: SM2000 (x, y, z) -> Blender (x, -z, y)
    # Mesh vertices are plain int16, NOT Q12 fixed-point — don't divide by 4096
    s = scale
    bm_verts = []
    for v in mesh_data.vertices:
        bv = bm.verts.new((v.x * s, -v.z * s, v.y * s))
        bm_verts.append(bv)

    bm.verts.ensure_lookup_table()

    # Add faces
    for face in mesh_data.faces:
        if face.is_invisible:
            continue

        # Remap vertex order for correct normals
        indices = face.vertex_indices
        try:
            if face.is_triangle:
                # Reverse winding: [0,1,2] -> [2,1,0]
                face_verts = [
                    bm_verts[indices[2]],
                    bm_verts[indices[1]],
                    bm_verts[indices[0]],
                ]
                face_uvs = list(reversed(face.uvs)) if face.uvs else []
            else:
                # Quad reorder: [0,1,2,3] -> [0,2,3,1]
                face_verts = [
                    bm_verts[indices[0]],
                    bm_verts[indices[2]],
                    bm_verts[indices[3]],
                    bm_verts[indices[1]],
                ]
                if face.uvs and len(face.uvs) >= 4:
                    face_uvs = [
                        face.uvs[0],
                        face.uvs[2],
                        face.uvs[3],
                        face.uvs[1],
                    ]
                else:
                    face_uvs = []
        except (IndexError, KeyError):
            continue

        # Skip degenerate faces
        if len(set(id(v) for v in face_verts)) < 3:
            continue

        try:
            bm_face = bm.faces.new(face_verts)
        except ValueError:
            # Duplicate face
            continue

        # Set material index for textured faces (slots filled by build_materials later)
        if face.texture_index >= 0:
            bm_face.material_index = face.texture_index

        # Set UV coordinates
        if face_uvs and face.is_textured:
            for loop, uv in zip(bm_face.loops, face_uvs):
                loop[uv_layer].uv = (uv[0] / uv_scale, uv[1] / uv_scale)

    # Finalize
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    return obj


def build_scene(scene_data: PSXSceneData, name: str = "PSXScene",
                scale: float = DEFAULT_IMPORT_SCALE,
                merge_meshes: bool = True) -> list:
    """Build Blender objects from a full PSX scene.

    Args:
        scene_data: Parsed PSX scene data
        name: Base name for created objects
        scale: Import scale factor
        merge_meshes: If True, merge all meshes into one object (good for levels)

    Returns:
        List of created Blender objects
    """
    created_objects = []

    if merge_meshes and len(scene_data.meshes) > 1:
        # Merge all meshes into a single object, applying object transforms
        obj = _build_merged_scene(scene_data, name, scale)
        if obj:
            created_objects.append(obj)
    else:
        # Create individual objects for each mesh, using model_index for lookup
        for i, psx_obj in enumerate(scene_data.objects):
            mi = psx_obj.model_index
            if mi < 0 or mi >= len(scene_data.meshes):
                continue
            mesh_data = scene_data.meshes[mi]

            obj_name = f"{name}_{i:03d}"
            obj = build_mesh_object(mesh_data, obj_name, scale, version=scene_data.version)

            # Apply object position
            s = scale / 4096.0
            obj.location = (psx_obj.x * s, -psx_obj.z * s, psx_obj.y * s)

            created_objects.append(obj)

    return created_objects


def _build_merged_scene(scene_data: PSXSceneData, name: str,
                        scale: float) -> bpy.types.Object:
    """Merge all scene meshes into a single Blender object with object transforms applied."""

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    uv_scale = 512.0 if scene_data.version >= PSX_VERSION_6 else 256.0

    # Mesh vertices are plain int16, NOT Q12 fixed-point — don't divide by 4096
    s = scale

    for psx_obj in scene_data.objects:
        mi = psx_obj.model_index
        if mi < 0 or mi >= len(scene_data.meshes):
            continue
        mesh_data = scene_data.meshes[mi]

        # Object world position
        obj_s = scale / 4096.0
        ox = psx_obj.x * obj_s
        oy = -psx_obj.z * obj_s
        oz = psx_obj.y * obj_s

        vert_offset = len(bm.verts)

        # Add vertices with object transform
        for v in mesh_data.vertices:
            bm.verts.new((v.x * s + ox, -v.z * s + oy, v.y * s + oz))

        bm.verts.ensure_lookup_table()

        # Add faces
        for face in mesh_data.faces:
            if face.is_invisible:
                continue

            indices = face.vertex_indices
            try:
                if face.is_triangle:
                    face_verts = [
                        bm.verts[vert_offset + indices[2]],
                        bm.verts[vert_offset + indices[1]],
                        bm.verts[vert_offset + indices[0]],
                    ]
                    face_uvs = list(reversed(face.uvs)) if face.uvs else []
                else:
                    face_verts = [
                        bm.verts[vert_offset + indices[0]],
                        bm.verts[vert_offset + indices[2]],
                        bm.verts[vert_offset + indices[3]],
                        bm.verts[vert_offset + indices[1]],
                    ]
                    if face.uvs and len(face.uvs) >= 4:
                        face_uvs = [face.uvs[0], face.uvs[2], face.uvs[3], face.uvs[1]]
                    else:
                        face_uvs = []
            except (IndexError, KeyError):
                continue

            if len(set(id(v) for v in face_verts)) < 3:
                continue

            try:
                bm_face = bm.faces.new(face_verts)
            except ValueError:
                continue

            # Set material index
            if face.texture_index >= 0:
                bm_face.material_index = face.texture_index

            if face_uvs and face.is_textured:
                for loop, uv in zip(bm_face.loops, face_uvs):
                    loop[uv_layer].uv = (uv[0] / uv_scale, uv[1] / uv_scale)

    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    return obj


def link_object_to_scene(obj: bpy.types.Object, collection_name: str = None):
    """Link an object to a scene collection."""
    if collection_name:
        if collection_name not in bpy.data.collections:
            col = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(col)
        else:
            col = bpy.data.collections[collection_name]
        col.objects.link(obj)
    else:
        bpy.context.collection.objects.link(obj)
