#!/usr/bin/env python3
"""Spider-Man 2000 PC — Extract and convert ALL audio from data.pkr.

Extracts:
  1. WAV files (656) — direct copy from PKR (already PCM)
  2. KAT sound banks (58) — decode 4-bit IMA ADPCM -> WAV per asset
  3. BIK voice/music (972) — extract raw .bik, convert to .wav if ffmpeg available
  4. SFX lookup tables (63) — export as .txt metadata files

Output structure:
  audio_export/
    wav/           — 656 WAV files from data\audio\
    kat/           — per-bank folders with decoded WAV per asset
    bik/           — 972 BIK files (+ .wav conversions if ffmpeg found)
    sfx/           — 63 SFX metadata text files

Usage:
    python extract_audio.py [--pkr PATH] [--output DIR] [--no-bik-convert] [--only TYPE]
"""

from __future__ import annotations

import os
import sys
import struct
import shutil
import subprocess
import argparse
import time

# Add parent dir so we can import from io_spiderman2000
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_spiderman2000.pkr_parser import PKRArchive
from io_spiderman2000.audio_decoder import (
    parse_kat, kat_asset_to_pcm, samples_to_wav, parse_sfx,
)


def find_ffmpeg() -> str | None:
    """Find ffmpeg executable on PATH."""
    return shutil.which('ffmpeg')


def extract_wav_files(pkr: PKRArchive, output_dir: str) -> int:
    """Extract all WAV files from data\\audio\\ directory."""
    wav_dir = os.path.join(output_dir, 'wav')
    os.makedirs(wav_dir, exist_ok=True)

    wav_files = pkr.list_files(ext='.wav')
    count = 0

    for entry in wav_files:
        data = pkr.read_file(entry)
        out_path = os.path.join(wav_dir, entry.name)

        with open(out_path, 'wb') as f:
            f.write(data)
        count += 1

    return count


def extract_kat_banks(pkr: PKRArchive, output_dir: str) -> tuple:
    """Extract and decode all KAT sound banks."""
    kat_dir = os.path.join(output_dir, 'kat')
    os.makedirs(kat_dir, exist_ok=True)

    kat_files = pkr.list_files(ext='.kat')
    bank_count = 0
    asset_count = 0

    for entry in kat_files:
        data = pkr.read_file(entry)
        bank = parse_kat(data)

        if bank.num_assets <= 0:
            continue

        # Create per-bank subdirectory
        bank_name = os.path.splitext(entry.name)[0]
        bank_dir = os.path.join(kat_dir, bank_name)
        os.makedirs(bank_dir, exist_ok=True)

        # Write bank metadata
        meta_path = os.path.join(bank_dir, '_metadata.txt')
        with open(meta_path, 'w') as f:
            f.write(f"KAT Bank: {entry.name}\n")
            f.write(f"Source: {entry.full_path}\n")
            f.write(f"File size: {entry.uncompressed_size} bytes\n")
            f.write(f"Assets: {bank.num_assets}\n")
            f.write(f"\n{'Index':>5}  {'Rate':>6}  {'Bits':>4}  {'Size':>8}  {'Offset':>8}  {'Samples':>8}\n")
            f.write(f"{'-'*5:>5}  {'-'*6:>6}  {'-'*4:>4}  {'-'*8:>8}  {'-'*8:>8}  {'-'*8:>8}\n")

            for asset in bank.assets:
                if asset.bit_depth == 4:
                    num_samples = asset.data_size * 2
                elif asset.bit_depth == 8:
                    num_samples = asset.data_size
                elif asset.bit_depth == 16:
                    num_samples = asset.data_size // 2
                else:
                    num_samples = 0

                duration_ms = int(num_samples / asset.sample_rate * 1000) if asset.sample_rate > 0 else 0
                f.write(f"{asset.index:>5}  {asset.sample_rate:>6}  {asset.bit_depth:>4}  "
                        f"{asset.data_size:>8}  {asset.offset:>8}  {num_samples:>8}  "
                        f"({duration_ms}ms)\n")

        # Decode each asset to WAV
        for asset in bank.assets:
            samples, sample_rate, channels = kat_asset_to_pcm(bank, asset.index)
            if not samples:
                continue

            wav_data = samples_to_wav(samples, sample_rate, channels)
            wav_path = os.path.join(bank_dir, f"{bank_name}_{asset.index:03d}.wav")

            with open(wav_path, 'wb') as f:
                f.write(wav_data)
            asset_count += 1

        bank_count += 1

    return bank_count, asset_count


