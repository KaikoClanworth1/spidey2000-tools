#!/usr/bin/env python3
"""Spider-Man 2000 PC -- Extract and convert all FMV cutscenes from media.pkr.

Extracts 25 BIK video files from media.pkr and converts to MP4 via ffmpeg.

Output structure:
  video_export/
    bik/           -- raw .bik files
    mp4/           -- converted .mp4 files (if ffmpeg available)

Usage:
    python extract_videos.py [--pkr PATH] [--output DIR] [--no-convert]
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_spiderman2000.pkr_parser import PKRArchive


# Friendly names for cutscene files
CUTSCENE_NAMES = {
    'ATVILOGO': 'Activision Logo',
    'Neversoft': 'Neversoft Logo',
    'treyarch': 'Treyarch Logo',
    'GrayMatt': 'Gray Matter Logo',
    'L1M1': 'Act 1 - Intro (Bank Heist)',
    'L1M2': 'Act 1 - Outro',
    'L2M1': 'Act 2 - Intro (Symbiote Invasion)',
    'L2M2': 'Act 2 - Mid',
    'L2M3': 'Act 2 - Outro',
    'L3M1': 'Act 3 - Intro (Venom Chase)',
    'L4M1': 'Act 4 - Intro (Doc Ock)',
    'L4M2': 'Act 4 - Outro',
    'L5M1': 'Act 5 - Intro (Carnage)',
    'L5M2': 'Act 5 - Mid 1',
    'L5M3': 'Act 5 - Mid 2',
    'L5M4': 'Act 5 - Outro',
    'L6M1': 'Act 6 - Intro (Monster Ock)',
    'L7M1': 'Act 7 - Intro',
    'L7M2': 'Act 7 - Mid',
    'L7M3': 'Act 7 - Outro',
    'L8M1': 'Act 8 - Intro (Final)',
    'L8M2': 'Act 8 - Mid',
    'L8M3': 'Act 8 - Mid 2',
    'L8M4': 'Act 8 - Outro',
    'L8M5': 'Act 8 - Ending',
}


def find_ffmpeg() -> str | None:
    return shutil.which('ffmpeg')


def find_ffprobe() -> str | None:
    return shutil.which('ffprobe')


def get_video_info(ffprobe: str, filepath: str) -> dict:
    """Get video duration, resolution, etc. via ffprobe."""
    try:
        result = subprocess.run(
            [ffprobe, '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', filepath],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            info = {}
            fmt = data.get('format', {})
            info['duration'] = float(fmt.get('duration', 0))
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    info['width'] = stream.get('width', 0)
                    info['height'] = stream.get('height', 0)
                    info['fps'] = eval(stream.get('r_frame_rate', '0/1'))
                    info['codec'] = stream.get('codec_name', '?')
                elif stream.get('codec_type') == 'audio':
                    info['audio_rate'] = stream.get('sample_rate', '?')
                    info['audio_codec'] = stream.get('codec_name', '?')
            return info
    except Exception:
        pass
    return {}


def main():
    parser = argparse.ArgumentParser(
        description='Extract and convert FMV cutscenes from Spider-Man 2000 PC media.pkr')
    parser.add_argument('--pkr', default=r'E:\Games\Spider-Man 2000\media.pkr',
                        help='Path to media.pkr')
    parser.add_argument('--output', default=r'E:\Games\Spider-Man 2000\video_export',
                        help='Output directory')
    parser.add_argument('--no-convert', action='store_true',
                        help='Skip MP4 conversion (just extract raw .bik files)')
    args = parser.parse_args()

    if not os.path.exists(args.pkr):
        print(f"ERROR: PKR file not found: {args.pkr}")
        sys.exit(1)

    ffmpeg = find_ffmpeg() if not args.no_convert else None
    ffprobe = find_ffprobe()

    if not args.no_convert and not ffmpeg:
        print("[!] ffmpeg not found -- BIK files will be extracted but not converted")

    print(f"Opening PKR: {args.pkr}")
    pkr = PKRArchive(args.pkr)
    print(f"  {len(pkr.files)} files in archive\n")

    bik_dir = os.path.join(args.output, 'bik')
    mp4_dir = os.path.join(args.output, 'mp4')
    os.makedirs(bik_dir, exist_ok=True)
    if ffmpeg:
        os.makedirs(mp4_dir, exist_ok=True)

    start = time.time()
    extract_count = 0
    convert_count = 0

    bik_files = [f for f in pkr.files if f.extension == '.bik']

    for entry in bik_files:
        base_name = os.path.splitext(entry.name)[0]
        friendly = CUTSCENE_NAMES.get(base_name, base_name)
        size_mb = entry.uncompressed_size / 1024 / 1024

        print(f"  [{extract_count+1:2d}/{len(bik_files)}] {entry.name:20s} ({size_mb:6.1f} MB)  {friendly}")

        # Extract raw BIK
        data = pkr.read_file(entry)
        bik_path = os.path.join(bik_dir, entry.name)
        with open(bik_path, 'wb') as f:
            f.write(data)
        extract_count += 1

        # Convert to MP4
        if ffmpeg:
            mp4_name = base_name + '.mp4'
            mp4_path = os.path.join(mp4_dir, mp4_name)

            try:
                result = subprocess.run(
                    [ffmpeg, '-y', '-i', bik_path,
                     '-c:v', 'libx264', '-crf', '18', '-preset', 'fast',
                     '-c:a', 'aac', '-b:a', '192k',
                     '-movflags', '+faststart',
                     mp4_path],
                    capture_output=True, timeout=120,
                )
                if result.returncode == 0 and os.path.exists(mp4_path):
                    convert_count += 1
                else:
                    stderr = result.stderr.decode('utf-8', errors='replace')[-200:]
                    print(f"         [!] ffmpeg error: {stderr}")
            except subprocess.TimeoutExpired:
                print(f"         [!] ffmpeg timed out")
            except FileNotFoundError:
                print(f"         [!] ffmpeg not found")

    elapsed = time.time() - start

    # Print summary with video info
    print(f"\n{'='*60}")
    print(f"Extraction complete!")
    print(f"  BIK files extracted: {extract_count}")
    if ffmpeg:
        print(f"  MP4 files converted: {convert_count}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Output: {args.output}")

    # Show video details if ffprobe available
    if ffprobe and convert_count > 0:
        print(f"\n{'='*60}")
        print(f"{'File':20s}  {'Resolution':>10s}  {'Duration':>8s}  {'Size':>8s}  Description")
        print(f"{'-'*20}  {'-'*10:>10s}  {'-'*8:>8s}  {'-'*8:>8s}  {'-'*20}")

        for entry in bik_files:
            base_name = os.path.splitext(entry.name)[0]
            mp4_path = os.path.join(mp4_dir, base_name + '.mp4')
            if not os.path.exists(mp4_path):
                continue
            info = get_video_info(ffprobe, mp4_path)
            res = f"{info.get('width', '?')}x{info.get('height', '?')}"
            dur = info.get('duration', 0)
            dur_str = f"{int(dur//60)}:{int(dur%60):02d}"
            size_mb = os.path.getsize(mp4_path) / 1024 / 1024
            friendly = CUTSCENE_NAMES.get(base_name, base_name)
            print(f"{base_name + '.mp4':20s}  {res:>10s}  {dur_str:>8s}  {size_mb:>6.1f}MB  {friendly}")

    pkr.close()


if __name__ == '__main__':
    main()
