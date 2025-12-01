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
"""Create fixtures for tests."""

from django.contrib.contenttypes.models import ContentType
from nautobot.dcim.models import Device, DeviceType, Location, LocationType, Manufacturer
from nautobot.extras.models import DynamicGroup, Role, Status, Tag
from nautobot.tenancy.models import Tenant

from nautobot_nvdatamodels import choices
from nautobot_nvdatamodels.models import NVLinkDomain, ResourceBlock


def common_test_data(cls):
    """Create common test data for NVLinkDomain and ResourceBlock."""
    cls.nvl_ct = ContentType.objects.get_for_model(NVLinkDomain)
    cls.rb_ct = ContentType.objects.get_for_model(ResourceBlock)
    cls.device_ct = ContentType.objects.get_for_model(Device)
    cls.location_ct = ContentType.objects.get_for_model(Location)
    cls.location_status = Status.objects.get_for_model(Location).first()
    if not cls.location_status:
        cls.location_status = Status.objects.create(name="Test Active")
        cls.location_status.content_types.add(cls.location_ct)
    cls.nvl_status = Status.objects.get_for_model(NVLinkDomain).first()
    cls.rb_status = Status.objects.get_for_model(ResourceBlock).first()
    cls.device_status = Status.objects.get_for_model(Device).first()
    cls.location_type = LocationType.objects.create(name="Test Location Type")
    cls.location_type.content_types.add(cls.nvl_ct, cls.rb_ct, cls.location_ct)
    cls.location = Location.objects.create(
        name="Test Location", location_type=cls.location_type, status=cls.location_status
    )
    cls.location2 = Location.objects.create(
        name="Test Location 2", location_type=cls.location_type, status=cls.location_status
    )
    cls.tag = Tag.objects.create(name="Test Tag", color="ff0000")
    cls.tag.content_types.set([cls.nvl_ct, cls.rb_ct])
    cls.tag2 = Tag.objects.create(name="Test Tag 2", color="00ff00")
    cls.tag2.content_types.set([cls.nvl_ct, cls.rb_ct])
    cls.manufacturer = Manufacturer.objects.create(name="Test Manufacturer")
    cls.device_type = DeviceType.objects.create(manufacturer=cls.manufacturer, model="Test Device Type")
    cls.device_role = Role.objects.create(name="Test Role")
    cls.tenant = Tenant.objects.create(name="Test Tenant")
    cls.tenant2 = Tenant.objects.create(name="Test Tenant 2")

    cls.nvl_role = Role.objects.create(name="Test NVL Role", color="ffffff")
    cls.nvl_role.content_types.add(cls.nvl_ct)
    cls.rb_role = Role.objects.create(name="Test RB Role", color="ffffff")
    cls.rb_role.content_types.add(cls.rb_ct)

    cls.unassigned_devices = [
        Device.objects.create(
            name=f"Unassigned Device {i}",
            role=cls.device_role,
            status=cls.device_status,
            location=cls.location,
            device_type=cls.device_type,
        )
        for i in range(11)
    ]


def nvl_test_data(cls):
    """NVLinkDomain test data."""
    common_test_data(cls)

    cls.nvl_domains = [
        NVLinkDomain.objects.create(
            name="Test NVLink Domain 1",
            location=cls.location,
            status=cls.nvl_status,
            protocol=choices.NVLinkDomainProtocolChoices.NVLINK_V5,
            topology=choices.NVLinkDomainTopologyChoices.GB200_NVL36R1_C2G4,
            cluster_id="cluster-1",
            tags=[cls.tag],
        ),
        NVLinkDomain.objects.create(
            name="Test NVLink Domain 2",
            location=cls.location2,
            status=cls.nvl_status,
            protocol=choices.NVLinkDomainProtocolChoices.NVLINK_V3,
            topology=choices.NVLinkDomainTopologyChoices.GB200_NVL72R2_C2G4,
            cluster_id="cluster-2",
            role=cls.nvl_role,
            tenant=cls.tenant,
            tags=[cls.tag2],
        ),
        NVLinkDomain.objects.create(
            name="Test NVLink Domain 3",
            location=cls.location,
            status=cls.nvl_status,
            protocol=choices.NVLinkDomainProtocolChoices.INFINIBAND,
            cluster_id="cluster-3",
            tenant=cls.tenant2,
            tags=[cls.tag],
        ),
    ]


