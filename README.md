# Automated Desktop and Downloads Organizer

This Python project automatically organizes files in your Desktop and Downloads folders into category-based subfolders.

## Features
- Creates folders automatically such as Documents, Images, Videos, Audio, Archives, Code, Executables, Design, and Other
- Uses the Gemini API to suggest a folder name for unknown files when possible
- Works on Windows and can be launched from a batch file

## Run it
From this folder, run:

```bash
python organizer.py
```

To preview changes without moving files:

```bash
python organizer.py --dry-run
```

To use a custom folder location:

```bash
python organizer.py --desktop "C:/Users/YourName/Desktop" --downloads "C:/Users/YourName/Downloads"
```

## Windows launcher
Double-click the batch file:

```text
organize_windows.bat
```
