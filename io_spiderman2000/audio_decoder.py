# Spider-Man 2000 PC — Audio decoding (KAT sound banks, SFX tables, IMA ADPCM)

import struct
from dataclasses import dataclass, field


# IMA ADPCM step table (89 entries)
_IMA_STEP_TABLE = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
]

# IMA ADPCM index table (16 entries)
_IMA_INDEX_TABLE = [
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8,
]


@dataclass
class KATAsset:
    """A single sound asset within a KAT sound bank."""
    index: int
    flag: int           # field_0: always 1
    offset: int         # field_4: byte offset from file start to ADPCM data
    data_size: int      # field_8: size of ADPCM data in bytes
    sample_rate: int    # field_C: sample rate in Hz (12000, 16000, etc.)
    unknown: int        # field_10: always 0
    bit_depth: int      # field_14: 4 (ADPCM), 8, or 16


@dataclass
class KATBank:
    """Parsed KAT sound bank."""
    num_assets: int
    assets: list        # list of KATAsset
    raw_data: bytes     # full file data for reading audio chunks


@dataclass
class SFXEntry:
    """A single entry in an SFX sound mapping table."""
    sound_id: int
    buffer_index: int   # index into DXSound buffer array
    flags: int
    volume: int
    pitch: int


@dataclass
class SFXTable:
    """Parsed SFX lookup table."""
    entries: list       # list of SFXEntry


def parse_kat(data: bytes) -> KATBank:
    """Parse a KAT sound bank file.

    Layout:
        i32  numAssets
        SSfxAsset[numAssets]  (44 bytes each)
        ... raw ADPCM audio data ...

    SSfxAsset (0x2C = 44 bytes):
        i32  flag         (+0x00)
        i32  offset       (+0x04) byte offset from file start
        u32  data_size    (+0x08) size of ADPCM data
        i32  sample_rate  (+0x0C) Hz
        i32  unknown      (+0x10) always 0
        i32  bit_depth    (+0x14) 4, 8, or 16
        24 bytes padding  (+0x18 to +0x2B)
    """
    if len(data) < 4:
        return KATBank(0, [], data)

    num_assets = struct.unpack_from('<i', data, 0)[0]
    if num_assets <= 0 or num_assets > 1000:
        return KATBank(0, [], data)

    assets = []
    for i in range(num_assets):
        base = 4 + i * 44
        if base + 44 > len(data):
            break

        flag = struct.unpack_from('<i', data, base)[0]
        offset = struct.unpack_from('<i', data, base + 4)[0]
        data_size = struct.unpack_from('<I', data, base + 8)[0]
        sample_rate = struct.unpack_from('<i', data, base + 12)[0]
        unknown = struct.unpack_from('<i', data, base + 16)[0]
        bit_depth = struct.unpack_from('<i', data, base + 20)[0]

        # Validate
        if sample_rate < 99 or sample_rate > 999999:
            continue
        if bit_depth not in (4, 8, 16):
            continue

        assets.append(KATAsset(
            index=i,
            flag=flag,
            offset=offset,
            data_size=data_size,
            sample_rate=sample_rate,
            unknown=unknown,
            bit_depth=bit_depth,
        ))

    return KATBank(num_assets=num_assets, assets=assets, raw_data=data)


def extract_kat_audio(bank: KATBank, asset_index: int) -> bytes:
    """Extract raw audio data for a specific asset from a KAT bank."""
    if asset_index < 0 or asset_index >= len(bank.assets):
        return b''

    asset = bank.assets[asset_index]
    start = asset.offset
    end = start + asset.data_size

    if start < 0 or end > len(bank.raw_data):
        return b''

    return bank.raw_data[start:end]


def decode_ima_adpcm(adpcm_data: bytes) -> list:
    """Decode 4-bit IMA ADPCM data to 16-bit PCM samples.

    Each byte contains two nibbles: low nibble first, then high nibble.
    Decoder state starts at predictor=0, step_index=0 (no preamble).

    Returns list of signed 16-bit integer samples.
    """
    predictor = 0
    step_index = 0
    samples = []

    for byte in adpcm_data:
        # Low nibble first
        for nibble in (byte & 0x0F, (byte >> 4) & 0x0F):
            step = _IMA_STEP_TABLE[step_index]

            # Compute difference
            diff = step >> 3
            if nibble & 4:
                diff += step
            if nibble & 2:
                diff += step >> 1
            if nibble & 1:
                diff += step >> 2

            # Apply sign (bit 3)
            if nibble & 8:
                predictor -= diff
            else:
                predictor += diff

            # Clamp to 16-bit signed range
            if predictor > 32767:
                predictor = 32767
            elif predictor < -32768:
                predictor = -32768

            samples.append(predictor)

            # Update step index
            step_index += _IMA_INDEX_TABLE[nibble]
            if step_index < 0:
                step_index = 0
            elif step_index > 88:
                step_index = 88

    return samples