def rb_test_data(cls):
    """ResourceBlock test data."""
    common_test_data(cls)

    cls.static_devices = [
        Device.objects.create(
            name=f"Static Device {i}",
            role=cls.device_role,
            status=cls.device_status,
            location=cls.location,
            device_type=cls.device_type,
        )
        for i in range(6)
    ]
    cls.dynamic_devices = [
        Device.objects.create(
            name=f"Dynamic Device {i}",
            role=cls.device_role,
            status=cls.device_status,
            location=cls.location,
            device_type=cls.device_type,
        )
        for i in range(6)
    ]

    cls.dynamic_groups = [
        DynamicGroup.objects.create(
            name="Test Dynamic Group",
            content_type=cls.device_ct,
            filter={"q": "Dynamic Device"},
        ),
        DynamicGroup.objects.create(
            name="Test Dynamic Group 2",
            content_type=cls.device_ct,
            filter={"location": [cls.location2.name]},
        ),
    ]

    cls.resource_blocks = [
        ResourceBlock.objects.create(
            name="Test Resource Block 1",
            location=cls.location,
            status=cls.rb_status,
            protocol=choices.ResourceBlockProtocolChoices.ETHERNET,
            dynamic_group=cls.dynamic_groups[0],
            tags=[cls.tag],
        ),
        ResourceBlock.objects.create(
            name="Test Resource Block 2",
            location=cls.location2,
            status=cls.rb_status,
            protocol=choices.ResourceBlockProtocolChoices.INFINIBAND,
            role=cls.rb_role,
            tenant=cls.tenant,
            dynamic_group=cls.dynamic_groups[1],
            tags=[cls.tag2],
        ),
        ResourceBlock.objects.create(
            name="Test Resource Block 3",
            location=cls.location,
            status=cls.rb_status,
            protocol=choices.ResourceBlockProtocolChoices.RDMA,
            tenant=cls.tenant2,
            tags=[cls.tag],
        ),
        ResourceBlock.objects.create(
            name="Test Resource Block 4",
            location=cls.location2,
            status=cls.rb_status,
            protocol=choices.ResourceBlockProtocolChoices.SPECTRUMX,
            role=cls.rb_role,
            tags=[cls.tag, cls.tag2],
        ),
    ]

    cls.resource_blocks[0].devices.set(cls.static_devices[:2])
    cls.resource_blocks[1].devices.set(cls.static_devices[2:4])
    cls.resource_blocks[2].devices.set(cls.static_devices[4:6])


def transaction_test_data(instance):
    """Create test data for TransactionTestCase (instance-based not class-based)."""
    instance.rb_ct = ContentType.objects.get_for_model(ResourceBlock)
    instance.device_ct = ContentType.objects.get_for_model(Device)
    instance.location_ct = ContentType.objects.get_for_model(Location)

    instance.location_status = Status.objects.get_for_model(Location).first()
    if not instance.location_status:
        instance.location_status = Status.objects.create(name="Transaction Active")
        instance.location_status.content_types.add(instance.location_ct)

    instance.rb_status = Status.objects.get_for_model(ResourceBlock).first()
    if not instance.rb_status:
        instance.rb_status = Status.objects.create(name="Transaction RB Active")
        instance.rb_status.content_types.add(instance.rb_ct)

    instance.device_status = Status.objects.get_for_model(Device).first()
    if not instance.device_status:
        instance.device_status = Status.objects.create(name="Transaction Device Active")
        instance.device_status.content_types.add(instance.device_ct)

    instance.location_type = LocationType.objects.create(name="Transaction Test Location Type")
    instance.location_type.content_types.add(instance.rb_ct, instance.location_ct)
    instance.location = Location.objects.create(
        name="Transaction Test Location",
        location_type=instance.location_type,
        status=instance.location_status,
    )
    instance.manufacturer = Manufacturer.objects.create(name="Transaction Test Manufacturer")
    instance.device_type = DeviceType.objects.create(
        manufacturer=instance.manufacturer, model="Transaction Test Device Type"
    )
    instance.device_role = Role.objects.create(name="Transaction Test Role")

    # Create test devices
    instance.test_devices = [
        Device.objects.create(
            name=f"Transaction Test Device {i}",
            role=instance.device_role,
            status=instance.device_status,
            location=instance.location,
            device_type=instance.device_type,
        )
        for i in range(6)
    ]

    # Add helper function
    instance.create_test_device = lambda name: Device.objects.create(
        name=name,
        role=instance.device_role,
        status=instance.device_status,
        location=instance.location,
        device_type=instance.device_type,
    )
