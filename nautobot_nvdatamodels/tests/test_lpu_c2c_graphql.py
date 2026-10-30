#  SPDX-FileCopyrightText: Copyright (c) "2026" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Tests for the LPU C2C GraphQL projection."""

import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import graphene
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from nautobot.core.graphql import execute_query
from nautobot.core.testing import TestCase
from nautobot.dcim.models import Device, Location, Rack
from nautobot.extras.models import Role
from nautobot.users.models import ObjectPermission
from promise import Promise

from nautobot_nvdatamodels import choices, models
from nautobot_nvdatamodels.graphql import types as graphql_types
from nautobot_nvdatamodels.graphql.loaders import DomainEvaluationLoader, get_lpu_c2c_loaders
from nautobot_nvdatamodels.graphql.types import install_device_type_lpu_c2c_shim
from nautobot_nvdatamodels.lpu_c2c.evaluator import ProjectionPermissionDenied, evaluate_domain
from nautobot_nvdatamodels.tests import fixtures

DOMAIN_QUERY = """
query DomainProjection($id: [String]) {
  lpuC2cDomains(id: $id) {
    id
    projectionState
    diagnostics { code severity message affectedObjects { objectType objectId } }
    endpoints {
      device { id name }
      domain { id }
      coordinate { rackOrdinal traySlot }
    }
  }
}
"""

DEVICE_QUERY = """
query DeviceProjection($location: [String]) {
  devices(location: $location) {
    id
    name
    lpuC2c {
      device { id name }
      domain { id name topology projectionState diagnostics { code severity } }
      coordinate { rackOrdinal traySlot }
    }
  }
}
"""

DEVICE_SCALE_QUERY = DEVICE_QUERY.replace(
    "$location: [String]",
    "$id: [String]",
).replace(
    "devices(location: $location)",
    "devices(id: $id)",
)


