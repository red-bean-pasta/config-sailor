import unittest

from config_sailor.patch.base.spec import PatchNode
from config_sailor.patch.base.schemas import SpecError
from config_sailor.patch import user_patcher, agent_patcher, version_patcher


class TestQueryDirective(unittest.TestCase):

    def test_basic_query_replace(self):
        doc = {
            "items": [
                {"name": "apple", "price": 10},
                {"name": "banana", "price": 20},
            ],
            "summary": {
                "prices": []
            }
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": ["items"]},
                    "$pluck": "price",
                    "$destination": {"$scope": ["summary"]},
                    "$plant": "prices",
                    "$mode": "replace"
                }
            ]
        }
        node = PatchNode.model_validate(spec)
        result = node.patch(doc)
        self.assertEqual(result["summary"]["prices"], [10, 20])

    def test_alias_take_and_give_rejected(self):
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "items"},
                    "$take": "price",
                    "$destination": {"$scope": "summary"},
                    "$give": "prices",
                    "$mode": "replace"
                }
            ]
        }
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            PatchNode.model_validate(spec)

    def test_append_and_prepend_on_array(self):
        doc = {
            "nodes": [
                {"tag": "node-1"},
                {"tag": "node-2"}
            ],
            "selector": {
                "outbounds": ["direct"]
            }
        }
        spec_append = {
            "$query": [
                {
                    "$source": {"$scope": ["nodes"]},
                    "$pluck": "tag",
                    "$destination": {"$scope": ["selector"]},
                    "$plant": "outbounds",
                    "$mode": "append"
                }
            ]
        }
        res_append = PatchNode.model_validate(spec_append).patch(doc)
        self.assertEqual(res_append["selector"]["outbounds"], ["direct", "node-1", "node-2"])

        doc2 = {
            "nodes": [
                {"tag": "node-1"},
                {"tag": "node-2"}
            ],
            "selector": {
                "outbounds": ["direct"]
            }
        }
        spec_prepend = {
            "$query": [
                {
                    "$source": {"$scope": ["nodes"]},
                    "$pluck": "tag",
                    "$destination": {"$scope": ["selector"]},
                    "$plant": "outbounds",
                    "$mode": "prepend"
                }
            ]
        }
        res_prepend = PatchNode.model_validate(spec_prepend).patch(doc2)
        self.assertEqual(res_prepend["selector"]["outbounds"], ["node-1", "node-2", "direct"])

    def test_append_on_absent_and_scalar_fields(self):
        doc = {
            "nodes": [{"tag": "node-1"}],
            "target_absent": {},
            "target_scalar": {"outbounds": "direct"}
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "target_absent"},
                    "$plant": "outbounds",
                    "$mode": "append"
                },
                {
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "target_scalar"},
                    "$plant": "outbounds",
                    "$mode": "append"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["target_absent"]["outbounds"], ["node-1"])
        self.assertEqual(res["target_scalar"]["outbounds"], ["direct", "node-1"])

    def test_nullable_default_true(self):
        doc = {
            "nodes": [
                {"name": "has_tag", "tag": "v1"},
                {"name": "null_tag", "tag": None},
                {"name": "missing_tag"}
            ],
            "target": {"existing_null": None}
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "target"},
                    "$plant": "existing_null",
                    "$mode": "append",
                    "$nullable": True
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        # destination had existing null -> [None], plus collected ["v1", None, None]
        self.assertEqual(res["target"]["existing_null"], [None, "v1", None, None])

    def test_nullable_false(self):
        doc = {
            "nodes": [
                {"name": "has_tag", "tag": "v1"},
                {"name": "null_tag", "tag": None},
                {"name": "missing_tag"}
            ],
            "target": {"existing_null": None}
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "target"},
                    "$plant": "existing_null",
                    "$mode": "append",
                    "$nullable": False
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        # existing null normalized to [], collected drops missing/None -> ["v1"]
        self.assertEqual(res["target"]["existing_null"], ["v1"])

    def test_flatten_false_vs_true(self):
        doc = {
            "shops": [
                {"name": "ShopA", "tags": ["t1", "t2"]},
                {"name": "ShopB", "tags": ["t3"]}
            ],
            "target": {}
        }
        spec_unflattened = {
            "$query": [
                {
                    "$source": {"$scope": "shops"},
                    "$pluck": "tags",
                    "$destination": {"$scope": "target"},
                    "$plant": "tags",
                    "$flatten": False
                }
            ]
        }
        res1 = PatchNode.model_validate(spec_unflattened).patch(doc)
        self.assertEqual(res1["target"]["tags"], [["t1", "t2"], ["t3"]])

        doc2 = {
            "shops": [
                {"name": "ShopA", "tags": ["t1", "t2"]},
                {"name": "ShopB", "tags": ["t3"]}
            ],
            "target": {}
        }
        spec_flattened = {
            "$query": [
                {
                    "$source": {"$scope": "shops"},
                    "$pluck": "tags",
                    "$destination": {"$scope": "target"},
                    "$plant": "tags",
                    "$flatten": True
                }
            ]
        }
        res2 = PatchNode.model_validate(spec_flattened).patch(doc2)
        self.assertEqual(res2["target"]["tags"], ["t1", "t2", "t3"])

    def test_nested_scope_and_paths(self):
        doc = {
            "new york": {
                "clothes shops": [
                    {"name": "Store1", "more info": {"tag": "tag-ny-1"}},
                    {"name": "Store2", "more info": {"tag": "tag-ny-2"}}
                ]
            },
            "shanghai": {
                "my shops": [
                    {"name": "MainStore", "details": {}}
                ]
            }
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": ["new york", "clothes shops"]},
                    "$pluck": ["more info", "tag"],
                    "$destination": {"$scope": ["shanghai", "my shops"]},
                    "$plant": ["details", "tags"],
                    "$mode": "replace"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["shanghai"]["my shops"][0]["details"]["tags"], ["tag-ny-1", "tag-ny-2"])

    def test_source_and_destination_locators(self):
        doc = {
            "outbounds": [
                {"tag": "direct", "type": "direct"},
                {"tag": "hk-1", "type": "vmess"},
                {"tag": "us-1", "type": "vmess"},
                {"tag": "Landing", "type": "selector", "outbounds": ["direct"]}
            ]
        }
        spec = {
            "$query": [
                {
                    "$source": {
                        "$scope": ["outbounds"],
                        "$where": [{"type": "vmess"}]
                    },
                    "$pluck": "tag",
                    "$destination": {
                        "$scope": ["outbounds"],
                        "$where": [{"tag": "Landing"}]
                    },
                    "$plant": "outbounds",
                    "$mode": "append"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        landing = next(o for o in res["outbounds"] if o["tag"] == "Landing")
        self.assertEqual(landing["outbounds"], ["direct", "hk-1", "us-1"])

    def test_read_before_write_isolation(self):
        doc = {
            "outbounds": [
                {"tag": "hk-1", "type": "node"},
                {"tag": "hk-2", "type": "node"},
                {"tag": "Selector", "type": "selector", "outbounds": []}
            ]
        }
        # Destination modifies the same array being queried
        spec = {
            "$query": [
                {
                    "$source": {
                        "$scope": ["outbounds"],
                        "$not": [{"type": "selector"}]
                    },
                    "$pluck": "tag",
                    "$destination": {
                        "$scope": ["outbounds"],
                        "$where": [{"type": "selector"}]
                    },
                    "$plant": "outbounds",
                    "$mode": "append"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        selector_obj = res["outbounds"][2]
        self.assertEqual(selector_obj["outbounds"], ["hk-1", "hk-2"])

    def test_pipeline_insert_then_query(self):
        doc = {
            "outbounds": [
                {"tag": "node-1", "type": "vmess"},
                {"tag": "node-2", "type": "vmess"}
            ]
        }
        # Insert a new selector, then query node tags into it
        spec = {
            "outbounds": {
                "$insert": [
                    {
                        "$index": [0],
                        "$value": [{"tag": "Proxy", "type": "selector", "outbounds": ["direct"]}]
                    }
                ]
            },
            "$query": [
                {
                    "$source": {
                        "$scope": ["outbounds"],
                        "$where": [{"type": "vmess"}]
                    },
                    "$pluck": "tag",
                    "$destination": {
                        "$scope": ["outbounds"],
                        "$where": [{"tag": "Proxy"}]
                    },
                    "$plant": "outbounds",
                    "$mode": "append"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["outbounds"][0]["tag"], "Proxy")
        self.assertEqual(res["outbounds"][0]["outbounds"], ["direct", "node-1", "node-2"])

    def test_broadcast_to_multiple_destinations(self):
        doc = {
            "tags": [{"name": "A"}, {"name": "B"}],
            "targets": [
                {"id": 1, "items": []},
                {"id": 2, "items": []}
            ]
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "tags"},
                    "$pluck": "name",
                    "$destination": {"$scope": "targets"},
                    "$plant": "items",
                    "$mode": "replace"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["targets"][0]["items"], ["A", "B"])
        self.assertEqual(res["targets"][1]["items"], ["A", "B"])
        # Ensure deepcopy: mutating one doesn't affect the other
        res["targets"][0]["items"].append("C")
        self.assertEqual(res["targets"][1]["items"], ["A", "B"])

    def test_user_conditional_patcher(self):
        doc = {
            "nodes": [{"tag": "n1"}],
            "group": {"members": []}
        }
        spec = """
        {
            "$query": [
                {
                    "$user": "alice",
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "group"},
                    "$plant": "members",
                    "$mode": "append"
                }
            ]
        }
        """
        # Matches alice
        res_alice = user_patcher.patch("alice", spec, doc)
        self.assertEqual(res_alice["group"]["members"], ["n1"])

        # Does not match bob
        doc2 = {"nodes": [{"tag": "n1"}], "group": {"members": []}}
        res_bob = user_patcher.patch("bob", spec, doc2)
        self.assertEqual(res_bob["group"]["members"], [])

    def test_agent_and_version_patchers(self):
        doc = {"nodes": [{"tag": "n1"}], "group": {"members": []}}
        spec_agent = """
        {
            "$query": [
                {
                    "$agent": "sing-box",
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "group"},
                    "$plant": "members"
                }
            ]
        }
        """
        res_agent = agent_patcher.patch("sing-box", spec_agent, doc)
        self.assertEqual(res_agent["group"]["members"], ["n1"])

        doc2 = {"nodes": [{"tag": "n1"}], "group": {"members": []}}
        spec_ver = """
        {
            "$query": [
                {
                    "$version": ">=1.0.0",
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "group"},
                    "$plant": "members"
                }
            ]
        }
        """
        res_ver = version_patcher.patch("1.5.0", spec_ver, doc2)
        self.assertEqual(res_ver["group"]["members"], ["n1"])

    def test_regex_matching_in_locators(self):
        doc = {
            "nodes": [
                {"tag": "us-ny-01", "type": "vmess"},
                {"tag": "us-la-02", "type": "vmess"},
                {"tag": "hk-01", "type": "vmess"}
            ],
            "us_group": {"nodes": []}
        }
        spec = {
            "$query": [
                {
                    "$regex": True,
                    "$source": {
                        "$scope": "nodes",
                        "$where": [{"tag": "^us-.*"}]
                    },
                    "$pluck": "tag",
                    "$destination": {"$scope": "us_group"},
                    "$plant": "nodes"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["us_group"]["nodes"], ["us-ny-01", "us-la-02"])

    def test_regex_error_fails_loudly(self):
        import pydantic
        spec = {
            "$query": [
                {
                    "$regex": True,
                    "$source": {
                        "$scope": "nodes",
                        "$where": [{"tag": "["}]  # invalid regex
                    },
                    "$pluck": "tag",
                    "$destination": {"$scope": "nodes"},
                    "$plant": "nodes"
                }
            ]
        }
        with self.assertRaises(pydantic.ValidationError) as cm:
            PatchNode.model_validate(spec)
        self.assertIn("Regex invalid", str(cm.exception))

    def test_invalid_destination_element_fails_loudly(self):
        doc = {
            "nodes": [{"tag": "n1"}],
            "invalid_dest": ["string_item_1", "string_item_2"]
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "invalid_dest"},
                    "$plant": "outbounds"
                }
            ]
        }
        node = PatchNode.model_validate(spec)
        with self.assertRaises(ValueError):
            node.patch(doc)

    def test_intermediate_non_dict_step_fails_loudly(self):
        # "new york" resolves to an int, cannot traverse to "clothes shops"
        doc = {"new york": 42}
        spec = {
            "$query": [
                {
                    "$source": {"$scope": ["new york", "clothes shops"]},
                    "$pluck": "tag",
                    "$destination": {"$scope": "new york"},
                    "$plant": "tag"
                }
            ]
        }
        node = PatchNode.model_validate(spec)
        with self.assertRaises(ValueError) as cm:
            node.patch(doc)
        self.assertIn("must resolve to an object", str(cm.exception))

    def test_empty_source_results(self):
        doc = {
            "nodes": [{"tag": "node-1", "type": "vless"}],
            "target": {"existing": ["kept"]}
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "nodes", "$where": [{"type": "nonexistent"}]},
                    "$pluck": "tag",
                    "$destination": {"$scope": "target"},
                    "$plant": "existing",
                    "$mode": "append"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["target"]["existing"], ["kept"])

    def test_flatten_mixed_types(self):
        doc = {
            "items": [
                {"tags": ["a", "b"]},
                {"tags": "c"},
                {"tags": ["d", None]}
            ],
            "target": {}
        }
        spec_nullable = {
            "$query": [
                {
                    "$source": {"$scope": "items"},
                    "$pluck": "tags",
                    "$destination": {"$scope": "target"},
                    "$plant": "all_tags",
                    "$flatten": True,
                    "$nullable": True
                }
            ]
        }
        res1 = PatchNode.model_validate(spec_nullable).patch(doc)
        self.assertEqual(res1["target"]["all_tags"], ["a", "b", "c", "d", None])

        doc2 = {
            "items": [
                {"tags": ["a", "b"]},
                {"tags": "c"},
                {"tags": ["d", None]}
            ],
            "target": {}
        }
        spec_non_nullable = {
            "$query": [
                {
                    "$source": {"$scope": "items"},
                    "$pluck": "tags",
                    "$destination": {"$scope": "target"},
                    "$plant": "all_tags",
                    "$flatten": True,
                    "$nullable": False
                }
            ]
        }
        res2 = PatchNode.model_validate(spec_non_nullable).patch(doc2)
        self.assertEqual(res2["target"]["all_tags"], ["a", "b", "c", "d"])

    def test_missing_scopes_do_not_crash(self):
        doc = {"nodes": [{"tag": "n1"}]}
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "nonexistent_source"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "nodes"},
                    "$plant": "items"
                },
                {
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "nonexistent_dest"},
                    "$plant": "items"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["nodes"][0]["items"], [])

    def test_default_mode_is_replace(self):
        doc = {
            "nodes": [{"tag": "n1"}],
            "target": {"items": ["old"]}
        }
        spec = {
            "$query": [
                {
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "target"},
                    "$plant": "items"
                }
            ]
        }
        res = PatchNode.model_validate(spec).patch(doc)
        self.assertEqual(res["target"]["items"], ["n1"])

    def test_user_regex_matching_on_query(self):
        doc = {"nodes": [{"tag": "n1"}], "target": {"items": []}}
        spec = """
        {
            "$query": [
                {
                    "$regex": true,
                    "$user": ["dev-.*"],
                    "$source": {"$scope": "nodes"},
                    "$pluck": "tag",
                    "$destination": {"$scope": "target"},
                    "$plant": "items",
                    "$mode": "replace"
                }
            ]
        }
        """
        # dev-john matches regex
        res1 = user_patcher.patch("dev-john", spec, doc)
        self.assertEqual(res1["target"]["items"], ["n1"])

        # prod-john does not match
        doc2 = {"nodes": [{"tag": "n1"}], "target": {"items": []}}
        res2 = user_patcher.patch("prod-john", spec, doc2)
        self.assertEqual(res2["target"]["items"], [])


if __name__ == '__main__':
    unittest.main()
