"""
Remove a profile whose owner can't sign in any more (a Cadet who left the program), for the device owner.

    python tools/remove_profile.py                       list the profiles
    python tools/remove_profile.py "Cadet Ruiz"          remove that profile (asks first)
    python tools/remove_profile.py "Cadet Ruiz" --data E:\\Cadet Foundry Data    (Cadet Foundry running from a USB drive)

Close Cadet Foundry first. Every file in that profile's folder is deleted -- private files and class records alike -- and
the profile leaves the sign-in list. Nothing is read or decrypted. Export the class report first if the school keeps
records (docs/PILOT_DATA_HANDLING.md). A Cadet who can sign in should use Me -> Delete profile instead.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    if "--data" in argv:
        i = argv.index("--data")
        os.environ["CADETFOUNDRY_DATA"] = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    sys.path.insert(0, str(ROOT))
    from cadetfoundry import profiles, store

    every = profiles.all_profiles()
    print(f"Data folder: {store.DATA}")
    if not argv:
        for p in every:
            print(f"  {p['name']}  ({p['kind']})")
        print(f"{len(every)} profile(s). To remove one: python tools/remove_profile.py \"<name>\"")
        return 0
    found = [p for p in every if p["name"].casefold() == argv[0].casefold()]
    if len(found) != 1:
        print("No profile has exactly that name." if not found else "More than one profile has that name.")
        return 1
    p = found[0]
    if input(f"Delete {p['name']} ({p['kind']}) and all of their files? Type DELETE to confirm: ").strip() != "DELETE":
        print("Nothing was deleted.")
        return 1
    profiles.delete(p["id"])
    print(f"{p['name']} was removed. (Deleted files can still be recovered from an unencrypted disk -- keep BitLocker on.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
