"""Controlled, transactional mutations for LPU C2C domains."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from nautobot.dcim.models import Device, Rack
from nautobot.extras.models import Status

from nautobot_nvdatamodels import models

from .evaluator import evaluate_domain
from .types import ProjectionState


class DomainMutationNotAllowed(PermissionError):
    """Raised when a domain's lifecycle state forbids a topology mutation."""


class ConfirmationRequired(ValueError):
    """Raised when a topology-changing operation was not explicitly confirmed."""


class InvalidTopologyProjection(ValueError):
    """Raised when activation is requested for an invalid topology projection."""

    def __init__(self, diagnostics):
        self.diagnostics = tuple(diagnostics)
        super().__init__("LPU C2C topology projection is invalid.")


def _pk(value):
    return getattr(value, "pk", value)


def _status_name(status):
    return status.name.removeprefix("LPU C2C ")


def _locked_domain(domain):
    domain = (
        models.LPUC2CDomain.objects.select_for_update(of=("self",))
        .select_related("status")
        .get(pk=_pk(domain))
    )
    if _status_name(domain.status) not in {"Planned", "Maintenance"}:
        raise DomainMutationNotAllowed("Only Planned and Maintenance domains may be mutated.")
    return domain


def _locked_positions(domain):
    return list(
        models.LPUC2CDomainRackPosition.objects.select_for_update().filter(domain=domain).order_by("ordinal")
    )


def _locked_domain_and_positions_for_position(position):
    """Lock a position's domain before locking any of its topology rows."""
    position_id = _pk(position)
    domain_id = models.LPUC2CDomainRackPosition.objects.only("domain_id").get(pk=position_id).domain_id
    domain = _locked_domain(domain_id)
    positions = _locked_positions(domain)
    try:
        position = next(item for item in positions if item.pk == position_id)
    except StopIteration as error:
        raise models.LPUC2CDomainRackPosition.DoesNotExist from error
    return domain, positions, position


def _domain_id_for_position(position):
    return models.LPUC2CDomainRackPosition.objects.only("domain_id").get(pk=_pk(position)).domain_id


def _locked_rack(rack):
    return None if rack is None else Rack.objects.select_for_update().get(pk=_pk(rack))


def _save_position(position):
    position.full_clean()
    position.save()
    return position


def _renumber(positions, ordered):
    """Persist an ordering without colliding with the immediate unique constraint."""
    if not positions:
        return
    offset = max(position.ordinal for position in positions) + len(positions) + 1
    models.LPUC2CDomainRackPosition.objects.filter(pk__in=[position.pk for position in positions]).update(
        ordinal=F("ordinal") + offset
    )
    by_pk = {position.pk: position for position in positions}
    for ordinal, position in enumerate(ordered):
        position = by_pk[position.pk]
        position.ordinal = ordinal
        _save_position(position)


def _require_confirmation(confirmed):
    if not confirmed:
        raise ConfirmationRequired("This topology mutation requires confirmed=True.")


@transaction.atomic
def append_position(domain, rack=None):
    """Append an occupied or vacant ordinal to a mutable domain."""
    domain = _locked_domain(domain)
    positions = _locked_positions(domain)
    position = models.LPUC2CDomainRackPosition(domain=domain, ordinal=len(positions), rack=_locked_rack(rack))
    return _save_position(position)


@transaction.atomic
def fill_position(position, rack):
    """Fill an existing vacant ordinal."""
    _domain, _positions, position = _locked_domain_and_positions_for_position(position)
    if position.rack_id:
        raise ValidationError({"rack": "Rack position is already occupied."})
    position.rack = _locked_rack(rack)
    return _save_position(position)


@transaction.atomic
def vacate_position(position):
    """Vacate an ordinal, preserving it while removing its endpoint configuration."""
    _domain, _positions, position = _locked_domain_and_positions_for_position(position)
    models.LPUC2CEndpointConfiguration.objects.select_for_update().filter(rack_position=position).delete()
    position.rack = None
    return _save_position(position)


@transaction.atomic
def remove_and_compact_position(position, *, confirmed=False):
    """Delete one ordinal and compact all later positions."""
    _require_confirmation(confirmed)
    domain, positions, position = _locked_domain_and_positions_for_position(position)
    remaining = [item for item in positions if item.pk != position.pk]
    position.delete()
    _renumber(remaining, remaining)


