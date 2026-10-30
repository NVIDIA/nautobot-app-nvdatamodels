#  SPDX-FileCopyrightText: Copyright (c) "2026" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Tests for the LPU C2C UI, routes, and Device extension."""

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.context_processors import PermWrapper
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.test import RequestFactory
from django.urls import NoReverseMatch, reverse
from nautobot.core.testing import TestCase
from nautobot.extras.models import Status

from nautobot_nvdatamodels import forms, models, navigation, tables
from nautobot_nvdatamodels.lpu_c2c import evaluator, mutations
from nautobot_nvdatamodels.lpu_c2c.types import (
    Diagnostic,
    DiagnosticSeverity,
    ObjectReference,
    ProjectionState,
)
from nautobot_nvdatamodels.template_content import DeviceNVIDIAContent
from nautobot_nvdatamodels.tests import fixtures


class LPUC2CViewTestCase(TestCase):
    """Exercise the Domain workflows and read-only projections."""

    @classmethod
    def setUpTestData(cls):
        fixtures.lpu_c2c_test_data(cls)

    def grant_projection_permissions(self):
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.view_lpuc2cdevicetypecompatibility",
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "dcim.view_rack",
            "dcim.view_device",
        )

    def grant_domain_form_permissions(self):
        self.add_permissions(
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "extras.view_status",
            "dcim.view_location",
            "tenancy.view_tenant",
        )

    def domain_form_data(self, **overrides):
        data = {
            "name": self.domain.name,
            "status": self.domain.status_id,
            "topology": self.domain.topology,
            "location": self.domain.location_id,
            "tenant": "",
        }
        data.update(overrides)
        return data

    def make_ready_projection(self, *, vacancy=False):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        if vacancy:
            models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=1)
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )

    def test_domain_and_workflow_routes_are_stable_without_generic_position_ui(self):
        domain_id = uuid4()
        device_id = uuid4()
        self.assertEqual(
            reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_list"),
            "/plugins/nvdatamodels/lpu-c2c-domains/",
        )
        self.assertEqual(
            reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain", args=[domain_id]),
            f"/plugins/nvdatamodels/lpu-c2c-domains/{domain_id}/",
        )
        self.assertEqual(
            reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_add"),
            "/plugins/nvdatamodels/lpu-c2c-domains/add/",
        )
        self.assertEqual(
            reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_edit", args=[domain_id]),
            f"/plugins/nvdatamodels/lpu-c2c-domains/{domain_id}/edit/",
        )
        self.assertEqual(
            reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_delete", args=[domain_id]),
            f"/plugins/nvdatamodels/lpu-c2c-domains/{domain_id}/delete/",
        )
        self.assertEqual(
            reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_rack_operation", args=[domain_id]),
            f"/plugins/nvdatamodels/lpu-c2c-domains/{domain_id}/rack-operation/",
        )
        self.assertEqual(
            reverse("plugins:nautobot_nvdatamodels:lpuc2c_endpoint_configuration", args=[device_id]),
            f"/plugins/nvdatamodels/devices/{device_id}/lpu-c2c-endpoint/",
        )
        for route_name in (
            "lpuc2cdomainrackposition_list",
            "lpuc2cdomainrackposition_add",
            "lpuc2cdomainrackposition_edit",
            "lpuc2cdomainrackposition_delete",
        ):
            with self.subTest(route_name=route_name), self.assertRaises(NoReverseMatch):
                reverse(f"plugins:nautobot_nvdatamodels:{route_name}", args=[domain_id])

    def test_domain_detail_uses_one_evaluation_for_ordered_vacancies_and_coordinates(self):
        self.make_ready_projection(vacancy=True)
        self.grant_projection_permissions()

        with patch(
            "nautobot_nvdatamodels.views.evaluate_domain", wraps=evaluator.evaluate_domain
        ) as evaluate:
            response = self.client.get(self.domain.get_absolute_url())

        self.assertHttpStatus(response, 200)
        evaluate.assert_called_once_with(self.domain, user=self.user, require_complete_visibility=True)
        self.assertEqual([row.ordinal for row in response.context["rack_position_rows"]], [0, 1])
        self.assertEqual(response.context["rack_position_rows"][0].rack, self.rack)
        self.assertIsNone(response.context["rack_position_rows"][1].rack)
        self.assertEqual(response.context["evaluation_state"], ProjectionState.READY)
        self.assertEqual(len(response.context["endpoint_rows"]), 1)
        self.assertEqual(response.context["endpoint_rows"][0].device, self.device)
        self.assertEqual(response.context["endpoint_rows"][0].coordinate.rack_ordinal, 0)
        self.assertEqual(response.context["diagnostics"], ())
        self.assertContains(response, "Vacant")
        self.assertContains(response, self.device.name)
        self.assertContains(response, "Rack 0 / Tray 1")

    def test_domain_detail_shows_one_diagnostic_list_and_hides_invalid_coordinates(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        self.grant_projection_permissions()

        response = self.client.get(self.domain.get_absolute_url())

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["evaluation_state"], ProjectionState.INVALID)
        self.assertEqual(len(response.context["endpoint_rows"]), 1)
        self.assertEqual(response.context["endpoint_rows"][0].device, self.device)
        self.assertIsNone(response.context["endpoint_rows"][0].coordinate)
        self.assertTrue(response.context["diagnostics"])
        self.assertContains(response, self.device.name)
        self.assertContains(response, "Unavailable", count=1)
        self.assertContains(response, "INCOMPATIBLE_DEVICE_TYPE", count=1)
        self.assertNotContains(response, "Rack 0 / Tray 1")

    def test_invalid_domain_detail_does_not_duplicate_domain_diagnostics_per_candidate(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=1, rack=self.rack)
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology,
            device_type=self.device_type,
        )
        second_device = type(self.device).objects.create(
            name="Second invalid Domain candidate",
            role=self.device.role,
            status=self.device.status,
            location=self.device.location,
            rack=self.rack,
            position=10,
            device_type=self.device_type,
        )
        self.grant_projection_permissions()

        response = self.client.get(self.domain.get_absolute_url())

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["evaluation_state"], ProjectionState.INVALID)
        self.assertEqual(
            {row.device for row in response.context["endpoint_rows"]},
            {self.device, second_device},
        )
        self.assertTrue(all(row.coordinate is None for row in response.context["endpoint_rows"]))
        self.assertContains(response, self.device.name)
        self.assertContains(response, second_device.name)
        self.assertContains(response, "Unavailable", count=2)
        self.assertContains(response, "NON_DENSE_RACK_ORDINALS", count=1)
        self.assertNotContains(response, "Rack 1 /")

    def test_domain_operation_buttons_require_change_permission(self):
        self.make_ready_projection()
        self.grant_projection_permissions()
        response = self.client.get(self.domain.get_absolute_url())
        self.assertNotContains(response, "Manage rack positions")

        self.add_permissions("nautobot_nvdatamodels.change_lpuc2cdomain")
        response = self.client.get(self.domain.get_absolute_url())
        self.assertContains(response, "Manage rack positions")

    def test_domain_operation_buttons_respect_constrained_change_permission(self):
        self.make_ready_projection()
        self.grant_projection_permissions()
        self.add_permissions(
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            constraints={"pk": self.other_domain.pk},
        )

        response = self.client.get(self.domain.get_absolute_url())

        self.assertHttpStatus(response, 200)
        self.assertNotContains(response, "Manage rack positions")
        self.assertNotContains(
            response,
            reverse(
                "plugins:nautobot_nvdatamodels:lpuc2c_endpoint_configuration",
                args=[self.device.pk],
            ),
        )

    def test_domain_activation_is_atomic_and_rolls_back_ordinary_edits_on_service_failure(self):
        self.make_ready_projection()
        self.grant_projection_permissions()
        self.grant_domain_form_permissions()
        active = Status.objects.get_for_model(models.LPUC2CDomain).get(name="Active")
        diagnostic = Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code="BECAME_INVALID",
            message="Projection became invalid during activation.",
            affected_objects=(ObjectReference(self.domain._meta.label_lower, self.domain.pk),),
        )
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_edit", args=[self.domain.pk])

        with patch(
            "nautobot_nvdatamodels.views.mutations.activate_domain",
            side_effect=mutations.InvalidTopologyProjection((diagnostic,)),
        ) as activate:
            response = self.client.post(
                url,
                self.domain_form_data(name="Must roll back", status=active.pk),
            )

        self.assertHttpStatus(response, 200)
        self.assertFalse(response.context["form"].errors, response.context["form"].errors.as_text())
        activate.assert_called_once()
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, "LPU C2C Domain")
        self.assertEqual(self.domain.status_id, self.planned_status.pk)
        self.assertContains(response, "Projection became invalid during activation")

    def test_domain_activation_service_runs_only_for_real_transition(self):
        self.make_ready_projection()
        self.grant_projection_permissions()
        self.grant_domain_form_permissions()
        active = Status.objects.get_for_model(models.LPUC2CDomain).get(name="Active")
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_edit", args=[self.domain.pk])

        with patch.object(mutations, "activate_domain", wraps=mutations.activate_domain) as activate:
            response = self.client.post(
                url,
                self.domain_form_data(name="Activated domain", status=active.pk),
            )
        self.assertHttpStatus(response, 302)
        activate.assert_called_once()
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, "Activated domain")
        self.assertEqual(self.domain.status_id, active.pk)

        with patch.object(mutations, "activate_domain") as activate:
            response = self.client.post(
                url,
                self.domain_form_data(name="Still active", status=active.pk),
            )
        self.assertHttpStatus(response, 302)
        activate.assert_not_called()
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, "Still active")

    def test_domain_edit_requires_active_to_transition_to_maintenance(self):
        active = Status.objects.get(name="LPU C2C Active")
        maintenance = Status.objects.get(name="LPU C2C Maintenance")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active)
        self.grant_domain_form_permissions()
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_edit", args=[self.domain.pk])

        response = self.client.post(url, self.domain_form_data(status=self.planned_status.pk))

        self.assertHttpStatus(response, 200)
        self.assertIn("status", response.context["form"].errors)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, active.pk)

        response = self.client.post(url, self.domain_form_data(status=maintenance.pk))

        self.assertHttpStatus(response, 302)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, maintenance.pk)

    def test_constrained_permission_rolls_back_activation_and_ordinary_edits(self):
        self.make_ready_projection()
        original_name = self.domain.name
        active = Status.objects.get_for_model(models.LPUC2CDomain).get(name="Active")
        self.grant_projection_permissions()
        self.add_permissions(
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            constraints={"name": original_name},
        )
        self.add_permissions("extras.view_status", "dcim.view_location", "tenancy.view_tenant")
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_edit", args=[self.domain.pk])

        with patch.object(mutations, "activate_domain", wraps=mutations.activate_domain) as activate:
            response = self.client.post(
                url,
                self.domain_form_data(name="Outside change permission", status=active.pk),
            )

        self.assertHttpStatus(response, 200)
        activate.assert_called_once()
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, original_name)
        self.assertEqual(self.domain.status_id, self.planned_status.pk)
        self.assertContains(response, "object-level permissions violation")

    def test_rack_operation_view_get_post_service_errors_and_safe_return(self):
        self.grant_domain_form_permissions()
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_rack_operation", args=[self.domain.pk])
        response = self.client.get(url)
        self.assertHttpStatus(response, 200)
        self.assertIsInstance(response.context["form"], forms.LPUC2CRackOperationForm)

        with patch.object(mutations, "append_position") as append:
            response = self.client.post(
                url,
                {"operation": "append", "return_url": "https://attacker.invalid/"},
            )
        append.assert_called_once()
        self.assertRedirects(response, self.domain.get_absolute_url(), fetch_redirect_response=False)

        with patch.object(
            mutations,
            "append_position",
            side_effect=ValidationError({"rack": "Rack changed concurrently."}),
        ):
            response = self.client.post(url, {"operation": "append"})
        self.assertHttpStatus(response, 200)
        self.assertContains(response, "Rack changed concurrently")

    def test_rack_operation_view_requires_domain_change_permission(self):
        self.add_permissions("nautobot_nvdatamodels.view_lpuc2cdomain")
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_rack_operation", args=[self.domain.pk])
        self.assertHttpStatus(self.client.get(url), 403)

    def test_rack_operation_rejects_hidden_rack_uuid_without_service_call(self):
        vacancy = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        self.add_permissions("nautobot_nvdatamodels.change_lpuc2cdomain")
        self.add_permissions("nautobot_nvdatamodels.view_lpuc2cdomainrackposition")
        self.add_permissions("dcim.view_rack", constraints={"pk": self.other_rack.pk})
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_rack_operation", args=[self.domain.pk])

        with patch.object(mutations, "fill_position") as fill:
            response = self.client.post(
                url,
                {"operation": "fill", "position": vacancy.pk, "rack": self.rack.pk},
            )

        self.assertHttpStatus(response, 200)
        fill.assert_not_called()
        self.assertIn("rack", response.context["form"].errors)

    def test_rack_operation_rejects_hidden_position_uuid_without_service_call(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        self.add_permissions("nautobot_nvdatamodels.change_lpuc2cdomain")
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            constraints={"pk": uuid4()},
        )
        self.add_permissions("dcim.view_rack")
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_rack_operation", args=[self.domain.pk])

        with patch.object(mutations, "vacate_position") as vacate:
            response = self.client.post(url, {"operation": "vacate", "position": position.pk})

        self.assertHttpStatus(response, 200)
        vacate.assert_not_called()
        self.assertIn("position", response.context["form"].errors)

    def test_device_first_rack_form_does_not_render_hidden_rack(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        self.add_permissions("nautobot_nvdatamodels.change_lpuc2cdomain")
        self.add_permissions("nautobot_nvdatamodels.view_lpuc2cdomainrackposition")
        self.add_permissions("dcim.view_device")
        self.add_permissions("dcim.view_rack", constraints={"pk": self.other_rack.pk})
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_rack_operation", args=[self.domain.pk])

        response = self.client.get(f"{url}?device={self.device.pk}")

        self.assertHttpStatus(response, 200)
        self.assertFalse(response.context["form"].fields["rack"].queryset.filter(pk=self.rack.pk).exists())

    def test_endpoint_configuration_view_delegates_device_first_write_and_removal(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        self.grant_domain_form_permissions()
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_device",
            "dcim.view_rack",
        )
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2c_endpoint_configuration", args=[self.device.pk])
        response = self.client.get(url)
        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["device"], self.device)

        with patch.object(mutations, "set_endpoint_configuration") as service:
            response = self.client.post(url, {"excluded": True})
        self.assertRedirects(response, self.device.get_absolute_url(), fetch_redirect_response=False)
        service.assert_called_once_with(
            self.device,
            position,
            excluded=True,
            tray_slot=None,
        )

        with patch.object(mutations, "set_endpoint_configuration") as service:
            response = self.client.post(url, {})
        self.assertHttpStatus(response, 302)
        service.assert_called_once()

    def test_endpoint_configuration_view_rejects_inaccessible_candidate_domain(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        self.add_permissions("nautobot_nvdatamodels.change_lpuc2cdomain", constraints={"pk": uuid4()})
        self.add_permissions("dcim.view_device")
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2c_endpoint_configuration", args=[self.device.pk])
        self.assertHttpStatus(self.client.get(url), 404)

    def test_endpoint_configuration_rejects_hidden_position_without_service_call(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        self.add_permissions("nautobot_nvdatamodels.change_lpuc2cdomain")
        self.add_permissions("dcim.view_device", "dcim.view_rack")
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            constraints={"pk": uuid4()},
        )
        url = reverse("plugins:nautobot_nvdatamodels:lpuc2c_endpoint_configuration", args=[self.device.pk])

        with patch.object(mutations, "set_endpoint_configuration") as service:
            response = self.client.post(url, {"excluded": True})

        self.assertHttpStatus(response, 404)
        service.assert_not_called()

    def test_workflow_views_map_service_object_races_to_retry_errors(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        self.grant_domain_form_permissions()
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_device",
            "dcim.view_rack",
        )
        rack_url = reverse("plugins:nautobot_nvdatamodels:lpuc2cdomain_rack_operation", args=[self.domain.pk])
        endpoint_url = reverse(
            "plugins:nautobot_nvdatamodels:lpuc2c_endpoint_configuration", args=[self.device.pk]
        )

        with patch.object(mutations, "append_position", side_effect=models.LPUC2CDomain.DoesNotExist):
            rack_response = self.client.post(rack_url, {"operation": "append"})
        with patch.object(
            mutations,
            "set_endpoint_configuration",
            side_effect=models.LPUC2CDomainRackPosition.DoesNotExist,
        ):
            endpoint_response = self.client.post(endpoint_url, {"excluded": True})

        self.assertHttpStatus(rack_response, 200)
        self.assertContains(rack_response, "changed concurrently; retry")
        self.assertHttpStatus(endpoint_response, 200)
        self.assertContains(endpoint_response, "changed concurrently; retry")

    def test_domain_detail_uses_projection_tables_as_single_display_definition(self):
        template_source = get_template("nautobot_nvdatamodels/lpuc2cdomain_retrieve.html").template.source

        self.assertIn("{% render_table rack_position_table %}", template_source)
        self.assertIn("{% render_table endpoint_table %}", template_source)
        self.assertNotIn("for row in rack_position_rows", template_source)
        self.assertNotIn("for row in endpoint_rows", template_source)
        self.assertIn("actions", tables.LPUC2CEndpointProjectionTable.base_columns)

    def test_tables_and_navigation_expose_domains_but_not_stored_memberships(self):
        self.assertIs(tables.LPUC2CDomainTable._meta.model, models.LPUC2CDomain)
        self.assertIsNone(tables.LPUC2CRackPositionProjectionTable._meta.model)
        self.assertIsNone(tables.LPUC2CEndpointProjectionTable._meta.model)
        item = next(item for item in navigation.items if item.name == "LPU C2C Domains")
        self.assertEqual(item.permissions, {"nautobot_nvdatamodels.view_lpuc2cdomain"})
        self.assertEqual(item.buttons[0].permissions, {"nautobot_nvdatamodels.add_lpuc2cdomain"})


class DeviceNVIDIAContentTestCase(TestCase):
    """The Device extension evaluates at most one visible candidate Domain."""

    @classmethod
    def setUpTestData(cls):
        fixtures.lpu_c2c_test_data(cls)

    def grant_projection_permissions(self):
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.view_lpuc2cdevicetypecompatibility",
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "dcim.view_rack",
            "dcim.view_device",
        )

    def render_extension(self):
        request = RequestFactory().get(self.device.get_absolute_url())
        request.user = self.user
        return DeviceNVIDIAContent(
            {"object": self.device, "request": request, "perms": PermWrapper(self.user)}
        ).right_page()

    def make_candidate(self, *, compatible=True):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        if compatible:
            models.LPUC2CDeviceTypeCompatibility.objects.create(
                topology=self.domain.topology, device_type=self.device_type
            )
        return position

    def test_ready_device_shows_domain_and_coordinate_after_one_evaluation(self):
        self.make_candidate()
        self.grant_projection_permissions()
        with patch(
            "nautobot_nvdatamodels.template_content.evaluate_domain",
            wraps=evaluator.evaluate_domain,
        ) as evaluate:
            content = self.render_extension()

        evaluate.assert_called_once_with(self.domain, user=self.user, require_complete_visibility=True)
        self.assertIn(self.domain.get_absolute_url(), content)
        self.assertIn("Rack 0 / Tray 1", content)
        self.assertIn("ready", content)

    def test_device_endpoint_button_respects_constrained_domain_change_permission(self):
        self.make_candidate()
        self.grant_projection_permissions()
        self.add_permissions(
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            constraints={"pk": self.other_domain.pk},
        )

        content = self.render_extension()

        self.assertIn(self.domain.get_absolute_url(), content)
        self.assertNotIn(
            reverse(
                "plugins:nautobot_nvdatamodels:lpuc2c_endpoint_configuration",
                args=[self.device.pk],
            ),
            content,
        )

    def test_invalid_device_shows_domain_state_and_diagnostics_without_coordinate(self):
        self.make_candidate(compatible=False)
        self.grant_projection_permissions()
        content = self.render_extension()

        self.assertIn(self.domain.get_absolute_url(), content)
        self.assertIn("invalid", content)
        self.assertIn("INCOMPATIBLE_DEVICE_TYPE", content)
        self.assertNotIn("Rack 0 / Tray 1", content)

    def test_excluded_device_shows_no_membership_or_relationship(self):
        position = self.make_candidate()
        models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        self.grant_projection_permissions()
        content = self.render_extension()

        self.assertNotIn(self.domain.get_absolute_url(), content)
        self.assertNotIn("INCOMPATIBLE_DEVICE_TYPE", content)

    def test_device_without_domain_does_not_evaluate_any_domain(self):
        self.grant_projection_permissions()
        with patch("nautobot_nvdatamodels.template_content.evaluate_domain") as evaluate:
            content = self.render_extension()

        evaluate.assert_not_called()
        self.assertNotIn(self.domain.get_absolute_url(), content)

    def test_inaccessible_candidate_domain_is_not_evaluated_or_leaked(self):
        self.make_candidate()
        self.add_permissions("dcim.view_device")
        with patch("nautobot_nvdatamodels.template_content.evaluate_domain") as evaluate:
            content = self.render_extension()

        evaluate.assert_not_called()
        self.assertNotIn(self.domain.get_absolute_url(), content)
