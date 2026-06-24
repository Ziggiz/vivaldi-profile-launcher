#!/usr/bin/env python3
"""Vivaldi profile launcher – core CLI.

Commands:
    list             – list profiles from Local State
    open             – start / focus a profile
    create           – clone the template profile -> new profile
    open-or-create   – open if it exists, otherwise create + open

See README.md for the full overview. Standard library only.

Exit codes:
    0  ok
    2  config/environment error
    3  profile not found
    4  profile already exists
    5  Vivaldi is running (when it must not be)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_NOT_FOUND = 3
EXIT_EXISTS = 4
EXIT_RUNNING = 5

DEFAULT_CONFIG = {
    "vivaldi_binary": "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
    "user_data_dir": "~/Library/Application Support/Vivaldi",
    "template_profile_name": "Default-template",
    "wipe_on_clone": [
        "History", "History-journal", "Visited Links",
        "Top Sites", "Top Sites-journal",
        "Current Session", "Current Tabs", "Last Session", "Last Tabs",
        "Sessions", "Cookies", "Cookies-journal",
        "Login Data", "Login Data-journal", "Web Data", "Web Data-journal",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg):
    """Log to stderr – stdout is kept clean for machine-readable output."""
    print(msg, file=sys.stderr)


def die(code, msg):
    log(msg)
    sys.exit(code)


def expand(path):
    return Path(os.path.expanduser(str(path)))


def load_config(explicit_path=None):
    """Read config.json (next to this script, or explicit_path).

    If the file is missing, the defaults are used. Paths are not expanded here –
    that happens at use time so the JSON stays close to the original.
    """
    cfg = dict(DEFAULT_CONFIG)
    if explicit_path:
        path = Path(explicit_path)
    else:
        path = Path(__file__).resolve().parent / "config.json"
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            die(EXIT_CONFIG, f"Could not read {path}: {exc}")
        cfg.update(user)
    return cfg


def user_data_dir(cfg):
    return expand(cfg["user_data_dir"])


def local_state_path(cfg):
    return user_data_dir(cfg) / "Local State"


def read_local_state(cfg):
    path = local_state_path(cfg)
    if not path.exists():
        die(EXIT_CONFIG,
            f"Could not find Local State: {path}\n"
            f"Is user_data_dir correct in config.json?")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        die(EXIT_CONFIG, f"Could not parse Local State: {exc}")


def info_cache(state):
    return state.get("profile", {}).get("info_cache", {})


def list_profiles(cfg):
    """-> list of {"name", "dir"}, sorted alphabetically by name."""
    state = read_local_state(cfg)
    profiles = [
        {"name": info.get("name", folder), "dir": folder}
        for folder, info in info_cache(state).items()
    ]
    profiles.sort(key=lambda p: p["name"].lower())
    return profiles


def find_profile(cfg, name):
    """Look up a profile by display name (case-insensitive). -> dict or None."""
    needle = name.strip().lower()
    for prof in list_profiles(cfg):
        if prof["name"].lower() == needle:
            return prof
    return None


def vivaldi_is_running():
    """True if the main Vivaldi process is running."""
    try:
        res = subprocess.run(
            ["pgrep", "-x", "Vivaldi"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return res.returncode == 0
    except OSError:
        return False


def launch_profile(cfg, folder):
    """Start / focus the profile in directory `folder`.

    Calling the binary directly with --profile-directory lets Chromium's process
    singleton focus an already-open window instead of opening a duplicate.
    """
    binary = expand(cfg["vivaldi_binary"])
    if not binary.exists():
        die(EXIT_CONFIG,
            f"Could not find the Vivaldi binary: {binary}\n"
            f"Check vivaldi_binary in config.json.")
    log(f"Starting profile: {folder}")
    subprocess.Popen(
        [str(binary), f"--profile-directory={folder}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Bring Vivaldi to the front of the window order.
    subprocess.run(
        ["osascript", "-e", 'tell application "Vivaldi" to activate'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def next_profile_dir(udd, state):
    """Lowest free "Profile N" – not an existing folder and not in info_cache."""
    existing = set(info_cache(state).keys())
    n = 1
    while True:
        candidate = f"Profile {n}"
        if candidate not in existing and not (udd / candidate).exists():
            return candidate
        n += 1


def quit_vivaldi(timeout=15):
    """Ask Vivaldi to quit gracefully and wait until the process is gone."""
    log("Quitting Vivaldi …")
    subprocess.run(
        ["osascript", "-e", 'tell application "Vivaldi" to quit'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not vivaldi_is_running():
            return True
        time.sleep(0.5)
    return not vivaldi_is_running()


def atomic_write_json(path, data):
    """Write JSON atomically (temp file in the same dir -> os.replace)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_list(cfg, args):
    profiles = list_profiles(cfg)
    if args.json:
        json.dump(profiles, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for prof in profiles:
            print(prof["name"])
    return EXIT_OK


def cmd_open(cfg, args):
    prof = find_profile(cfg, args.name)
    if not prof:
        log(f"NOT_FOUND: {args.name}")
        return EXIT_NOT_FOUND
    launch_profile(cfg, prof["dir"])
    return EXIT_OK


def cmd_create(cfg, args):
    name = args.name.strip()
    if not name:
        die(EXIT_CONFIG, "Empty profile name.")

    udd = user_data_dir(cfg)
    if not udd.exists():
        die(EXIT_CONFIG, f"Could not find user_data_dir: {udd}")

    # Collision?
    if find_profile(cfg, name):
        log(f"EXISTS: the profile \"{name}\" already exists.")
        return EXIT_EXISTS

    state = read_local_state(cfg)

    # Find the template folder via its display name.
    template_name = cfg["template_profile_name"]
    template = find_profile(cfg, template_name)
    if not template:
        die(EXIT_CONFIG,
            f"Could not find the template profile \"{template_name}\".\n"
            f"Create a profile with this name in Vivaldi (with the desired "
            f"shortcuts/bookmarks), or change template_profile_name in config.json.")
    template_dir = udd / template["dir"]
    if not template_dir.exists():
        die(EXIT_CONFIG, f"Template folder does not exist on disk: {template_dir}")

    new_dir = next_profile_dir(udd, state)
    dest = udd / new_dir
    wipe = cfg["wipe_on_clone"]

    log(f"Template: {template['name']!r} ({template['dir']})")
    log(f"New profile: {name!r} -> {new_dir}")

    if args.dry_run:
        log("[dry-run] Would do the following:")
        log(f"  1. copy {template_dir} -> {dest}")
        log(f"  2. delete from the clone: {', '.join(wipe)}")
        log(f"  3. add info_cache['{new_dir}'] with name={name!r}")
        log(f"  4. append '{new_dir}' to profiles_order")
        log(f"  5. set profile.name in {new_dir}/Preferences")
        if args.open:
            log(f"  6. start the profile {new_dir}")
        log("[dry-run] Nothing was written.")
        return EXIT_OK

    # Writing requires Vivaldi to be closed, since Vivaldi rewrites Local State
    # on exit and would otherwise overwrite our changes.
    if vivaldi_is_running():
        if not args.yes:
            log("Vivaldi is running. It must quit before we can write Local State safely.")
            try:
                answer = input("Quit Vivaldi now? [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer not in ("y", "yes"):
                log("Aborted – Vivaldi is still running.")
                return EXIT_RUNNING
        if not quit_vivaldi():
            die(EXIT_RUNNING, "Could not quit Vivaldi. Aborting.")

    # 1. Copy the template folder.
    log(f"Copying {template_dir} -> {dest}")
    shutil.copytree(template_dir, dest, symlinks=True)

    # 2. Wipe ephemeral files.
    for entry in wipe:
        target = dest / entry
        try:
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
                log(f"  deleted folder: {entry}")
            elif target.exists() or target.is_symlink():
                target.unlink()
                log(f"  deleted file: {entry}")
        except OSError as exc:
            log(f"  warning: could not delete {entry}: {exc}")

    # 3. Back up Local State before writing.
    ls_path = local_state_path(cfg)
    backup = ls_path.with_name("Local State.bak")
    shutil.copy2(ls_path, backup)
    log(f"Backup: {backup}")

    # 4. Register in info_cache + profiles_order.
    profile_section = state.setdefault("profile", {})
    cache = profile_section.setdefault("info_cache", {})
    cache[new_dir] = {
        "name": name,
        "is_using_default_name": False,
        "is_using_default_avatar": True,
        "avatar_icon": "chrome://theme/IDR_PROFILE_AVATAR_26",
        "active_time": 0,
    }
    order = profile_section.setdefault("profiles_order", [])
    if new_dir not in order:
        order.append(new_dir)

    atomic_write_json(ls_path, state)
    log("Local State updated.")

    # 5. Set profile.name in the profile's own Preferences.
    prefs_path = dest / "Preferences"
    if prefs_path.exists():
        try:
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            prefs.setdefault("profile", {})["name"] = name
            atomic_write_json(prefs_path, prefs)
            log("Preferences.profile.name set.")
        except (OSError, ValueError) as exc:
            log(f"Warning: could not update Preferences: {exc}")

    log(f"Profile \"{name}\" created as {new_dir}.")

    # 6. Start.
    if args.open:
        launch_profile(cfg, new_dir)

    return EXIT_OK


def cmd_open_or_create(cfg, args):
    if find_profile(cfg, args.name):
        return cmd_open(cfg, args)
    log(f"The profile \"{args.name}\" does not exist – creating a new one.")
    return cmd_create(cfg, args)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="vivaldi_profiles.py",
        description="Search, open and create Vivaldi profiles on macOS.",
    )
    p.add_argument("--config", help="Path to config.json (overrides the default).")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("list", help="List profiles.")
    pl.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    pl.set_defaults(func=cmd_list)

    po = sub.add_parser("open", help="Start / focus a profile.")
    po.add_argument("name", help="Display name of the profile.")
    po.set_defaults(func=cmd_open)

    pc = sub.add_parser("create", help="Clone the template profile into a new profile.")
    pc.add_argument("name", help="Display name of the new profile.")
    pc.add_argument("--open", dest="open", action="store_true", default=True,
                    help="Start the profile after creation (default).")
    pc.add_argument("--no-open", dest="open", action="store_false",
                    help="Do not start the profile after creation.")
    pc.add_argument("--dry-run", action="store_true",
                    help="Show what would happen without writing anything.")
    pc.add_argument("--yes", "-y", action="store_true",
                    help="Do not prompt before quitting Vivaldi.")
    pc.set_defaults(func=cmd_create)

    poc = sub.add_parser("open-or-create",
                         help="Open if the profile exists, otherwise create + open.")
    poc.add_argument("name", help="Display name of the profile.")
    poc.add_argument("--open", dest="open", action="store_true", default=True,
                     help=argparse.SUPPRESS)
    poc.add_argument("--no-open", dest="open", action="store_false",
                     help=argparse.SUPPRESS)
    poc.add_argument("--dry-run", action="store_true",
                     help="Use dry-run for any create that happens.")
    poc.add_argument("--yes", "-y", action="store_true",
                     help="Do not prompt before quitting Vivaldi.")
    poc.set_defaults(func=cmd_open_or_create)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    return args.func(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
