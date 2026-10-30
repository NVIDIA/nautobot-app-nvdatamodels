"""Live, read-only evaluation of LPU C2C domains."""

from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Q
from nautobot.dcim.models import Device, Location, Rack

from nautobot_nvdatamodels import models

from .topology import CoordinatePolicyError, resolve_local_coordinate
from .types import (
    Diagnostic,
    DiagnosticSeverity,
    DomainEvaluation,
    EndpointCoordinate,
    EndpointProjection,
    ObjectReference,
    ProjectionState,
    RackPositionProjection,
)


class ProjectionPermissionDenied(PermissionError):
    """Raised when a caller cannot see every object in a domain projection."""


@dataclass(frozen=True)
class DomainEvaluationSnapshot:
    """One evaluation and the exact source-object references used to compute it."""

    evaluation: DomainEvaluation
    required_objects: tuple[ObjectReference, ...]


def object_reference(instance):
    """Return the transport-independent reference for a Nautobot object."""
    return ObjectReference(object_type=instance._meta.label_lower, object_id=instance.pk)


def error(code, message, *affected_objects):
    """Build a stable error diagnostic."""
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=message,
        affected_objects=tuple(
            object_reference(instance) for instance in affected_objects if instance is not None
        ),
    )


def _is_in_domain_location(domain, rack, location_paths):
    return domain.location_id in location_paths.get(rack.location_id, ())


def _location_ancestor_paths(domains, positions):
    """Return ancestor/self IDs for rack Locations with one query per tree depth."""
    parent_by_location = {domain.location_id: domain.location.parent_id for domain in domains}
    rack_location_ids = set()
    for position in positions:
        if position.rack_id is not None:
            rack_location_ids.add(position.rack.location_id)
            parent_by_location[position.rack.location_id] = position.rack.location.parent_id

    frontier = {
        parent_id
        for parent_id in parent_by_location.values()
        if parent_id is not None and parent_id not in parent_by_location
    }
    while frontier:
        parents = dict(Location.objects.filter(pk__in=frontier).values_list("pk", "parent_id"))
        parent_by_location.update(parents)
        frontier = {
            parent_id
            for parent_id in parents.values()
            if parent_id is not None and parent_id not in parent_by_location
        }

    paths = {}
    for location_id in rack_location_ids:
        path = set()
        current_id = location_id
        while current_id is not None and current_id not in path:
            path.add(current_id)
            current_id = parent_by_location.get(current_id)
        paths[location_id] = frozenset(path)
    return paths


def _visibility_denied_domains(user, required_ids):
    """Return domain IDs with one or more required objects outside the caller's view."""
    denied_domains = set()
    for model, object_domains in required_ids.items():
        object_ids = set(object_domains)
        if object_ids:
            visible_ids = set(
                model.objects.restrict(user, "view").filter(pk__in=object_ids).values_list("pk", flat=True)
            )
            for object_id in object_ids - visible_ids:
                denied_domains.update(object_domains[object_id])
    return denied_domains


def _required_visibility_ids(
    domains,
    positions_by_domain,
    configurations_by_domain,
    devices_by_rack,
    compatibilities_by_domain,
):
    """Collect every source object required for complete Domain projection visibility."""
    required_ids = defaultdict(lambda: defaultdict(set))
    for domain in domains:
        required_ids[models.LPUC2CDomain][domain.pk].add(domain.pk)
        for position in positions_by_domain[domain.pk]:
            required_ids[models.LPUC2CDomainRackPosition][position.pk].add(domain.pk)
            if position.rack_id:
                required_ids[Rack][position.rack_id].add(domain.pk)
        for configuration in configurations_by_domain[domain.pk]:
            required_ids[models.LPUC2CEndpointConfiguration][configuration.pk].add(domain.pk)
            required_ids[Device][configuration.device_id].add(domain.pk)
        for compatibility in compatibilities_by_domain[domain.pk]:
            required_ids[models.LPUC2CDeviceTypeCompatibility][compatibility.pk].add(domain.pk)
        for position in positions_by_domain[domain.pk]:
            for device in devices_by_rack[position.rack_id]:
                required_ids[Device][device.pk].add(domain.pk)
    return required_ids


