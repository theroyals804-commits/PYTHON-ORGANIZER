from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

DEFAULT_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyATUTw3T-IFI4ACv8psQKex1eRj5T-6KLg")
DEFAULT_MODEL = "gemini-2.0-flash"

CATEGORY_MAP: Dict[str, set[str]] = {
    "Documents": {
        ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".csv", ".tsv",
        ".xlsx", ".xls", ".ppt", ".pptx", ".odp", ".ods", ".json", ".xml",
        ".yaml", ".yml", ".sql", ".log", ".epub", ".mobi", ".azw"
    },
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tif", ".tiff", ".heic", ".heif"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"},
    "Audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Code": {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".cc", ".h", ".hpp", ".cs", ".php", ".rb", ".go", ".rs", ".swift", ".kt", ".html", ".css", ".scss", ".sass", ".toml", ".ini", ".cfg", ".conf", ".sh", ".bash", ".ps1", ".bat", ".cmd", ".sql", ".ipynb"},
    "Executables": {".exe", ".msi", ".apk", ".app", ".appimage", ".deb", ".rpm", ".dll", ".so", ".dylib"},
    "Design": {".psd", ".ai", ".fig", ".xd", ".sketch"},
    "Spreadsheets": {".xlsx", ".xls", ".csv", ".tsv", ".ods"},
    "Presentations": {".ppt", ".pptx", ".key", ".odp"},
}

SKIP_NAMES = {".DS_Store", "desktop.ini", "Thumbs.db"}


def infer_category(file_path: Path, api_key: str) -> str:
    ext = file_path.suffix.lower()
    for category, exts in CATEGORY_MAP.items():
        if ext in exts:
            return category

    mime_type, _ = mimetypes.guess_type(file_path.name)
    if mime_type:
        if mime_type.startswith("image/"):
            return "Images"
        if mime_type.startswith("video/"):
            return "Videos"
        if mime_type.startswith("audio/"):
            return "Audio"
        if "zip" in mime_type or "archive" in mime_type:
            return "Archives"

    if api_key:
        try:
            suggestion = ask_gemini(file_path.name, api_key)
            if suggestion:
                return sanitize_category(suggestion)
        except Exception:
            pass

    return "Other"


def sanitize_category(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", label.strip())
    cleaned = cleaned.replace("folder", "").strip()
    cleaned = cleaned.replace("Folder", "").strip()
    if not cleaned:
        return "Other"
    if len(cleaned) > 30:
        cleaned = cleaned[:30].rstrip()
    return cleaned or "Other"


def ask_gemini(file_name: str, api_key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Classify this filename into one short folder name. "
                            "Return only one short phrase and nothing else. "
                            f"File: {file_name}"
                        )
                    }
                ]
            }
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read().decode("utf-8"))

    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    if not parts:
        return ""
    return parts[0].get("text", "").strip()


def organize_folder(folder_path: Path, api_key: str, dry_run: bool = False, verbose: bool = False) -> Tuple[int, int]:
    folder_path = folder_path.expanduser().resolve()
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    created_folders = 0
    moved_files = 0

    for item in sorted(folder_path.iterdir()):
        if item.name in SKIP_NAMES:
            continue
        if item.is_dir():
            continue
        if item.is_file():
            category = infer_category(item, api_key)
            destination_dir = folder_path / category
            if not destination_dir.exists():
                if dry_run:
                    print(f"[dry-run] Would create: {destination_dir}")
                else:
                    destination_dir.mkdir(parents=True, exist_ok=True)
                created_folders += 1

            destination_path = destination_dir / item.name
            if destination_path.exists():
                stem = item.stem
                suffix = item.suffix
                counter = 1
                while destination_path.exists():
                    destination_path = destination_dir / f"{stem} ({counter}){suffix}"
                    counter += 1

            if dry_run:
                print(f"[dry-run] Would move {item.name} -> {destination_path}")
            else:
                try:
                    shutil.move(str(item), str(destination_path))
                    moved_files += 1
                except (PermissionError, OSError) as exc:
                    print(f"Skipped {item.name}: {exc}")
                    continue

            if verbose:
                print(f"{item.name} -> {category}")

    return created_folders, moved_files


def normalize_drive_letter(raw_value: str) -> str | None:
    value = raw_value.strip().rstrip("\\/")
    if not value:
        return None
    if value[0].isalpha() and len(value) == 1:
        return value.upper()
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return value[0].upper()
    return None


def build_drive_path(drive_letter: str) -> Path:
    return Path(f"{drive_letter}:\\")


def parse_drives(args: Sequence[str]) -> List[str]:
    drives: List[str] = []
    for index, arg in enumerate(args):
        if arg == "--drives":
            for value in args[index + 1 :]:
                if value.startswith("--"):
                    break
                for part in value.split(","):
                    normalized = normalize_drive_letter(part)
                    if normalized:
                        drives.append(normalized)
            break
    return drives


def parse_args() -> Tuple[Path | None, Path | None, List[str], bool, bool]:
    args = sys.argv[1:]
    desktop_path = None
    downloads_path = None
    dry_run = False
    verbose = False
    drive_letters = parse_drives(args)

    for index, arg in enumerate(args):
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--verbose":
            verbose = True
        elif arg == "--desktop" and index + 1 < len(args):
            desktop_path = Path(args[index + 1]).expanduser()
        elif arg == "--downloads" and index + 1 < len(args):
            downloads_path = Path(args[index + 1]).expanduser()
        elif arg in {"--help", "-h"}:
            print("Usage: python organizer.py [--desktop PATH] [--downloads PATH] [--drives E F] [--dry-run] [--verbose]")
            raise SystemExit(0)

    return desktop_path, downloads_path, drive_letters, dry_run, verbose


def main() -> None:
    desktop_path, downloads_path, drive_letters, dry_run, verbose = parse_args()
    api_key = os.getenv("GEMINI_API_KEY", DEFAULT_GEMINI_API_KEY)

    home = Path.home()
    desktop_root = desktop_path or (home / "Desktop")
    downloads_root = downloads_path or (home / "Downloads")

    targets = [(desktop_root, "Desktop"), (downloads_root, "Downloads")]
    total_created = 0
    total_moved = 0

    for target_path, label in targets:
        if not target_path.exists():
            print(f"Skipping {label}: {target_path} does not exist.")
            continue

        print(f"Organizing {label}: {target_path}")
        created, moved = organize_folder(target_path, api_key, dry_run=dry_run, verbose=verbose)
        total_created += created
        total_moved += moved
        print(f"Summary for {label}: created {created} folders, moved {moved} files")

    for drive_letter in drive_letters:
        drive_path = build_drive_path(drive_letter)
        if not drive_path.exists():
            print(f"Skipping Drive {drive_letter}: {drive_path} does not exist.")
            continue
        print(f"Organizing Drive {drive_letter}: {drive_path}")
        created, moved = organize_folder(drive_path, api_key, dry_run=dry_run, verbose=verbose)
        total_created += created
        total_moved += moved
        print(f"Summary for Drive {drive_letter}: created {created} folders, moved {moved} files")

    print(f"Finished. Created {total_created} folders and moved {total_moved} files.")


if __name__ == "__main__":
    main()
