import tempfile
import unittest
import json
from pathlib import Path

from src.dataset_profiler import ProfileError, profile_directory, verify_profile


ROOT = Path(__file__).resolve().parents[1]


class DatasetProfilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "out")
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        (self.project / "dataset").mkdir(parents=True)
        (self.project / "out").mkdir()
        self.source = self.base / "incoming"
        self.source.mkdir()
        (self.source / "nested").mkdir()
        (self.source / "board.kicad_pcb").write_bytes(b"opaque native bytes\x00")
        (self.source / "nested" / "photo.bin").write_bytes(b"opaque evidence")
        self.output = self.project / "dataset" / "profile"

    def tearDown(self):
        self.temp.cleanup()

    def test_profiles_preserves_identity_and_never_claims_qualification(self):
        result = profile_directory(self.project, self.source, "client:sample:20261021:v1", self.output)
        checked = verify_profile(self.output)
        self.assertEqual(result["status"], "PROFILED")
        self.assertEqual(checked["status"], "PASS")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual((self.output / "raw/nested/photo.bin").read_bytes(), b"opaque evidence")
        profile = json.loads((self.output / "metadata/profile.json").read_text())
        recipe = json.loads((self.output / "metadata/registration_recipe.json").read_text())
        self.assertEqual(profile["intake"]["qualification"], "NOT_RUN")
        self.assertEqual(profile["intake"]["workbench_registration"], "NOT_RUN")
        self.assertEqual(recipe["dataset"]["intake_status"], "PROFILED_NOT_QUALIFIED")
        self.assertIn("NOT_ESTABLISHED", profile["limits"].__str__() + json.dumps(profile))
        with self.assertRaises(ProfileError):
            profile_directory(self.project, self.source, "client:sample:20261021:v1", self.output)

    def test_verifier_rejects_tampered_preserved_file(self):
        profile_directory(self.project, self.source, "client:sample:20261021:v1", self.output)
        (self.output / "raw/board.kicad_pcb").write_bytes(b"tampered")
        with self.assertRaisesRegex(ProfileError, "checksum"):
            verify_profile(self.output)

    def test_rejects_symlinks_and_output_outside_out(self):
        (self.source / "linked").symlink_to(self.source / "board.kicad_pcb")
        with self.assertRaisesRegex(ProfileError, "Symbolic links"):
            profile_directory(self.project, self.source, "client:sample:20261021:v1", self.output)
        (self.source / "linked").unlink()
        with self.assertRaisesRegex(ProfileError, "inside"):
            profile_directory(self.project, self.source, "client:sample:20261021:v1", self.base / "outside")


if __name__ == "__main__":
    unittest.main()
