# Spider-Man 2000 PC — Texture decoding (4-bit, 8-bit, 16-bit PSX formats)
# Supports Dreamcast PVR VQ-compressed and Rectangle (linear) formats

from .constants import (
    PVR_VQ_ARGB1555, PVR_VQ_RGB565, PVR_VQ_ARGB4444,
    PVR_RECT_RGB565, PVR_RECT_ARGB4444,
    PVR_TWID_ARGB1555, PVR_TWID_RGB565, PVR_TWID_ARGB4444,
    VQ_CODEBOOK_SIZE,
)

# VQ format IDs (data type 0x03)
_VQ_FORMATS = {PVR_VQ_ARGB1555, PVR_VQ_RGB565, PVR_VQ_ARGB4444}

# Rectangle/linear format IDs (data type 0x09)
_RECT_FORMATS = {PVR_RECT_RGB565, PVR_RECT_ARGB4444}

# Twiddled format IDs (data type 0x01) — pixels stored in Morton/Z-order
_TWID_FORMATS = {PVR_TWID_ARGB1555, PVR_TWID_RGB565, PVR_TWID_ARGB4444}


def _color_format(pixel_format: int) -> int:
    """Extract color format from pixel_format (low byte)."""
    return pixel_format & 0xFF


def _decode_pixel_16bit(c: int, color_fmt: int) -> tuple:
    """Decode a single 16-bit pixel based on PVR color format."""
    if color_fmt == 0x00:  # ARGB1555: A(15) R(14-10) G(9-5) B(4-0)
        a = ((c >> 15) & 1) * 255
        r = ((c >> 10) & 0x1F) * 255 // 31
        g = ((c >> 5) & 0x1F) * 255 // 31
        b = ((c >> 0) & 0x1F) * 255 // 31
        return (r, g, b, a)
    elif color_fmt == 0x02:  # ARGB4444: A(15-12) R(11-8) G(7-4) B(3-0)
        a = ((c >> 12) & 0xF) * 255 // 15
        r = ((c >> 8) & 0xF) * 255 // 15
        g = ((c >> 4) & 0xF) * 255 // 15
        b = ((c >> 0) & 0xF) * 255 // 15
        return (r, g, b, a)
    else:  # 0x01 = RGB565: R(15-11) G(10-5) B(4-0)
        r = ((c >> 11) & 0x1F) * 255 // 31
        g = ((c >> 5) & 0x3F) * 255 // 63
        b = ((c >> 0) & 0x1F) * 255 // 31
        return (r, g, b, 255)


def _morton_index(x: int, y: int) -> int:
    """Compute Morton/Z-order index from (x, y) coordinates."""
    result = 0
    for i in range(16):
        result |= ((x >> i) & 1) << (2 * i)
        result |= ((y >> i) & 1) << (2 * i + 1)
    return result


def _decode_vq_16bit(pixel_data: bytes, width: int, height: int,
                     color_fmt: int) -> list:
    """Decode a VQ-compressed 16-bit texture (Dreamcast PVR format).

    Structure: 2048-byte codebook (256 entries × 4 pixels × 2 bytes),
    followed by (w/2)×(h/2) indices in Morton/Z-order.
    """
    if len(pixel_data) < VQ_CODEBOOK_SIZE:
        return []

    # Parse codebook: 256 entries, each = 4 pixels in 2x2 block
    # PVR codebook pixel order (Morton/Z-order within 2x2 block):
    # entry[0]=(0,0) TL, entry[1]=(0,1) BL, entry[2]=(1,0) TR, entry[3]=(1,1) BR
    codebook = []
    for i in range(256):
        entry = []
        for j in range(4):
            offset = (i * 4 + j) * 2
            c = pixel_data[offset] | (pixel_data[offset + 1] << 8)
            entry.append(_decode_pixel_16bit(c, color_fmt))
        codebook.append(entry)

    # Index data follows codebook
    index_data = pixel_data[VQ_CODEBOOK_SIZE:]

    # Block grid dimensions
    bw = width // 2
    bh = height // 2

    # Output pixel grid
    pixels = [(0, 0, 0, 0)] * (width * height)

    for by in range(bh):
        for bx in range(bw):
            morton_idx = _morton_index(bx, by)
            if morton_idx >= len(index_data):
                continue

            cb_idx = index_data[morton_idx]
            entry = codebook[cb_idx]

            # Place 2x2 block — codebook entries are Morton-ordered:
            # [0]=(0,0) TL, [1]=(0,1) BL, [2]=(1,0) TR, [3]=(1,1) BR
            px = bx * 2
            py = by * 2
            pixels[py * width + px] = entry[0]              # (0,0) top-left
            pixels[(py + 1) * width + px] = entry[1]        # (0,1) bottom-left
            pixels[py * width + px + 1] = entry[2]          # (1,0) top-right
            pixels[(py + 1) * width + px + 1] = entry[3]    # (1,1) bottom-right

    return pixels


