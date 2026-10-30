"""Tests for controlled LPU C2C topology mutations."""

from threading import Barrier, Thread
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from nautobot.dcim.models import Device, Rack
from nautobot.extras.models import Status

from nautobot_nvdatamodels import models
from nautobot_nvdatamodels.lpu_c2c import mutations
from nautobot_nvdatamodels.tests import fixtures


class LPUC2CMutationTestCase(TransactionTestCase):
    """Exercise atomic, status-gated topology changes."""

    def setUp(self):
        fixtures.lpu_c2c_test_data(self)
        self.rack_two = Rack.objects.create(
            name="LPU C2C Mutation Rack Two", location=self.rack.location, status=self.rack.status
        )
        self.rack_three = Rack.objects.create(
            name="LPU C2C Mutation Rack Three", location=self.rack.location, status=self.rack.status
        )

    def positions(self):
        return list(self.domain.rack_positions.order_by("ordinal"))

    def test_append_position_assigns_next_ordinal(self):
        position = mutations.append_position(self.domain.pk, rack=self.rack)
        self.assertEqual(position.ordinal, 0)
        self.assertEqual(position.rack_id, self.rack.pk)

    def test_fill_position_assigns_vacancy_without_changing_ordinal(self):
        position = mutations.append_position(self.domain.pk)
        result = mutations.fill_position(position.pk, self.rack)
        self.assertEqual(result.ordinal, 0)
        self.assertEqual(result.rack_id, self.rack.pk)

    def test_vacate_position_preserves_ordinal_and_deletes_configurations(self):
        position = mutations.append_position(self.domain.pk, rack=self.rack)
        models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=position, excluded=True
        )
        mutations.vacate_position(position.pk)
        position.refresh_from_db()
        self.assertIsNone(position.rack)
        self.assertEqual(position.ordinal, 0)
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.exists())

    def test_remove_and_compact_deletes_position_and_shifts_later_ordinals(self):
        first = mutations.append_position(self.domain.pk, rack=self.rack)
        mutations.append_position(self.domain.pk, rack=self.rack_two)
        mutations.remove_and_compact_position(first.pk, confirmed=True)
        self.assertEqual([(item.ordinal, item.rack_id) for item in self.positions()], [(0, self.rack_two.pk)])

    def test_insert_position_makes_room_at_requested_ordinal(self):
        mutations.append_position(self.domain.pk, rack=self.rack)
        inserted = mutations.insert_position(self.domain.pk, 0, rack=self.rack_two, confirmed=True)
        self.assertEqual(inserted.ordinal, 0)
        self.assertEqual(
            [(item.ordinal, item.rack_id) for item in self.positions()],
            [(0, self.rack_two.pk), (1, self.rack.pk)],
        )

    def test_reorder_positions_applies_requested_order(self):
        first = mutations.append_position(self.domain.pk, rack=self.rack)
        second = mutations.append_position(self.domain.pk, rack=self.rack_two)
        mutations.reorder_positions(self.domain.pk, [second.pk, first.pk], confirmed=True)
        self.assertEqual([item.pk for item in self.positions()], [second.pk, first.pk])

    def test_set_endpoint_configuration_deletes_noop_and_persists_override(self):
        position = mutations.append_position(self.domain.pk, rack=self.rack)
        configuration = mutations.set_endpoint_configuration(self.device.pk, position.pk, tray_slot=16)
        self.assertEqual(configuration.device_id, self.device.pk)
        self.assertEqual(configuration.tray_slot, 16)
        result = mutations.set_endpoint_configuration(self.device.pk, position.pk)
        self.assertIsNone(result)
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.exists())

    def test_endpoint_configuration_cannot_bypass_active_source_domain_by_reassignment(self):
        source_position = mutations.append_position(self.domain.pk, rack=self.rack)
        target_position = mutations.append_position(self.other_domain.pk, rack=self.rack_two)
        models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=source_position, excluded=True
        )
        active = Status.objects.get(name="Active")
        self.domain.status = active
        self.domain.save()
        Device.objects.filter(pk=self.device.pk).update(rack=self.rack_two, location=self.rack_two.location)

        with self.assertRaises(mutations.DomainMutationNotAllowed):
            mutations.set_endpoint_configuration(self.device.pk, target_position.pk, excluded=True)

        configuration = models.LPUC2CEndpointConfiguration.objects.get(device=self.device)
        self.assertEqual(configuration.rack_position_id, source_position.pk)

    def test_stale_endpoint_configuration_can_be_deleted_through_its_mutable_source_domain(self):
        source_position = mutations.append_position(self.domain.pk, rack=self.rack)
        models.LPUC2CEndpointConfiguration.objects.create(
            device=self.device, rack_position=source_position, excluded=True
        )
        Device.objects.filter(pk=self.device.pk).update(rack=self.rack_two, location=self.rack_two.location)

        result = mutations.set_endpoint_configuration(self.device.pk, source_position.pk)

        self.assertIsNone(result)
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.filter(device=self.device).exists())

    def test_occupied_rack_rolls_back_insert(self):
        mutations.append_position(self.domain.pk, rack=self.rack)
        with self.assertRaises(ValidationError):
            mutations.insert_position(self.other_domain.pk, 0, rack=self.rack, confirmed=True)
        self.assertEqual(self.other_domain.rack_positions.count(), 0)

    def test_active_domain_rejects_mutations(self):
        active = Status.objects.get(name="LPU C2C Active")
        self.domain.status = active
        self.domain.save()
        with self.assertRaises(mutations.DomainMutationNotAllowed):
            mutations.append_position(self.domain.pk)

    def test_destructive_reorders_require_confirmation(self):
        position = mutations.append_position(self.domain.pk)
        with self.assertRaises(mutations.ConfirmationRequired):
            mutations.insert_position(self.domain.pk, 0)
        with self.assertRaises(mutations.ConfirmationRequired):
            mutations.remove_and_compact_position(position.pk)
        with self.assertRaises(mutations.ConfirmationRequired):
            mutations.reorder_positions(self.domain.pk, [position.pk])

    def test_activate_domain_rejects_invalid_projection_without_status_change(self):
        mutations.append_position(self.domain.pk, rack=self.rack)
        with self.assertRaises(mutations.InvalidTopologyProjection) as context:
            mutations.activate_domain(self.domain.pk)
        self.assertTrue(context.exception.diagnostics)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, self.planned_status.pk)

    def test_activate_domain_sets_active_for_ready_projection(self):
        mutations.append_position(self.domain.pk, rack=self.rack)
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )
        domain = mutations.activate_domain(self.domain.pk)
        self.assertEqual(domain.status.name, "Active")

    def test_activation_validates_domain_before_persisting_status(self):
        mutations.append_position(self.domain.pk, rack=self.rack)
        models.LPUC2CDeviceTypeCompatibility.objects.create(
            topology=self.domain.topology, device_type=self.device_type
        )
        with patch.object(models.LPUC2CDomain, "full_clean", side_effect=ValidationError("invalid domain")):
            with self.assertRaises(ValidationError):
                mutations.activate_domain(self.domain.pk)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status_id, self.planned_status.pk)

    def test_postgresql_concurrent_appends_allocate_distinct_dense_ordinals(self):
        """The domain lock serializes simultaneous append requests."""
        barrier = Barrier(2)
        failures = []

        def append_after_barrier():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                mutations.append_position(self.domain.pk)
            except Exception as error:  # pragma: no cover - asserted by the parent thread
                failures.append(error)
            finally:
                connection.close()

        threads = [Thread(target=append_after_barrier) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertFalse(failures)
        self.assertEqual(
            list(self.domain.rack_positions.order_by("ordinal").values_list("ordinal", flat=True)), [0, 1]
        )

    def test_postgresql_concurrent_append_and_fill_complete_without_lock_order_failure(self):
        """Append and fill share the domain-first lock order under contention."""
        vacant_position = mutations.append_position(self.domain.pk)
        barrier = Barrier(2)
        failures = []

        def mutate_after_barrier(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
            except Exception as error:  # pragma: no cover - asserted by the parent thread
                failures.append(error)
            finally:
                connection.close()

        threads = [
            Thread(target=mutate_after_barrier, args=(lambda: mutations.append_position(self.domain.pk),)),
            Thread(
                target=mutate_after_barrier,
                args=(lambda: mutations.fill_position(vacant_position.pk, self.rack),),
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertFalse(failures)
        self.assertEqual(
            list(self.domain.rack_positions.order_by("ordinal").values_list("ordinal", flat=True)), [0, 1]
        )
        vacant_position.refresh_from_db()
        self.assertEqual(vacant_position.rack_id, self.rack.pk)

    def test_postgresql_concurrent_configuration_update_and_vacate_complete_without_deadlock(self):
        """Configuration mutation never holds a device lock while waiting for the domain lock."""
        position = mutations.append_position(self.domain.pk, rack=self.rack)
        mutations.set_endpoint_configuration(self.device.pk, position.pk, excluded=True)
        barrier = Barrier(2)
        failures = []

        def mutate_after_barrier(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
            except Exception as error:  # pragma: no cover - asserted by the parent thread
                failures.append(error)
            finally:
                connection.close()

        threads = [
            Thread(
                target=mutate_after_barrier,
                args=(lambda: mutations.set_endpoint_configuration(self.device.pk, position.pk),),
            ),
            Thread(target=mutate_after_barrier, args=(lambda: mutations.vacate_position(position.pk),)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertFalse(failures)
        position.refresh_from_db()
        self.assertIsNone(position.rack_id)
        self.assertFalse(models.LPUC2CEndpointConfiguration.objects.filter(device=self.device).exists())
