#  SPDX-FileCopyrightText: Copyright (c) "2025" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License")
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""NVLink GraphQL compatibility and expanded reference permissions."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from nautobot.core.graphql import execute_query
from nautobot.users.models import ObjectPermission

from nautobot_nvdatamodels import models
from nautobot_nvdatamodels.tests import fixtures

EXPANDED_QUERY = """
query($domains: [String]) {
  nvlink_domains(name: $domains) {
    name topology protocol
    nvlink_domain_topology { name description }
    nvlink_domain_protocol { name description }
  }
}
"""


class NVLinkGraphQLTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.nvl_test_data(cls)
        cls.user = get_user_model().objects.create_superuser(username="graphql-admin", password="test")
        cls.topology = models.NVLinkDomainTopology.objects.create(
            name="vr_nvl72r1_c2g4", description="VR NVL72"
        )
        cls.protocol = models.NVLinkDomainProtocol.objects.create(
            name="custom_nvlink", description="Custom NVLink"
        )
        cls.domain = cls.nvl_domains[0]
        cls.domain.topology = cls.topology
        cls.domain.protocol = cls.protocol
        cls.domain.save()

    def query(self, query, user=None, **variables):
        result = execute_query(query, variables=variables, user=user or self.user)
        self.assertIsNone(result.errors, result.errors)
        return result.data

    def test_scalar_shortcuts_alongside_expanded_references_and_null_assignments(self):
        domain = self.query(EXPANDED_QUERY, domains=[self.domain.name])["nvlink_domains"][0]
        for field, reference in (("topology", self.topology), ("protocol", self.protocol)):
            self.assertEqual(domain[field], reference.name)
            self.assertEqual(
                domain[f"nvlink_domain_{field}"],
                {"name": reference.name, "description": reference.description},
            )
        models.NVLinkDomain.objects.filter(pk=self.domain.pk).update(topology=None, protocol=None)
        domain = self.query(EXPANDED_QUERY, domains=[self.domain.name])["nvlink_domains"][0]
        for field in ("topology", "protocol", "nvlink_domain_topology", "nvlink_domain_protocol"):
            self.assertIsNone(domain[field])

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_expanded_references_respect_permissions_without_breaking_scalar_names(self):
        user = get_user_model().objects.create_user(username="graphql-reader", password="test")
        permission = ObjectPermission.objects.create(name="View domains", actions=["view"])
        permission.object_types.add(ContentType.objects.get_for_model(models.NVLinkDomain))
        permission.users.add(user)
        domain = self.query(EXPANDED_QUERY, user=user, domains=[self.domain.name])["nvlink_domains"][0]
        self.assertEqual(domain["topology"], self.topology.name)
        self.assertEqual(domain["protocol"], self.protocol.name)
        self.assertIsNone(domain["nvlink_domain_topology"])
        self.assertIsNone(domain["nvlink_domain_protocol"])
        permission = ObjectPermission.objects.create(
            name="View selected topology", actions=["view"], constraints={"pk": str(self.topology.pk)}
        )
        permission.object_types.add(ContentType.objects.get_for_model(models.NVLinkDomainTopology))
        permission.users.add(user)
        user = get_user_model().objects.get(pk=user.pk)
        domain = self.query(EXPANDED_QUERY, user=user, domains=[self.domain.name])["nvlink_domains"][0]
        self.assertEqual(domain["nvlink_domain_topology"]["name"], self.topology.name)
        self.assertIsNone(domain["nvlink_domain_protocol"])

    def test_expanded_fields_can_be_selected_without_scalar_shortcuts(self):
        data = self.query(
            "query($domains: [String]) { nvlink_domains(name: $domains) { name "
            "nvlink_domain_topology { description } nvlink_domain_protocol { description } } }",
            domains=[self.domain.name],
        )["nvlink_domains"][0]
        self.assertEqual(data["nvlink_domain_topology"], {"description": self.topology.description})
        self.assertEqual(data["nvlink_domain_protocol"], {"description": self.protocol.description})

    def test_reference_root_queries_remain_available(self):
        data = self.query("{ nvlink_domain_topologies { name } nvlink_domain_protocols { name } }")
        self.assertIn({"name": self.topology.name}, data["nvlink_domain_topologies"])
        self.assertIn({"name": self.protocol.name}, data["nvlink_domain_protocols"])