def decode_pcm8(data: bytes) -> list:
    """Decode 8-bit unsigned PCM to 16-bit signed samples."""
    return [(b - 128) * 256 for b in data]


def decode_pcm16(data: bytes) -> list:
    """Decode 16-bit signed PCM (little-endian) to sample list."""
    samples = []
    for i in range(0, len(data) - 1, 2):
        sample = struct.unpack_from('<h', data, i)[0]
        samples.append(sample)
    return samples


def kat_asset_to_pcm(bank: KATBank, asset_index: int) -> tuple:
    """Decode a KAT asset to PCM samples.

    Returns (samples: list[int], sample_rate: int, channels: int).
    samples are signed 16-bit integers.
    """
    if asset_index < 0 or asset_index >= len(bank.assets):
        return [], 0, 0

    asset = bank.assets[asset_index]
    raw = extract_kat_audio(bank, asset_index)
    if not raw:
        return [], 0, 0

    if asset.bit_depth == 4:
        samples = decode_ima_adpcm(raw)
    elif asset.bit_depth == 8:
        samples = decode_pcm8(raw)
    elif asset.bit_depth == 16:
        samples = decode_pcm16(raw)
    else:
        return [], 0, 0

    return samples, asset.sample_rate, 1  # always mono


def samples_to_wav(samples: list, sample_rate: int, channels: int = 1,
                   bits_per_sample: int = 16) -> bytes:
    """Convert PCM samples to a WAV file in memory.

    Args:
        samples: list of signed 16-bit integer samples
        sample_rate: sample rate in Hz
        channels: number of channels (1 = mono)
        bits_per_sample: output bit depth (16)

    Returns:
        Complete WAV file as bytes.
    """
    # Pack samples as 16-bit little-endian signed
    pcm_data = struct.pack(f'<{len(samples)}h', *samples)

    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = len(pcm_data)

    # Build WAV header
    wav = bytearray()
    wav.extend(b'RIFF')
    wav.extend(struct.pack('<I', 36 + data_size))  # file size - 8
    wav.extend(b'WAVE')

    # fmt chunk
    wav.extend(b'fmt ')
    wav.extend(struct.pack('<I', 16))              # chunk size
    wav.extend(struct.pack('<H', 1))               # PCM format
    wav.extend(struct.pack('<H', channels))
    wav.extend(struct.pack('<I', sample_rate))
    wav.extend(struct.pack('<I', byte_rate))
    wav.extend(struct.pack('<H', block_align))
    wav.extend(struct.pack('<H', bits_per_sample))

    # data chunk
    wav.extend(b'data')
    wav.extend(struct.pack('<I', data_size))
    wav.extend(pcm_data)

    return bytes(wav)


def parse_sfx(data: bytes) -> SFXTable:
    """Parse an SFX sound mapping table.

    Layout:
        u32  header (usually small count or flags)
        Repeated 16-byte records until 0xFFFFFFFF terminator:
            u32  sound_id
            u32  buffer_index
            u32  flags
            u32  volume_pitch (packed)
    """
    entries = []
    if len(data) < 8:
        return SFXTable(entries)

    # Skip 4-byte header
    pos = 4

    while pos + 16 <= len(data):
        sound_id = struct.unpack_from('<I', data, pos)[0]
        if sound_id == 0xFFFFFFFF:
            break

        buffer_index = struct.unpack_from('<I', data, pos + 4)[0]
        flags = struct.unpack_from('<I', data, pos + 8)[0]
        vol_pitch = struct.unpack_from('<I', data, pos + 12)[0]

        volume = vol_pitch & 0xFFFF
        pitch = (vol_pitch >> 16) & 0xFFFF

        entries.append(SFXEntry(
            sound_id=sound_id,
            buffer_index=buffer_index,
            flags=flags,
            volume=volume,
            pitch=pitch,
        ))
        pos += 16

    return SFXTable(entries)
