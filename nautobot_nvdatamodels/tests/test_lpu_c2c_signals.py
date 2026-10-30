"""Tests for LPU C2C Nautobot record provisioning."""

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from nautobot.dcim.models import Device, Rack
from nautobot.extras.models import Role, Status

from nautobot_nvdatamodels.models import LPUC2CDomain
from nautobot_nvdatamodels.signals import provision_lpu_c2c_records


class LPUC2CProvisioningTestCase(TestCase):
    """Verify provisioning creates stable Nautobot records for LPU C2C."""

    def setUp(self):
        """Remove records provisioned by the database-ready signal during test setup."""
        Role.objects.filter(name="LPU Tray").delete()
        Status.objects.filter(name="Active").delete()

    def test_provision_is_idempotent(self):
        """Provisioning twice creates one tray role."""
        provision_lpu_c2c_records(sender=None, apps=apps)
        provision_lpu_c2c_records(sender=None, apps=apps)

        self.assertEqual(Role.objects.filter(name="LPU Tray").count(), 1)
        role = Role.objects.get(name="LPU Tray")
        self.assertEqual(list(role.content_types.all()), [ContentType.objects.get_for_model(Device)])

    def test_provision_reuses_existing_role_and_active_status(self):
        """Provisioning enriches existing LPU records instead of replacing them."""
        rack_content_type = ContentType.objects.get_for_model(Rack)
        role = Role.objects.create(
            name="LPU Tray",
            color="ffffff",
            description="Administrator-managed tray role.",
        )
        role.content_types.add(rack_content_type)
        active_status = Status.objects.create(
            name="Active",
            color="ffffff",
            description="Administrator-managed active status.",
        )
        active_status.content_types.add(rack_content_type)

        provision_lpu_c2c_records(sender=None, apps=apps)

        role.refresh_from_db()
        self.assertEqual(role.pk, Role.objects.get(name="LPU Tray").pk)
        self.assertEqual(role.color, "ffffff")
        self.assertEqual(role.description, "Administrator-managed tray role.")
        self.assertEqual(
            set(role.content_types.all()),
            {rack_content_type, ContentType.objects.get_for_model(Device)},
        )
        active_status.refresh_from_db()
        self.assertEqual(active_status.pk, Status.objects.get(name="Active").pk)
        self.assertEqual(active_status.color, "ffffff")
        self.assertEqual(active_status.description, "Administrator-managed active status.")
        self.assertEqual(
            set(active_status.content_types.all()),
            {rack_content_type, ContentType.objects.get_for_model(LPUC2CDomain)},
        )
