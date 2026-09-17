#  SPDX-FileCopyrightText: Copyright (c) "2026" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Tests for LPU C2C topology coordinate policy."""

from decimal import Decimal

from django.test import SimpleTestCase

from nautobot_nvdatamodels import choices
from nautobot_nvdatamodels.lpu_c2c.topology import (
    CoordinatePolicyError,
    LocalCoordinate,
    derive_local_coordinate,
    resolve_local_coordinate,
)


class LPUC2CTopologyTestCase(SimpleTestCase):
    """Validate topology coordinate policies."""

    def test_lp30_native_positions_map_to_one_based_rack_wide_tray_slots(self):
        """LP30 native positions map bottom-to-top across the whole rack."""
        for tray_slot in range(1, 17):
            with self.subTest(tray_slot=tray_slot):
                self.assertEqual(
                    derive_local_coordinate(
                        choices.LPUC2CTopologyChoices.LP30_C2C,
                        Decimal(6 + 2 * tray_slot),
                    ),
                    LocalCoordinate(tray_slot=tray_slot),
                )

    def test_lp30_native_position_boundaries_match_scheduler_indices(self):
        """LP30 U8 and U38 map to the scheduler's first and last tray slots."""
        self.assertEqual(
            derive_local_coordinate(choices.LPUC2CTopologyChoices.LP30_C2C, Decimal(8)),
            LocalCoordinate(tray_slot=1),
        )
        self.assertEqual(
            derive_local_coordinate(choices.LPUC2CTopologyChoices.LP30_C2C, Decimal(38)),
            LocalCoordinate(tray_slot=16),
        )

    def test_lp30_sort_keys_follow_rack_wide_tray_slots(self):
        """LP30 coordinates sort from the bottom to the top of a rack."""
        coordinates = [LocalCoordinate(tray_slot=16), LocalCoordinate(tray_slot=1)]

        self.assertEqual(
            sorted(coordinates, key=LocalCoordinate.sort_key),
            [LocalCoordinate(tray_slot=1), LocalCoordinate(tray_slot=16)],
        )

    def test_invalid_lp30_native_position_has_stable_error_code(self):
        """LP30 U9 is rejected as an invalid native position."""
        with self.assertRaises(CoordinatePolicyError) as context:
            derive_local_coordinate(choices.LPUC2CTopologyChoices.LP30_C2C, Decimal(9))

        self.assertIn("not valid", str(context.exception))
        self.assertEqual(context.exception.code, "INVALID_NATIVE_POSITION")

    def test_lp30_overrides_accept_every_scheduler_tray_slot(self):
        """LP30 overrides accept every one-based rack-wide tray slot."""
        for tray_slot in range(1, 17):
            with self.subTest(tray_slot=tray_slot):
                self.assertEqual(
                    resolve_local_coordinate(
                        choices.LPUC2CTopologyChoices.LP30_C2C,
                        Decimal(8),
                        tray_slot=tray_slot,
                    ),
                    LocalCoordinate(tray_slot=tray_slot),
                )

    def test_lp30_override_rejects_out_of_range_tray_slots(self):
        """LP30 overrides reject values outside the scheduler's 1 through 16 range."""
        for tray_slot in (0, 17):
            with (
                self.subTest(tray_slot=tray_slot),
                self.assertRaises(CoordinatePolicyError) as context,
            ):
                resolve_local_coordinate(
                    choices.LPUC2CTopologyChoices.LP30_C2C,
                    Decimal(8),
                    tray_slot=tray_slot,
                )

            self.assertEqual(context.exception.code, "INVALID_COORDINATE_OVERRIDE")

    def test_lp30_override_rejects_non_integer_tray_slots(self):
        """LP30 tray-slot overrides must be actual integers, not integer-like values."""
        for value in (1.0, Decimal(1), False):
            with (
                self.subTest(value=repr(value)),
                self.assertRaises(CoordinatePolicyError) as context,
            ):
                resolve_local_coordinate(
                    choices.LPUC2CTopologyChoices.LP30_C2C,
                    Decimal(8),
                    tray_slot=value,
                )

            self.assertEqual(context.exception.code, "INVALID_COORDINATE_OVERRIDE")
