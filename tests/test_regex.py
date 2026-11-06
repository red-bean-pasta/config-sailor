import unittest

from config_sailor.patch.base.spec import PatchNode
from config_sailor.patch.base.schemas import SpecError
from config_sailor.patch import user_patcher, agent_patcher


class TestRegexDirectives(unittest.TestCase):

    def test_modify_remove_regex(self):
        spec = {
            "$modify": {
                "regex": True,
                "$remove": ["^temp_", ".*_bak$"]
            }
        }
        target = {
            "temp_1": "a",
            "temp_2": "b",
            "file_bak": "c",
            "permanent": "d"
        }
        node = PatchNode.model_validate(spec)
        result = node.patch(target)
        self.assertEqual(result, {"permanent": "d"})

    def test_modify_remove_literal_by_default(self):
        spec = {
            "$modify": {
                "$remove": ["temp_.*"]
            }
        }
        target = {
            "temp_1": "a",
            "temp_.*": "match_me"
        }
        node = PatchNode.model_validate(spec)
        result = node.patch(target)
        self.assertEqual(result, {"temp_1": "a"})

    def test_modify_if_not_regex(self):
        spec = {
            "$modify": {
                "$regex": True,
                "$if": [{"host": r".*\.example\.com$"}],
                "$assign": {"matched": True}
            }
        }
        node = PatchNode.model_validate(spec)
        target1 = {"host": "api.example.com"}
        self.assertEqual(node.patch(target1), {"host": "api.example.com", "matched": True})

        target2 = {"host": "api.other.com"}
        self.assertEqual(node.patch(target2), {"host": "api.other.com"})

    def test_modify_prune_regex(self):
        spec = {
            "$modify": {
                "regex": True,
                "$prune": [["settings", "^secret_"]]
            }
        }
        target = {
            "settings": {
                "secret_key": "123",
                "secret_token": "abc",
                "public_name": "app"
            }
        }
        node = PatchNode.model_validate(spec)
        result = node.patch(target)
        self.assertEqual(result, {"settings": {"public_name": "app"}})

    def test_select_rename_with_dollar_and_slash_groups(self):
        spec = {
            "$select": {
                "regex": True,
                "$by": ["id"],
                "$in": ["^srv_.*"],
                "$rename": {
                    "^srv_([a-z]+)_([0-9]+)$": "node-$1-$2"
                }
            }
        }
        targets = [
            {"id": "srv_east_101", "role": "web"},
            {"id": "db_main", "role": "db"}
        ]
        node = PatchNode.model_validate(spec)
        result = node.patch(targets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"id": "node-east-101", "role": "web"})

    def test_select_override_regex(self):
        spec = {
            "$select": {
                "$regex": True,
                "$by": ["region"],
                "$in": [".*"],
                "$override": {
                    "^us-.*": {"datacenter": "US"},
                    "^eu-.*": {"datacenter": "EU"}
                }
            }
        }
        targets = [
            {"region": "us-west-1"},
            {"region": "eu-central-1"}
        ]
        node = PatchNode.model_validate(spec)
        result = node.patch(targets)
        self.assertEqual(result, [
            {"region": "us-west-1", "datacenter": "US"},
            {"region": "eu-central-1", "datacenter": "EU"}
        ])

    def test_replace_regex(self):
        spec = {
            "$replace": {
                "regex": True,
                "$from": [r"user-(\d+)"],
                "$to": r"customer-$1"
            }
        }
        target = {
            "name": "Order for user-42",
            "note": "user-999 reported issue"
        }
        node = PatchNode.model_validate(spec)
        result = node.patch(target)
        self.assertEqual(result, {
            "name": "Order for customer-42",
            "note": "customer-999 reported issue"
        })

    def test_replace_literal_by_default(self):
        spec = {
            "$replace": {
                "$from": ["user-(.*)"],
                "$to": "customer"
            }
        }
        target = {
            "a": "user-(.*)",
            "b": "user-123"
        }
        node = PatchNode.model_validate(spec)
        result = node.patch(target)
        self.assertEqual(result, {
            "a": "customer",
            "b": "user-123"
        })

    def test_filter_where_regex(self):
        spec = {
            "$filter": {
                "regex": True,
                "$where": [{"code": "^ERR_[0-9]+"}]
            }
        }
        targets = [
            {"code": "ERR_404", "msg": "not found"},
            {"code": "INFO_100", "msg": "ok"},
            {"code": "ERR_500", "msg": "server error"}
        ]
        node = PatchNode.model_validate(spec)
        result = node.patch(targets)
        self.assertEqual(result, [
            {"code": "ERR_404", "msg": "not found"},
            {"code": "ERR_500", "msg": "server error"}
        ])

    def test_user_patcher_regex(self):
        spec = """
        {
            "$modify": {
                "regex": true,
                "$user": ["^dev-.*", "admin"],
                "$assign": {"access": "granted"}
            }
        }
        """
        config = {"access": "denied"}

        # Matching regex dev user
        res1 = user_patcher.patch("dev-alice", spec, config)
        self.assertEqual(res1, {"access": "granted"})

        # Matching literal admin
        res2 = user_patcher.patch("admin", spec, config)
        self.assertEqual(res2, {"access": "granted"})

        # Non-matching user
        res3 = user_patcher.patch("qa-bob", spec, config)
        self.assertEqual(res3, {"access": "denied"})

    def test_user_patcher_literal_by_default(self):
        spec = """
        {
            "$modify": {
                "$user": ["dev-.*"],
                "$assign": {"access": "granted"}
            }
        }
        """
        config = {"access": "denied"}
        # Should NOT match dev-alice when regex is false
        res = user_patcher.patch("dev-alice", spec, config)
        self.assertEqual(res, {"access": "denied"})
        # Should match literal dev-.*
        res_lit = user_patcher.patch("dev-.*", spec, config)
        self.assertEqual(res_lit, {"access": "granted"})

    def test_agent_patcher_regex(self):
        spec = """
        {
            "$modify": {
                "$regex": true,
                "$agent": ["curl/.*", "(?i)clash"],
                "$assign": {"optimized": true}
            }
        }
        """
        config = {"optimized": False}
        res1 = agent_patcher.patch("curl/8.18.0", spec, config)
        self.assertEqual(res1, {"optimized": True})

        res2 = agent_patcher.patch("ClashForWindows/0.20", spec, config)
        self.assertEqual(res2, {"optimized": True})

        res3 = agent_patcher.patch("Mozilla/5.0", spec, config)
        self.assertEqual(res3, {"optimized": False})

    def test_modify_to_array_with_regex(self):
        spec = {
            "$modify": {
                "regex": True,
                "$to": [{"name": "^srv_.*"}],
                "$assign": {"verified": True}
            }
        }
        targets = [
            {"name": "srv_1", "verified": False},
            {"name": "cli_1", "verified": False},
            {"name": "srv_2", "verified": False}
        ]
        node = PatchNode.model_validate(spec)
        result = node.patch(targets)
        self.assertEqual(result, [
            {"name": "srv_1", "verified": True},
            {"name": "cli_1", "verified": False},
            {"name": "srv_2", "verified": True}
        ])

    def test_user_boolean_with_regex(self):
        spec = """
        {
            "$modify": {
                "regex": true,
                "$user": true,
                "$assign": {"all_users": true}
            }
        }
        """
        config = {"all_users": False}
        res = user_patcher.patch("anyone", spec, config)
        self.assertEqual(res, {"all_users": True})

    def test_replace_recursive_regex(self):
        spec = {
            "$replace": {
                "regex": True,
                "$from": [r"http://localhost:([0-9]+)"],
                "$to": r"https://prod.com:$1",
                "$recursive": True
            }
        }
        target = {
            "endpoint": "http://localhost:8080/api",
            "nested": {
                "urls": [
                    "http://localhost:9000/metrics",
                    "http://localhost:9443/config"
                ]
            }
        }
        node = PatchNode.model_validate(spec)
        result = node.patch(target)
        self.assertEqual(result, {
            "endpoint": "https://prod.com:8080/api",
            "nested": {
                "urls": [
                    "https://prod.com:9000/metrics",
                    "https://prod.com:9443/config"
                ]
            }
        })

    def test_insert_where_regex(self):
        spec = {
            "$insert": {
                "regex": True,
                "$where": [{"id": "^step-[0-9]+$"}],
                "$value": [{"id": "step-inserted", "action": "audit"}]
            }
        }
        targets = [
            {"id": "step-1", "action": "start"},
            {"id": "step-2", "action": "process"},
            {"id": "final", "action": "end"}
        ]
        node = PatchNode.model_validate(spec)
        result = node.patch(targets)
        self.assertEqual(len(result), 4)
        # Should be inserted after the last match of where (step-2)
        self.assertEqual(result[2], {"id": "step-inserted", "action": "audit"})
        self.assertEqual(result[3], {"id": "final", "action": "end"})

    def test_invalid_user_regex_raises_spec_error(self):
        import pydantic
        bad_spec = """
        {
            "$modify": {
                "regex": true,
                "$user": ["[unclosed"],
                "$assign": {"access": "granted"}
            }
        }
        """
        with self.assertRaises(pydantic.ValidationError) as cm:
            user_patcher.patch("test", bad_spec, {})
        self.assertIn("Regex invalid", str(cm.exception))

    def test_invalid_agent_regex_raises_spec_error(self):
        import pydantic
        bad_spec = """
        {
            "$modify": {
                "regex": true,
                "$agent": ["(unclosed"],
                "$assign": {"access": "granted"}
            }
        }
        """
        with self.assertRaises(pydantic.ValidationError) as cm:
            agent_patcher.patch("test", bad_spec, {})
        self.assertIn("Regex invalid", str(cm.exception))

    def test_invalid_regex_raises_spec_error(self):
        import pydantic
        bad_spec = {
            "$modify": {
                "regex": True,
                "$remove": ["[unclosed"]
            }
        }
        with self.assertRaises(pydantic.ValidationError) as cm:
            PatchNode.model_validate(bad_spec)
        self.assertIn("Regex invalid", str(cm.exception))

    def test_modify_drop_with_regex(self):
        spec = {
            "$modify": {
                "regex": True,
                "$to": {"type": "selector"},
                "$drop": {
                    "items": [r".*_legacy$"]
                }
            }
        }
        data = [
            {
                "tag": "group_a",
                "type": "selector",
                "items": [
                    "node_1",
                    "node_2",
                    "node_3_legacy",
                    "node_4_legacy"
                ]
            },
            {
                "tag": "direct",
                "type": "direct"
            }
        ]
        node = PatchNode.model_validate(spec)
        result = node.patch(data)
        self.assertEqual(result[0]["items"], [
            "node_1",
            "node_2"
        ])

    def test_modify_drop_literal(self):
        spec = {
            "$modify": {
                "$to": {"type": "selector"},
                "$drop": {
                    "outbounds": ["drop_me"]
                }
            }
        }
        data = [
            {
                "type": "selector",
                "outbounds": ["keep_me", "drop_me"]
            }
        ]
        node = PatchNode.model_validate(spec)
        result = node.patch(data)
        self.assertEqual(result[0]["outbounds"], ["keep_me"])

    def test_modify_drop_invalid_regex_raises(self):
        import pydantic
        bad_spec = {
            "$modify": {
                "regex": True,
                "$drop": {
                    "outbounds": ["[unclosed"]
                }
            }
        }
        with self.assertRaises(pydantic.ValidationError) as cm:
            PatchNode.model_validate(bad_spec)
        self.assertIn("Regex invalid", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