@transaction.atomic
def insert_position(domain, ordinal, rack=None, *, confirmed=False):
    """Insert an occupied or vacant ordinal, shifting later positions."""
    _require_confirmation(confirmed)
    domain = _locked_domain(domain)
    positions = _locked_positions(domain)
    if ordinal < 0 or ordinal > len(positions):
        raise ValidationError({"ordinal": "Ordinal must be within the current domain positions."})
    offset = len(positions) + max((position.ordinal for position in positions), default=-1) + 2
    if positions:
        models.LPUC2CDomainRackPosition.objects.filter(pk__in=[position.pk for position in positions]).update(
            ordinal=F("ordinal") + offset
        )
    position = models.LPUC2CDomainRackPosition(domain=domain, ordinal=ordinal, rack=_locked_rack(rack))
    _save_position(position)
    for existing in positions:
        existing.ordinal += 1 if existing.ordinal >= ordinal else 0
        _save_position(existing)
    return position


@transaction.atomic
def reorder_positions(domain, position_ids, *, confirmed=False):
    """Set the complete order of a domain's rack positions."""
    _require_confirmation(confirmed)
    domain = _locked_domain(domain)
    positions = _locked_positions(domain)
    requested_ids = [_pk(position) for position in position_ids]
    actual_ids = [position.pk for position in positions]
    if len(requested_ids) != len(set(requested_ids)) or set(requested_ids) != set(actual_ids):
        raise ValidationError({"position_ids": "Must contain every domain position exactly once."})
    positions_by_id = {position.pk: position for position in positions}
    _renumber(positions, [positions_by_id[position_id] for position_id in requested_ids])


@transaction.atomic
def set_endpoint_configuration(device, rack_position, *, excluded=False, tray_slot=None):
    """Create, update, or remove a device's endpoint exception configuration."""
    device_id = _pk(device)
    requested_position_id = _pk(rack_position)
    discovered_configuration = (
        models.LPUC2CEndpointConfiguration.objects.select_related("rack_position")
        .filter(device_id=device_id)
        .first()
    )
    requested_domain_id = _domain_id_for_position(requested_position_id)
    source_domain_id = (
        discovered_configuration.rack_position.domain_id if discovered_configuration else requested_domain_id
    )
    domain = _locked_domain(source_domain_id)
    positions = _locked_positions(domain)
    if requested_domain_id != domain.pk:
        raise ValidationError(
            {"rack_position": "Endpoint configurations cannot be reassigned between domains."}
        )
    position = next(item for item in positions if item.pk == requested_position_id)

    device = Device.objects.select_for_update().get(pk=device_id)
    configuration = (
        models.LPUC2CEndpointConfiguration.objects.select_for_update()
        .select_related("rack_position")
        .filter(device=device)
        .first()
    )
    if configuration and configuration.rack_position.domain_id != domain.pk:
        raise ValidationError({"device": "Endpoint configuration changed concurrently; retry the operation."})
    if not excluded and tray_slot is None:
        if configuration:
            configuration.delete()
        return None
    if discovered_configuration and not configuration:
        raise ValidationError({"device": "Endpoint configuration changed concurrently; retry the operation."})
    if device.rack_id != position.rack_id:
        raise ValidationError({"device": "Device rack must match the rack position rack."})
    if not configuration:
        configuration = models.LPUC2CEndpointConfiguration(device=device)
    configuration.rack_position = position
    configuration.excluded = excluded
    configuration.tray_slot = tray_slot
    configuration.full_clean()
    configuration.save()
    return configuration


@transaction.atomic
def activate_domain(domain):
    """Activate a domain only when its live projection is ready."""
    domain = _locked_domain(domain)
    _locked_positions(domain)
    evaluation = evaluate_domain(domain)
    if evaluation.state != ProjectionState.READY:
        raise InvalidTopologyProjection(evaluation.diagnostics)
    statuses = Status.objects.get_for_model(models.LPUC2CDomain)
    active_status = statuses.filter(name="Active").first() or statuses.get(name="LPU C2C Active")
    domain.status = active_status
    domain.full_clean()
    domain.save(update_fields=["status"])
    return domain
