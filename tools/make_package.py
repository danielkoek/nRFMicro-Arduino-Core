#!/usr/bin/env python3
"""
Build script for creating nRFMicro-Arduino-Core release archives.

Usage:
    python3 tools/make_package.py [options]

Options:
    --version VERSION       Version string (default: read from package.json)
    --output-dir DIR        Directory to write the archive to (default: repo root)
    --update-index          Update package_nRFMicro_index.json with the new entry
    --base-url URL          Base download URL (required with --update-index)
                            e.g. https://github.com/danielkoek/nRFMicro-Arduino-Core/releases/download/v1.2.0

Examples:
    # Build only, print checksum info
    python3 tools/make_package.py

    # Build and update index (local release prep)
    python3 tools/make_package.py --version 1.2.0 \\
        --update-index \\
        --base-url https://github.com/danielkoek/nRFMicro-Arduino-Core/releases/download/v1.2.0
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_BASE_NAME = "nRFMicro-Arduino-Core"

TOOLS_DEPENDENCIES = [
    {"packager": "Seeeduino", "name": "arm-none-eabi-gcc", "version": "9-2019q4"},
    {"packager": "Seeeduino", "name": "nrfjprog",           "version": "9.4.0"},
    {"packager": "Seeeduino", "name": "CMSIS",              "version": "5.7.0"},
]

BOARDS = [
    {"name": "nRFMicro"},
    {"name": "SuperMini nRF52840"},
    {"name": "nice!nano v2"},
]

# Directories / patterns excluded from the archive
IGNORE_PATTERNS = shutil.ignore_patterns(
    ".git", ".github",
    "__pycache__", "*.pyc", "*.pyo",
    "*.tar.bz2", "*.tar.gz", "*.zip",
)


def get_version_from_package_json():
    path = os.path.join(REPO_ROOT, "package.json")
    with open(path) as f:
        return json.load(f)["version"]


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def create_archive(version, output_dir):
    folder_name  = f"{ARCHIVE_BASE_NAME}-{version}"
    archive_name = f"{folder_name}.tar.bz2"
    archive_path = os.path.join(output_dir, archive_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, folder_name)
        shutil.copytree(REPO_ROOT, dest, ignore=IGNORE_PATTERNS)

        with tarfile.open(archive_path, "w:bz2") as tar:
            tar.add(dest, arcname=folder_name)

    return archive_path


def update_index(version, archive_name, checksum, size, base_url):
    index_path = os.path.join(REPO_ROOT, "package_nRFMicro_index.json")
    with open(index_path) as f:
        index = json.load(f)

    package   = index["packages"][0]
    platforms = package["platforms"]

    # Remove any existing entry for this exact version
    platforms = [p for p in platforms if p["version"] != version]

    platforms.append({
        "name":             "nRFMicro-like Boards",
        "architecture":     "nrf52",
        "version":          version,
        "category":         "Contributed",
        "help":             {"online": ""},
        "url":              f"{base_url.rstrip('/')}/{archive_name}",
        "archiveFileName":  archive_name,
        "checksum":         f"SHA-256:{checksum}",
        "size":             str(size),
        "boards":           BOARDS,
        "toolsDependencies": TOOLS_DEPENDENCIES,
    })

    # Keep entries sorted by semantic version
    platforms.sort(key=lambda p: [int(x) for x in p["version"].split(".")])
    package["platforms"] = platforms

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
        f.write("\n")

    print(f"Updated {index_path}")


def write_github_output(**kwargs):
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as f:
            for k, v in kwargs.items():
                f.write(f"{k}={v}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Package nRFMicro-Arduino-Core for the Arduino Board Manager"
    )
    parser.add_argument("--version",      help="Version string (default: from package.json)")
    parser.add_argument("--output-dir",   default=REPO_ROOT,
                        help="Directory to write the archive to (default: repo root)")
    parser.add_argument("--update-index", action="store_true",
                        help="Update package_nRFMicro_index.json")
    parser.add_argument("--base-url",
                        help="Base download URL, required with --update-index")
    args = parser.parse_args()

    if args.update_index and not args.base_url:
        print("error: --base-url is required when --update-index is set", file=sys.stderr)
        sys.exit(1)

    version    = args.version or get_version_from_package_json()
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Packaging version: {version}")

    archive_path = create_archive(version, output_dir)
    archive_name = os.path.basename(archive_path)
    checksum     = sha256_of_file(archive_path)
    size         = os.path.getsize(archive_path)

    print(f"Archive:  {archive_path}")
    print(f"SHA-256:  {checksum}")
    print(f"Size:     {size} bytes")
    print()
    print("package_nRFMicro_index.json snippet:")
    print(f'  "url":             "{args.base_url.rstrip("/") if args.base_url else "<BASE_URL>"}/{archive_name}",')
    print(f'  "archiveFileName": "{archive_name}",')
    print(f'  "checksum":        "SHA-256:{checksum}",')
    print(f'  "size":            "{size}",')

    if args.update_index:
        update_index(version, archive_name, checksum, size, args.base_url)

    write_github_output(
        version=version,
        archive_name=archive_name,
        archive_path=archive_path,
        checksum=checksum,
        size=str(size),
    )


if __name__ == "__main__":
    main()
