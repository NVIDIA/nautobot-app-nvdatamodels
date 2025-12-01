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
"""Unit tests for nautobot_nvdatamodels API."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from nautobot.core.testing import APITestCase, APIViewTestCases
from nautobot.dcim.models import Device
from rest_framework import status

from nautobot_nvdatamodels import choices
from nautobot_nvdatamodels.models import (
    NVLinkDomain,
    NVLinkDomainMembership,
    ResourceBlock,
    ResourceBlockMembership,
)
from nautobot_nvdatamodels.tests import fixtures

User = get_user_model()


class AppTest(APITestCase):
    """Test the nautobot_nvdatamodels API root."""

    def test_root(self):
        """Verify that the API root responds correctly."""
        url = reverse("plugins-api:nautobot_nvdatamodels-api:api-root")
        response = self.client.get(f"{url}?format=api", **self.header)
        self.assertEqual(response.status_code, 200)


class NVLinkDomainTest(APIViewTestCases.APIViewTestCase):
    """Test the NVLinkDomain API."""

    model = NVLinkDomain
    bulk_update_data = {
        "cluster_id": "updated-cluster-id",
    }
    choices_fields = ["protocol", "topology"]

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        fixtures.nvl_test_data(cls)

        cls.create_data = [
            {
                "name": "Test NVLink Domain 4",
                "location": cls.location.pk,
                "status": cls.nvl_status.pk,
                "protocol": choices.NVLinkDomainProtocolChoices.NVLINK_V5,
                "topology": choices.NVLinkDomainTopologyChoices.GB200_NVL36R1_C2G4,
                "cluster_id": "test-cluster-4",
            },
            {
                "name": "Test NVLink Domain 5",
                "location": cls.location.pk,
                "status": cls.nvl_status.pk,
                "role": cls.nvl_role.pk,
                "tenant": cls.tenant.pk,
                "protocol": choices.NVLinkDomainProtocolChoices.NVLINK_V3,
                "topology": choices.NVLinkDomainTopologyChoices.GB200_NVL72R2_C2G4,
                "cluster_id": "test-cluster-5",
            },
            {
                "name": "Test NVLink Domain 6",
                "location": cls.location2.pk,
                "status": cls.nvl_status.pk,
                "protocol": choices.NVLinkDomainProtocolChoices.INFINIBAND,
                "cluster_id": "test-cluster-6",
            },
        ]

    def get_deletable_object(self):
        """Get a domain that can be safely deleted (no memberships)."""
        return self.model.objects.create(
            name="Deletable Domain",
            location=self.location,
            status=self.nvl_status,
        )

    def get_deletable_object_pks(self):
        """Get domains that can be safely deleted (no memberships)."""
        domains = [
            self.model.objects.create(
                name=f"Deletable Domain {i}",
                location=self.location,
                status=self.nvl_status,
            )
            for i in range(1, 4)
        ]
        return [domain.pk for domain in domains]


class NVLinkDomainMembershipTest(
    APIViewTestCases.CreateObjectViewTestCase,
    APIViewTestCases.DeleteObjectViewTestCase,
    APIViewTestCases.ListObjectsViewTestCase,
):
    """Test the NVLinkDomainMembership API."""

    model = NVLinkDomainMembership
    bulk_update_data = {}  # No bulk updatable fields for membership
    choices_fields = []

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        fixtures.nvl_test_data(cls)
        cls.membership_devices = []
        for i in range(7, 15):
            device = Device.objects.create(
                device_type=cls.device_type,
                role=cls.device_role,
                name=f"Test Device {i}",
                location=cls.location,
                status=cls.device_status,
            )
            cls.membership_devices.append(device)

        NVLinkDomainMembership.objects.create(
            domain=cls.nvl_domains[0],
            member=cls.membership_devices[0],
        )
        NVLinkDomainMembership.objects.create(
            domain=cls.nvl_domains[0],
            member=cls.membership_devices[1],
        )
        NVLinkDomainMembership.objects.create(
            domain=cls.nvl_domains[1],
            member=cls.membership_devices[2],
        )

        cls.create_data = [
            {
                "domain": cls.nvl_domains[0].pk,
                "member": cls.membership_devices[3].pk,
            },
            {
                "domain": cls.nvl_domains[0].pk,
                "member": cls.membership_devices[4].pk,
            },
            {
                "domain": cls.nvl_domains[1].pk,
                "member": cls.membership_devices[5].pk,
            },
        ]

    def test_unique_membership_constraint(self):
        """Test that a device can only belong to one domain (unique constraint)."""
        test_device = Device.objects.create(
            device_type=self.device_type,
            role=self.device_role,
            name="Unique Test Device",
            location=self.location,
            status=self.device_status,
        )
        self.model.objects.create(
            domain=self.nvl_domains[0],
            member=test_device,
        )
        url = reverse("plugins-api:nautobot_nvdatamodels-api:nvlinkdomainmembership-list")
        self.add_permissions("nautobot_nvdatamodels.add_nvlinkdomainmembership")

        data = {
            "domain": self.nvl_domains[1].pk,
            "member": test_device.pk,
        }

        response = self.client.post(url, data, format="json", **self.header)
        # This should fail due to the OneToOneField constraint
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)


class ResourceBlockTest(APIViewTestCases.APIViewTestCase):
    """Test the ResourceBlock API."""

    model = ResourceBlock
    bulk_update_data = {
        "protocol": choices.ResourceBlockProtocolChoices.INFINIBAND,
    }
    choices_fields = ["protocol"]

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        fixtures.rb_test_data(cls)

        cls.create_data = [
            {
                "name": "Test Resource Block 5",
                "location": cls.location.pk,
                "status": cls.rb_status.pk,
                "protocol": choices.ResourceBlockProtocolChoices.ETHERNET,
            },
            {
                "name": "Test Resource Block 6",
                "location": cls.location.pk,
                "status": cls.rb_status.pk,
                "role": cls.rb_role.pk,
                "tenant": cls.tenant.pk,
                "protocol": choices.ResourceBlockProtocolChoices.SPECTRUMX,
                "dynamic_group": cls.dynamic_groups[0].pk,
            },
            {
                "name": "Test Resource Block 7",
                "location": cls.location2.pk,
                "status": cls.rb_status.pk,
                "protocol": choices.ResourceBlockProtocolChoices.RDMA,
            },
        ]

    def test_list_objects_depth_1(self):
        """Currently does not support depth=1."""

    def get_deletable_object(self):
        """Get a resource block that can be safely deleted (no memberships)."""
        return self.model.objects.create(
            name="Deletable Resource Block",
            location=self.location,
            status=self.rb_status,
        )

    def get_deletable_object_pks(self):
        """Get resource blocks that can be safely deleted (no memberships)."""
        resource_blocks = [
            self.model.objects.create(
                name=f"Deletable Resource Block {i}",
                location=self.location,
                status=self.rb_status,
            )
            for i in range(1, 4)
        ]
        return [rb.pk for rb in resource_blocks]

    def test_device_count_properties(self):
        """Test device count properties work correctly."""
        resource_block = self.model.objects.create(
            name="Test Count Properties RB",
            location=self.location,
            status=self.rb_status,
            dynamic_group=self.dynamic_groups[0],
        )
        test_device_1 = Device.objects.create(
            device_type=self.device_type,
            role=self.device_role,
            name="Test Count Device 1",
            location=self.location,
            status=self.device_status,
        )
        test_device_2 = Device.objects.create(
            device_type=self.device_type,
            role=self.device_role,
            name="Test Count Device 2",
            location=self.location,
            status=self.device_status,
        )
        resource_block.devices.set([test_device_1, test_device_2])
        self.assertEqual(resource_block.static_device_count, 2)
        self.assertGreaterEqual(resource_block.dynamic_device_count, 0)
        self.assertGreaterEqual(resource_block.device_count, 2)


class ResourceBlockMembershipTest(APIViewTestCases.APIViewTestCase):
    """Test the ResourceBlockMembership API."""

    model = ResourceBlockMembership
    bulk_update_data = {}  # No bulk updatable fields for membership
    choices_fields = []

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        fixtures.rb_test_data(cls)

        cls.membership_devices = []
        for i in range(15, 25):
            device = Device.objects.create(
                device_type=cls.device_type,
                role=cls.device_role,
                name=f"Test RBM Device {i}",
                location=cls.location,
                status=cls.device_status,
            )
            cls.membership_devices.append(device)
        ResourceBlockMembership.objects.create(
            resource_block=cls.resource_blocks[0],
            device=cls.membership_devices[0],
        )
        ResourceBlockMembership.objects.create(
            resource_block=cls.resource_blocks[0],
            device=cls.membership_devices[1],
        )
        ResourceBlockMembership.objects.create(
            resource_block=cls.resource_blocks[1],
            device=cls.membership_devices[2],
        )

        cls.create_data = [
            {
                "resource_block": cls.resource_blocks[0].pk,
                "device": cls.membership_devices[3].pk,
            },
            {
                "resource_block": cls.resource_blocks[0].pk,
                "device": cls.membership_devices[4].pk,
            },
            {
                "resource_block": cls.resource_blocks[1].pk,
                "device": cls.membership_devices[5].pk,
            },
        ]

    def test_unique_membership_constraint(self):
        """Test that a device can only belong to one resource block (unique constraint)."""
        # Ensure test data is committed to database for API visibility
        with transaction.atomic():
            # Refresh objects from database to ensure they exist in current transaction
            resource_block_0 = ResourceBlock.objects.get(pk=self.resource_blocks[0].pk)
            resource_block_1 = ResourceBlock.objects.get(pk=self.resource_blocks[1].pk)

            test_device = Device.objects.create(
                device_type=self.device_type,
                role=self.device_role,
                name="Unique RBM Test Device",
                location=self.location,
                status=self.device_status,
            )

            self.model.objects.create(
                resource_block=resource_block_0,
                device=test_device,
            )

        url = reverse("plugins-api:nautobot_nvdatamodels-api:resourceblockmembership-list")
        self.add_permissions("nautobot_nvdatamodels.add_resourceblockmembership")

        data = {
            "resource_block": resource_block_1.pk,
            "device": test_device.pk,
        }

        response = self.client.post(url, data, format="json", **self.header)
        # This should fail due to the OneToOneField constraint
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)
