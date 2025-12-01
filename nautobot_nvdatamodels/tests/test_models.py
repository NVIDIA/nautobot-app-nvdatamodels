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
"""Test models for NV Data Models app."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TransactionTestCase
from nautobot.core.testing.models import ModelTestCases
from nautobot.extras.models import DynamicGroup

from nautobot_nvdatamodels import choices, models
from nautobot_nvdatamodels.tests import fixtures


class NVLinkDomainTestCase(ModelTestCases.BaseModelTestCase):
    """Test NVLinkDomain model."""

    model = models.NVLinkDomain

    @classmethod
    def setUpTestData(cls):
        """Set up test data for NVLinkDomain tests."""
        fixtures.nvl_test_data(cls)

    def test_get_docs_url(self):
        """Skip docs URL test - no documentation available."""
        self.skipTest("No documentation available for this model")

    def test_create_nvlinkdomain_required_fields_only(self):
        """Test creating NVLinkDomain with only required fields and validate string representation."""
        nvlinkdomain = models.NVLinkDomain.objects.create(
            name="Development", location=self.location, status=self.nvl_status
        )
        self.assertEqual(nvlinkdomain.name, "Development")
        self.assertEqual(str(nvlinkdomain), "Development")

    def test_create_nvlinkdomain_all_fields(self):
        """Test creating NVLinkDomain with all fields populated."""
        nvlinkdomain = models.NVLinkDomain.objects.create(
            name="Production",
            location=self.location,
            status=self.nvl_status,
            protocol=choices.NVLinkDomainProtocolChoices.NVLINK_V5,
            topology=choices.NVLinkDomainTopologyChoices.GB200_NVL72R1_C2G4,
            cluster_id="cluster-1",
            role=self.nvl_role,
            tenant=self.tenant,
        )
        self.assertEqual(nvlinkdomain.name, "Production")
        self.assertEqual(nvlinkdomain.protocol, choices.NVLinkDomainProtocolChoices.NVLINK_V5)
        self.assertEqual(nvlinkdomain.topology, choices.NVLinkDomainTopologyChoices.GB200_NVL72R1_C2G4)
        self.assertEqual(nvlinkdomain.cluster_id, "cluster-1")
        self.assertEqual(nvlinkdomain.role, self.nvl_role)
        self.assertEqual(nvlinkdomain.tenant, self.tenant)

    def test_nvlinkdomain_required_fields_validation(self):
        """Test that required fields are validated."""
        # Test missing name
        with self.assertRaises(ValidationError):
            nvlinkdomain = models.NVLinkDomain(location=self.location, status=self.nvl_status)
            nvlinkdomain.full_clean()

        # Test missing location
        with self.assertRaises(ValidationError):
            nvlinkdomain = models.NVLinkDomain(name="Test Domain", status=self.nvl_status)
            nvlinkdomain.full_clean()

        # Test missing status
        with self.assertRaises(ValidationError):
            nvlinkdomain = models.NVLinkDomain(name="Test Domain", location=self.location)
            nvlinkdomain.full_clean()

    def test_nvlinkdomain_name_uniqueness(self):
        """Test that NVLinkDomain names must be unique."""
        # Create first instance
        models.NVLinkDomain.objects.create(name="UniqueTest", location=self.location, status=self.nvl_status)

        # Attempt to create duplicate - should fail validation
        duplicate = models.NVLinkDomain(name="UniqueTest", location=self.location, status=self.nvl_status)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

        # Should also fail at database level
        with self.assertRaises(IntegrityError):
            duplicate.save()

    def test_nvlinkdomain_protocol_choices(self):
        """Test protocol field accepts valid choices."""
        protocol_choices = choices.NVLinkDomainProtocolChoices.CHOICES

        for protocol_value, protocol_label in protocol_choices:
            with self.subTest(protocol=protocol_label):
                nvlinkdomain = models.NVLinkDomain.objects.create(
                    name=f"Test-{protocol_value}",
                    location=self.location,
                    status=self.nvl_status,
                    protocol=protocol_value,
                )
                self.assertEqual(nvlinkdomain.protocol, protocol_value)

    def test_nvlinkdomain_topology_choices(self):
        """Test topology field accepts valid choices."""
        topology_choices = choices.NVLinkDomainTopologyChoices.CHOICES

        for topology_value, topology_label in topology_choices:
            with self.subTest(topology=topology_label):
                nvlinkdomain = models.NVLinkDomain.objects.create(
                    name=f"Test-{topology_value}",
                    location=self.location,
                    status=self.nvl_status,
                    topology=topology_value,
                )
                self.assertEqual(nvlinkdomain.topology, topology_value)

    def test_nvlinkdomain_cluster_id_validation(self):
        """Test cluster_id field validation."""
        nvlinkdomain = models.NVLinkDomain.objects.create(
            name="Cluster Test",
            location=self.location,
            status=self.nvl_status,
            cluster_id="valid-cluster-123",
        )
        self.assertEqual(nvlinkdomain.cluster_id, "valid-cluster-123")

        nvlinkdomain2 = models.NVLinkDomain.objects.create(
            name="No Cluster Test", location=self.location, status=self.nvl_status, cluster_id=""
        )
        self.assertEqual(nvlinkdomain2.cluster_id, "")

    def test_nvlinkdomain_existing_fixtures(self):
        """Test the existing NVLinkDomain fixtures."""
        self.assertEqual(len(self.nvl_domains), 3)

        domain1 = self.nvl_domains[0]
        self.assertEqual(domain1.name, "Test NVLink Domain 1")
        self.assertEqual(domain1.protocol, choices.NVLinkDomainProtocolChoices.NVLINK_V5)
        self.assertEqual(domain1.topology, choices.NVLinkDomainTopologyChoices.GB200_NVL36R1_C2G4)
        self.assertEqual(domain1.cluster_id, "cluster-1")
        self.assertIn(self.tag, domain1.tags)

        domain2 = self.nvl_domains[1]
        self.assertEqual(domain2.name, "Test NVLink Domain 2")
        self.assertEqual(domain2.protocol, choices.NVLinkDomainProtocolChoices.NVLINK_V3)
        self.assertEqual(domain2.role, self.nvl_role)
        self.assertEqual(domain2.tenant, self.tenant)


class ResourceBlockTestCase(ModelTestCases.BaseModelTestCase):
    """Test ResourceBlock model."""

    model = models.ResourceBlock

    @classmethod
    def setUpTestData(cls):
        """Set up test data for ResourceBlock tests."""
        fixtures.rb_test_data(cls)

    def test_get_docs_url(self):
        """Skip docs URL test - no documentation available."""
        self.skipTest("No documentation available for this model")

    def test_create_resource_block_required_fields_only(self):
        """Test creating ResourceBlock with only required fields."""
        resource_block = models.ResourceBlock.objects.create(
            name="Minimal Resource Block", status=self.rb_status
        )
        self.assertEqual(resource_block.name, "Minimal Resource Block")
        self.assertEqual(resource_block.device_count, 0)
        self.assertEqual(resource_block.static_device_count, 0)
        self.assertEqual(resource_block.dynamic_device_count, 0)

    def test_create_resource_block_all_fields(self):
        """Test creating ResourceBlock with all fields populated."""
        resource_block = models.ResourceBlock.objects.create(
            name="Full Resource Block",
            location=self.location,
            status=self.rb_status,
            protocol=choices.ResourceBlockProtocolChoices.SPECTRUMX,
            role=self.rb_role,
            tenant=self.tenant,
            dynamic_group=self.dynamic_groups[0],
        )
        self.assertEqual(resource_block.name, "Full Resource Block")
        self.assertEqual(resource_block.protocol, choices.ResourceBlockProtocolChoices.SPECTRUMX)
        self.assertEqual(resource_block.role, self.rb_role)
        self.assertEqual(resource_block.tenant, self.tenant)
        self.assertEqual(resource_block.dynamic_group, self.dynamic_groups[0])

    def test_resource_block_required_fields_validation(self):
        """Test that required fields are validated."""
        # Test missing name
        with self.assertRaises(ValidationError):
            resource_block = models.ResourceBlock(status=self.rb_status)
            resource_block.full_clean()

        # Test missing status
        with self.assertRaises(ValidationError):
            resource_block = models.ResourceBlock(name="Test Resource Block")
            resource_block.full_clean()

    def test_resource_block_name_uniqueness(self):
        """Test that ResourceBlock names must be unique."""
        # Create first instance
        models.ResourceBlock.objects.create(name="UniqueTest", status=self.rb_status)

        # Attempt to create duplicate - should fail validation
        duplicate = models.ResourceBlock(name="UniqueTest", status=self.rb_status)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

        # Should also fail at database level
        with self.assertRaises(IntegrityError):
            duplicate.save()

    def test_resource_block_protocol_choices(self):
        """Test protocol field accepts valid choices."""
        protocol_choices = choices.ResourceBlockProtocolChoices.CHOICES

        for protocol_value, protocol_label in protocol_choices:
            with self.subTest(protocol=protocol_label):
                resource_block = models.ResourceBlock.objects.create(
                    name=f"Test-{protocol_value}",
                    status=self.rb_status,
                    protocol=protocol_value,
                )
                self.assertEqual(resource_block.protocol, protocol_value)

    def test_get_static_devices(self):
        """Test getting static devices from ResourceBlock."""
        # Use first resource block which has static devices assigned
        rb = self.resource_blocks[0]
        static_devices = rb.get_static_devices()

        # Should return only the manually assigned devices
        self.assertEqual(rb.static_device_count, 2)
        self.assertEqual(static_devices.count(), 2)

        # Check that returned devices are the ones we assigned in fixtures
        expected_devices = self.static_devices[:2]
        self.assertQuerysetEqual(static_devices, expected_devices, ordered=False)

    def test_get_dynamic_devices(self):
        """Test getting dynamic devices from ResourceBlock."""
        # Use first resource block which has dynamic group assigned
        rb = self.resource_blocks[0]
        dynamic_devices = rb.get_dynamic_devices()

        # Should return devices matching the dynamic group filter
        # Dynamic group filter matches devices starting with "Dynamic Device"
        expected_count = rb.dynamic_device_count
        self.assertGreater(expected_count, 0, "Dynamic group should contain devices")
        self.assertEqual(dynamic_devices.count(), expected_count)

    def test_get_all_devices(self):
        """Test getting all devices (static and dynamic) from ResourceBlock."""
        rb = self.resource_blocks[0]
        all_devices = rb.get_devices()

        # Verify total device count is consistent with static + dynamic counts
        total_count = rb.device_count
        static_count = rb.static_device_count
        dynamic_count = rb.dynamic_device_count

        self.assertGreaterEqual(total_count, static_count)
        self.assertGreaterEqual(total_count, dynamic_count)
        self.assertEqual(all_devices.count(), total_count)

    def test_get_devices_deduplication(self):
        """Test that get_devices() properly deduplicates overlapping devices."""
        # Create a new resource block with dynamic group
        rb = models.ResourceBlock.objects.create(
            name="Overlap Test RB",
            status=self.rb_status,
            location=self.location,
            dynamic_group=self.dynamic_groups[0],  # Contains dynamic devices by name filter
        )

        # Use unassigned devices from fixtures for static assignment
        overlap_test_devices = self.unassigned_devices[:4]
        rb.devices.set(overlap_test_devices)

        all_devices = rb.get_devices()

        # Verify device count logic is working correctly
        self.assertEqual(rb.static_device_count, 4)
        self.assertGreaterEqual(rb.device_count, rb.static_device_count)
        self.assertEqual(all_devices.count(), rb.device_count)

    def test_device_count_properties(self):
        """Test the device count properties update correctly."""
        # Use unassigned devices from fixtures instead of creating new ones
        count_test_devices = self.unassigned_devices[4:7]  # Use next 3 unassigned devices

        # Create empty resource block
        rb = models.ResourceBlock.objects.create(
            name="Count Test RB", status=self.rb_status, location=self.location
        )

        # Initially empty
        self.assertEqual(rb.device_count, 0)
        self.assertEqual(rb.static_device_count, 0)
        self.assertEqual(rb.dynamic_device_count, 0)

        # Add static devices
        rb.devices.set(count_test_devices)
        self.assertEqual(rb.static_device_count, 3)
        self.assertEqual(rb.device_count, 3)

        # Add dynamic group
        rb.dynamic_group = self.dynamic_groups[0]
        rb.save()

        # Verify dynamic devices are counted correctly
        dynamic_count = rb.dynamic_device_count
        total_count = rb.device_count
        self.assertGreaterEqual(total_count, 3)  # At least our 3 static devices
        self.assertEqual(dynamic_count, 6)

    def test_dynamic_group_none_handling(self):
        """Test behavior when dynamic_group is None."""
        rb = models.ResourceBlock.objects.create(
            name="No Dynamic Group RB", status=self.rb_status, location=self.location, dynamic_group=None
        )

        self.assertEqual(rb.dynamic_device_count, 0)
        self.assertEqual(rb.get_dynamic_devices().count(), 0)

    def test_empty_resource_block(self):
        """Test behavior with no devices assigned."""
        rb = models.ResourceBlock.objects.create(
            name="Empty RB", status=self.rb_status, location=self.location
        )

        self.assertEqual(rb.device_count, 0)
        self.assertEqual(rb.static_device_count, 0)
        self.assertEqual(rb.dynamic_device_count, 0)
        self.assertEqual(rb.get_devices().count(), 0)
        self.assertEqual(rb.get_static_devices().count(), 0)
        self.assertEqual(rb.get_dynamic_devices().count(), 0)

    def test_device_unique_constraint_validation(self):
        """Test that devices cannot be assigned to multiple ResourceBlocks."""
        # This test is moved to ResourceBlockTransactionTestCase since it involves IntegrityError
        # Here we just test the basic functionality using fixtures
        test_device = self.unassigned_devices[7]  # Use an unassigned device

        rb1 = models.ResourceBlock.objects.create(
            name="Basic Test RB", status=self.rb_status, location=self.location
        )

        # Basic assignment should work
        rb1.devices.add(test_device)
        self.assertEqual(rb1.static_device_count, 1)
        self.assertTrue(hasattr(test_device, "resource_block_membership"))
        self.assertEqual(test_device.resource_block_membership.resource_block, rb1)

    def test_device_assignment_through_membership_model(self):
        """Test device assignment creates proper ResourceBlockMembership instances."""
        # Use unassigned devices from fixtures instead of creating new ones
        test_devices = self.unassigned_devices[8:11]  # Use next 3 unassigned devices

        rb = models.ResourceBlock.objects.create(
            name="Membership Test RB", status=self.rb_status, location=self.location
        )

        # Assign devices
        rb.devices.set(test_devices)

        # Check that ResourceBlockMembership instances were created
        memberships = models.ResourceBlockMembership.objects.filter(resource_block=rb)
        self.assertEqual(memberships.count(), 3)

        # Check that each device has exactly one membership
        for device in test_devices:
            self.assertTrue(hasattr(device, "resource_block_membership"))
            self.assertEqual(device.resource_block_membership.resource_block, rb)

    def test_resource_block_existing_fixtures(self):
        """Test the existing ResourceBlock fixtures."""
        self.assertEqual(len(self.resource_blocks), 4)

        # Test first resource block
        rb1 = self.resource_blocks[0]
        self.assertEqual(rb1.name, "Test Resource Block 1")
        self.assertEqual(rb1.protocol, choices.ResourceBlockProtocolChoices.ETHERNET)
        self.assertEqual(rb1.dynamic_group, self.dynamic_groups[0])
        self.assertIn(self.tag, rb1.tags)
        self.assertEqual(rb1.static_device_count, 2)

        # Test second resource block
        rb2 = self.resource_blocks[1]
        self.assertEqual(rb2.name, "Test Resource Block 2")
        self.assertEqual(rb2.protocol, choices.ResourceBlockProtocolChoices.INFINIBAND)
        self.assertEqual(rb2.role, self.rb_role)
        self.assertEqual(rb2.tenant, self.tenant)


class ResourceBlockMembershipTestCase(ModelTestCases.BaseModelTestCase):
    """Test ResourceBlockMembership model."""

    model = models.ResourceBlockMembership

    @classmethod
    def setUpTestData(cls):
        """Set up test data for ResourceBlockMembership tests."""
        fixtures.rb_test_data(cls)

    def test_get_docs_url(self):
        """Skip docs URL test - no documentation available."""
        self.skipTest("No documentation available for this model")

    def test_create_membership_required_fields_only(self):
        """Test creating ResourceBlockMembership with only required fields."""
        test_device = self.unassigned_devices[0]
        membership = models.ResourceBlockMembership.objects.create(
            resource_block=self.resource_blocks[0], device=test_device
        )
        self.assertEqual(membership.resource_block, self.resource_blocks[0])
        self.assertEqual(membership.device, test_device)
        self.assertEqual(str(membership), f"{test_device} in {self.resource_blocks[0]}")

    def test_membership_required_fields_validation(self):
        """Test that required fields are validated."""
        test_device = self.unassigned_devices[1]
        with self.assertRaises(ValidationError):
            membership = models.ResourceBlockMembership(device=test_device)
            membership.full_clean()
        with self.assertRaises(ValidationError):
            membership = models.ResourceBlockMembership(resource_block=self.resource_blocks[0])
            membership.full_clean()

    def test_device_one_to_one_constraint(self):
        """Test that devices can only have one ResourceBlockMembership."""
        test_device = self.unassigned_devices[2]
        models.ResourceBlockMembership.objects.create(
            resource_block=self.resource_blocks[0], device=test_device
        )
        with self.assertRaises(IntegrityError):
            models.ResourceBlockMembership.objects.create(
                resource_block=self.resource_blocks[1], device=test_device
            )


class ResourceBlockTransactionTestCase(TransactionTestCase):
    """Additional ResourceBlock tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up test data that requires transaction handling."""
        # Use the transaction test data fixture
        fixtures.transaction_test_data(self)

    def test_device_unique_assignment_constraint(self):
        """Test that devices can only belong to one ResourceBlock at a time."""
        # Create two resource blocks
        rb1 = models.ResourceBlock.objects.create(
            name="First RB",
            status=self.rb_status,
            location=self.location,
        )
        rb2 = models.ResourceBlock.objects.create(
            name="Second RB",
            status=self.rb_status,
            location=self.location,
        )

        # Assign device to first resource block
        test_device = self.test_devices[0]
        rb1.devices.set([test_device])
        self.assertEqual(rb1.static_device_count, 1)
        self.assertIn(test_device, rb1.devices.all())

        # Attempt to assign same device to second resource block should fail
        with self.assertRaises(IntegrityError):
            rb2.devices.add(test_device)

    def test_device_multiple_assignment_integrity_error(self):
        """Test that attempting to assign a device to multiple ResourceBlocks raises IntegrityError."""
        # Create two resource blocks
        rb1 = models.ResourceBlock.objects.create(
            name="Multi Test RB1",
            status=self.rb_status,
            location=self.location,
        )
        rb2 = models.ResourceBlock.objects.create(
            name="Multi Test RB2",
            status=self.rb_status,
            location=self.location,
        )

        # Assign device to first resource block
        test_device = self.test_devices[1]  # Use a different device
        rb1.devices.add(test_device)
        self.assertEqual(rb1.static_device_count, 1)

        # Attempting to assign the same device to second resource block should fail
        with self.assertRaises(IntegrityError):
            rb2.devices.add(test_device)

        # Verify the device is still only in the first resource block
        self.assertEqual(rb1.static_device_count, 1)
        self.assertEqual(rb2.static_device_count, 0)

    def test_device_can_be_reassigned_after_removal(self):
        """Test that a device can be reassigned to a different ResourceBlock after removal."""
        # Create two resource blocks
        rb1 = models.ResourceBlock.objects.create(
            name="First Assignment RB",
            status=self.rb_status,
            location=self.location,
        )
        rb2 = models.ResourceBlock.objects.create(
            name="Second Assignment RB",
            status=self.rb_status,
            location=self.location,
        )

        test_device = self.test_devices[0]

        # Assign device to first resource block
        rb1.devices.set([test_device])
        self.assertEqual(rb1.static_device_count, 1)

        # Remove device from first resource block
        rb1.devices.remove(test_device)
        self.assertEqual(rb1.static_device_count, 0)

        # Now should be able to assign to second resource block
        rb2.devices.add(test_device)
        self.assertEqual(rb2.static_device_count, 1)
        self.assertIn(test_device, rb2.devices.all())

    def test_dynamic_group_device_updates(self):
        """Test that device counts update when dynamic group membership changes."""
        # Create dynamic group with filter that matches our test devices
        dynamic_group = DynamicGroup.objects.create(
            name="Transaction Dynamic Group",
            content_type=self.device_ct,
            filter={"name__startswith": ["Transaction Test Device"]},
        )

        rb = models.ResourceBlock.objects.create(
            name="Dynamic Update RB",
            status=self.rb_status,
            location=self.location,
            dynamic_group=dynamic_group,
        )

        # Should initially include all our test devices
        initial_count = rb.dynamic_device_count
        self.assertEqual(initial_count, 6)

        # Remove the dynamic group
        rb.dynamic_group = None
        rb.save()

        # Should now have no dynamic devices
        self.assertEqual(rb.dynamic_device_count, 0)
