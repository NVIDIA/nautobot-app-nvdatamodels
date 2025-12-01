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
"""Test forms for nautobot_nvdatamodels app."""

from nautobot.core.testing.forms import FormTestCases
from nautobot.dcim.models import Device
from nautobot.extras.models import DynamicGroup

from nautobot_nvdatamodels import choices, forms, models
from nautobot_nvdatamodels.tests import fixtures


class NVLinkDomainTestCase(FormTestCases.BaseFormTestCase):
    """Test NVLinkDomain forms."""

    form_class = forms.NVLinkDomainForm

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        fixtures.common_test_data(cls)

    def test_form_dynamic_model_choice_fields_query_params(self):
        """Skip this test as it doesn't understand filter extensions."""
        self.skipTest("Base test doesn't account for filter extension query params")

    def test_nvlinkdomain_form_with_all_fields(self):
        """Test NVLinkDomain form with all fields specified."""
        form = self.form_class(
            data={
                "name": "Test NVLink Domain",
                "location": self.location.pk,
                "status": self.nvl_status.pk,
                "role": self.nvl_role.pk,
                "tenant": self.tenant.pk,
                "protocol": choices.NVLinkDomainProtocolChoices.NVLINK_V5,
                "topology": choices.NVLinkDomainTopologyChoices.GB200_NVL36R1_C2G4,
                "cluster_id": "test-cluster-123",
                "tags": [self.tag.pk],
            }
        )
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_domain = form.save()
        self.assertEqual(saved_domain.name, "Test NVLink Domain")
        self.assertEqual(saved_domain.cluster_id, "test-cluster-123")
        self.assertEqual(saved_domain.protocol, choices.NVLinkDomainProtocolChoices.NVLINK_V5)

    def test_nvlinkdomain_form_required_fields_only(self):
        """Test NVLinkDomain form with only required fields."""
        form = self.form_class(
            data={
                "name": "Minimal Domain",
                "location": self.location.pk,
                "status": self.nvl_status.pk,
            }
        )
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_domain = form.save()
        self.assertEqual(saved_domain.name, "Minimal Domain")

    def test_nvlinkdomain_form_missing_required_name(self):
        """Test that name field is required."""
        form = self.form_class(
            data={
                "location": self.location.pk,
                "status": self.nvl_status.pk,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("This field is required.", form.errors["name"])

    def test_nvlinkdomain_form_missing_required_status(self):
        """Test that status field is required."""
        form = self.form_class(
            data={
                "name": "Test Domain",
                "location": self.location.pk,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_nvlinkdomain_form_duplicate_name(self):
        """Test form validation fails with duplicate name."""
        # Create existing domain
        models.NVLinkDomain.objects.create(
            name="Existing Domain",
            location=self.location,
            status=self.nvl_status,
        )

        form = self.form_class(
            data={
                "name": "Existing Domain",  # Duplicate name
                "location": self.location.pk,
                "status": self.nvl_status.pk,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_nvlinkdomain_form_with_protocol_and_topology(self):
        """Test form with protocol and topology choices."""
        form = self.form_class(
            data={
                "name": "Protocol Test Domain",
                "location": self.location.pk,
                "status": self.nvl_status.pk,
                "protocol": choices.NVLinkDomainProtocolChoices.INFINIBAND,
                "topology": choices.NVLinkDomainTopologyChoices.GB200_NVL72R2_C2G4,
            }
        )
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_domain = form.save()
        self.assertEqual(saved_domain.protocol, choices.NVLinkDomainProtocolChoices.INFINIBAND)
        self.assertEqual(saved_domain.topology, choices.NVLinkDomainTopologyChoices.GB200_NVL72R2_C2G4)

    def test_nvlinkdomain_form_with_members(self):
        """Test form with member devices."""
        # Create test devices that can be assigned
        test_device = Device.objects.create(
            name="Test Member Device",
            device_type=self.device_type,
            role=self.device_role,
            status=self.device_status,
            location=self.location,
        )

        form = self.form_class(
            data={
                "name": "Domain with Members",
                "location": self.location.pk,
                "status": self.nvl_status.pk,
                "members": [test_device.pk],
            }
        )
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_domain = form.save()
        self.assertTrue(saved_domain.nvlink_domain_membership.filter(member=test_device).exists())


class ResourceBlockTestCase(FormTestCases.BaseFormTestCase):
    """Test the ResourceBlock form."""

    form_class = forms.ResourceBlockForm

    @classmethod
    def setUpTestData(cls):
        """Set up the test case."""
        fixtures.common_test_data(cls)

        # Create additional test devices for form testing
        cls.form_test_devices = [
            Device.objects.create(
                name=f"Form Test Device {i}",
                role=cls.device_role,
                status=cls.device_status,
                location=cls.location,
                device_type=cls.device_type,
            )
            for i in range(5)
        ]

        # Create a dynamic group for form testing
        cls.form_dynamic_group = DynamicGroup.objects.create(
            name="Form Test Dynamic Group",
            content_type=cls.device_ct,
            filter={"name__startswith": ["Form Test Device"]},
        )

    def test_form_dynamic_model_choice_fields_query_params(self):
        """Skip this test as it doesn't understand filter extensions."""
        self.skipTest("Base test doesn't account for filter extension query params")

    def test_resourceblock_form_with_all_fields(self):
        """Test ResourceBlock form with all fields specified."""
        form_data = {
            "name": "Complete Resource Block",
            "status": self.rb_status.pk,
            "location": self.location.pk,
            "role": self.rb_role.pk,
            "tenant": self.tenant.pk,
            "protocol": choices.ResourceBlockProtocolChoices.ETHERNET,
            "devices": [self.form_test_devices[0].pk, self.form_test_devices[1].pk],
            "dynamic_group": self.form_dynamic_group.pk,
            "tags": [self.tag.pk],
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_rb = form.save()
        self.assertEqual(saved_rb.name, "Complete Resource Block")
        self.assertEqual(saved_rb.protocol, choices.ResourceBlockProtocolChoices.ETHERNET)
        self.assertEqual(saved_rb.static_device_count, 2)

    def test_resourceblock_form_required_fields_only(self):
        """Test ResourceBlock form with only required fields."""
        form_data = {
            "name": "Minimal Resource Block",
            "status": self.rb_status.pk,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_rb = form.save()
        self.assertEqual(saved_rb.name, "Minimal Resource Block")

    def test_resourceblock_form_without_devices(self):
        """Test ResourceBlock form without any devices assigned."""
        form_data = {
            "name": "Empty Resource Block",
            "status": self.rb_status.pk,
            "location": self.location.pk,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_rb = form.save()
        self.assertEqual(saved_rb.static_device_count, 0)

    def test_resourceblock_form_with_only_static_devices(self):
        """Test ResourceBlock form with only static devices."""
        form_data = {
            "name": "Static Only RB",
            "status": self.rb_status.pk,
            "location": self.location.pk,
            "devices": [self.form_test_devices[0].pk, self.form_test_devices[1].pk],
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_rb = form.save()
        self.assertEqual(saved_rb.static_device_count, 2)
        self.assertIsNone(saved_rb.dynamic_group)

    def test_resourceblock_form_with_only_dynamic_group(self):
        """Test ResourceBlock form with only dynamic group."""
        form_data = {
            "name": "Dynamic Only RB",
            "status": self.rb_status.pk,
            "location": self.location.pk,
            "dynamic_group": self.form_dynamic_group.pk,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        saved_rb = form.save()
        self.assertEqual(saved_rb.static_device_count, 0)
        self.assertEqual(saved_rb.dynamic_group, self.form_dynamic_group)

    def test_resourceblock_form_missing_required_fields(self):
        """Test ResourceBlock form with missing required fields."""
        form_data = {
            "name": "Incomplete RB",
            # Missing status
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_resourceblock_form_missing_required_name(self):
        """Test that name field is required."""
        form_data = {
            "status": self.rb_status.pk,
            "location": self.location.pk,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("This field is required.", form.errors["name"])

    def test_resourceblock_form_duplicate_name(self):
        """Test ResourceBlock form validation fails with duplicate name."""
        # Create an existing resource block
        models.ResourceBlock.objects.create(name="Existing RB", status=self.rb_status, location=self.location)

        form_data = {
            "name": "Existing RB",  # Duplicate name
            "status": self.rb_status.pk,
            "location": self.location.pk,
        }
        form = self.form_class(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_resourceblock_form_protocol_choices(self):
        """Test ResourceBlock form with different protocol choices."""
        for protocol_value, protocol_label in choices.ResourceBlockProtocolChoices.CHOICES:
            with self.subTest(protocol=protocol_value):
                form_data = {
                    "name": f"Protocol {protocol_value} RB",
                    "status": self.rb_status.pk,
                    "location": self.location.pk,
                    "protocol": protocol_value,
                }
                form = self.form_class(data=form_data)
                self.assertTrue(form.is_valid(), f"Form errors for {protocol_value}: {form.errors}")
                saved_rb = form.save()
                self.assertEqual(saved_rb.protocol, protocol_value)

    def test_resourceblock_form_save_creates_correct_relationships(self):
        """Test that saving form creates the resource block with correct relationships."""
        form_data = {
            "name": "Relationship Test RB",
            "status": self.rb_status.pk,
            "location": self.location.pk,
            "devices": [self.form_test_devices[0].pk, self.form_test_devices[1].pk],
            "dynamic_group": self.form_dynamic_group.pk,
            "role": self.rb_role.pk,
            "tenant": self.tenant.pk,
        }
        form = self.form_class(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        resource_block = form.save()
        self.assertEqual(resource_block.name, "Relationship Test RB")
        self.assertEqual(resource_block.static_device_count, 2)
        self.assertEqual(resource_block.dynamic_group, self.form_dynamic_group)
        self.assertEqual(resource_block.role, self.rb_role)
        self.assertEqual(resource_block.tenant, self.tenant)
        self.assertTrue(resource_block.devices.filter(pk=self.form_test_devices[0].pk).exists())
        self.assertTrue(resource_block.devices.filter(pk=self.form_test_devices[1].pk).exists())
