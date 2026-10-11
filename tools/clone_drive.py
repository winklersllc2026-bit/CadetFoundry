"""
Make a clean Vanguard flash drive for Cadets from a copy of the instructor's drive -- no profiles, no class records.

The instructor's drive has a folder "Make more flash drives". Its instructions say: copy the drive's contents (all but
VanguardData) to this computer, unplug that drive, plug in a blank one, and double-click "Make a Cadet drive.bat"
in the copy. That runs this script with the drive's own Python:

    python Vanguard/tools/clone_drive.py <the copied folder>            asks which drive to fill
    python Vanguard/tools/clone_drive.py <the copied folder> E:\\        straight to E:

Copies the app (Vanguard\\, with its Python, videos and offline AI if present) and the start files. Never copies
VanguardData: the new drive gets an empty one, so every Cadet starts fresh. Standard library only.
"""
from __future__ import annotations

import os
import shutil
import string
import sys
from pathlib import Path

SKIP = {"VanguardData", "System Volume Information", "$RECYCLE.BIN"}


def removable_drives() -> list[str]:
    """Windows: the letters of plugged-in removable drives (flash drives), e.g. ["E:\\"]."""
    if os.name != "nt":
        return []
    import ctypes
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    out = []
    for i, letter in enumerate(string.ascii_uppercase):
        if mask >> i & 1:
            root = f"{letter}:\\"
            if ctypes.windll.kernel32.GetDriveTypeW(root) == 2:      # DRIVE_REMOVABLE
                out.append(root)
    return out


def has_people(drive: Path) -> bool:
    """The drive already holds Vanguard profiles (someone's data) -- never overwrite those."""
    profiles = drive / "VanguardData" / "profiles"
    return profiles.is_dir() and any(profiles.iterdir())


def items_to_copy(src: Path) -> list[Path]:
    return [p for p in sorted(src.iterdir()) if p.name not in SKIP]


def copy_all(src: Path, dest: Path, say=print) -> int:
    """Copy everything but VanguardData from src to dest. Returns the bytes copied."""
    files = [f for item in items_to_copy(src) for f in ([item] if item.is_file() else item.rglob("*")) if f.is_file()]
    total = sum(f.stat().st_size for f in files)
    done, last = 0, -1
    for f in files:
        target = dest / f.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        done += f.stat().st_size
        pct = int(100 * done / total) if total else 100
        if pct // 5 != last:
            last = pct // 5
            say(f"  {pct:3d}%  ({done / 2**30:.2f} of {total / 2**30:.2f} GB)")
    (dest / "VanguardData").mkdir(exist_ok=True)                 # empty: every Cadet starts fresh
    return done


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    src = Path(argv[0]).resolve()
    if not (src / "Vanguard" / "run.py").exists():
        print(f"This doesn't look like a copy of a Vanguard drive (no Vanguard\\run.py in {src}).")
        return 1
    print("\n  MAKE A CADET FLASH DRIVE")
    print("  Copies Vanguard to a blank flash drive. No profiles or class records are copied.\n")
    if len(argv) > 1:
        target = argv[1]
    else:
        here = src.drive.upper() + "\\" if src.drive else ""
        drives = [d for d in removable_drives() if d != here]
        if not drives:
            print("  No flash drive found. Plug in the blank flash drive, wait a few seconds, and run this again.")
            return 1
        if len(drives) == 1:
            target = drives[0]
            answer = input(f"  Put Vanguard on the flash drive {target} ? Type Y and press Enter: ").strip().lower()
            if answer not in ("y", "yes"):
                print("  Nothing was changed.")
                return 1
        else:
            print("  Flash drives plugged in: " + ", ".join(drives))
            target = input("  Type the letter of the BLANK drive (for example E) and press Enter: ").strip().rstrip(":\\")
            target = f"{target.upper()}:\\" if len(target) == 1 else target
            if target not in drives:
                print(f"  {target} isn't one of the flash drives listed. Nothing was changed.")
                return 1
    dest = Path(target)
    if not dest.exists():
        print(f"  {dest} isn't there. Plug the flash drive in and run this again.")
        return 1
    if dest.resolve() == src or src.is_relative_to(dest.resolve()):
        print("  That's the drive you're copying from. Choose the blank flash drive.")
        return 1
    if has_people(dest):
        print(f"  {dest} already has Vanguard profiles on it. To protect them, nothing was changed.")
        print("  Use a blank flash drive (or move that drive's VanguardData folder somewhere safe first).")
        return 1
    need = sum(f.stat().st_size for item in items_to_copy(src)
               for f in ([item] if item.is_file() else item.rglob("*")) if f.is_file())
    free = shutil.disk_usage(dest).free
    if free < need:
        print(f"  {dest} has {free / 2**30:.1f} GB free; Vanguard needs {need / 2**30:.1f} GB. Use a bigger flash drive.")
        return 1
    print(f"\n  Copying to {dest} … (this can take several minutes; leave the drive plugged in)")
    copy_all(src, dest)
    print(f"\n  Done. The flash drive {dest} is ready for a Cadet.")
    print("  Unplug it (Eject first if Windows offers it). Plug in the next blank drive and run this again for another.")
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv[1:])
    except KeyboardInterrupt:
        code = 1
    sys.exit(code)