def _decode_twiddled_16bit(pixel_data: bytes, width: int, height: int,
                           color_fmt: int) -> list:
    """Decode a twiddled (Morton-order) 16-bit texture."""
    pixels = [(0, 0, 0, 0)] * (width * height)
    total = width * height

    for y in range(height):
        for x in range(width):
            morton = _morton_index(x, y)
            if morton >= total or morton * 2 + 1 >= len(pixel_data):
                continue
            c = pixel_data[morton * 2] | (pixel_data[morton * 2 + 1] << 8)
            pixels[y * width + x] = _decode_pixel_16bit(c, color_fmt)

    return pixels


def _decode_rect_16bit(pixel_data: bytes, width: int, height: int,
                       color_fmt: int) -> list:
    """Decode a rectangle (linear/raw) 16-bit texture."""
    pixels = []
    expected = width * height

    for i in range(min(len(pixel_data) // 2, expected)):
        c = pixel_data[i * 2] | (pixel_data[i * 2 + 1] << 8)
        pixels.append(_decode_pixel_16bit(c, color_fmt))

    while len(pixels) < expected:
        pixels.append((0, 0, 0, 0))

    return pixels


def decode_4bit_texture(pixel_data: bytes, palette: list, width: int, height: int) -> list:
    """Decode a 4-bit indexed texture. Each byte holds 2 pixels (low nibble first)."""
    pixels = []
    expected = width * height

    for byte_idx in range(len(pixel_data)):
        if len(pixels) >= expected:
            break
        b = pixel_data[byte_idx]
        lo = b & 0x0F
        hi = (b >> 4) & 0x0F

        if lo < len(palette):
            pixels.append(palette[lo])
        else:
            pixels.append((0, 0, 0, 0))

        if len(pixels) < expected:
            if hi < len(palette):
                pixels.append(palette[hi])
            else:
                pixels.append((0, 0, 0, 0))

    while len(pixels) < expected:
        pixels.append((0, 0, 0, 0))

    return pixels


def decode_8bit_texture(pixel_data: bytes, palette: list, width: int, height: int) -> list:
    """Decode an 8-bit indexed texture. One byte per pixel."""
    pixels = []
    expected = width * height

    for i in range(min(len(pixel_data), expected)):
        idx = pixel_data[i]
        if idx < len(palette):
            pixels.append(palette[idx])
        else:
            pixels.append((0, 0, 0, 0))

    while len(pixels) < expected:
        pixels.append((0, 0, 0, 0))

    return pixels


def decode_16bit_texture(pixel_data: bytes, width: int, height: int,
                         palette_id: int = 0) -> list:
    """Decode a 16-bit texture, handling both VQ-compressed and raw formats.

    Args:
        pixel_data: Raw pixel bytes (may include VQ codebook + indices)
        width: Texture width
        height: Texture height
        palette_id: pixel_format value (determines VQ vs rectangle and color format)
    """
    color_fmt = _color_format(palette_id)

    if palette_id in _VQ_FORMATS:
        return _decode_vq_16bit(pixel_data, width, height, color_fmt)
    elif palette_id in _TWID_FORMATS:
        return _decode_twiddled_16bit(pixel_data, width, height, color_fmt)
    else:
        # Rectangle/linear or unknown — decode as raw pixels
        return _decode_rect_16bit(pixel_data, width, height, color_fmt)


def psx_color_to_rgba(color: int) -> tuple:
    """Convert a single 16-bit PSX RGB555 color to (r, g, b, a)."""
    r = ((color >> 0) & 0x1F) * 255 // 31
    g = ((color >> 5) & 0x1F) * 255 // 31
    b = ((color >> 10) & 0x1F) * 255 // 31
    a = 0 if color == 0 else 255
    return (r, g, b, a)


def rgba_to_blender_pixels(rgba_list: list, width: int, height: int) -> list:
    """Convert list of (r,g,b,a) tuples to flat Blender pixel array (float 0-1)."""
    pixels = []
    for r, g, b, a in rgba_list:
        pixels.extend([r / 255.0, g / 255.0, b / 255.0, a / 255.0])
    return pixels


def create_blender_image(name: str, width: int, height: int, rgba_pixels: list):
    """Create a Blender image from RGBA pixel data."""
    import bpy

    image = bpy.data.images.new(name, width=width, height=height, alpha=True)

    flat_pixels = rgba_to_blender_pixels(rgba_pixels, width, height)

    # Blender images are bottom-up, PSX textures are top-down — flip vertically
    flipped = []
    for row in range(height - 1, -1, -1):
        start = row * width * 4
        flipped.extend(flat_pixels[start:start + width * 4])

    image.pixels = flipped
    image.pack()
    return image
