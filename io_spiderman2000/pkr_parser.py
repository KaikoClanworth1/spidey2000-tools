# Spider-Man 2000 PC — PKR3 archive reader

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from .constants import PKR3_MAGIC


@dataclass
class PKRDirectory:
    name: str
    start_index: int
    file_count: int


@dataclass
class PKRFileEntry:
    index: int
    name: str
    directory: str
    crc: int
    compressed: int
    offset: int
    uncompressed_size: int
    compressed_size: int

    @property
    def full_path(self) -> str:
        return self.directory + self.name

    @property
    def extension(self) -> str:
        dot = self.name.rfind('.')
        return self.name[dot:].lower() if dot >= 0 else ''

    @property
    def is_compressed(self) -> bool:
        return self.compressed == 2


class PKRArchive:
    """Lazy PKR3 archive reader. Parses directory on init, reads files on demand."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.directories: list[PKRDirectory] = []
        self.files: list[PKRFileEntry] = []
        self._fh = None

        self._fh = open(filepath, 'rb')
        self._parse_directory()

    def _parse_directory(self):
        f = self._fh
        f.seek(0)

        magic = f.read(4)
        if magic != PKR3_MAGIC:
            raise ValueError(f"Not a PKR3 file: magic={magic!r}")

        dir_offset = struct.unpack('<I', f.read(4))[0]
        f.seek(dir_offset)

        _unknown, num_dirs, total_files = struct.unpack('<III', f.read(12))

        # Read directory entries
        self.directories = []
        for _ in range(num_dirs):
            name = f.read(32).split(b'\x00')[0].decode('ascii', errors='replace')
            start_idx, count = struct.unpack('<II', f.read(8))
            self.directories.append(PKRDirectory(name, start_idx, count))

        # Build file-index-to-directory mapping
        file_dir_map = {}
        for d in self.directories:
            for i in range(d.start_index, d.start_index + d.file_count):
                file_dir_map[i] = d.name

        # Read file entries
        self.files = []
        for i in range(total_files):
            name = f.read(32).split(b'\x00')[0].decode('ascii', errors='replace')
            crc, compressed, offset, uncomp_size, comp_size = struct.unpack('<IiIII', f.read(20))
            directory = file_dir_map.get(i, '')
            self.files.append(PKRFileEntry(
                index=i,
                name=name,
                directory=directory,
                crc=crc,
                compressed=compressed,
                offset=offset,
                uncompressed_size=uncomp_size,
                compressed_size=comp_size,
            ))

    def read_file(self, entry: PKRFileEntry) -> bytes:
        """Read and decompress a file from the archive."""
        if self._fh is None:
            self._fh = open(self.filepath, 'rb')

        self._fh.seek(entry.offset)
        raw = self._fh.read(entry.compressed_size)

        if entry.is_compressed:
            data = zlib.decompress(raw)
            if len(data) != entry.uncompressed_size:
                raise ValueError(
                    f"Size mismatch for {entry.name}: "
                    f"got {len(data)}, expected {entry.uncompressed_size}"
                )
            return data
        return raw

    def read_file_by_index(self, index: int) -> bytes:
        """Read a file by its index in the archive."""
        return self.read_file(self.files[index])

    def list_files(self, ext: str = None, directory: str = None) -> list[PKRFileEntry]:
        """List files, optionally filtered by extension and/or directory."""
        result = self.files
        if ext:
            ext_lower = ext.lower() if ext.startswith('.') else '.' + ext.lower()
            result = [f for f in result if f.extension == ext_lower]
        if directory:
            dir_lower = directory.lower().rstrip('\\') + '\\'
            result = [f for f in result if f.directory.lower() == dir_lower]
        return result

    def find_file(self, name: str, directory: str = None) -> PKRFileEntry | None:
        """Find a file by name (case-insensitive). Returns first match."""
        name_lower = name.lower()
        for entry in self.files:
            if entry.name.lower() == name_lower:
                if directory is None or entry.directory.lower() == directory.lower():
                    return entry
        return None

    def find_level_files(self, level_id: str) -> dict:
        """Find all files for a level (G, O, L, T components)."""
        result = {}
        suffixes = {
            'G': f'{level_id}_G.psx',
            'O': f'{level_id}_O.psx',
            'L': f'{level_id}_L.psx',
            'T': f'{level_id}_T.trg',
        }
        for key, filename in suffixes.items():
            entry = self.find_file(filename)
            if entry:
                result[key] = entry
        return result

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
