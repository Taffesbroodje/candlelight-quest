"""Tests for src/text_rpg/utils.py — safe_json and safe_props."""
from __future__ import annotations

import json

import pytest

from text_rpg.utils import safe_json, safe_props


class TestSafeJson:
    def test_none_returns_empty_dict(self):
        assert safe_json(None) == {}

    def test_none_with_default(self):
        assert safe_json(None, []) == []

    def test_valid_json_string(self):
        assert safe_json('{"a": 1}') == {"a": 1}

    def test_invalid_json_string(self):
        assert safe_json("not json") == {}

    def test_invalid_json_string_with_default(self):
        assert safe_json("not json", {"fallback": True}) == {"fallback": True}

    def test_empty_string(self):
        assert safe_json("") == {}

    def test_list_passthrough(self):
        data = [1, 2, 3]
        assert safe_json(data) is data

    def test_dict_passthrough(self):
        data = {"key": "value"}
        assert safe_json(data) is data

    def test_int_passthrough(self):
        assert safe_json(42) == 42

    def test_json_array_string(self):
        assert safe_json("[1, 2, 3]") == [1, 2, 3]


class TestSafeProps:
    def test_empty_properties(self):
        assert safe_props({"properties": {}}) == {}

    def test_none_properties(self):
        assert safe_props({"properties": None}) == {}

    def test_missing_key(self):
        assert safe_props({}) == {}

    def test_json_string_properties(self):
        assert safe_props({"properties": '{"hp": 10}'}) == {"hp": 10}

    def test_dict_properties(self):
        data = {"properties": {"hp": 10, "ac": 12}}
        assert safe_props(data) == {"hp": 10, "ac": 12}