def _required_objects_by_domain(required_ids):
    objects_by_domain = defaultdict(list)
    for model, object_domains in required_ids.items():
        for object_id, domain_ids in object_domains.items():
            reference = ObjectReference(object_type=model._meta.label_lower, object_id=object_id)
            for domain_id in domain_ids:
                objects_by_domain[domain_id].append(reference)
    return {
        domain_id: tuple(
            sorted(
                references,
                key=lambda reference: (reference.object_type, str(reference.object_id)),
            )
        )
        for domain_id, references in objects_by_domain.items()
    }


def domain_snapshot_visibility_errors(snapshots, user):
    """Authorize exactly the source references carried by evaluated snapshots."""
    if user is None:
        return {
            domain_pk: ProjectionPermissionDenied("Complete visibility requires an authenticated user.")
            for domain_pk in snapshots
        }

    source_models = {
        model._meta.label_lower: model
        for model in (
            models.LPUC2CDomain,
            models.LPUC2CDomainRackPosition,
            models.LPUC2CEndpointConfiguration,
            models.LPUC2CDeviceTypeCompatibility,
            Rack,
            Device,
        )
    }
    required_ids = defaultdict(lambda: defaultdict(set))
    missing_domains = set()
    for domain_pk, snapshot in snapshots.items():
        if snapshot is None:
            missing_domains.add(domain_pk)
            continue
        for reference in snapshot.required_objects:
            model = source_models[reference.object_type]
            required_ids[model][reference.object_id].add(domain_pk)
    denied_domains = _visibility_denied_domains(user, required_ids)
    denied_domains.update(missing_domains)
    return {
        domain_pk: ProjectionPermissionDenied("Complete visibility is required for this LPU C2C domain.")
        for domain_pk in denied_domains
    }


def _diagnostic_sort_key(diagnostic):
    return diagnostic.code, tuple(
        (reference.object_type, str(reference.object_id)) for reference in diagnostic.affected_objects
    )


def evaluate_domain(domain, user=None, require_complete_visibility=False):
    """Evaluate a single LPU C2C domain from its installed devices."""
    result = evaluate_domains(
        [domain.pk], user=user, require_complete_visibility=require_complete_visibility
    ).get(domain.pk)
    if isinstance(result, ProjectionPermissionDenied):
        raise result
    return result


