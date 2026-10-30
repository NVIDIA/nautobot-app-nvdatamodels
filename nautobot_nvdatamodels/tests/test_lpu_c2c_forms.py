#  SPDX-FileCopyrightText: Copyright (c) "2026" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Tests for lifecycle-safe LPU C2C UI forms."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from nautobot.dcim.models import Device, Rack
from nautobot.extras.models import Status

from nautobot_nvdatamodels import forms, models
from nautobot_nvdatamodels.lpu_c2c import mutations
from nautobot_nvdatamodels.lpu_c2c.types import ProjectionState
from nautobot_nvdatamodels.tests import fixtures


class LPUC2CFormTestCase(TestCase):
    """Exercise form validation and mutation-service delegation."""

    @classmethod
    def setUpTestData(cls):
        fixtures.lpu_c2c_test_data(cls)
        cls.active_status = Status.objects.get(name="LPU C2C Active")
        cls.maintenance_status = Status.objects.get(name="LPU C2C Maintenance")
        cls.rack_two = Rack.objects.create(
            name="LPU C2C Form Rack Two", location=cls.rack.location, status=cls.rack.status
        )
        cls.device_two = Device.objects.create(
            name="LPU C2C Form Device Two",
            role=cls.device.role,
            status=cls.device.status,
            location=cls.rack_two.location,
            rack=cls.rack_two,
            position=12,
            device_type=cls.device_type,
        )

    def domain_data(self, **overrides):
        data = {
            "name": self.domain.name,
            "status": self.domain.status_id,
            "topology": self.domain.topology,
            "location": self.domain.location_id,
            "tenant": "",
        }
        data.update(overrides)
        return data

    def test_domain_form_exposes_only_normalized_fields_and_requires_topology(self):
        form = forms.LPUC2CDomainForm(instance=self.domain)

        self.assertTrue({"name", "status", "topology", "location", "tenant"} <= set(form.fields))
        self.assertFalse({"role", "rack", "rack_group", "cluster_id", "members"} & set(form.fields))
        self.assertTrue(form.fields["topology"].required)

    def test_domain_form_allows_planned_creation(self):
        form = forms.LPUC2CDomainForm(data=self.domain_data(name="New planned LPU C2C Domain"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_domain_form_requires_active_to_transition_to_maintenance(self):
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=self.active_status)
        self.domain.refresh_from_db()

        planned_form = forms.LPUC2CDomainForm(
            data=self.domain_data(status=self.planned_status.pk),
            instance=self.domain,
        )
        self.assertFalse(planned_form.is_valid())
        self.assertIn("status", planned_form.errors)

        self.domain.refresh_from_db()
        maintenance_form = forms.LPUC2CDomainForm(
            data=self.domain_data(status=self.maintenance_status.pk),
            instance=self.domain,
        )
        self.assertTrue(maintenance_form.is_valid(), maintenance_form.errors)

    def test_domain_form_checks_projection_only_when_entering_active(self):
        invalid = SimpleNamespace(
            state=ProjectionState.INVALID,
            diagnostics=(SimpleNamespace(message="Rack projection is invalid."),),
        )
        with patch("nautobot_nvdatamodels.forms.evaluate_domain", return_value=invalid) as evaluator:
            form = forms.LPUC2CDomainForm(
                data=self.domain_data(status=self.active_status.pk), instance=self.domain
            )

            self.assertFalse(form.is_valid())
            self.assertIn("status", form.errors)
            self.assertIn("Rack projection is invalid", str(form.errors["status"]))
            evaluator.assert_called_once()

        self.domain.status = self.active_status
        self.domain.save(update_fields=["status"])
        with patch("nautobot_nvdatamodels.forms.evaluate_domain") as evaluator:
            form = forms.LPUC2CDomainForm(data=self.domain_data(), instance=self.domain)
            self.assertTrue(form.is_valid(), form.errors)
            evaluator.assert_not_called()

    def test_rack_operation_choices_are_exact(self):
        self.assertEqual(
            forms.LPUC2CRackOperationForm.OPERATION_CHOICES,
            (
                ("append", "Append position"),
                ("fill", "Fill vacancy"),
                ("vacate", "Vacate position"),
                ("remove_and_compact", "Remove and compact"),
                ("insert", "Insert position"),
                ("reorder", "Reorder positions"),
            ),
        )

    def test_rack_operation_dispatches_all_six_services(self):
        first = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        second = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=1)
        cases = (
            ("append", {"rack": self.rack.pk}, "append_position"),
            ("fill", {"position": first.pk, "rack": self.rack.pk}, "fill_position"),
            ("vacate", {"position": second.pk}, "vacate_position"),
            (
                "remove_and_compact",
                {"position": second.pk, "confirmed": True},
                "remove_and_compact_position",
            ),
            ("insert", {"ordinal": 1, "confirmed": True}, "insert_position"),
            (
                "reorder",
                {"position_ids": f"{second.pk},{first.pk}", "confirmed": True},
                "reorder_positions",
            ),
        )

        for operation, operation_data, service_name in cases:
            with self.subTest(operation=operation):
                data = {"operation": operation, **operation_data}
                form = forms.LPUC2CRackOperationForm(domain=self.domain, data=data)
                self.assertTrue(form.is_valid(), form.errors)
                with patch.object(mutations, service_name) as service:
                    form.save()
                    service.assert_called_once()

    def test_rack_operation_rejects_active_domain_and_missing_operation_inputs(self):
        position = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=self.active_status)
        self.domain.refresh_from_db()

        active_form = forms.LPUC2CRackOperationForm(domain=self.domain, data={"operation": "append"})
        self.assertFalse(active_form.is_valid())
        self.assertIn("Only Planned and Maintenance", str(active_form.errors))

        self.domain.status = self.planned_status
        self.domain.save(update_fields=["status"])
        required_cases = (
            ("fill", {"position": position.pk}),
            ("insert", {"confirmed": True}),
            ("reorder", {"confirmed": True}),
        )
        for operation, data in required_cases:
            with self.subTest(operation=operation):
                form = forms.LPUC2CRackOperationForm(
                    domain=self.domain, data={"operation": operation, **data}
                )
                self.assertFalse(form.is_valid())

    def test_rack_operation_requires_confirmation_for_ordinal_changes(self):
        position = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        for operation, data in (
            ("remove_and_compact", {"position": position.pk}),
            ("insert", {"ordinal": 0}),
            ("reorder", {"position_ids": str(position.pk)}),
        ):
            with self.subTest(operation=operation):
                form = forms.LPUC2CRackOperationForm(
                    domain=self.domain, data={"operation": operation, **data}
                )
                self.assertFalse(form.is_valid())
                self.assertIn("confirmed", form.errors)

    def test_rack_operation_real_reorder_passes_uuid_compatible_values_to_service(self):
        first = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        second = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=1)
        form = forms.LPUC2CRackOperationForm(
            domain=self.domain,
            data={
                "operation": "reorder",
                "position_ids": f"{second.pk},{first.pk}",
                "confirmed": True,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(
            list(self.domain.rack_positions.order_by("ordinal").values_list("pk", flat=True)),
            [second.pk, first.pk],
        )

    def test_fill_rejects_rack_already_occupying_another_same_domain_position(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        vacancy = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=1)
        form = forms.LPUC2CRackOperationForm(
            domain=self.domain,
            data={"operation": "fill", "position": vacancy.pk, "rack": self.rack.pk},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("rack", form.errors)
        self.assertIn("already has a position", str(form.errors["rack"]))

    def test_device_first_rack_operation_allows_only_append_or_selected_vacancy(self):
        vacancy = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        append_form = forms.LPUC2CRackOperationForm(
            domain=self.domain, device=self.device, data={"operation": "append"}
        )
        fill_form = forms.LPUC2CRackOperationForm(
            domain=self.domain,
            device=self.device,
            data={"operation": "fill", "position": vacancy.pk},
        )
        insert_form = forms.LPUC2CRackOperationForm(
            domain=self.domain,
            device=self.device,
            data={"operation": "insert", "ordinal": 0, "confirmed": True},
        )

        self.assertTrue(append_form.is_valid(), append_form.errors)
        self.assertEqual(append_form.cleaned_data["rack"], self.rack)
        self.assertTrue(fill_form.is_valid(), fill_form.errors)
        self.assertEqual(fill_form.cleaned_data["rack"], self.rack)
        self.assertFalse(insert_form.is_valid())
        self.assertIn("append or fill", str(insert_form.errors))

    def test_device_first_rack_operation_rejects_missing_or_other_domain_rack(self):
        Device.objects.filter(pk=self.device.pk).update(rack=None, position=None)
        self.device.refresh_from_db()
        no_rack_form = forms.LPUC2CRackOperationForm(
            domain=self.domain, device=self.device, data={"operation": "append"}
        )
        self.assertFalse(no_rack_form.is_valid())
        self.assertIn("does not have a Rack", str(no_rack_form.errors))

        models.LPUC2CDomainRackPosition.objects.create(
            domain=self.other_domain, ordinal=0, rack=self.rack_two
        )
        other_domain_form = forms.LPUC2CRackOperationForm(
            domain=self.domain, device=self.device_two, data={"operation": "append"}
        )
        self.assertFalse(other_domain_form.is_valid())
        self.assertIn("another LPU C2C Domain", str(other_domain_form.errors))

    def test_endpoint_form_derives_position_and_delegates_exclusion_override_and_removal(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        form = forms.LPUC2CEndpointConfigurationForm(device=self.device)
        self.assertEqual(set(form.fields), {"device", "excluded", "tray_slot"})
        self.assertEqual(form.fields["tray_slot"].min_value, 1)
        self.assertEqual(form.fields["tray_slot"].max_value, 16)
        cases = (
            (
                {"excluded": True},
                {"excluded": True, "tray_slot": None},
            ),
            (
                {"tray_slot": 16},
                {"excluded": False, "tray_slot": 16},
            ),
            ({}, {"excluded": False, "tray_slot": None}),
        )
        for data, expected in cases:
            with self.subTest(data=data):
                form = forms.LPUC2CEndpointConfigurationForm(device=self.device, data=data)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.rack_position, position)
                with patch.object(mutations, "set_endpoint_configuration") as service:
                    form.save()
                    service.assert_called_once_with(self.device, position, **expected)

    def test_endpoint_form_uses_existing_configuration_and_rejects_active_domain(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        form = forms.LPUC2CEndpointConfigurationForm(device=self.device)
        self.assertEqual(form.initial["excluded"], True)
        self.assertEqual(form.rack_position, position)

        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=self.active_status)
        form = forms.LPUC2CEndpointConfigurationForm(device=self.device, data={"excluded": False})
        self.assertFalse(form.is_valid())
        self.assertIn("Only Planned and Maintenance", str(form.errors))
        self.assertEqual(configuration.rack_position, position)

    def test_endpoint_form_rejects_device_without_rack_or_domain_position(self):
        no_position = forms.LPUC2CEndpointConfigurationForm(device=self.device, data={"excluded": True})
        self.assertFalse(no_position.is_valid())
        self.assertIn("not assigned to an LPU C2C Domain rack position", str(no_position.errors))

        Device.objects.filter(pk=self.device.pk).update(rack=None, position=None)
        self.device.refresh_from_db()
        no_rack = forms.LPUC2CEndpointConfigurationForm(device=self.device, data={"excluded": True})
        self.assertFalse(no_rack.is_valid())
        self.assertIn("does not have a Rack", str(no_rack.errors))
