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

from nautobot.apps.testing import ViewTestCases
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
