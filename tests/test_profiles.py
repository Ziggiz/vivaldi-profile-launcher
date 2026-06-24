#!/usr/bin/env python3
"""Unit tests for vivaldi_profiles.py against a fake user-data dir.

Run: python3 -m unittest discover -s tests
  or: python3 tests/test_profiles.py
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Make the core importable no matter where the test is run from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vivaldi_profiles as vp  # noqa: E402


def make_local_state():
    return {
        "browser": {"some_existing_key": True},
        "profile": {
            "info_cache": {
                "Default": {"name": "Private", "is_using_default_name": False},
                "Profile 1": {"name": "Client – Acme", "is_using_default_name": False},
                "Profile 2": {"name": "Default-template", "is_using_default_name": False},
            },
            "profiles_order": ["Default", "Profile 1", "Profile 2"],
            "last_used": "Profile 1",
        },
    }


class Args:
    """Small stand-in for an argparse namespace."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


class ProfilesTest(unittest.TestCase):
    def setUp(self):
        # Isolate the tests from the real Vivaldi: never check/quit the actual
        # process. (Without this, the create path could close the user's browser.)
        self._orig_running = vp.vivaldi_is_running
        self._orig_quit = vp.quit_vivaldi
        vp.vivaldi_is_running = lambda: False
        vp.quit_vivaldi = lambda timeout=15: True

        self.tmp = Path(tempfile.mkdtemp(prefix="vivaldi-test-"))
        self.udd = self.tmp / "Vivaldi"
        self.udd.mkdir()

        # Local State
        (self.udd / "Local State").write_text(
            json.dumps(make_local_state(), ensure_ascii=False),
            encoding="utf-8",
        )

        # Template folder (Profile 2) with a mix of files to keep/delete.
        template = self.udd / "Profile 2"
        template.mkdir()
        (template / "Bookmarks").write_text("{}", encoding="utf-8")
        (template / "Preferences").write_text(
            json.dumps({"profile": {"name": "Default-template"}}),
            encoding="utf-8",
        )
        (template / "History").write_text("data", encoding="utf-8")
        (template / "Cookies").write_text("data", encoding="utf-8")
        sessions = template / "Sessions"
        sessions.mkdir()
        (sessions / "session_123").write_text("data", encoding="utf-8")

        # A couple of other profile folders.
        (self.udd / "Default").mkdir()
        (self.udd / "Profile 1").mkdir()

        self.cfg = {
            "vivaldi_binary": "/nonexistent/Vivaldi",
            "user_data_dir": str(self.udd),
            "template_profile_name": "Default-template",
            "wipe_on_clone": list(vp.DEFAULT_CONFIG["wipe_on_clone"]),
        }

    def tearDown(self):
        vp.vivaldi_is_running = self._orig_running
        vp.quit_vivaldi = self._orig_quit
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- list -------------------------------------------------------------
    def test_list_returns_names_and_dirs(self):
        profiles = vp.list_profiles(self.cfg)
        by_name = {p["name"]: p["dir"] for p in profiles}
        self.assertEqual(by_name["Private"], "Default")
        self.assertEqual(by_name["Client – Acme"], "Profile 1")
        self.assertEqual(by_name["Default-template"], "Profile 2")
        # Sorted alphabetically (case-insensitive).
        names = [p["name"] for p in profiles]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_find_profile_case_insensitive(self):
        self.assertEqual(vp.find_profile(self.cfg, "private")["dir"], "Default")
        self.assertIsNone(vp.find_profile(self.cfg, "does not exist"))

    # --- create -----------------------------------------------------------
    def test_create_clones_template_and_wipes(self):
        args = Args(name="New Client", open=False, dry_run=False, yes=True)
        rc = vp.cmd_create(self.cfg, args)
        self.assertEqual(rc, vp.EXIT_OK)

        # Next free folder is Profile 3 (1 and 2 exist, Default exists).
        new_dir = self.udd / "Profile 3"
        self.assertTrue(new_dir.is_dir())

        # Kept files.
        self.assertTrue((new_dir / "Bookmarks").exists())
        self.assertTrue((new_dir / "Preferences").exists())

        # Deleted volatile files.
        self.assertFalse((new_dir / "History").exists())
        self.assertFalse((new_dir / "Cookies").exists())
        self.assertFalse((new_dir / "Sessions").exists())

        # Local State updated correctly.
        state = json.loads((self.udd / "Local State").read_text(encoding="utf-8"))
        cache = state["profile"]["info_cache"]
        self.assertIn("Profile 3", cache)
        self.assertEqual(cache["Profile 3"]["name"], "New Client")
        self.assertFalse(cache["Profile 3"]["is_using_default_name"])
        self.assertIn("Profile 3", state["profile"]["profiles_order"])
        # Existing structure untouched.
        self.assertTrue(state["browser"]["some_existing_key"])

        # profile.name set in the new Preferences.
        prefs = json.loads((new_dir / "Preferences").read_text(encoding="utf-8"))
        self.assertEqual(prefs["profile"]["name"], "New Client")

    def test_create_makes_backup_and_keeps_valid_json(self):
        args = Args(name="New Client", open=False, dry_run=False, yes=True)
        vp.cmd_create(self.cfg, args)
        backup = self.udd / "Local State.bak"
        self.assertTrue(backup.exists())
        # The backup is still valid JSON and matches the original structure.
        data = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"]["last_used"], "Profile 1")
        self.assertNotIn("Profile 3", data["profile"]["info_cache"])

    def test_create_name_collision_returns_4(self):
        args = Args(name="Private", open=False, dry_run=False, yes=True)
        rc = vp.cmd_create(self.cfg, args)
        self.assertEqual(rc, vp.EXIT_EXISTS)
        # Nothing new created.
        self.assertFalse((self.udd / "Profile 3").exists())

    def test_create_dry_run_writes_nothing(self):
        args = Args(name="New Client", open=False, dry_run=True, yes=True)
        rc = vp.cmd_create(self.cfg, args)
        self.assertEqual(rc, vp.EXIT_OK)
        self.assertFalse((self.udd / "Profile 3").exists())
        self.assertFalse((self.udd / "Local State.bak").exists())
        state = json.loads((self.udd / "Local State").read_text(encoding="utf-8"))
        self.assertNotIn("Profile 3", state["profile"]["info_cache"])

    def test_next_profile_dir_skips_existing(self):
        state = vp.read_local_state(self.cfg)
        self.assertEqual(vp.next_profile_dir(self.udd, state), "Profile 3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
