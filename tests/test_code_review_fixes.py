import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

for mod in ["fastapi", "fastapi.security", "argon2", "argon2.exceptions", "anyio", "portalocker"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

from config_sailor.config_managing import user_manager
from config_sailor.config_managing.encryptor import encrypt
from config_sailor.patch.base import querier, selector
from config_sailor.patch.base.schemas import Modify, Query
from config_sailor.patch.base.spec import PatchNode
from config_sailor.utils import json_helper, regex_helper


class TestCodeReviewFixes(unittest.TestCase):

    def test_get_auth_rules_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Existing directory -> appends auth.json
            self.assertEqual(
                user_manager.get_auth_rules_path(tmp_path),
                tmp_path / "auth.json",
            )
            # Path ending with auth.json (file doesn't need to exist yet)
            auth_file = tmp_path / "auth.json"
            self.assertEqual(user_manager.get_auth_rules_path(auth_file), auth_file)

            # Invalid file name raises ValueError
            bad_file = tmp_path / "other.json"
            with self.assertRaises(ValueError):
                user_manager.get_auth_rules_path(bad_file)

            # Non-existent directory path without auth.json raises ValueError
            non_existent = tmp_path / "subdir"
            with self.assertRaises(ValueError):
                user_manager.get_auth_rules_path(non_existent)

    def test_plant_field_fails_loudly_on_primitive_intermediate_step(self):
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "sources"},
                    "$pluck": "value",
                    "$destination": {"$scope": "dest"},
                    "$plant": ["level1", "target"],
                    "$mode": "replace"
                }
            ]
        }
        # dest.level1 is an int, not an object
        doc = {
            "sources": [{"value": 42}],
            "dest": {"level1": 100}
        }
        node = PatchNode.model_validate(spec)
        with self.assertRaises(ValueError) as cm:
            node.patch(doc)
        self.assertIn("must resolve to an object", str(cm.exception))

    def test_encrypt_always_replaces_suffix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            json_file = tmp_path / "config.json"
            json_file.write_text("{}")
            encrypt(json_file, None)
            self.assertTrue((tmp_path / "config.enc").exists())

            txt_file = tmp_path / "config.yaml"
            txt_file.write_text("{}")
            encrypt(txt_file, None)
            self.assertTrue((tmp_path / "config.enc").exists())

    def test_selector_missing_key_does_not_match_none(self):
        # Directly test _compare_by_option: missing key must not match None
        self.assertFalse(selector._compare_by_option(["tag"], None, {}))
        # Existing key with explicit None value matches None
        self.assertTrue(selector._compare_by_option(["tag"], None, {"tag": None}))
        # Missing key must not match string option
        self.assertFalse(selector._compare_by_option(["tag"], "val", {}))

    def test_resolve_path_error_message_on_root(self):
        with self.assertRaises(ValueError) as cm:
            json_helper.resolve_path([1, 2, 3], ["step1"])
        self.assertIn("Target root must resolve to an object", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            json_helper.resolve_path({"step1": "not-an-obj"}, ["step1", "step2"])
        self.assertIn("Path step 'step1' must resolve to an object", str(cm.exception))

    def test_modify_normalize_to_mixed_array(self):
        m = Modify.model_validate({"$to": [1, 2, 3]})
        self.assertEqual(len(m.to), 1)
        self.assertEqual(m.to[0].index, [1, 2, 3])

        # Mixed array should not be wrapped as $index
        m2 = Modify.model_validate({"$to": [{"tag": "foo"}]})
        self.assertEqual(len(m2.to), 1)
        self.assertEqual(m2.to[0].where, [{"tag": "foo"}])

    def test_to_python_replacement_single_pass(self):
        self.assertEqual(regex_helper.to_python_replacement("$$"), "$")
        self.assertEqual(regex_helper.to_python_replacement("$$100"), "$100")
        self.assertEqual(regex_helper.to_python_replacement("$1"), r"\g<1>")
        self.assertEqual(regex_helper.to_python_replacement("${name}"), r"\g<name>")
        self.assertEqual(regex_helper.to_python_replacement("$<group>"), r"\g<group>")
        self.assertEqual(regex_helper.to_python_replacement("prefix_${name}_$1_suffix"), r"prefix_\g<name>_\g<1>_suffix")

    def test_validate_patterns_helper(self):
        # Valid patterns pass without exception
        regex_helper.validate_patterns(["^valid_.*$", "literal"], {"group_a": "value"})

        # Invalid pattern raises RegexError
        with self.assertRaises(regex_helper.RegexError):
            regex_helper.validate_patterns(["[unclosed"])

        # Non-string elements in collections are safely ignored
        regex_helper.validate_patterns([123, None, True])


if __name__ == "__main__":
    unittest.main()
