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
"""Unit tests for views."""

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse
from nautobot.apps.testing import ViewTestCases
from nautobot.dcim.models import Device
from nautobot.extras.models import Status

from nautobot_nvdatamodels import choices, models
from nautobot_nvdatamodels.tests import fixtures


class NVLinkDomainViewTest(ViewTestCases.PrimaryObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the NVLinkDomain views."""

    model = models.NVLinkDomain

    # This is needed to prevent failures when redirects happen
    test_create_object_with_constrained_permission = None
    test_create_object_with_permission = None
    test_edit_object_with_constrained_permission = None
    test_edit_object_with_permission = None

    @classmethod
    def setUpTestData(cls):
        fixtures.nvl_test_data(cls)
        cls.status = Status.objects.get_for_model(models.NVLinkDomain).first()
        cls.bulk_edit_data = {"cluster_id": "Bulk edit views"}
        cls.form_data = {
            "name": "Test 1",
            "location": cls.location.pk,
            "status": cls.status.pk,
            "tags": [cls.tag.pk],
        }
        cls.csv_data = (
            "name,location,status",
            f"Test csv1,{cls.location.pk},{cls.status.pk}",
            f"Test csv2,{cls.location.pk},{cls.status.pk}",
            f"Test csv3,{cls.location.pk},{cls.status.pk}",
        )

    def _add_members(self, domain, statuses):
        for i, status in enumerate(statuses):
            device = Device.objects.create(
                name=f"Member {i}",
                role=self.device_role,
                status=status,
                location=self.location,
                device_type=self.device_type,
            )
            models.NVLinkDomainMembership.objects.create(domain=domain, member=device)

    def _detail_url(self, domain, query=""):
        return reverse("plugins:nautobot_nvdatamodels:nvlinkdomain", kwargs={"pk": domain.pk}) + query

    def _setup_members(self):
        self.add_permissions("nautobot_nvdatamodels.view_nvlinkdomain", "dcim.view_device")
        deleted, _ = Status.objects.get_or_create(name="Deleted")
        deleted.content_types.add(ContentType.objects.get_for_model(Device))
        domain = self.nvl_domains[0]
        self._add_members(domain, [self.device_status, self.device_status, deleted])
        return domain

    def test_members_hide_deleted_by_default_with_notice(self):
        """Hidden statuses are excluded from list and count, and the header says so."""
        domain = self._setup_members()

        response = self.client.get(self._detail_url(domain))

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["member_count"], 2)
        self.assertEqual(response.context["hidden_member_count"], 1)
        self.assertContains(response, "Members (2)")
        self.assertContains(response, "1 Deleted hidden")
        self.assertContains(response, "show_hidden_members=true")
        self.assertNotContains(response, "Member 2")

    def test_members_show_hidden_includes_deleted(self):
        """show_hidden_members=true lists and counts every member."""
        domain = self._setup_members()

        response = self.client.get(self._detail_url(domain, "?show_hidden_members=true"))

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["member_count"], 3)
        self.assertContains(response, "Members (3)")
        self.assertContains(response, "including Deleted devices")
        self.assertContains(response, "Member 2")

    def test_members_show_hidden_ignores_invalid_value(self):
        """A junk query value behaves like the default instead of erroring."""
        domain = self._setup_members()

        response = self.client.get(self._detail_url(domain, "?show_hidden_members=abc"))

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["member_count"], 2)

    @override_settings(PLUGINS_CONFIG={"nautobot_nvdatamodels": {"hidden_member_statuses": []}})
    def test_members_hidden_statuses_configurable(self):
        """With no hidden statuses configured nothing is filtered and no notice shows."""
        domain = self._setup_members()

        response = self.client.get(self._detail_url(domain))

        self.assertEqual(response.context["member_count"], 3)
        self.assertNotContains(response, "show_hidden_members")


class ResourceBlockViewTest(ViewTestCases.PrimaryObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the ResourceBlock views."""

    model = models.ResourceBlock

    # This is needed to prevent failures when redirects happen
    test_create_object_with_constrained_permission = None
    test_create_object_with_permission = None
    test_edit_object_with_constrained_permission = None
    test_edit_object_with_permission = None
    test_list_objects_without_permission = None

    @classmethod
    def setUpTestData(cls):
        fixtures.rb_test_data(cls)
        cls.status = Status.objects.get_for_model(models.ResourceBlock).first()
        cls.bulk_edit_data = {"protocol": choices.ResourceBlockProtocolChoices.ETHERNET}
        cls.form_data = {
            "name": "New Resource Block",
            "location": cls.location.pk,
            "status": cls.status.pk,
            "protocol": choices.ResourceBlockProtocolChoices.SPECTRUMX,
            "tags": [cls.tag.pk],
        }
        cls.csv_data = (
            "name,location,status,protocol",
            f"Test csv1,{cls.location.pk},{cls.status.pk},{choices.ResourceBlockProtocolChoices.ETHERNET}",
            f"Test csv2,{cls.location.pk},{cls.status.pk},{choices.ResourceBlockProtocolChoices.INFINIBAND}",
            f"Test csv3,{cls.location.pk},{cls.status.pk},{choices.ResourceBlockProtocolChoices.RDMA}",
        )

    def test_get_extra_context(self):
        """Test the get_extra_context method on the ResourceBlock view."""
        # Grant necessary permissions for this test
        self.add_permissions("nautobot_nvdatamodels.view_resourceblock")
        self.add_permissions("dcim.view_device")

        # Debug: Check if devices are actually assigned
        rb = self.resource_blocks[0]
        static_devices = list(rb.devices.all())
        dynamic_devices = list(rb.dynamic_group.members.all()) if rb.dynamic_group else []

        # Verify devices are assigned correctly
        self.assertEqual(
            len(static_devices),
            2,
            f"Expected 2 static devices, got {len(static_devices)}: {[d.name for d in static_devices]}",
        )
        self.assertEqual(
            len(dynamic_devices),
            6,
            f"Expected 6 dynamic devices, got {len(dynamic_devices)}: {[d.name for d in dynamic_devices]}",
        )

        # Make a request to the instance detail view
        response = self.client.get(rb.get_absolute_url())
        self.assertHttpStatus(response, 200)

        # Check that the device tables are in the context
        self.assertIn("static_device_table", response.context)
        self.assertIn("dynamic_device_table", response.context)

        # Check the number of rows in each table (resource_blocks[0] has 2 static devices and dynamic group with 6 devices)
        self.assertEqual(len(response.context["static_device_table"].rows), 2)
        self.assertEqual(len(response.context["dynamic_device_table"].rows), 6)

    def test_resource_block_detail_view_content(self):
        """Test that the detail view shows device information."""
        # Grant necessary permissions for this test
        self.add_permissions("nautobot_nvdatamodels.view_resourceblock")
        self.add_permissions("dcim.view_device")

        rb = self.resource_blocks[0]
        response = self.client.get(rb.get_absolute_url())
        self.assertHttpStatus(response, 200)

        # Check that static device names appear in the response
        static_devices = list(rb.devices.all())
        for device in static_devices:
            self.assertContains(response, device.name)

        # Check that dynamic device names appear in the response
        dynamic_devices = list(rb.dynamic_group.members.all()) if rb.dynamic_group else []
        for device in dynamic_devices:
            self.assertContains(response, device.name)