class LPUC2CGraphQLTestCase(TestCase):
    """Exercise both directions of the symmetric endpoint projection."""

    @classmethod
    def setUpTestData(cls):
        fixtures.lpu_c2c_test_data(cls)
        cls.position = models.LPUC2CDomainRackPosition.objects.create(
            domain=cls.domain, ordinal=0, rack=cls.rack
        )
        cls.compatibility = models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=choices.LPUC2CTopologyChoices.LP30_C2C,
            device_type=cls.device_type,
        )
        cls.graphql_admin = get_user_model().objects.create_superuser(username="lpu-c2c-graphql-admin")

    def execute(self, query, *, variables=None, user=None):
        """Execute through Nautobot's actual schema and return the response dictionary."""
        return execute_query(query, variables=variables, user=user or self.graphql_admin).to_dict()

    def test_schema_exposes_domain_projection_and_device_compatibility_field(self):
        """Schema introspection includes the custom Domain fields and Device shim."""
        result = self.execute(
            """
            query {
              domain: __type(name: "LPUC2CDomainType") {
                fields { name type { kind name ofType { kind name } } }
              }
              device: __type(name: "DeviceType") { fields { name } }
              endpoint: __type(name: "LPUC2CEndpointProjectionType") { fields { name } }
              coordinate: __type(name: "LPUC2CCoordinateType") { fields { name } }
              diagnostic: __type(name: "LPUC2CDiagnosticType") {
                fields { name type { kind name ofType { kind name } } }
              }
              __schema { queryType { fields { name } } }
            }
            """
        )

        self.assertNotIn("errors", result)
        self.assertEqual(
            {"projectionState", "diagnostics", "endpoints"}
            & {field["name"] for field in result["data"]["domain"]["fields"]},
            {"projectionState", "diagnostics", "endpoints"},
        )
        self.assertIn("lpuC2c", {field["name"] for field in result["data"]["device"]["fields"]})
        self.assertNotIn("diagnostics", {field["name"] for field in result["data"]["endpoint"]["fields"]})
        self.assertEqual(
            {field["name"] for field in result["data"]["coordinate"]["fields"]},
            {"rackOrdinal", "traySlot"},
        )
        domain_fields = {field["name"]: field for field in result["data"]["domain"]["fields"]}
        diagnostic_fields = {field["name"]: field for field in result["data"]["diagnostic"]["fields"]}
        self.assertEqual(domain_fields["projectionState"]["type"]["kind"], "ENUM")
        self.assertEqual(
            domain_fields["projectionState"]["type"]["name"],
            "LPUC2CProjectionState",
        )
        self.assertEqual(diagnostic_fields["severity"]["type"]["kind"], "NON_NULL")
        self.assertEqual(
            diagnostic_fields["severity"]["type"]["ofType"]["name"],
            "LPUC2CDiagnosticSeverity",
        )
        root_fields = {field["name"] for field in result["data"]["__schema"]["queryType"]["fields"]}
        self.assertTrue({"lpuC2cDomain", "lpuC2cDomains", "lpu_c2c_domain", "lpu_c2c_domains"} <= root_fields)

    def test_domain_query_returns_derived_endpoints_and_evaluates_only_once(self):
        """All Domain derived fields share one request-scoped loader promise."""
        from nautobot_nvdatamodels.graphql import loaders

        with patch.object(
            loaders,
            "evaluate_domain_snapshots",
            wraps=loaders.evaluate_domain_snapshots,
        ) as evaluate:
            result = self.execute(DOMAIN_QUERY, variables={"id": [str(self.domain.pk)]})

        self.assertNotIn("errors", result)
        projection = result["data"]["lpuC2cDomains"][0]
        self.assertEqual(projection["projectionState"], "READY")
        self.assertEqual(projection["diagnostics"], [])
        self.assertEqual(
            projection["endpoints"],
            [
                {
                    "device": {"id": str(self.device.pk), "name": self.device.name},
                    "domain": {"id": str(self.domain.pk)},
                    "coordinate": {
                        "rackOrdinal": 0,
                        "traySlot": 1,
                    },
                }
            ],
        )
        self.assertEqual(evaluate.call_count, 1)

    def test_batched_location_ancestry_matches_domain_hierarchy_for_multiple_racks(self):
        """Batched ancestry preserves the Domain-parent semantics without per-Rack queries."""
        child_location = Location.objects.create(
            name="LPU C2C GraphQL Ancestry Child",
            location_type=self.rack.location.location_type,
            status=self.rack.location.status,
            parent=self.rack.location,
        )
        child_rack = Rack.objects.create(
            name="LPU C2C GraphQL Ancestry Rack",
            location=child_location,
            status=self.rack.status,
        )
        models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain,
            ordinal=1,
            rack=child_rack,
        )

        evaluation = evaluate_domain(self.domain)

        self.assertNotIn(
            "RACK_OUTSIDE_DOMAIN_LOCATION",
            [diagnostic.code for diagnostic in evaluation.diagnostics],
        )

    def test_device_query_returns_same_intermediate_endpoint_shape(self):
        """Device projections include typed Device, Domain, and coordinate fields."""
        result = self.execute(
            DEVICE_QUERY,
            variables={"location": [str(self.device.location_id)]},
        )

        self.assertNotIn("errors", result)
        self.assertEqual(
            [item["id"] for item in result["data"]["devices"]],
            [str(self.device.pk)],
        )
        endpoint = result["data"]["devices"][0]["lpuC2c"]
        self.assertEqual(endpoint["device"], {"id": str(self.device.pk), "name": self.device.name})
        self.assertEqual(endpoint["domain"]["id"], str(self.domain.pk))
        self.assertEqual(
            endpoint["domain"]["projectionState"],
            "READY",
            endpoint["domain"]["diagnostics"],
        )
        self.assertEqual(endpoint["domain"]["diagnostics"], [])
        self.assertEqual(endpoint["coordinate"]["rackOrdinal"], 0)

    def test_invalid_domain_preserves_endpoints_with_null_coordinates(self):
        """Invalidity is represented at Domain scope without duplicating diagnostics."""
        models.LPUC2CDeviceTypeCompatibility.objects.all().delete()

        result = self.execute(DOMAIN_QUERY, variables={"id": [str(self.domain.pk)]})

        self.assertNotIn("errors", result)
        projection = result["data"]["lpuC2cDomains"][0]
        self.assertEqual(projection["projectionState"], "INVALID")
        self.assertIn("INCOMPATIBLE_DEVICE_TYPE", [item["code"] for item in projection["diagnostics"]])
        self.assertEqual(len(projection["endpoints"]), 1)
        self.assertIsNone(projection["endpoints"][0]["coordinate"])

    def test_inaccessible_domain_projection_fails_closed_with_graphql_errors(self):
        """A visible Domain with an invisible projection source does not emit a partial projection."""
        user = get_user_model().objects.create_user(username="lpu-c2c-domain-limited")
        self._grant_view(user, self.domain)

        result = self.execute(DOMAIN_QUERY, variables={"id": [str(self.domain.pk)]}, user=user)

        projection = result["data"]["lpuC2cDomains"][0]
        self.assertIsNone(projection["projectionState"])
        self.assertIsNone(projection["diagnostics"])
        self.assertIsNone(projection["endpoints"])
        self.assertTrue(result["errors"])
        self.assertFalse(any(self.device.name in error["message"] for error in result["errors"]))

    def test_hidden_relevant_compatibility_gates_domain_projection_fields(self):
        """Domain-derived fields fail closed when their evaluated compatibility is hidden."""
        user = get_user_model().objects.create_user(username="lpu-c2c-compatibility-limited")
        for instance in (self.domain, self.position, self.rack, self.device):
            self._grant_view(user, instance)

        result = self.execute(DOMAIN_QUERY, variables={"id": [str(self.domain.pk)]}, user=user)

        projection = result["data"]["lpuC2cDomains"][0]
        self.assertIsNone(projection["projectionState"])
        self.assertIsNone(projection["diagnostics"])
        self.assertIsNone(projection["endpoints"])
        self.assertTrue(result["errors"])
        self.assertNotIn(str(self.compatibility.pk), json.dumps(result))

    def test_hidden_compatibility_preserves_device_identity_but_gates_nested_domain_fields(self):
        """Device membership identity needs Device and Domain visibility, not compatibility visibility."""
        user = get_user_model().objects.create_user(username="lpu-c2c-device-compatibility-limited")
        for instance in (self.device, self.domain, self.position, self.rack):
            self._grant_view(user, instance)

        result = self.execute(
            DEVICE_QUERY,
            variables={"location": [str(self.device.location_id)]},
            user=user,
        )

        endpoint = result["data"]["devices"][0]["lpuC2c"]
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint["device"]["id"], str(self.device.pk))
        self.assertEqual(endpoint["domain"]["id"], str(self.domain.pk))
        self.assertEqual(endpoint["domain"]["name"], self.domain.name)
        self.assertEqual(endpoint["coordinate"]["rackOrdinal"], 0)
        self.assertIsNone(endpoint["domain"]["projectionState"])
        self.assertIsNone(endpoint["domain"]["diagnostics"])
        self.assertTrue(result["errors"])
        self.assertNotIn(str(self.compatibility.pk), json.dumps(result))

    def test_device_projection_preserves_visible_identity_when_domain_sources_are_hidden(self):
        """Device-side identity needs Device and Domain visibility, not all projection sources."""
        models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=self.position, excluded=True
        )
        no_domain_location = Location.objects.create(
            name="No LPU C2C domain location",
            location_type=self.rack.location.location_type,
            status=self.rack.location.status,
            parent=self.location,
        )
        no_domain_rack = Rack.objects.create(
            name="No LPU C2C domain rack",
            location=no_domain_location,
            status=self.rack.status,
        )
        no_domain_device = Device.objects.create(
            name="No LPU C2C domain",
            role=Role.objects.get(name="LPU Tray"),
            status=self.device.status,
            location=no_domain_location,
            rack=no_domain_rack,
            position=8,
            device_type=self.device_type,
        )
        superuser_result = self.execute(
            DEVICE_QUERY,
            variables={
                "location": [str(self.device.location_id), str(no_domain_location.pk)],
            },
        )
        self.assertNotIn("errors", superuser_result)
        self.assertEqual(
            {item["id"] for item in superuser_result["data"]["devices"]},
            {str(self.device.pk), str(no_domain_device.pk)},
        )
        self.assertTrue(all(item["lpuC2c"] is None for item in superuser_result["data"]["devices"]))

        models.LPUC2CEndpointConfiguration.objects.filter(device=self.device).delete()
        user = get_user_model().objects.create_user(username="lpu-c2c-device-limited")
        self._grant_view(user, self.device)
        self._grant_view(user, self.domain)
        limited_result = self.execute(
            DEVICE_QUERY,
            variables={"location": [str(self.device.location_id)]},
            user=user,
        )
        self.assertEqual(
            [item["id"] for item in limited_result["data"]["devices"]],
            [str(self.device.pk)],
        )
        endpoint = limited_result["data"]["devices"][0]["lpuC2c"]
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint["device"]["id"], str(self.device.pk))
        self.assertEqual(endpoint["domain"]["id"], str(self.domain.pk))
        self.assertEqual(endpoint["domain"]["name"], self.domain.name)
        self.assertEqual(endpoint["coordinate"]["rackOrdinal"], 0)
        self.assertIsNone(endpoint["domain"]["projectionState"])
        self.assertIsNone(endpoint["domain"]["diagnostics"])
        self.assertTrue(limited_result["errors"])
        hidden_names = {self.rack.name, self.position._meta.verbose_name, self.device.name}
        self.assertFalse(
            any(
                hidden_name in error["message"]
                for hidden_name in hidden_names
                for error in limited_result["errors"]
            )
        )

    def test_device_projection_hides_candidate_domain_without_domain_permission(self):
        """Device-only visibility does not reveal candidate Domain identity or authorization errors."""
        user = get_user_model().objects.create_user(username="lpu-c2c-device-only")
        self._grant_view(user, self.device)

        result = self.execute(
            DEVICE_QUERY,
            variables={"location": [str(self.device.location_id)]},
            user=user,
        )

        self.assertNotIn("errors", result)
        self.assertEqual(
            [item["id"] for item in result["data"]["devices"]],
            [str(self.device.pk)],
        )
        self.assertIsNone(result["data"]["devices"][0]["lpuC2c"])
        encoded_result = json.dumps(result)
        self.assertNotIn(str(self.domain.pk), encoded_result)
        self.assertNotIn(self.domain.name, encoded_result)

    def test_snapshot_authorization_uses_exact_evaluated_sources(self):
        """Authorization checks stored source IDs instead of rediscovering a later row set."""
        from nautobot_nvdatamodels.lpu_c2c import evaluator

        hidden_device = Device.objects.create(
            name="Hidden snapshot LPU tray",
            role=Role.objects.get(name="LPU Tray"),
            status=self.device.status,
            location=self.rack.location,
            rack=self.rack,
            position=10,
            device_type=self.incompatible_device_type,
        )
        user = get_user_model().objects.create_user(username="lpu-c2c-snapshot-limited")
        for instance in (self.domain, self.position, self.rack, self.device):
            self._grant_view(user, instance)

        snapshots = evaluator.evaluate_domain_snapshots([self.domain.pk])
        snapshot = snapshots[self.domain.pk]
        affected_ids = {
            reference.object_id
            for diagnostic in snapshot.evaluation.diagnostics
            for reference in diagnostic.affected_objects
        }
        self.assertIn(hidden_device.pk, affected_ids)
        hidden_device.delete()

        with patch.object(
            evaluator,
            "evaluate_domain_snapshots",
            side_effect=AssertionError("authorization reevaluated the domain"),
        ):
            errors = evaluator.domain_snapshot_visibility_errors(snapshots, user)

        self.assertIn(self.domain.pk, errors)
        self.assertNotIn(str(hidden_device.pk), str(errors[self.domain.pk]))

    def test_domain_loader_generically_denies_an_absent_raw_snapshot(self):
        """A stale Domain key never raises or discloses object details."""
        missing_domain_pk = uuid4()
        raw_domains = SimpleNamespace(load_many=lambda _domain_pks: Promise.resolve([None]))
        loader = DomainEvaluationLoader(self.graphql_admin, raw_domains)

        result = loader.batch_load_fn([missing_domain_pk]).get()[0]

        self.assertIsInstance(result, ProjectionPermissionDenied)
        self.assertEqual(
            str(result),
            "Complete visibility is required for this LPU C2C domain.",
        )
        self.assertNotIn(str(missing_domain_pk), str(result))

    def test_device_loader_maps_an_absent_raw_domain_snapshot_to_null(self):
        """A Domain deleted after candidate discovery produces no Device projection."""
        from nautobot_nvdatamodels.graphql import loaders

        raw_domains = SimpleNamespace(load_many=lambda _domain_pks: Promise.resolve([None]))
        loader = loaders.DeviceEndpointLoader(self.graphql_admin, raw_domains)
        with patch.object(
            loaders,
            "discover_device_endpoint_candidates",
            return_value=(
                (self.device.pk,),
                {self.device.pk: self.domain.pk},
                {self.domain.pk},
            ),
        ):
            result = loader.batch_load_fn([self.device.pk]).get()

        self.assertEqual(result, [None])

    def test_device_query_evaluates_each_candidate_domain_once_total(self):
        """Device endpoint and nested Domain fields reuse one raw Domain evaluation."""
        from unittest.mock import Mock

        from nautobot_nvdatamodels.graphql import loaders
        from nautobot_nvdatamodels.lpu_c2c import evaluator

        evaluate = Mock(wraps=evaluator.evaluate_domain_snapshots)
        with (
            patch.object(evaluator, "evaluate_domain_snapshots", evaluate),
            patch.object(loaders, "evaluate_domain_snapshots", evaluate),
        ):
            result = self.execute(
                DEVICE_QUERY,
                variables={"location": [str(self.device.location_id)]},
            )

        self.assertNotIn("errors", result)
        endpoint = result["data"]["devices"][0]["lpuC2c"]
        self.assertEqual(endpoint["domain"]["id"], str(self.domain.pk))
        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(set(evaluate.call_args.args[0]), {self.domain.pk})

    def test_combined_domain_and_device_traversal_evaluates_domain_once_per_request(self):
        """Both root directions share one raw evaluation in the same GraphQL operation."""
        from unittest.mock import Mock

        from nautobot_nvdatamodels.graphql import loaders
        from nautobot_nvdatamodels.lpu_c2c import evaluator

        query = """
        query CombinedProjection($domainId: [String], $location: [String]) {
          lpuC2cDomains(id: $domainId) {
            id projectionState diagnostics { code }
          }
          devices(location: $location) {
            id
            lpuC2c {
              domain { id projectionState diagnostics { code } }
            }
          }
        }
        """
        evaluate = Mock(wraps=evaluator.evaluate_domain_snapshots)
        with (
            patch.object(evaluator, "evaluate_domain_snapshots", evaluate),
            patch.object(loaders, "evaluate_domain_snapshots", evaluate),
        ):
            result = self.execute(
                query,
                variables={
                    "domainId": [str(self.domain.pk)],
                    "location": [str(self.device.location_id)],
                },
            )

        self.assertNotIn("errors", result)
        self.assertEqual(result["data"]["lpuC2cDomains"][0]["projectionState"], "READY")
        self.assertEqual(
            result["data"]["devices"][0]["lpuC2c"]["domain"]["projectionState"],
            "READY",
        )
        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(set(evaluate.call_args.args[0]), {self.domain.pk})

    def test_loader_cache_is_request_scoped(self):
        """Loader instances are reused only inside one request object."""
        first_request = SimpleNamespace(user=self.graphql_admin)
        second_request = SimpleNamespace(user=self.graphql_admin)

        first = get_lpu_c2c_loaders(first_request)

        self.assertIs(first, get_lpu_c2c_loaders(first_request))
        self.assertIsNot(first, get_lpu_c2c_loaders(second_request))

    def test_device_projection_query_count_is_flat_for_thirty_two_devices(self):
        """Batch loaders prevent per-Device projection queries."""
        from nautobot_nvdatamodels.graphql import loaders

        second_location = Location.objects.create(
            name="LPU C2C GraphQL Location Two",
            location_type=self.rack.location.location_type,
            status=self.rack.location.status,
            parent=self.location,
        )
        second_rack = Rack.objects.create(
            name="LPU C2C GraphQL Rack Two", location=second_location, status=self.rack.status
        )
        models.LPUC2CDomainRackPosition.objects.create(domain=self.other_domain, ordinal=0, rack=second_rack)
        self.other_device.rack = second_rack
        self.other_device.location = second_location
        self.other_device.device_type = self.device_type
        self.other_device.position = 8
        self.other_device.save()
        tray_role = Role.objects.get(name="LPU Tray")
        devices = [self.device, self.other_device]

        def query_count(selected):
            variables = {"id": [str(device.pk) for device in selected]}
            with (
                patch.object(
                    loaders,
                    "discover_device_endpoint_candidates",
                    wraps=loaders.discover_device_endpoint_candidates,
                ) as discover_devices,
                patch.object(
                    loaders,
                    "evaluate_domain_snapshots",
                    wraps=loaders.evaluate_domain_snapshots,
                ) as evaluate_domain_batch,
                CaptureQueriesContext(connection) as queries,
            ):
                result = self.execute(DEVICE_SCALE_QUERY, variables=variables)
            self.assertNotIn("errors", result)
            self.assertEqual(
                {item["id"] for item in result["data"]["devices"]},
                {str(device.pk) for device in selected},
            )
            self.assertTrue(all(item["lpuC2c"] is not None for item in result["data"]["devices"]))
            self.assertEqual(discover_devices.call_count, 1)
            self.assertEqual(set(discover_devices.call_args.args[0]), {device.pk for device in selected})
            self.assertEqual(evaluate_domain_batch.call_count, 1)
            self.assertEqual(
                set(evaluate_domain_batch.call_args.args[0]),
                {self.domain.pk, self.other_domain.pk},
            )
            return len(queries)

        small_count = query_count(devices)
        for index in range(30):
            domain = self.domain if index % 2 == 0 else self.other_domain
            location = Location.objects.create(
                name=f"LPU C2C GraphQL Scale Location {index:02d}",
                location_type=self.rack.location.location_type,
                status=self.rack.location.status,
                parent=self.location,
            )
            rack = Rack.objects.create(
                name=f"LPU C2C GraphQL Scale Rack {index:02d}",
                location=location,
                status=self.rack.status,
            )
            models.LPUC2CDomainRackPosition.objects.create(
                domain=domain,
                ordinal=(index // 2) + 1,
                rack=rack,
            )
            devices.append(
                Device.objects.create(
                    name=f"LPU C2C GraphQL Scale {index:02d}",
                    role=tray_role,
                    status=self.device.status,
                    location=location,
                    rack=rack,
                    position=8,
                    device_type=self.device_type,
                )
            )
        large_count = query_count(devices)

        self.assertLessEqual(large_count, small_count + 3)

    def test_domain_projection_query_count_is_flat_for_thirty_two_endpoints(self):
        """Domain-root endpoint object references batch for two and thirty-two Devices."""
        query = """
        query DomainEndpointScale($id: [String]) {
          lpuC2cDomains(id: $id) {
            id
            endpoints {
              device { id name }
              domain { id name }
            }
          }
        }
        """
        second_location = Location.objects.create(
            name="LPU C2C Domain Scale Location Two",
            location_type=self.rack.location.location_type,
            status=self.rack.location.status,
            parent=self.location,
        )
        second_rack = Rack.objects.create(
            name="LPU C2C Domain Scale Rack Two",
            location=second_location,
            status=self.rack.status,
        )
        models.LPUC2CDomainRackPosition.objects.create(
            domain=self.other_domain,
            ordinal=0,
            rack=second_rack,
        )
        self.other_device.rack = second_rack
        self.other_device.location = second_location
        self.other_device.device_type = self.device_type
        self.other_device.position = 8
        self.other_device.save()
        tray_role = Role.objects.get(name="LPU Tray")
        devices = [self.device, self.other_device]
        variables = {"id": [str(self.domain.pk), str(self.other_domain.pk)]}

        def query_count(expected_devices):
            with CaptureQueriesContext(connection) as queries:
                result = self.execute(query, variables=variables)
            self.assertNotIn("errors", result)
            endpoints = [
                endpoint for domain in result["data"]["lpuC2cDomains"] for endpoint in domain["endpoints"]
            ]
            self.assertEqual(
                {endpoint["device"]["id"] for endpoint in endpoints},
                {str(device.pk) for device in expected_devices},
            )
            self.assertEqual(len(endpoints), len(expected_devices))
            self.assertEqual(
                {endpoint["domain"]["id"] for endpoint in endpoints},
                {str(self.domain.pk), str(self.other_domain.pk)},
            )
            return len(queries)

        small_count = query_count(devices)
        for index in range(30):
            domain = self.domain if index % 2 == 0 else self.other_domain
            location = Location.objects.create(
                name=f"LPU C2C Domain Scale Location {index:02d}",
                location_type=self.rack.location.location_type,
                status=self.rack.location.status,
                parent=self.location,
            )
            rack = Rack.objects.create(
                name=f"LPU C2C Domain Scale Rack {index:02d}",
                location=location,
                status=self.rack.status,
            )
            models.LPUC2CDomainRackPosition.objects.create(
                domain=domain,
                ordinal=(index // 2) + 1,
                rack=rack,
            )
            devices.append(
                Device.objects.create(
                    name=f"LPU C2C Domain Scale {index:02d}",
                    role=tray_role,
                    status=self.device.status,
                    location=location,
                    rack=rack,
                    position=8,
                    device_type=self.device_type,
                )
            )
        large_count = query_count(devices)

        self.assertLessEqual(large_count, small_count + 3)

    @staticmethod
    def _grant_view(user, instance):
        permission = ObjectPermission.objects.create(
            name=f"View {instance._meta.label_lower} {instance.pk}",
            actions=["view"],
            constraints={"pk": str(instance.pk)},
        )
        permission.object_types.add(ContentType.objects.get_for_model(instance))
        permission.users.add(user)


class DeviceTypeShimTestCase(TestCase):
    """Verify defensive installation onto Nautobot's pre-existing DeviceType."""

    def test_install_is_idempotent_for_our_marked_field(self):
        class FakeDeviceType:
            _meta = SimpleNamespace(fields={})

        first = install_device_type_lpu_c2c_shim(FakeDeviceType)
        second = install_device_type_lpu_c2c_shim(FakeDeviceType)

        self.assertIs(first, second)
        self.assertIs(FakeDeviceType._meta.fields["lpu_c2c"], first)
        self.assertTrue(hasattr(FakeDeviceType, "resolve_lpu_c2c"))

    def test_install_refuses_to_overwrite_an_unowned_field(self):
        class FakeDeviceType:
            _meta = SimpleNamespace(fields={"lpu_c2c": object()})

        with self.assertRaisesRegex(RuntimeError, "DeviceType.lpu_c2c"):
            install_device_type_lpu_c2c_shim(FakeDeviceType)

    def test_install_refuses_effective_graphql_name_collision_under_alternate_key(self):
        class FakeDeviceType:
            _meta = SimpleNamespace(
                fields={"another_python_key": graphene.Field(graphene.String, name="lpuC2c")}
            )

        with self.assertRaisesRegex(RuntimeError, "lpuC2c"):
            install_device_type_lpu_c2c_shim(FakeDeviceType)

    def test_install_ignores_unrelated_dynamic_field_without_resolving_it(self):
        dynamic = graphene.Dynamic(lambda: graphene.Field(graphene.String))

        class FakeDeviceType:
            _meta = SimpleNamespace(fields={"unrelated_dynamic": dynamic})

        installed = install_device_type_lpu_c2c_shim(FakeDeviceType)

        self.assertIs(FakeDeviceType._meta.fields["unrelated_dynamic"], dynamic)
        self.assertIs(FakeDeviceType._meta.fields["lpu_c2c"], installed)

    def test_install_refuses_unowned_class_attribute_and_resolver_collisions(self):
        for colliding_attribute in ("lpu_c2c", "resolve_lpu_c2c"):
            with self.subTest(colliding_attribute=colliding_attribute):
                fake_device_type = type(
                    "FakeDeviceType",
                    (),
                    {
                        "_meta": SimpleNamespace(fields={}),
                        colliding_attribute: object(),
                    },
                )

                with self.assertRaisesRegex(RuntimeError, colliding_attribute):
                    install_device_type_lpu_c2c_shim(fake_device_type)

    def test_install_refuses_inherited_unowned_field_without_invoking_descriptor(self):
        class UnownedDescriptor:
            def __get__(self, instance, owner):
                raise AssertionError("inherited lpu_c2c descriptor was invoked")

        class BaseDeviceType:
            lpu_c2c = UnownedDescriptor()

        class FakeDeviceType(BaseDeviceType):
            _meta = SimpleNamespace(fields={})

        with self.assertRaisesRegex(RuntimeError, "lpu_c2c"):
            install_device_type_lpu_c2c_shim(FakeDeviceType)

    def test_install_refuses_inherited_unowned_resolver_without_invoking_descriptor(self):
        class UnownedDescriptor:
            def __get__(self, instance, owner):
                raise AssertionError("inherited resolve_lpu_c2c descriptor was invoked")

        class BaseDeviceType:
            resolve_lpu_c2c = UnownedDescriptor()

        class FakeDeviceType(BaseDeviceType):
            _meta = SimpleNamespace(fields={})

        with self.assertRaisesRegex(RuntimeError, "resolve_lpu_c2c"):
            install_device_type_lpu_c2c_shim(FakeDeviceType)

    def test_query_alias_install_is_idempotent(self):
        source_single = SimpleNamespace()
        source_list = SimpleNamespace()

        class FakeQueryMixin:
            lpu_c2c_domain = source_single
            lpu_c2c_domains = source_list

            @staticmethod
            def resolve_lpu_c2c_domain():
                return None

            @staticmethod
            def resolve_lpu_c2c_domains():
                return None

        graphql_types.install_lpu_c2c_query_aliases(FakeQueryMixin)
        first_single = FakeQueryMixin.lpuC2cDomain
        first_list = FakeQueryMixin.lpuC2cDomains
        graphql_types.install_lpu_c2c_query_aliases(FakeQueryMixin)

        self.assertIs(FakeQueryMixin.lpuC2cDomain, source_single)
        self.assertIs(FakeQueryMixin.lpuC2cDomains, source_list)
        self.assertIs(FakeQueryMixin.lpuC2cDomain, first_single)
        self.assertIs(FakeQueryMixin.lpuC2cDomains, first_list)
        self.assertIs(
            FakeQueryMixin.resolve_lpuC2cDomains,
            FakeQueryMixin.resolve_lpu_c2c_domains,
        )

    def test_query_alias_install_refuses_collision(self):
        class FakeQueryMixin:
            lpu_c2c_domain = SimpleNamespace()
            lpu_c2c_domains = SimpleNamespace()
            lpuC2cDomains = object()

        with self.assertRaisesRegex(RuntimeError, "lpuC2cDomains"):
            graphql_types.install_lpu_c2c_query_aliases(FakeQueryMixin)

    def test_query_factory_shim_repeated_install_and_schema_generation(self):
        """Repeated lifecycle calls preserve snake/camel roots and resolver aliases."""
        from graphene_django.types import ObjectType
        from nautobot.core.graphql import schema as nautobot_schema

        first_factory = graphql_types.install_lpu_c2c_query_factory_shim()
        second_factory = graphql_types.install_lpu_c2c_query_factory_shim()

        self.assertIs(first_factory, second_factory)
        self.assertIs(first_factory, nautobot_schema.generate_query_mixin)
        for index in range(2):
            query_mixin = first_factory()
            query_type = type(f"RepeatedLPUC2CQuery{index}", (ObjectType, query_mixin), {})
            generated_schema = graphene.Schema(query=query_type, auto_camelcase=False)
            root_fields = set(generated_schema.get_query_type().fields)
            self.assertTrue(
                {"lpuC2cDomain", "lpuC2cDomains", "lpu_c2c_domain", "lpu_c2c_domains"} <= root_fields
            )
            self.assertIs(
                query_mixin.resolve_lpuC2cDomain,
                query_mixin.resolve_lpu_c2c_domain,
            )
            self.assertIs(
                query_mixin.resolve_lpuC2cDomains,
                query_mixin.resolve_lpu_c2c_domains,
            )
