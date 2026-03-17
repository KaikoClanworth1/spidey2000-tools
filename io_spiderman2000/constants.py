# Spider-Man 2000 PC — Format constants

# PKR3 archive
PKR3_MAGIC = b'PKR3'

# PSX format versions
PSX_VERSION_3 = 0x0003  # THPS1-era
PSX_VERSION_4 = 0x0004  # Spider-Man 2000 / THPS2
PSX_VERSION_6 = 0x0006  # THPS2X-era

# Face flags (bitmask)
FF_HAS_UV = 0x0001
FF_TEXTURED = 0x0002
FF_TRIANGLE = 0x0010
FF_INVISIBLE = 0x0080
FF_GOURAUD = 0x0800

# PVR pixel_format: low byte = color format, high byte = data type
# Color formats: 0x00=ARGB1555, 0x01=RGB565, 0x02=ARGB4444
# Data types: 0x03=VQ compressed, 0x09=Rectangle (linear/raw)
PVR_VQ_ARGB1555 = 0x0300   # 768  — VQ compressed ARGB1555
PVR_VQ_RGB565 = 0x0301     # 769  — VQ compressed RGB565
PVR_VQ_ARGB4444 = 0x0302   # 770  — VQ compressed ARGB4444
PVR_TWID_ARGB1555 = 0x0100  # 256  — Twiddled (Morton) ARGB1555
PVR_TWID_RGB565 = 0x0101    # 257  — Twiddled (Morton) RGB565
PVR_TWID_ARGB4444 = 0x0102  # 258  — Twiddled (Morton) ARGB4444
PVR_RECT_RGB565 = 0x0901   # 2305 — Rectangle (raw) RGB565
PVR_RECT_ARGB4444 = 0x0902 # 2306 — Rectangle (raw) ARGB4444

# Legacy aliases
PAL_ARGB5551 = PVR_VQ_ARGB1555
PAL_RGB565_A = PVR_VQ_RGB565
PAL_ARGB4444_A = PVR_VQ_ARGB4444
PAL_RGB565_B = PVR_RECT_RGB565
PAL_ARGB4444_B = PVR_RECT_ARGB4444

# VQ codebook size (256 entries × 4 pixels × 2 bytes per pixel)
VQ_CODEBOOK_SIZE = 2048

# Vertex coordinate scale (Q12 fixed-point)
VERTEX_SCALE = 1.0 / 4096.0

# Default import scale for Blender
DEFAULT_IMPORT_SCALE = 0.01

# Section terminators
TERMINATOR = 0xFFFFFFFF

# Level name table
LEVEL_NAMES = {
    "L1A1": "Bank Heist",
    "L1A2": "Rooftop Chase",
    "L1A2a": "Rooftop Chase (Alt)",
    "L1A3": "Warehouse Rooftop",
    "L1A4": "Warehouse Interior",
    "L2A1": "Chemical Plant",
    "L2A2": "Chemical Plant Interior",
    "L3A1": "Sewer Entrance",
    "L3A1a": "Sewer Entrance (Alt)",
    "L3A2": "Sewer Tunnels",
    "L3A3": "Sewer Lab",
    "L3A4": "Sewer Depths",
    "L3A5": "Lizard Chase",
    "L4A1": "Subway Station",
    "L5A1": "Symbiote Invasion",
    "L5A2": "Symbiote Chaos",
    "L5A3": "Symbiote Streets",
    "L5A4": "Symbiote Building",
    "L5A5": "Symbiote Hive",
    "L5A6": "Symbiote Lab",
    "L5A7": "Symbiote Finale",
    "L6A1": "Waterfront",
    "L6A2": "Waterfront Interior",
    "L6A3": "Doc Ock's Lab",
    "L6A4": "Doc Ock Boss",
    "L7A1": "Carnage Attack",
    "L7A2": "Carnage Chase",
    "L7A3": "Carnage Interior",
    "L7A4": "Carnage Boss",
    "L7A5": "Carnage Finale",
    "L8A1": "Venom Chase",
    "L8A2": "Venom Building",
    "L8A3": "Venom Interior",
    "L8A4": "Venom Boss",
    "L8A5": "Venom Escape",
    "L8A6": "Final Battle",
    "L9A1": "Training 1",
    "L9A2": "Training 2",
    "L9A3": "Training 3",
    "L9A4": "Training 4",
    "LBA1": "Bonus 1",
    "LBA2": "Bonus 2",
    "LBA3": "Bonus 3",
    "LBA4": "Bonus 4",
    "LCA1": "Comic Cover 1",
    "LCA2": "Comic Cover 2",
    "LCA3": "Comic Cover 3",
    "LCA4": "Comic Cover 4",
    "LDA1": "Gallery 1",
    "LDA2": "Gallery 2",
    "LDA3": "Gallery 3",
    "LFA1": "FMV Arena 1",
    "LGA1": "Special Stage",
    "LHA1": "Hidden Stage",
    "DEM1": "Demo 1",
    "DEM2": "Demo 2",
    "DEM3": "Demo 3",
    "DEM4": "Demo 4",
    "zArt": "Art Gallery",
}
