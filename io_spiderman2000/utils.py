# Spider-Man 2000 PC — Utility classes and functions

import struct


class BinaryReader:
    """Lightweight binary reader with little-endian unpacking."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self._len = len(data)

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int):
        self._pos = pos

    def skip(self, n: int):
        self._pos += n

    def remaining(self) -> int:
        return self._len - self._pos

    def read(self, n: int) -> bytes:
        end = self._pos + n
        if end > self._len:
            raise EOFError(f"Read past end: pos={self._pos}, requested={n}, size={self._len}")
        result = self._data[self._pos:end]
        self._pos = end
        return result

    def read_u8(self) -> int:
        return self.read(1)[0]

    def read_u16(self) -> int:
        return struct.unpack_from('<H', self._data, self._advance(2))[0]

    def read_u32(self) -> int:
        return struct.unpack_from('<I', self._data, self._advance(4))[0]

    def read_i16(self) -> int:
        return struct.unpack_from('<h', self._data, self._advance(2))[0]

    def read_i32(self) -> int:
        return struct.unpack_from('<i', self._data, self._advance(4))[0]

    def read_float(self) -> float:
        return struct.unpack_from('<f', self._data, self._advance(4))[0]

    def read_string(self, n: int) -> str:
        raw = self.read(n)
        end = raw.find(b'\x00')
        if end >= 0:
            raw = raw[:end]
        return raw.decode('ascii', errors='replace')

    def _advance(self, n: int) -> int:
        pos = self._pos
        self._pos += n
        if self._pos > self._len:
            raise EOFError(f"Read past end: pos={pos}, requested={n}, size={self._len}")
        return pos


def sm2000_to_blender_pos(x: float, y: float, z: float, scale: float = 1.0) -> tuple:
    """Convert SM2000 coordinates to Blender (swap Y/Z, negate new Y)."""
    return (x * scale, -z * scale, y * scale)


def sm2000_to_blender_quat(x: float, y: float, z: float, w: float) -> tuple:
    """Convert SM2000 quaternion (x,y,z,w) to Blender (w,x,y,z) with axis remap."""
    return (w, x, -z, y)


def normalize_uv(u: float, v: float, tex_w: int, tex_h: int) -> tuple:
    """Normalize UV coords to 0-1 range with V-flip for Blender."""
    if tex_w <= 0 or tex_h <= 0:
        return (0.0, 0.0)
    return (u / tex_w, 1.0 - v / tex_h)
