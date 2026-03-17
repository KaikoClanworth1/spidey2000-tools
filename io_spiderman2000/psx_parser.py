# Spider-Man 2000 PC — Neversoft PSX scene/model parser
# Based on format analysis from thps2-tools (JayFoxRox) and spidey-tools (krystalgamer)

from dataclasses import dataclass, field
from .utils import BinaryReader
from .constants import (
    PSX_VERSION_3, PSX_VERSION_4, PSX_VERSION_6,
    FF_HAS_UV, FF_TEXTURED, FF_TRIANGLE, FF_INVISIBLE, FF_GOURAUD,
    TERMINATOR,
)


@dataclass
class PSXVertex:
    x: int
    y: int
    z: int


@dataclass
class PSXNormal:
    x: int
    y: int
    z: int


@dataclass
class PSXFace:
    vertex_indices: list  # 3 or 4 indices
    is_triangle: bool
    is_textured: bool
    is_gouraud: bool
    is_invisible: bool
    texture_index: int
    uvs: list  # list of (u, v) tuples per vertex
    gpu_colors: list  # list of (r, g, b) per vertex for gouraud faces
    normal_index: int
    surface_flags: int
    base_flags: int


@dataclass
class PSXBoundingBox:
    radius: int
    xmin: int
    xmax: int
    ymin: int
    ymax: int
    zmin: int
    zmax: int


@dataclass
class PSXMesh:
    unknown_flags: int
    vertices: list  # list of PSXVertex
    normals: list  # list of PSXNormal
    faces: list  # list of PSXFace
    bbox: PSXBoundingBox = None


@dataclass
class PSXObject:
    flags: int
    x: int  # fixed-point position (raw, divide by 4096 for world units)
    y: int
    z: int
    model_index: int


@dataclass
class PSXTextureInfo:
    color_count: int  # 16, 256, or 65536
    palette_name: int  # CRC32 hash
    name_index: int
    width: int
    height: int
    pixel_data: bytes = b''
    flags: int = 0


@dataclass
class PSXPalette:
    name: int  # CRC32 hash
    colors: list = field(default_factory=list)  # list of (r, g, b, a) tuples


@dataclass
class PSXSceneData:
    version: int
    tag_start: int
    objects: list  # list of PSXObject
    meshes: list  # list of PSXMesh
    textures: list = field(default_factory=list)
    palettes_4bit: list = field(default_factory=list)
    palettes_8bit: list = field(default_factory=list)
    texture_names: list = field(default_factory=list)
    model_names: list = field(default_factory=list)


