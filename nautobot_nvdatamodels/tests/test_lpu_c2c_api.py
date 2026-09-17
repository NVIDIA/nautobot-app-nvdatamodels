#  SPDX-FileCopyrightText: Copyright (c) "2025" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Unit tests for the LPU C2C API."""

from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse
from drf_spectacular.generators import SchemaGenerator
from nautobot.core.testing import APITestCase
from nautobot.dcim.models import Rack
from nautobot.extras.models import Status
from nautobot.tenancy.models import Tenant
from rest_framework import status

from nautobot_nvdatamodels import choices, models
from nautobot_nvdatamodels.api import serializers
from nautobot_nvdatamodels.lpu_c2c import mutations
from nautobot_nvdatamodels.tests import fixtures


class LPUC2CAPIViewTestCase(APITestCase):
    """Test the LPU C2C API routes."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        fixtures.lpu_c2c_test_data(cls)

    def test_domain_list_and_detail_routes(self):
        """Domain list and detail routes have stable URLs."""
        self.assertEqual(
            reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-list"),
            "/api/plugins/nvdatamodels/lpu-c2c-domains/",
        )
        self.assertEqual(
            reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-detail", args=[self.domain.pk]),
            f"/api/plugins/nvdatamodels/lpu-c2c-domains/{self.domain.pk}/",
        )

    def test_topology_projection_route(self):
        """Topology projection has a stable domain action URL."""
        self.assertEqual(
            reverse(
                "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-topology-projection",
                args=[self.domain.pk],
            ),
            f"/api/plugins/nvdatamodels/lpu-c2c-domains/{self.domain.pk}/topology-projection/",
        )

    def test_rack_position_list_route(self):
        """Rack-position list has the exact public URL."""
        self.assertEqual(
            reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomainrackposition-list"),
            "/api/plugins/nvdatamodels/lpu-c2c-rack-positions/",
        )

    def test_rack_position_operation_route(self):
        """Rack-position mutation has a stable domain action URL."""
        self.assertEqual(
            reverse(
                "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
                args=[self.domain.pk],
            ),
            f"/api/plugins/nvdatamodels/lpu-c2c-domains/{self.domain.pk}/rack-position-operation/",
        )

    def test_device_type_compatibility_routes(self):
        """Device-type compatibility CRUD has the exact public URL."""
        self.assertEqual(
            reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdevicetypecompatibility-list"),
            "/api/plugins/nvdatamodels/lpu-c2c-device-type-compatibilities/",
        )

    def test_endpoint_configuration_routes(self):
        """Endpoint-configuration CRUD has the exact public URL."""
        self.assertEqual(
            reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-list"),
            "/api/plugins/nvdatamodels/lpu-c2c-endpoint-configurations/",
        )

    def test_openapi_schema_includes_endpoint_configuration_routes(self):
        """Schema generation supports the endpoint configuration API."""
        schema = SchemaGenerator().get_schema(request=None, public=True)

        self.assertIn(
            "/plugins/nvdatamodels/lpu-c2c-endpoint-configurations/",
            schema["paths"],
        )

    def test_rack_positions_reject_all_generic_writes(self):
        """Rack positions are immutable through the generic REST endpoint."""
        position = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomainrackposition-list")
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomainrackposition-detail", args=[position.pk]
        )
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.change_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.delete_lpuc2cdomainrackposition",
        )
        requests = (
            ("post", list_url, {"domain": self.domain.pk, "ordinal": 1}),
            ("patch", detail_url, {"ordinal": 1}),
            ("put", detail_url, {"domain": self.domain.pk, "ordinal": 1}),
            ("delete", detail_url, None),
        )

        for method, url, data in requests:
            with self.subTest(method=method):
                response = getattr(self.client, method)(url, data, format="json", **self.header)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_domain_crud_and_rack_position_reads_use_normalized_api_fields(self):
        """Actual API reads and Domain create expose only normalized model fields."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "extras.view_status",
            "dcim.view_location",
        )
        domain_list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-list")
        create_response = self.client.post(
            domain_list_url,
            {
                "name": "LPU C2C API Created Domain",
                "location": self.location.pk,
                "status": self.planned_status.pk,
                "topology": choices.LPUC2CTopologyChoices.LP30_C2C,
            },
            format="json",
            **self.header,
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        obsolete_fields = {"role", "rack", "rack_group", "cluster_id"}
        self.assertTrue(obsolete_fields.isdisjoint(create_response.data))
        self.assertTrue(
            {"id", "name", "location", "tenant", "status", "topology"} <= set(create_response.data)
        )

        domain_detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-detail",
            args=[create_response.data["id"]],
        )
        domain_list_response = self.client.get(domain_list_url, **self.header)
        domain_detail_response = self.client.get(domain_detail_url, **self.header)
        self.assertEqual(domain_list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(domain_detail_response.status_code, status.HTTP_200_OK)
        self.assertTrue(obsolete_fields.isdisjoint(domain_detail_response.data))

        position_list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomainrackposition-list")
        position_detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomainrackposition-detail",
            args=[position.pk],
        )
        position_list_response = self.client.get(position_list_url, **self.header)
        position_detail_response = self.client.get(position_detail_url, **self.header)
        self.assertEqual(position_list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(position_detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {"domain", "ordinal", "rack"} & set(position_detail_response.data),
            {"domain", "ordinal", "rack"},
        )

    def test_domain_create_rejects_active_status(self):
        """REST creation cannot bypass the controlled activation workflow."""
        active = Status.objects.get(name="LPU C2C Active")
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cdomain",
            "extras.view_status",
            "dcim.view_location",
        )
        url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-list")

        response = self.client.post(
            url,
            {
                "name": "Active API Created Domain",
                "location": self.location.pk,
                "status": active.pk,
                "topology": choices.LPUC2CTopologyChoices.LP30_C2C,
            },
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("status", response.data)
        self.assertFalse(models.LPUC2CDomain.objects.filter(name="Active API Created Domain").exists())

    def test_invalid_topology_projection_returns_diagnostics_with_http_200(self):
        """An invalid live topology is data, not an HTTP conflict."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_rack",
            "dcim.view_device",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-topology-projection",
            args=[self.domain.pk],
        )

        response = self.client.get(url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["state"], "invalid")
        self.assertIsNone(response.data["projection"])
        self.assertTrue(response.data["diagnostics"])
        self.assertTrue(all("severity" in diagnostic for diagnostic in response.data["diagnostics"]))
        affected_object = response.data["diagnostics"][0]["affected_objects"][0]
        self.assertEqual(set(affected_object), {"object_type", "id", "display"})

    def test_projection_output_validates_through_typed_envelope_serializer(self):
        """Projection transport shape is explicit and preserves stable object types."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_rack",
            "dcim.view_device",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-topology-projection",
            args=[self.domain.pk],
        )
        response = self.client.get(url, **self.header)

        envelope = serializers.LPUC2CProjectionEnvelopeSerializer(data=response.data)

        self.assertTrue(envelope.is_valid(), envelope.errors)
        self.assertEqual(response.data["domain"]["object_type"], "nautobot_nvdatamodels.lpuc2cdomain")
        self.assertTrue(
            all(
                reference["object_type"]
                for diagnostic in response.data["diagnostics"]
                for reference in diagnostic["affected_objects"]
            )
        )

    def test_domain_serializer_excludes_obsolete_prototype_fields(self):
        """Domain CRUD exposes only fields from the normalized domain model."""
        field_names = set(serializers.LPUC2CDomainSerializer(instance=self.domain).fields)

        self.assertTrue({"id", "name", "location", "tenant", "status", "topology"} <= field_names)
        self.assertTrue({"role", "rack", "rack_group", "cluster_id"}.isdisjoint(field_names))

    def test_ready_topology_projection_serializes_domain_racks_and_endpoints(self):
        """A ready evaluation returns complete object-reference projection data."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.view_lpuc2cdevicetypecompatibility",
            "dcim.view_rack",
            "dcim.view_device",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-topology-projection",
            args=[self.domain.pk],
        )

        response = self.client.get(url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["state"], "ready")
        self.assertEqual(
            response.data["domain"],
            {
                "object_type": "nautobot_nvdatamodels.lpuc2cdomain",
                "id": str(self.domain.pk),
                "display": self.domain.name,
            },
        )
        self.assertEqual(response.data["diagnostics"], [])
        projection = response.data["projection"]
        self.assertEqual(projection["rack_positions"][0]["position"]["id"], str(position.pk))
        self.assertEqual(projection["rack_positions"][0]["rack"]["id"], str(self.rack.pk))
        self.assertEqual(projection["endpoints"][0]["device"]["id"], str(self.device.pk))
        self.assertEqual(
            projection["endpoints"][0]["coordinate"],
            {"rack_ordinal": 0, "tray_slot": 1},
        )
        self.assertNotIn("diagnostics", projection)
        self.assertNotIn("diagnostics", projection["endpoints"][0])

    def test_projection_returns_403_without_any_partial_data_when_a_source_is_hidden(self):
        """Projection authorization is all-or-nothing across every source object."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.view_lpuc2cdevicetypecompatibility",
            "dcim.view_rack",
            "dcim.view_device",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-topology-projection",
            args=[self.domain.pk],
        )

        with patch.object(Rack.objects, "restrict", return_value=Rack.objects.exclude(pk=self.rack.pk)):
            response = self.client.get(url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        rendered_response = str(response.data)
        self.assertNotIn(str(self.rack.pk), rendered_response)
        self.assertNotIn(self.rack.name, rendered_response)
        self.assertNotIn(str(self.device.pk), rendered_response)
        self.assertNotIn(self.device.name, rendered_response)

    def test_projection_returns_403_when_relevant_compatibility_is_hidden(self):
        """A hidden compatibility row that affected evaluation fail-closes the envelope."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        compatibility = models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology,
            device_type=self.device_type,
        )
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.view_lpuc2cdevicetypecompatibility",
            "dcim.view_rack",
            "dcim.view_device",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-topology-projection",
            args=[self.domain.pk],
        )

        with patch.object(
            models.LPUC2CDeviceTypeCompatibility.objects,
            "restrict",
            return_value=models.LPUC2CDeviceTypeCompatibility.objects.exclude(pk=compatibility.pk),
        ):
            response = self.client.get(url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        rendered_response = str(response.data)
        self.assertNotIn(str(compatibility.pk), rendered_response)
        self.assertNotIn(str(self.device.pk), rendered_response)
        self.assertNotIn(self.device.name, rendered_response)

    def test_projection_returns_404_for_missing_domain(self):
        """A nonexistent Domain remains an ordinary not-found response."""
        self.add_permissions("nautobot_nvdatamodels.view_lpuc2cdomain")
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-topology-projection",
            args=[uuid4()],
        )

        response = self.client.get(url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_endpoint_configuration_generic_writes_delegate_to_mutation_service(self):
        """Generic endpoint writes cannot bypass lifecycle-safe mutation logic."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-list")
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.change_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.delete_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_device",
        )

        with patch.object(
            mutations,
            "set_endpoint_configuration",
            wraps=mutations.set_endpoint_configuration,
        ) as service:
            response = self.client.post(
                list_url,
                {"device": self.device.pk, "rack_position": position.pk, "excluded": True},
                format="json",
                **self.header,
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            self.assertEqual(service.call_count, 1)

            configuration = models.LPUC2CEndpointConfiguration.objects.get(device=self.device)
            detail_url = reverse(
                "plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-detail",
                args=[configuration.pk],
            )
            response = self.client.patch(detail_url, {"excluded": True}, format="json", **self.header)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(service.call_count, 2)

            response = self.client.delete(detail_url, **self.header)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(service.call_count, 3)

    def test_endpoint_configuration_post_rejects_noop(self):
        """A single create must represent an exclusion or coordinate override."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_device",
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-list")

        with patch.object(
            mutations,
            "set_endpoint_configuration",
            wraps=mutations.set_endpoint_configuration,
        ) as service:
            response = self.client.post(
                list_url,
                {"device": self.device.pk, "rack_position": position.pk, "excluded": False},
                format="json",
                **self.header,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        service.assert_not_called()
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.exists())

    def test_endpoint_configuration_writes_accept_scheduler_tray_slots(self):
        """REST writes persist one-based rack-wide LP30 tray-slot overrides."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.change_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_device",
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-list")

        response = self.client.post(
            list_url,
            {"device": self.device.pk, "rack_position": position.pk, "tray_slot": 16},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["tray_slot"], 16)
        configuration = models.LPUC2CEndpointConfiguration.objects.get(device=self.device)
        self.assertEqual(configuration.tray_slot, 16)

        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-detail",
            args=[configuration.pk],
        )
        response = self.client.patch(detail_url, {"tray_slot": 1}, format="json", **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["tray_slot"], 1)
        configuration.refresh_from_db()
        self.assertEqual(configuration.tray_slot, 1)

    def test_endpoint_configuration_bulk_post_rejects_noop(self):
        """Bulk create rejects no-op rows before invoking mutation services."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_device",
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-list")

        with patch.object(
            mutations,
            "set_endpoint_configuration",
            wraps=mutations.set_endpoint_configuration,
        ) as service:
            response = self.client.post(
                list_url,
                [{"device": self.device.pk, "rack_position": position.pk, "excluded": False}],
                format="json",
                **self.header,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        service.assert_not_called()
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.exists())

    def test_endpoint_configuration_delete_cannot_bypass_active_domain_lifecycle(self):
        """Generic DELETE delegates through the service even for an Active domain."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        active_status = Status.objects.get(name="LPU C2C Active")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active_status)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.delete_lpuc2cendpointconfiguration",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-detail",
            args=[configuration.pk],
        )

        response = self.client.delete(detail_url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(models.LPUC2CEndpointConfiguration.objects.filter(pk=configuration.pk).exists())

    def test_endpoint_configuration_patch_cannot_bypass_active_domain_lifecycle(self):
        """Generic PATCH cannot mutate endpoint configuration on an Active domain."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        active_status = Status.objects.get(name="LPU C2C Active")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active_status)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.change_lpuc2cendpointconfiguration",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-detail",
            args=[configuration.pk],
        )

        response = self.client.patch(detail_url, {"tray_slot": 2}, format="json", **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        configuration.refresh_from_db()
        self.assertTrue(configuration.excluded)
        self.assertIsNone(configuration.tray_slot)

    def test_endpoint_configuration_patch_rejects_identity_reassignment(self):
        """A detail PATCH cannot retarget its configuration to a mutable domain."""
        source_position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        target_position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.other_domain, ordinal=0, rack=self.other_rack
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=source_position, excluded=True
        )
        active_status = Status.objects.get(name="LPU C2C Active")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active_status)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.change_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "dcim.view_device",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-detail",
            args=[configuration.pk],
        )

        response = self.client.patch(
            detail_url,
            {"device": self.other_device.pk, "rack_position": target_position.pk},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        configuration.refresh_from_db()
        self.assertEqual(configuration.device_id, self.device.pk)
        self.assertEqual(configuration.rack_position_id, source_position.pk)
        self.assertEqual(models.LPUC2CEndpointConfiguration.objects.count(), 1)

    def test_endpoint_configuration_patch_rolls_back_object_permission_violation(self):
        """A PATCH cannot move a configuration outside its change constraint."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        self.add_permissions("nautobot_nvdatamodels.view_lpuc2cendpointconfiguration")
        self.add_permissions(
            "nautobot_nvdatamodels.change_lpuc2cendpointconfiguration",
            constraints={"excluded": True},
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-detail",
            args=[configuration.pk],
        )

        response = self.client.patch(
            detail_url,
            {"excluded": False, "tray_slot": 2},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        configuration.refresh_from_db()
        self.assertTrue(configuration.excluded)
        self.assertIsNone(configuration.tray_slot)

    def test_endpoint_configuration_patch_returns_204_when_service_removes_noop(self):
        """A PATCH that removes the exception has an intentional empty response."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.change_lpuc2cendpointconfiguration",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-detail",
            args=[configuration.pk],
        )

        response = self.client.patch(detail_url, {"excluded": False}, format="json", **self.header)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.filter(pk=configuration.pk).exists())

    def test_endpoint_configuration_bulk_write_routes_are_not_exposed(self):
        """List-level PATCH and DELETE cannot bypass endpoint mutation services."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        self.add_permissions(
            "nautobot_nvdatamodels.change_lpuc2cendpointconfiguration",
            "nautobot_nvdatamodels.delete_lpuc2cendpointconfiguration",
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-list")

        patch_response = self.client.patch(
            list_url,
            [{"id": str(configuration.pk), "excluded": False}],
            format="json",
            **self.header,
        )
        put_response = self.client.put(
            list_url,
            [{"id": str(configuration.pk), "excluded": False}],
            format="json",
            **self.header,
        )
        delete_response = self.client.delete(list_url, **self.header)

        self.assertEqual(patch_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(put_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(delete_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(models.LPUC2CEndpointConfiguration.objects.filter(pk=configuration.pk).exists())

    def test_invalid_domain_activation_rolls_back_all_patch_changes(self):
        """Activation and accompanying field updates are one atomic operation."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        active_status = Status.objects.get(name="LPU C2C Active")
        original_name = self.domain.name
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "extras.view_status",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-detail", args=[self.domain.pk]
        )

        response = self.client.patch(
            detail_url,
            {"name": "Must Roll Back", "status": active_status.pk},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertTrue(response.data["diagnostics"])
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, original_name)
        self.assertEqual(self.domain.status_id, self.planned_status.pk)

    def test_ready_domain_activation_delegates_to_mutation_service(self):
        """A valid status transition to Active uses controlled activation."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )
        active_status = Status.objects.get(name="LPU C2C Active")
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "extras.view_status",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-detail", args=[self.domain.pk]
        )

        with patch.object(mutations, "activate_domain", wraps=mutations.activate_domain) as service:
            response = self.client.patch(
                detail_url, {"status": active_status.pk}, format="json", **self.header
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        service.assert_called_once()
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status.name.removeprefix("LPU C2C "), "Active")

    def test_already_active_domain_patch_does_not_reactivate(self):
        """PATCHing canonical Active onto an Active domain is an ordinary update."""
        active_status = Status.objects.get(name="LPU C2C Active")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active_status)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "extras.view_status",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-detail", args=[self.domain.pk]
        )

        with patch.object(mutations, "activate_domain", wraps=mutations.activate_domain) as service:
            response = self.client.patch(
                detail_url,
                {"name": "Still Active Domain", "status": active_status.pk},
                format="json",
                **self.header,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        service.assert_not_called()
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, "Still Active Domain")
        self.assertEqual(self.domain.status_id, active_status.pk)

    def test_domain_patch_requires_active_to_transition_to_maintenance(self):
        active = Status.objects.get(name="LPU C2C Active")
        maintenance = Status.objects.get(name="LPU C2C Maintenance")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "extras.view_status",
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-detail", args=[self.domain.pk]
        )

        response = self.client.patch(
            detail_url,
            {"status": self.planned_status.pk},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("status", response.data)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, active.pk)

        response = self.client.patch(
            detail_url,
            {"status": maintenance.pk},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, maintenance.pk)

    def test_domain_patch_rolls_back_object_permission_violation(self):
        """A PATCH cannot move a Domain outside its change constraint."""
        original_name = self.domain.name
        self.add_permissions("nautobot_nvdatamodels.view_lpuc2cdomain")
        self.add_permissions(
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            constraints={"name": original_name},
        )
        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-detail", args=[self.domain.pk]
        )

        response = self.client.patch(
            detail_url,
            {"name": "Outside Domain Permission"},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, original_name)

    def test_domain_bulk_activation_route_is_not_exposed(self):
        """List-level PATCH cannot bypass controlled activation."""
        active_status = Status.objects.get(name="LPU C2C Active")
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "extras.view_status",
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-list")

        response = self.client.patch(
            list_url,
            [{"id": str(self.domain.pk), "status": active_status.pk}],
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, self.planned_status.pk)

    def test_device_type_compatibility_supports_crud_and_rejects_duplicate_pair(self):
        """Compatibility CRUD preserves the topology/device-type unique pair."""
        self.add_permissions(
            "nautobot_nvdatamodels.add_lpuc2cdevicetypecompatibility",
            "nautobot_nvdatamodels.view_lpuc2cdevicetypecompatibility",
            "nautobot_nvdatamodels.change_lpuc2cdevicetypecompatibility",
            "nautobot_nvdatamodels.delete_lpuc2cdevicetypecompatibility",
            "dcim.view_devicetype",
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdevicetypecompatibility-list")
        payload = {"topology": self.domain.topology, "device_type": self.device_type.pk}

        create_response = self.client.post(list_url, payload, format="json", **self.header)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        duplicate_response = self.client.post(list_url, payload, format="json", **self.header)
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)

        detail_url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdevicetypecompatibility-detail",
            args=[create_response.data["id"]],
        )
        delete_response = self.client.delete(detail_url, **self.header)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_domain_filters_cover_location_tenant_status_topology_and_name_search(self):
        """Domain list filters expose each supported discovery dimension."""
        tenant = Tenant.objects.create(name="LPU C2C Filter Tenant")
        maintenance_status = Status.objects.get(name="LPU C2C Maintenance")
        models.LPUC2CDomain.objects.filter(pk=self.other_domain.pk).update(
            location=self.other_location,
            tenant=tenant,
            status=maintenance_status,
        )
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "tenancy.view_tenant",
        )
        list_url = reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-list")
        filters = (
            ({"q": self.domain.name}, {str(self.domain.pk)}),
            ({"location": self.location.pk}, {str(self.domain.pk)}),
            ({"tenant": tenant.pk}, {str(self.other_domain.pk)}),
            ({"status": self.planned_status.pk}, {str(self.domain.pk)}),
            ({"topology": self.domain.topology}, {str(self.domain.pk), str(self.other_domain.pk)}),
        )

        for query, expected_ids in filters:
            with self.subTest(query=query):
                response = self.client.get(list_url, query, **self.header)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual({item["id"] for item in response.data["results"]}, expected_ids)

    def test_supporting_model_filters_cover_their_domain_relationships(self):
        """Rack positions, compatibilities, and endpoint configurations have simple filters."""
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        other_position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.other_domain, ordinal=0, rack=self.other_rack
        )
        compatibility = models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )
        configuration = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        models.LPUC2CEndpointConfiguration.objects.create(
            device=self.other_device, rack_position=other_position, excluded=True
        )
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomainrackposition",
            "nautobot_nvdatamodels.view_lpuc2cdevicetypecompatibility",
            "nautobot_nvdatamodels.view_lpuc2cendpointconfiguration",
        )
        cases = (
            (
                reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdomainrackposition-list"),
                {"domain": self.domain.pk},
                str(position.pk),
            ),
            (
                reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cdevicetypecompatibility-list"),
                {"topology": self.domain.topology},
                str(compatibility.pk),
            ),
            (
                reverse("plugins-api:nautobot_nvdatamodels-api:lpuc2cendpointconfiguration-list"),
                {"device": self.device.pk},
                str(configuration.pk),
            ),
        )

        for url, query, expected_id in cases:
            with self.subTest(url=url):
                response = self.client.get(url, query, **self.header)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual([item["id"] for item in response.data["results"]], [expected_id])

    def test_rack_position_action_dispatches_all_six_operations_to_mutation_service(self):
        """The domain action is a thin dispatcher over controlled mutations."""
        position = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "dcim.view_rack",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )
        operations = (
            (
                "append_position",
                {"operation": "append", "rack": self.rack.pk},
                (self.domain,),
                {"rack": self.rack},
            ),
            (
                "fill_position",
                {"operation": "fill", "ordinal": 0, "rack": self.rack.pk},
                (position, self.rack),
                {},
            ),
            (
                "vacate_position",
                {"operation": "vacate", "ordinal": 0},
                (position,),
                {},
            ),
            (
                "remove_and_compact_position",
                {"operation": "remove_and_compact", "ordinal": 0, "confirmed": True},
                (position,),
                {"confirmed": True},
            ),
            (
                "insert_position",
                {"operation": "insert", "ordinal": 0, "rack": self.rack.pk, "confirmed": True},
                (self.domain, 0, self.rack),
                {"confirmed": True},
            ),
            (
                "reorder_positions",
                {"operation": "reorder", "ordering": [0], "confirmed": True},
                (self.domain, [position.pk]),
                {"confirmed": True},
            ),
        )

        for service_name, payload, expected_args, expected_kwargs in operations:
            with (
                self.subTest(operation=payload["operation"]),
                patch.object(mutations, service_name, return_value=None) as service,
            ):
                response = self.client.post(url, payload, format="json", **self.header)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                service.assert_called_once_with(*expected_args, **expected_kwargs)

    def test_rack_position_action_rejects_inapplicable_operation_fields(self):
        """Recognized fields are accepted only for the operations that consume them."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "dcim.view_rack",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )
        cases = (
            ("append_position", {"operation": "append", "ordinal": 0}),
            (
                "fill_position",
                {"operation": "fill", "ordinal": 0, "rack": self.rack.pk, "ordering": [0]},
            ),
            ("vacate_position", {"operation": "vacate", "ordinal": 0, "rack": self.rack.pk}),
            (
                "remove_and_compact_position",
                {"operation": "remove_and_compact", "ordinal": 0, "rack": self.rack.pk},
            ),
            (
                "insert_position",
                {"operation": "insert", "ordinal": 0, "ordering": [0], "confirmed": True},
            ),
            (
                "reorder_positions",
                {"operation": "reorder", "ordering": [0], "rack": self.rack.pk, "confirmed": True},
            ),
        )

        for service_name, payload in cases:
            with (
                self.subTest(operation=payload["operation"]),
                patch.object(mutations, service_name, return_value=None) as service,
            ):
                response = self.client.post(url, payload, format="json", **self.header)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                service.assert_not_called()

        self.assertEqual(models.LPUC2CDomainRackPosition.objects.filter(domain=self.domain).count(), 1)

    def test_rack_position_action_maps_missing_confirmation_to_http_400(self):
        """Confirmation-required service errors become client errors."""
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )
        payloads = (
            {"operation": "remove_and_compact", "ordinal": 0},
            {"operation": "insert", "ordinal": 0},
            {"operation": "reorder", "ordering": [0]},
        )

        for payload in payloads:
            with self.subTest(operation=payload["operation"]):
                response = self.client.post(url, payload, format="json", **self.header)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rack_position_action_maps_active_domain_lifecycle_violation_to_http_400(self):
        """An Active domain cannot be mutated through the REST action."""
        active_status = Status.objects.get(name="LPU C2C Active")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active_status)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "dcim.view_rack",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )

        response = self.client.post(
            url, {"operation": "append", "rack": self.rack.pk}, format="json", **self.header
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.LPUC2CDomainRackPosition.objects.filter(domain=self.domain).exists())

    def test_rack_position_action_rejects_rack_hidden_by_object_permissions(self):
        """A Rack outside the caller's visible queryset cannot enter an operation."""
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
        )
        self.add_permissions("dcim.view_rack", constraints={"name": self.other_rack.name})
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )

        response = self.client.post(
            url,
            {"operation": "append", "rack": self.rack.pk},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("rack", response.data)
        self.assertFalse(models.LPUC2CDomainRackPosition.objects.filter(domain=self.domain).exists())

    def test_rack_position_action_rejects_position_from_another_domain(self):
        """A detail action cannot target a position outside its URL domain."""
        other_position = models.LPUC2CDomainRackPosition.objects.create(domain=self.other_domain, ordinal=0)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
            "dcim.view_rack",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )
        payloads = (
            {"operation": "fill", "ordinal": 0, "rack": self.rack.pk},
            {"operation": "vacate", "ordinal": 0},
            {
                "operation": "remove_and_compact",
                "ordinal": 0,
                "confirmed": True,
            },
        )

        for payload in payloads:
            with self.subTest(operation=payload["operation"]):
                response = self.client.post(url, payload, format="json", **self.header)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        other_position.refresh_from_db()
        self.assertIsNone(other_position.rack_id)

    def test_rack_position_action_rejects_malformed_or_missing_operation_inputs(self):
        """Operation payloads are validated before reaching mutation services."""
        position = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )
        payloads = (
            {"operation": "fill", "ordinal": "not-an-integer", "rack": "not-a-uuid"},
            {"operation": "insert"},
            {"operation": "reorder"},
            {"operation": "vacate", "position": position.pk},
            {"operation": "unknown"},
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(url, payload, format="json", **self.header)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rack_position_action_rejects_unknown_payload_keys(self):
        """The operation action rejects deprecated or otherwise unknown fields."""
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )

        response = self.client.post(
            url,
            {"operation": "append", "position": uuid4()},
            format="json",
            **self.header,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.LPUC2CDomainRackPosition.objects.filter(domain=self.domain).exists())

    def test_rack_position_action_rejects_non_object_payload(self):
        """Malformed JSON container types produce a client error without mutation."""
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )

        response = self.client.post(url, [{}], format="json", **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.LPUC2CDomainRackPosition.objects.filter(domain=self.domain).exists())

    def test_rack_position_action_uses_change_permission(self):
        """View and change permissions authorize the POST detail operation."""
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.change_lpuc2cdomain",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )

        response = self.client.post(url, {"operation": "append"}, format="json", **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(models.LPUC2CDomainRackPosition.objects.filter(domain=self.domain).count(), 1)

    def test_rack_position_action_rejects_add_without_change_permission(self):
        """Add permission cannot authorize a mutation of an existing domain."""
        self.add_permissions(
            "nautobot_nvdatamodels.view_lpuc2cdomain",
            "nautobot_nvdatamodels.add_lpuc2cdomain",
        )
        url = reverse(
            "plugins-api:nautobot_nvdatamodels-api:lpuc2cdomain-rack-position-operation",
            args=[self.domain.pk],
        )

        response = self.client.post(url, {"operation": "append"}, format="json", **self.header)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(models.LPUC2CDomainRackPosition.objects.filter(domain=self.domain).exists())