def evaluate_domain_snapshots(domain_pks):
    """Evaluate Domains and retain the exact source references used by each result."""
    domains = list(
        models.LPUC2CDomain.objects.filter(pk__in=domain_pks)
        .select_related("location", "status")
        .order_by("name")
    )
    positions = list(
        models.LPUC2CDomainRackPosition.objects.filter(domain__in=domains)
        .select_related("rack", "rack__location", "domain", "domain__location")
        .order_by("domain_id", "ordinal")
    )
    positions_by_domain = defaultdict(list)
    position_by_rack_id = {}
    for position in positions:
        positions_by_domain[position.domain_id].append(position)
        if position.rack_id:
            position_by_rack_id[position.rack_id] = position

    location_paths = _location_ancestor_paths(domains, positions)

    configurations = list(
        models.LPUC2CEndpointConfiguration.objects.filter(rack_position__in=positions).select_related(
            "device", "device__role", "rack_position", "rack_position__domain"
        )
    )
    configurations_by_domain = defaultdict(list)
    for configuration in configurations:
        configurations_by_domain[configuration.rack_position.domain_id].append(configuration)

    installed_devices = list(
        Device.objects.filter(rack_id__in=position_by_rack_id, role__name="LPU Tray").select_related(
            "rack", "device_type", "role", "location"
        )
    )
    devices_by_rack = defaultdict(list)
    for device in installed_devices:
        devices_by_rack[device.rack_id].append(device)

    devices_by_domain = {}
    candidate_device_type_ids_by_topology = defaultdict(set)
    for domain in domains:
        configured_devices = [
            configuration.device
            for configuration in configurations_by_domain[domain.pk]
            if configuration.device.role.name == "LPU Tray"
        ]
        devices_by_id = {device.pk: device for device in configured_devices}
        for position in positions_by_domain[domain.pk]:
            for device in devices_by_rack[position.rack_id]:
                devices_by_id[device.pk] = device
        domain_devices = list(devices_by_id.values())
        devices_by_domain[domain.pk] = domain_devices
        candidate_device_type_ids_by_topology[domain.topology].update(
            device.device_type_id for device in domain_devices
        )

    compatibility_filter = Q(pk__in=())
    for topology, device_type_ids in candidate_device_type_ids_by_topology.items():
        compatibility_filter |= Q(topology=topology, device_type_id__in=device_type_ids)
    compatibilities = list(
        models.LPUC2CDeviceTypeCompatibility.objects.filter(compatibility_filter).only(
            "id", "topology", "device_type_id"
        )
    )
    compatibility_by_pair = {
        (compatibility.topology, compatibility.device_type_id): compatibility
        for compatibility in compatibilities
    }
    compatible_pairs = set(compatibility_by_pair)
    compatibilities_by_domain = defaultdict(list)
    for domain in domains:
        compatibilities_by_domain[domain.pk].extend(
            compatibility_by_pair[pair]
            for pair in {(domain.topology, device.device_type_id) for device in devices_by_domain[domain.pk]}
            if pair in compatibility_by_pair
        )
    required_ids = _required_visibility_ids(
        domains,
        positions_by_domain,
        configurations_by_domain,
        devices_by_rack,
        compatibilities_by_domain,
    )
    required_objects_by_domain = _required_objects_by_domain(required_ids)

    snapshots = {}
    for domain in domains:
        domain_positions = positions_by_domain[domain.pk]
        domain_configurations = configurations_by_domain[domain.pk]
        domain_devices = devices_by_domain[domain.pk]

        diagnostics = []
        expected_ordinals = list(range(len(domain_positions)))
        if [position.ordinal for position in domain_positions] != expected_ordinals:
            diagnostics.append(
                error("NON_DENSE_RACK_ORDINALS", "Rack ordinals must be dense and zero-based.", domain)
            )

        for position in domain_positions:
            if position.rack and not _is_in_domain_location(domain, position.rack, location_paths):
                diagnostics.append(
                    error(
                        "RACK_OUTSIDE_DOMAIN_LOCATION",
                        "A domain rack must be in the domain location hierarchy.",
                        position,
                        position.rack,
                    )
                )

        racks = []
        for position in domain_positions:
            racks.append(
                RackPositionProjection(
                    position=object_reference(position),
                    rack=object_reference(position.rack) if position.rack else None,
                )
            )

        configuration_by_device = {
            configuration.device_id: configuration for configuration in domain_configurations
        }
        for configuration in domain_configurations:
            if configuration.rack_position.rack_id != configuration.device.rack_id:
                diagnostics.append(
                    error(
                        "ENDPOINT_CONFIGURATION_RACK_MISMATCH",
                        "Endpoint configuration rack must match the device rack.",
                        configuration.device,
                        configuration,
                        configuration.rack_position,
                    )
                )
        candidates = []
        for device in domain_devices:
            configuration = configuration_by_device.get(device.pk)
            position = position_by_rack_id.get(device.rack_id)
            if configuration and configuration.rack_position.rack_id != device.rack_id:
                position = configuration.rack_position
            if position is None:
                continue
            if (domain.topology, device.device_type_id) not in compatible_pairs:
                diagnostics.append(
                    error(
                        "INCOMPATIBLE_DEVICE_TYPE",
                        "Installed LPU tray device type is not compatible with the domain topology.",
                        device,
                    )
                )
            if configuration and configuration.excluded:
                continue
            try:
                local_coordinate = resolve_local_coordinate(
                    domain.topology,
                    device.position,
                    tray_slot=configuration.tray_slot if configuration else None,
                )
            except CoordinatePolicyError as policy_error:
                diagnostics.append(error(policy_error.code, str(policy_error), device, configuration))
                local_coordinate = None
            candidates.append((position.ordinal, local_coordinate, device))

        candidates.sort(
            key=lambda candidate: (
                candidate[0],
                candidate[1].sort_key() if candidate[1] is not None else (99, 99),
                str(candidate[2].pk),
            )
        )
        coordinates = defaultdict(list)
        for ordinal, local_coordinate, device in candidates:
            if local_coordinate is not None:
                coordinates[
                    EndpointCoordinate(
                        rack_ordinal=ordinal,
                        tray_slot=local_coordinate.tray_slot,
                    )
                ].append(device)
        for coordinate_devices in coordinates.values():
            if len(coordinate_devices) > 1:
                diagnostics.append(
                    error(
                        "DUPLICATE_COORDINATE",
                        "Multiple devices resolve to the same endpoint coordinate.",
                        *coordinate_devices,
                    )
                )

        diagnostics.sort(key=_diagnostic_sort_key)
        invalid = any(diagnostic.severity == DiagnosticSeverity.ERROR for diagnostic in diagnostics)
        endpoints = tuple(
            EndpointProjection(
                device=object_reference(device),
                domain=object_reference(domain),
                coordinate=(
                    None
                    if invalid or local_coordinate is None
                    else EndpointCoordinate(
                        rack_ordinal=ordinal,
                        tray_slot=local_coordinate.tray_slot,
                    )
                ),
            )
            for ordinal, local_coordinate, device in candidates
        )
        snapshots[domain.pk] = DomainEvaluationSnapshot(
            evaluation=DomainEvaluation(
                domain=object_reference(domain),
                state=ProjectionState.INVALID if invalid else ProjectionState.READY,
                rack_positions=tuple(racks),
                endpoints=endpoints,
                diagnostics=tuple(diagnostics),
            ),
            required_objects=required_objects_by_domain.get(domain.pk, ()),
        )
    return snapshots


