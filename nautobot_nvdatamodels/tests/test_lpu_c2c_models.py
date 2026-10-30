"""Tests for LPU C2C domain models."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from nautobot_nvdatamodels import choices, models
from nautobot_nvdatamodels.tests import fixtures


class LPUC2CModelTestCase(TestCase):
    """Validate LPU C2C persistence and cross-model invariants."""

    @classmethod
    def setUpTestData(cls):
        fixtures.lpu_c2c_test_data(cls)

    def test_active_domain_can_transition_only_to_maintenance(self):
        active = type(self.planned_status).objects.get(name="LPU C2C Active")
        maintenance = type(self.planned_status).objects.get(name="LPU C2C Maintenance")
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active)

        self.domain.refresh_from_db()
        self.domain.status = self.planned_status
        with self.assertRaises(ValidationError) as context:
            self.domain.full_clean()
        self.assertIn("status", context.exception.message_dict)

        self.domain.refresh_from_db()
        self.domain.status = maintenance
        self.domain.full_clean()

    def test_active_domain_rejects_location_change(self):
        active = type(self.planned_status).objects.get(name="LPU C2C Active")
        models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain,
            ordinal=0,
            rack=self.rack,
        )
        models.LPUC2CDomain.objects.filter(pk=self.domain.pk).update(status=active)

        self.domain.refresh_from_db()
        self.domain.location = self.other_location
        with self.assertRaises(ValidationError) as context:
            self.domain.full_clean()

        self.assertIn("location", context.exception.message_dict)

    def test_domain_name_uniqueness_fails_at_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.LPUC2CDomain.objects.create(
                name=self.domain.name,
                status=self.planned_status,
                location=self.location,
                topology=choices.LPUC2CTopologyChoices.LP30_C2C,
            )

    def test_rack_cannot_occupy_two_domains(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0, rack=self.rack)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.LPUC2CDomainRackPosition.objects.create(
                domain=self.other_domain, ordinal=0, rack=self.rack
            )

    def test_duplicate_ordinal_per_domain_fails_at_database(self):
        models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=0)

    def test_rack_must_be_within_domain_location_hierarchy(self):
        position = models.LPUC2CDomainRackPosition(domain=self.domain, ordinal=0, rack=self.other_rack)
        with self.assertRaises(ValidationError) as context:
            position.full_clean()
        self.assertIn("rack", context.exception.message_dict)

    def test_duplicate_topology_device_type_compatibility_fails_at_database(self):
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.LPUC2CDeviceTypeCompatibility.objects.create(
                topology=self.domain.topology, device_type=self.device_type
            )

    def test_endpoint_configuration_rejects_device_rack_mismatch(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        config = models.LPUC2CEndpointConfiguration(
            device=self.other_device, rack_position=position, excluded=True
        )
        with self.assertRaises(ValidationError) as context:
            config.full_clean()
        self.assertIn("device", context.exception.message_dict)

    def test_endpoint_configuration_rejects_noop_row(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        config = models.LPUC2CEndpointConfiguration(device=self.device, rack_position=position)
        with self.assertRaises(ValidationError) as context:
            config.full_clean()
        self.assertIn("__all__", context.exception.message_dict)

    def test_endpoint_configuration_rejects_invalid_typed_override(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        config = models.LPUC2CEndpointConfiguration(device=self.device, rack_position=position, tray_slot=0)
        with self.assertRaises(ValidationError) as context:
            config.full_clean()
        self.assertIn("__all__", context.exception.message_dict)

    def test_endpoint_configuration_device_is_unique_at_database(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        another_position = models.LPUC2CDomainRackPosition.objects.create(domain=self.domain, ordinal=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.LPUC2CEndpointConfiguration.objects.create(
                device=self.device, rack_position=another_position, excluded=True
            )

    def test_deletion_contract(self):
        position = models.LPUC2CDomainRackPosition.objects.create(
            domain=self.domain, ordinal=0, rack=self.rack
        )
        config = models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        with self.assertRaises(ProtectedError):
            self.rack.delete()
        self.device.delete()
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.filter(pk=config.pk).exists())
        self.domain.delete()
        self.assertFalse(models.LPUC2CDomainRackPosition.objects.filter(pk=position.pk).exists())