def extract_bik_files(pkr: PKRArchive, output_dir: str,
                      convert: bool = True) -> tuple:
    """Extract BIK files and optionally convert to WAV with ffmpeg."""
    bik_dir = os.path.join(output_dir, 'bik')
    os.makedirs(bik_dir, exist_ok=True)

    ffmpeg = find_ffmpeg() if convert else None
    if convert and not ffmpeg:
        print("  [!] ffmpeg not found on PATH — BIK files will be extracted but not converted")

    bik_files = pkr.list_files(ext='.bik')
    extract_count = 0
    convert_count = 0

    for entry in bik_files:
        data = pkr.read_file(entry)
        bik_path = os.path.join(bik_dir, entry.name)

        with open(bik_path, 'wb') as f:
            f.write(data)
        extract_count += 1

        # Convert to WAV if ffmpeg available
        if ffmpeg:
            wav_name = os.path.splitext(entry.name)[0] + '.wav'
            wav_path = os.path.join(bik_dir, wav_name)

            try:
                result = subprocess.run(
                    [ffmpeg, '-y', '-i', bik_path, '-vn', '-acodec', 'pcm_s16le',
                     '-ar', '22050', wav_path],
                    capture_output=True, timeout=30,
                )
                if result.returncode == 0 and os.path.exists(wav_path):
                    convert_count += 1
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

    return extract_count, convert_count


def extract_sfx_tables(pkr: PKRArchive, output_dir: str) -> int:
    """Extract and parse SFX lookup tables to text files."""
    sfx_dir = os.path.join(output_dir, 'sfx')
    os.makedirs(sfx_dir, exist_ok=True)

    sfx_files = pkr.list_files(ext='.sfx')
    count = 0

    for entry in sfx_files:
        data = pkr.read_file(entry)
        table = parse_sfx(data)

        sfx_name = os.path.splitext(entry.name)[0]
        txt_path = os.path.join(sfx_dir, f"{sfx_name}.txt")

        with open(txt_path, 'w') as f:
            f.write(f"SFX Table: {entry.name}\n")
            f.write(f"Source: {entry.full_path}\n")
            f.write(f"File size: {entry.uncompressed_size} bytes\n")
            f.write(f"Entries: {len(table.entries)}\n\n")

            f.write(f"{'SoundID':>8}  {'BufIdx':>6}  {'Flags':>10}  {'Volume':>6}  {'Pitch':>6}\n")
            f.write(f"{'-'*8:>8}  {'-'*6:>6}  {'-'*10:>10}  {'-'*6:>6}  {'-'*6:>6}\n")

            for e in table.entries:
                f.write(f"{e.sound_id:>8}  {e.buffer_index:>6}  0x{e.flags:08X}  "
                        f"{e.volume:>6}  {e.pitch:>6}\n")

        # Also save raw .sfx file
        raw_path = os.path.join(sfx_dir, entry.name)
        with open(raw_path, 'wb') as f:
            f.write(data)

        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(
        description='Extract and convert all audio from Spider-Man 2000 PC data.pkr')
    parser.add_argument('--pkr', default=r'E:\Games\Spider-Man 2000\data.pkr',
                        help='Path to data.pkr')
    parser.add_argument('--output', default=r'E:\Games\Spider-Man 2000\audio_export',
                        help='Output directory')
    parser.add_argument('--no-bik-convert', action='store_true',
                        help='Skip BIK->WAV conversion (just extract raw .bik files)')
    parser.add_argument('--only', choices=['wav', 'kat', 'bik', 'sfx'],
                        help='Only extract one type')
    args = parser.parse_args()

    if not os.path.exists(args.pkr):
        print(f"ERROR: PKR file not found: {args.pkr}")
        sys.exit(1)

    print(f"Opening PKR: {args.pkr}")
    pkr = PKRArchive(args.pkr)
    print(f"  {len(pkr.files)} files in archive\n")

    os.makedirs(args.output, exist_ok=True)
    start = time.time()

    # 1. WAV files
    if not args.only or args.only == 'wav':
        print("[1/4] Extracting WAV files...")
        wav_count = extract_wav_files(pkr, args.output)
        print(f"  -> {wav_count} WAV files extracted\n")

    # 2. KAT sound banks
    if not args.only or args.only == 'kat':
        print("[2/4] Decoding KAT sound banks (IMA ADPCM -> WAV)...")
        bank_count, asset_count = extract_kat_banks(pkr, args.output)
        print(f"  -> {bank_count} banks, {asset_count} audio assets decoded\n")

    # 3. BIK files
    if not args.only or args.only == 'bik':
        print("[3/4] Extracting BIK voice/music files...")
        bik_extract, bik_convert = extract_bik_files(
            pkr, args.output, convert=not args.no_bik_convert)
        msg = f"  -> {bik_extract} BIK files extracted"
        if bik_convert > 0:
            msg += f", {bik_convert} converted to WAV"
        print(msg + "\n")

    # 4. SFX tables
    if not args.only or args.only == 'sfx':
        print("[4/4] Parsing SFX lookup tables...")
        sfx_count = extract_sfx_tables(pkr, args.output)
        print(f"  -> {sfx_count} SFX tables exported\n")

    elapsed = time.time() - start
    print(f"Done! Output: {args.output}")
    print(f"Time: {elapsed:.1f}s")

    pkr.close()


if __name__ == '__main__':
    main()