class PSXParser:
    """Parser for Neversoft 'Big Guns' engine PSX scene files."""

    def __init__(self, data: bytes):
        self.reader = BinaryReader(data)
        self.data = data
        self.version = 0
        self.tag_start = 0

    def parse(self) -> PSXSceneData:
        r = self.reader
        r.seek(0)

        # Header
        self.version = r.read_u16()
        _validation = r.read_u16()
        self.tag_start = r.read_u32()

        # Objects
        objects = self._parse_objects()

        # Model offsets
        model_count = r.read_u32()
        model_offsets = [r.read_u32() for _ in range(model_count)]

        # Parse each model/mesh
        meshes = []
        for offset in model_offsets:
            r.seek(offset)
            mesh = self._parse_mesh()
            meshes.append(mesh)

        scene = PSXSceneData(
            version=self.version,
            tag_start=self.tag_start,
            objects=objects,
            meshes=meshes,
        )

        # Parse tags and post-tag data (palettes, textures)
        self._parse_tags_and_textures(scene, model_count)

        return scene

    def _parse_objects(self) -> list:
        r = self.reader
        obj_count = r.read_u32()
        objects = []

        for _ in range(obj_count):
            flags = r.read_u32()
            x = r.read_i32()
            y = r.read_i32()
            z = r.read_i32()
            _unk1 = r.read_u32()
            _unk2 = r.read_u16()
            model_index = r.read_u16()
            _unk_x = r.read_i16()
            _unk_y = r.read_i16()
            _unk3 = r.read_u32()
            _unk_rgbx = r.read_u32()

            objects.append(PSXObject(
                flags=flags,
                x=x, y=y, z=z,
                model_index=model_index,
            ))

        return objects

    def _parse_mesh(self) -> PSXMesh:
        r = self.reader

        if self.version >= PSX_VERSION_4:
            unknown_flags = r.read_u16()
            vert_count = r.read_u16()
            norm_count = r.read_u16()
            face_count = r.read_u16()
        else:
            unknown_flags = r.read_u32()
            vert_count = r.read_u32()
            norm_count = r.read_u32()
            face_count = r.read_u32()

        # Bounding box (20 bytes)
        radius = r.read_u32()
        xmax = r.read_i16()
        xmin = r.read_i16()
        ymax = r.read_i16()
        ymin = r.read_i16()
        zmax = r.read_i16()
        zmin = r.read_i16()
        _bbox_unk = r.read_u32()

        bbox = PSXBoundingBox(radius, xmin, xmax, ymin, ymax, zmin, zmax)

        # Vertices
        vertices = []
        for _ in range(vert_count):
            x = r.read_i16()
            y = r.read_i16()
            z = r.read_i16()
            _pad = r.read_u16()
            vertices.append(PSXVertex(x, y, z))

        # Normals
        normals = []
        for _ in range(norm_count):
            x = r.read_i16()
            y = r.read_i16()
            z = r.read_i16()
            _pad = r.read_u16()
            normals.append(PSXNormal(x, y, z))

        # Faces
        faces = self._parse_faces(face_count, unknown_flags)

        return PSXMesh(
            unknown_flags=unknown_flags,
            vertices=vertices,
            normals=normals,
            faces=faces,
            bbox=bbox,
        )

    def _parse_faces(self, face_count: int, model_flags: int) -> list:
        r = self.reader
        faces = []
        has_texture_index = (model_flags & 1) == 0

        for _ in range(face_count):
            face_start = r.tell()

            base_flags = r.read_u16()
            length = r.read_u16()
            next_offset = face_start + length

            is_triangle = bool(base_flags & FF_TRIANGLE)
            is_textured = bool(base_flags & FF_HAS_UV)
            is_invisible = bool(base_flags & FF_INVISIBLE)
            is_gouraud = bool(base_flags & FF_GOURAUD)

            # Vertex indices
            if self.version >= PSX_VERSION_4:
                vi = [r.read_u8() for _ in range(4)]
            else:
                vi = [r.read_u16() for _ in range(4)]

            # GPU command (4 bytes)
            gpu_bytes = [r.read_u8() for _ in range(4)]
            gpu_colors = []
            if is_gouraud:
                # Per-vertex palette indices for gouraud shading
                count = 3 if is_triangle else 4
                gpu_colors = [(gpu_bytes[i], gpu_bytes[i], gpu_bytes[i]) for i in range(count)]

            # Normal index + surface flags
            normal_index = r.read_u16()
            surface_flags = r.read_u16()

            # Texture index (conditional)
            texture_index = -1
            if has_texture_index and (base_flags & FF_TEXTURED):
                texture_index = r.read_u32()

            # UV coordinates (conditional)
            uvs = []
            if base_flags & FF_HAS_UV:
                count = 3 if is_triangle else 4
                if self.version >= PSX_VERSION_6:
                    # v6: 4 x u16 U, then 4 x u16 V
                    us = [r.read_u16() for _ in range(4)]
                    vs = [r.read_u16() for _ in range(4)]
                    uvs = [(us[i], vs[i]) for i in range(count)]
                else:
                    # v3/v4: 4 pairs of (u8 U, u8 V) interleaved
                    for _ in range(4):
                        u = r.read_u8()
                        v = r.read_u8()
                        if len(uvs) < count:
                            uvs.append((u, v))

            # Extra data based on flags
            if base_flags & 0x0008:
                r.skip(8)
            if has_texture_index and (base_flags & 0x0020):
                r.skip(4)

            # Trim vertex indices for triangles
            if is_triangle:
                vi = vi[:3]

            faces.append(PSXFace(
                vertex_indices=vi,
                is_triangle=is_triangle,
                is_textured=is_textured,
                is_gouraud=is_gouraud,
                is_invisible=is_invisible,
                texture_index=texture_index,
                uvs=uvs,
                gpu_colors=gpu_colors,
                normal_index=normal_index,
                surface_flags=surface_flags,
                base_flags=base_flags,
            ))

            # Seek to next face (in case we missed some conditional data)
            r.seek(next_offset)

        return faces

    def _parse_tags_and_textures(self, scene: PSXSceneData, model_count: int):
        """Parse the tags section and post-tag palette/texture data."""
        r = self.reader

        if self.tag_start <= 0 or self.tag_start >= len(self.data):
            return

        r.seek(self.tag_start)

        # Parse tags until terminator
        while r.remaining() >= 8:
            tag_type = r.read_u32()
            if tag_type == TERMINATOR:
                break
            tag_length = r.read_u32()
            if tag_length > 0 and r.remaining() >= tag_length:
                r.skip(tag_length)
            else:
                break

        if r.remaining() < 4:
            return

        # Model name CRC hashes
        scene.model_names = [r.read_u32() for _ in range(model_count)]

        if r.remaining() < 4:
            return

        # Texture name CRC hashes
        tex_name_count = r.read_u32()
        scene.texture_names = [r.read_u32() for _ in range(tex_name_count)]

        # 4-bit palettes
        if r.remaining() >= 4:
            pal4_count = r.read_u32()
            for _ in range(pal4_count):
                if r.remaining() < 4 + 16 * 2:
                    break
                name = r.read_u32()
                colors = []
                for _ in range(16):
                    c = r.read_u16()
                    colors.append(self._rgb555_to_rgba(c))
                scene.palettes_4bit.append(PSXPalette(name=name, colors=colors))

        # 8-bit palettes
        if r.remaining() >= 4:
            pal8_count = r.read_u32()
            for _ in range(pal8_count):
                if r.remaining() < 4 + 256 * 2:
                    break
                name = r.read_u32()
                colors = []
                for _ in range(256):
                    c = r.read_u16()
                    colors.append(self._rgb555_to_rgba(c))
                scene.palettes_8bit.append(PSXPalette(name=name, colors=colors))

        # Textures
        if r.remaining() >= 4:
            self._parse_textures(scene)

    def _parse_textures(self, scene: PSXSceneData):
        r = self.reader

        tex_count_or_marker = r.read_u32()

        # v6 special handling: 0xFFFFFFFF means there are texture references first
        if tex_count_or_marker == TERMINATOR:
            # Skip texture references
            ref_count = r.read_u32()
            for _ in range(ref_count):
                r.skip(32 + 4)  # name string + u32
            # Skip cubemap references
            if r.remaining() >= 4:
                cube_count = r.read_u32()
                for _ in range(cube_count):
                    r.skip(32 + 4)
            if r.remaining() < 4:
                return
            tex_count_or_marker = r.read_u32()

        tex_count = tex_count_or_marker
        if tex_count == 0 or tex_count > 10000:
            return

        # Texture offsets
        tex_offsets = []
        for _ in range(tex_count):
            if r.remaining() < 4:
                return
            tex_offsets.append(r.read_u32())

        # Parse each texture
        for toff in tex_offsets:
            if toff >= len(self.data):
                continue
            r.seek(toff)

            if r.remaining() < 20:
                break

            flags = r.read_u32()
            color_count = r.read_u32()
            palette_name = r.read_u32()
            name_index = r.read_u32()
            width = r.read_u16()
            height = r.read_u16()

            # Align width based on color depth
            if color_count == 16:
                width = (width + 3) & ~3
            elif color_count == 256:
                width = (width + 1) & ~1

            # Calculate pixel data size
            if color_count == 16:
                pixel_size = (width * height) // 2
            elif color_count == 256:
                pixel_size = width * height
            elif color_count == 65536:
                pixel_size = width * height * 2
            else:
                pixel_size = 0

            if self.version >= PSX_VERSION_6:
                # v6 textures have extra header data
                # Per thps2-tools: 8 bytes total if ANY of 512|1024|2048 is set
                extra = 0
                if flags & (512 | 1024 | 2048):
                    extra = 8
                if flags & 4096:
                    extra += 4
                if extra > 0:
                    r.skip(extra)

                # Format uint32 + length-prefixed data
                # Per thps2-tools: data_len includes pixel_format(4) + data_len(4),
                # so actual pixel data is data_len - 8 bytes, followed by 2 floats
                if r.remaining() >= 8:
                    pixel_format = r.read_u32()
                    data_len = r.read_u32()
                    pixel_bytes = max(0, data_len - 8)
                    if r.remaining() >= pixel_bytes:
                        pixel_data = r.read(pixel_bytes)
                    else:
                        pixel_data = b''
                    # Skip the 2 trailing floats (unknown purpose)
                    if r.remaining() >= 8:
                        r.skip(8)
                else:
                    pixel_data = b''
                    pixel_format = 0
            else:
                # v3/v4: pixel data follows directly
                pixel_format = flags
                if r.remaining() >= pixel_size:
                    pixel_data = r.read(pixel_size)
                else:
                    pixel_data = b''

            # For v6, use pixel_format for color decoding; for v3/v4, use flags
            fmt = pixel_format if self.version >= PSX_VERSION_6 else flags

            scene.textures.append(PSXTextureInfo(
                color_count=color_count,
                palette_name=palette_name,
                name_index=name_index,
                width=width,
                height=height,
                pixel_data=pixel_data,
                flags=fmt,
            ))

    @staticmethod
    def _rgb555_to_rgba(color: int) -> tuple:
        """Convert a 16-bit RGB555 PSX color to (r, g, b, a) 8-bit tuple."""
        r = ((color >> 0) & 0x1F) * 255 // 31
        g = ((color >> 5) & 0x1F) * 255 // 31
        b = ((color >> 10) & 0x1F) * 255 // 31
        # Transparency: color == 0 means fully transparent
        a = 0 if color == 0 else 255
        return (r, g, b, a)
