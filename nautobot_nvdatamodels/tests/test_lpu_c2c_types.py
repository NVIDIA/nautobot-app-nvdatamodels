"""Tests for LPU C2C transport types and their supported runtime contract."""

import enum
import importlib.util
import json
import sys
from dataclasses import fields
from types import ModuleType
from unittest.mock import patch

from django.test import SimpleTestCase

from nautobot_nvdatamodels import NautobotNVIDIAConfig
from nautobot_nvdatamodels.lpu_c2c import types as lpu_c2c_types


class LPUC2CTypesTestCase(SimpleTestCase):
    """Keep transport enums compatible with every supported Python runtime."""

    def test_endpoint_coordinate_has_only_scheduler_fields(self):
        """The endpoint coordinate contains only the scheduler's public indices."""
        self.assertEqual(
            [field.name for field in fields(lpu_c2c_types.EndpointCoordinate)],
            ["rack_ordinal", "tray_slot"],
        )

    def test_types_module_imports_without_python_311_strenum(self):
        """The Python 3.10 runtime contract cannot depend on enum.StrEnum."""
        python_310_enum = ModuleType("enum")
        python_310_enum.Enum = enum.Enum
        module_name = f"{lpu_c2c_types.__name__}_python_310"
        spec = importlib.util.spec_from_file_location(module_name, lpu_c2c_types.__file__)
        module = importlib.util.module_from_spec(spec)

        with patch.dict(sys.modules, {"enum": python_310_enum, module_name: module}):
            spec.loader.exec_module(module)

        self.assertEqual(module.ProjectionState.READY.value, "ready")
        self.assertEqual(module.DiagnosticSeverity.ERROR.value, "error")

    def test_transport_enums_serialize_as_lowercase_strings(self):
        """Replacing StrEnum must preserve the public lowercase JSON values."""
        values = {
            "state": lpu_c2c_types.ProjectionState.INVALID,
            "severity": lpu_c2c_types.DiagnosticSeverity.WARNING,
        }

        self.assertEqual(
            json.loads(json.dumps(values)),
            {"state": "invalid", "severity": "warning"},
        )
        self.assertIsInstance(lpu_c2c_types.ProjectionState.READY, str)
        self.assertIsInstance(lpu_c2c_types.DiagnosticSeverity.ERROR, str)
        self.assertEqual(str(lpu_c2c_types.ProjectionState.READY), "ready")
        self.assertEqual(str(lpu_c2c_types.DiagnosticSeverity.ERROR), "error")

    def test_app_declares_dependency_floor_as_minimum_nautobot_version(self):
        """Runtime compatibility starts at the same Nautobot release as packaging."""
        self.assertEqual(NautobotNVIDIAConfig.min_version, "2.4.20")