def evaluate_domains(domain_pks, user=None, require_complete_visibility=False):
    """Evaluate Domains and authorize the exact evaluated source snapshot when requested."""
    if require_complete_visibility and user is None:
        raise ProjectionPermissionDenied("Complete visibility requires an authenticated user.")
    snapshots = evaluate_domain_snapshots(domain_pks)
    errors = domain_snapshot_visibility_errors(snapshots, user) if require_complete_visibility else {}
    return {
        domain_pk: errors.get(domain_pk, snapshot.evaluation) for domain_pk, snapshot in snapshots.items()
    }


def discover_device_endpoint_candidates(device_pks, user):
    """Discover visible Devices and their visible candidate Domain IDs."""
    requested_pks = tuple(dict.fromkeys(device_pks))
    visible_devices = list(
        Device.objects.restrict(user, "view").filter(pk__in=requested_pks).select_related("rack")
    )
    visible_devices_by_pk = {device.pk: device for device in visible_devices}

    configurations = list(
        models.LPUC2CEndpointConfiguration.objects.filter(device_id__in=visible_devices_by_pk).select_related(
            "rack_position", "rack_position__domain"
        )
    )
    configuration_by_device = {configuration.device_id: configuration for configuration in configurations}

    rack_ids = {
        device.rack_id
        for device in visible_devices
        if device.rack_id and device.pk not in configuration_by_device
    }
    positions_by_rack = {
        position.rack_id: position
        for position in models.LPUC2CDomainRackPosition.objects.filter(rack_id__in=rack_ids).select_related(
            "domain"
        )
    }

    candidate_domain_by_device = {}
    for device in visible_devices:
        configuration = configuration_by_device.get(device.pk)
        position = configuration.rack_position if configuration else positions_by_rack.get(device.rack_id)
        if position is not None:
            candidate_domain_by_device[device.pk] = position.domain_id

    visible_domain_ids = set(
        models.LPUC2CDomain.objects.restrict(user, "view")
        .filter(pk__in=set(candidate_domain_by_device.values()))
        .values_list("pk", flat=True)
    )
    return requested_pks, candidate_domain_by_device, visible_domain_ids


def project_device_endpoints(requested_pks, candidate_domain_by_device, evaluations):
    """Map requested Devices onto endpoints from supplied raw Domain evaluations."""
    endpoints = {}
    for device_pk in requested_pks:
        domain_pk = candidate_domain_by_device.get(device_pk)
        evaluation = evaluations.get(domain_pk)
        if evaluation is None or isinstance(evaluation, ProjectionPermissionDenied):
            endpoints[device_pk] = None
            continue
        endpoints[device_pk] = next(
            (endpoint for endpoint in evaluation.endpoints if endpoint.device.object_id == device_pk),
            None,
        )
    return endpoints


def evaluate_device_endpoints(device_pks, user, *, domain_evaluator=None):
    """Synchronously evaluate the Domain endpoint for each visible requested Device."""
    requested_pks, candidate_domain_by_device, visible_domain_ids = discover_device_endpoint_candidates(
        device_pks, user
    )
    if domain_evaluator is None:
        domain_evaluator = evaluate_domains
    evaluations = domain_evaluator(
        visible_domain_ids,
        user=user,
        require_complete_visibility=False,
    )
    return project_device_endpoints(requested_pks, candidate_domain_by_device, evaluations)
