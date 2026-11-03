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
"""Exercise reference-table migration with pre-existing domain data."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, tag

from nautobot_nvdatamodels.tests import fixtures


@tag("migration_test")
class NVLinkReferenceMigrationTest(TransactionTestCase):
    migrate_from = ("nautobot_nvdatamodels", "0003_fix_nvlinkdomainmembership_related_name")
    migrate_to = ("nautobot_nvdatamodels", "0006_remove_nvlink_domain_legacy_fields")

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def test_forward_and_reverse_preserve_assignments(self):
        fixtures.common_test_data(self)
        old_apps = self.migrate(self.migrate_from)
        try:
            domain_model = old_apps.get_model("nautobot_nvdatamodels", "NVLinkDomain")
            expected = [
                ("nvlink_v5", "gb200_nvl72r1_c2g4"),
                ("custom_protocol", "custom_topology"),
                (None, None),
                ("", ""),
            ]
            ids = []
            for index, (protocol, topology) in enumerate(expected):
                domain = domain_model.objects.create(
                    name=f"Migration {index}",
                    location_id=self.location.pk,
                    status_id=self.nvl_status.pk,
                    protocol=protocol,
                    topology=topology,
                )
                ids.append(domain.pk)
            new_apps = self.migrate(self.migrate_to)
            domain_model = new_apps.get_model("nautobot_nvdatamodels", "NVLinkDomain")
            for pk, (protocol, topology) in zip(ids, expected):
                domain = domain_model.objects.get(pk=pk)
                self.assertEqual(domain.protocol.name if domain.protocol else None, protocol or None)
                self.assertEqual(domain.topology.name if domain.topology else None, topology or None)
            for kind in ("Protocol", "Topology"):
                self.assertEqual(
                    new_apps.get_model("nautobot_nvdatamodels", f"NVLinkDomain{kind}").objects.count(), 8
                )
            old_apps = self.migrate(self.migrate_from)
            domain_model = old_apps.get_model("nautobot_nvdatamodels", "NVLinkDomain")
            for pk, (protocol, topology) in zip(ids, expected):
                domain = domain_model.objects.get(pk=pk)
                self.assertEqual(domain.protocol, protocol or None)
                self.assertEqual(domain.topology, topology or None)
        finally:
            self.migrate(self.migrate_to)
