#  SPDX-FileCopyrightText: Copyright (c) "2026" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Tests for live LPU C2C domain evaluation."""

from contextlib import ExitStack
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from nautobot.dcim.models import Device, Rack
from nautobot.extras.models import Role

from nautobot_nvdatamodels import choices, models
from nautobot_nvdatamodels.lpu_c2c.evaluator import (
    ProjectionPermissionDenied,
    evaluate_domain,
    evaluate_domain_snapshots,
    evaluate_domains,
)
from nautobot_nvdatamodels.lpu_c2c.types import EndpointCoordinate, ProjectionState
from nautobot_nvdatamodels.tests import fixtures


class LPUC2CEvaluatorTestCase(TestCase):
    """Evaluate endpoints from currently installed LPU Tray devices."""

    @classmethod
    def setUpTestData(cls):
        fixtures.lpu_c2c_test_data(cls)
        cls.rack_two = Rack.objects.create(
            name="LPU C2C Rack Two", location=cls.rack.location, status=cls.rack.status
        )
        cls.first_position = models.LPUC2CDomainRackPosition.objects.create(
            domain=cls.domain, ordinal=0, rack=cls.rack
        )
        cls.second_position = models.LPUC2CDomainRackPosition.objects.create(
            domain=cls.domain, ordinal=1, rack=cls.rack_two
        )
        cls.compatibility = models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=choices.LPUC2CTopologyChoices.LP30_C2C, device_type=cls.device_type
        )
        tray_role = Role.objects.get(name="LPU Tray")
        cls.second_device = Device.objects.create(
            name="Compatible LPU Tray Two",
            role=tray_role,
            status=cls.device.status,
            location=cls.rack_two.location,
            rack=cls.rack_two,
            position=10,
            device_type=cls.device_type,
        )
        cls.excluded_device = Device.objects.create(
            name="Excluded LPU Tray",
            role=tray_role,
            status=cls.device.status,
            location=cls.rack.location,
            rack=cls.rack,
            position=12,
            device_type=cls.device_type,
        )
        cls.non_lpu_device = Device.objects.create(
            name="Non LPU Device",
            role=Role.objects.create(name="Not an LPU Tray"),
            status=cls.device.status,
            location=cls.rack.location,
            rack=cls.rack,
            position=14,
            device_type=cls.device_type,
        )
        models.LPUC2CEndpointConfiguration.objects.create(
            device=cls.second_device, rack_position=cls.second_position, tray_slot=16
        )
        models.LPUC2CEndpointConfiguration.objects.create(
            device=cls.excluded_device, rack_position=cls.first_position, excluded=True
        )

    def test_evaluation_derives_ready_endpoints_from_live_devices(self):
        """Compatible LPU Tray devices produce sorted endpoint projections."""
        evaluation = evaluate_domain(self.domain)

        self.assertEqual(evaluation.state, ProjectionState.READY)
        self.assertEqual(
            [endpoint.device.object_id for endpoint in evaluation.endpoints],
            [self.device.pk, self.second_device.pk],
        )
        self.assertEqual(
            [endpoint.coordinate for endpoint in evaluation.endpoints],
            [
                EndpointCoordinate(rack_ordinal=0, tray_slot=1),
                EndpointCoordinate(rack_ordinal=1, tray_slot=16),
            ],
        )

    def test_evaluation_reads_new_live_member_without_membership_row(self):
        """A compatible tray added after evaluation appears in the next evaluation."""
        first_evaluation = evaluate_domain(self.domain)
        tray_role = Role.objects.get(name="LPU Tray")
        added_device = Device.objects.create(
            name="Live LPU Tray",
            role=tray_role,
            status=self.device.status,
            location=self.rack.location,
            rack=self.rack,
            position=10,
            device_type=self.device_type,
        )

        second_evaluation = evaluate_domain(self.domain)

        self.assertNotIn(
            added_device.pk, [endpoint.device.object_id for endpoint in first_evaluation.endpoints]
        )
        self.assertIn(
            added_device.pk, [endpoint.device.object_id for endpoint in second_evaluation.endpoints]
        )

    def assert_invalid(self, code):
        """Assert that a domain-wide error fail-closes every endpoint coordinate."""
        evaluation = evaluate_domain(self.domain)

        self.assertEqual(evaluation.state, ProjectionState.INVALID)
        self.assertIn(code, [diagnostic.code for diagnostic in evaluation.diagnostics])
        self.assertTrue(evaluation.endpoints)
        self.assertTrue(all(endpoint.coordinate is None for endpoint in evaluation.endpoints))
        return evaluation

    def test_sparse_rack_ordinals_are_invalid(self):
        """Rack position ordinals must be a dense zero-based sequence."""
        models.LPUC2CDomainRackPosition.objects.filter(pk=self.second_position.pk).update(ordinal=2)

        self.assert_invalid("NON_DENSE_RACK_ORDINALS")

    def test_rack_outside_domain_location_is_invalid(self):
        """A rack moved outside the domain location hierarchy invalidates the projection."""
        Rack.objects.filter(pk=self.rack.pk).update(location=self.other_location)

        self.assert_invalid("RACK_OUTSIDE_DOMAIN_LOCATION")

    def test_incompatible_lpu_device_type_is_invalid(self):
        """Every installed LPU tray must be compatible with the domain topology."""
        Device.objects.filter(pk=self.device.pk).update(device_type=self.incompatible_device_type)

        self.assert_invalid("INCOMPATIBLE_DEVICE_TYPE")

    def test_invalid_native_position_is_invalid(self):
        """Invalid native rack positions are diagnostics rather than silently omitted."""
        Device.objects.filter(pk=self.device.pk).update(position=9)

        self.assert_invalid("INVALID_NATIVE_POSITION")

    def test_invalid_coordinate_override_is_invalid(self):
        """Invalid persisted overrides preserve the endpoint but fail-close coordinates."""
        models.LPUC2CEndpointConfiguration.objects.filter(
            pk=self.second_device.lpu_c2c_endpoint_configuration.pk
        ).update(tray_slot=99)

        self.assert_invalid("INVALID_COORDINATE_OVERRIDE")

    def test_duplicate_coordinates_reference_both_devices(self):
        """Duplicate raw coordinates identify all colliding device UUIDs."""
        duplicate = Device.objects.create(
            name="Duplicate Coordinate LPU Tray",
            role=Role.objects.get(name="LPU Tray"),
            status=self.device.status,
            location=self.rack.location,
            rack=self.rack,
            position=10,
            device_type=self.device_type,
        )
        models.LPUC2CEndpointConfiguration.objects.create(
            device=duplicate, rack_position=self.first_position, tray_slot=1
        )

        evaluation = self.assert_invalid("DUPLICATE_COORDINATE")
        diagnostic = next(item for item in evaluation.diagnostics if item.code == "DUPLICATE_COORDINATE")
        self.assertEqual(
            {reference.object_id for reference in diagnostic.affected_objects}, {self.device.pk, duplicate.pk}
        )

    def test_endpoint_configuration_rack_mismatch_is_invalid(self):
        """A persisted endpoint configuration must still target the device's rack."""
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=self.first_position, tray_slot=1
        )
        models.LPUC2CEndpointConfiguration.objects.filter(pk=configuration.pk).update(
            rack_position=self.second_position
        )

        self.assert_invalid("ENDPOINT_CONFIGURATION_RACK_MISMATCH")

    def test_partial_or_vacant_racks_without_interfaces_or_cables_remain_ready(self):
        """Missing trays, interfaces, and cables do not make a valid domain invalid."""
        self.second_device.delete()

        evaluation = evaluate_domain(self.domain)

        self.assertEqual(evaluation.state, ProjectionState.READY)
        self.assertEqual([endpoint.device.object_id for endpoint in evaluation.endpoints], [self.device.pk])

    def test_moving_a_configured_device_invalidates_without_mutating_domain_or_config(self):
        """A live device move is detected read-only and leaves its domain status untouched."""
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=self.first_position, tray_slot=1
        )
        active = type(self.planned_status).objects.get(name="LPU C2C Active")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active)
        Device.objects.filter(pk=self.device.pk).update(rack=self.other_rack, location=self.other_location)

        self.assert_invalid("ENDPOINT_CONFIGURATION_RACK_MISMATCH")
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, active.pk)
        self.assertEqual(models.LPUC2CEndpointConfiguration.objects.filter(pk=configuration.pk).count(), 1)

    def test_configured_non_lpu_tray_is_not_an_endpoint(self):
        """Endpoint configuration does not promote a role-changed device into the projection."""
        Device.objects.filter(pk=self.second_device.pk).update(role=self.non_lpu_device.role)

        evaluation = evaluate_domain(self.domain)

        self.assertEqual(evaluation.state, ProjectionState.READY)
        self.assertEqual([endpoint.device.object_id for endpoint in evaluation.endpoints], [self.device.pk])

    def test_complete_visibility_requires_a_user(self):
        """Complete visibility cannot be evaluated without an authenticated principal."""
        with self.assertRaises(ProjectionPermissionDenied):
            evaluate_domain(self.domain, require_complete_visibility=True)

    def test_snapshot_requires_only_compatibilities_relevant_to_domain_candidates(self):
        """Exact snapshots carry candidate compatibility rows, never the global matrix."""
        unrelated_device_type = models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology,
            device_type=self.incompatible_device_type,
        )

        snapshot = evaluate_domain_snapshots([self.domain.pk])[self.domain.pk]
        compatibility_ids = {
            reference.object_id
            for reference in snapshot.required_objects
            if reference.object_type == models.LPUC2CDeviceTypeCompatibility._meta.label_lower
        }

        self.assertEqual(compatibility_ids, {self.compatibility.pk})
        self.assertNotIn(unrelated_device_type.pk, compatibility_ids)

    def test_complete_visibility_denies_each_projection_source(self):
        """Every source object in a projection must be viewable by the caller."""
        user = get_user_model().objects.create_superuser(username="lpu-c2c-admin")
        sources = (
            (models.LPUC2CDomain, self.domain.pk),
            (models.LPUC2CDomainRackPosition, self.first_position.pk),
            (Rack, self.rack.pk),
            (models.LPUC2CEndpointConfiguration, self.second_device.lpu_c2c_endpoint_configuration.pk),
            (models.LPUC2CDeviceTypeCompatibility, self.compatibility.pk),
            (Device, self.device.pk),
        )

        for model, hidden_id in sources:
            with (
                self.subTest(model=model.__name__),
                patch.object(model.objects, "restrict", return_value=model.objects.exclude(pk=hidden_id)),
            ):
                with self.assertRaises(ProjectionPermissionDenied):
                    evaluate_domain(self.domain, user=user, require_complete_visibility=True)

                results = evaluate_domains(
                    [self.domain.pk, self.other_domain.pk], user=user, require_complete_visibility=True
                )
                self.assertIsInstance(results[self.domain.pk], ProjectionPermissionDenied)
                self.assertNotIsInstance(results[self.other_domain.pk], ProjectionPermissionDenied)

    def test_complete_visibility_ignores_hidden_unrelated_compatibility_rows(self):
        """A compatibility for another candidate pair is not part of this Domain snapshot."""
        unrelated = models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology,
            device_type=self.incompatible_device_type,
        )
        user = get_user_model().objects.create_superuser(username="lpu-c2c-relevance-admin")

        with patch.object(
            models.LPUC2CDeviceTypeCompatibility.objects,
            "restrict",
            return_value=models.LPUC2CDeviceTypeCompatibility.objects.exclude(pk=unrelated.pk),
        ) as restrict:
            evaluation = evaluate_domain(
                self.domain,
                user=user,
                require_complete_visibility=True,
            )

        self.assertEqual(evaluation.state, ProjectionState.READY)
        restrict.assert_called_once_with(user, "view")

    def test_complete_visibility_batches_one_query_per_projection_model(self):
        """Batched visibility is evaluated once per model, not once per domain."""
        user = get_user_model().objects.create_superuser(username="lpu-c2c-batch-admin")
        source_models = (
            models.LPUC2CDomain,
            models.LPUC2CDomainRackPosition,
            Rack,
            models.LPUC2CEndpointConfiguration,
            models.LPUC2CDeviceTypeCompatibility,
            Device,
        )

        with ExitStack() as stack:
            restrictions = [
                stack.enter_context(patch.object(model.objects, "restrict", wraps=model.objects.restrict))
                for model in source_models
            ]
            results = evaluate_domains(
                [self.domain.pk, self.other_domain.pk], user=user, require_complete_visibility=True
            )

        self.assertTrue(
            all(not isinstance(result, ProjectionPermissionDenied) for result in results.values())
        )
        self.assertEqual([restriction.call_count for restriction in restrictions], [1, 1, 1, 1, 1, 1])

    def test_diagnostics_are_sorted_deterministically(self):
        """Multiple errors have a stable code and affected-object ordering."""
        Device.objects.filter(pk=self.device.pk).update(device_type=self.incompatible_device_type, position=9)

        evaluation = evaluate_domain(self.domain)

        keys = [
            (
                diagnostic.code,
                tuple(
                    (reference.object_type, str(reference.object_id))
                    for reference in diagnostic.affected_objects
                ),
            )
            for diagnostic in evaluation.diagnostics
        ]
        self.assertEqual(keys, sorted(keys))

    def test_multi_domain_evaluation_returns_a_result_for_each_requested_domain(self):
        """Direct batched evaluation keeps one projection per requested domain."""
        results = evaluate_domains([self.domain.pk, self.other_domain.pk])

        self.assertEqual(set(results), {self.domain.pk, self.other_domain.pk})
        self.assertEqual(results[self.domain.pk].state, ProjectionState.READY)
        self.assertEqual(results[self.other_domain.pk].state, ProjectionState.READY)
