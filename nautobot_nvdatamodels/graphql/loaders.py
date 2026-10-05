#  SPDX-FileCopyrightText: Copyright (c) "2026" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Request-scoped batch loaders for LPU C2C GraphQL projections."""

from types import SimpleNamespace

from nautobot.dcim.models import Device
from promise import Promise
from promise.dataloader import DataLoader

from nautobot_nvdatamodels import models
from nautobot_nvdatamodels.lpu_c2c.evaluator import (
    discover_device_endpoint_candidates,
    domain_snapshot_visibility_errors,
    evaluate_domain_snapshots,
    project_device_endpoints,
)


class RawDomainEvaluationLoader(DataLoader):
    """Batch raw Domain evaluations for reuse by both GraphQL directions."""

    def batch_load_fn(self, domain_pks):
        """Evaluate every requested Domain exactly once without visibility serialization."""
        snapshots = evaluate_domain_snapshots(domain_pks)
        return Promise.resolve([snapshots.get(domain_pk) for domain_pk in domain_pks])


class DomainEvaluationLoader(DataLoader):
    """Batch complete-visibility Domain evaluations for one request user."""

    def __init__(self, user, raw_domains):
        self.user = user
        self.raw_domains = raw_domains
        super().__init__()

    def batch_load_fn(self, domain_pks):
        """Evaluate every requested Domain in one evaluator call."""
        return self.raw_domains.load_many(domain_pks).then(
            lambda snapshots: self._authorize(domain_pks, snapshots)
        )

    def _authorize(self, domain_pks, snapshots):
        snapshots_by_domain = dict(zip(domain_pks, snapshots))
        errors = domain_snapshot_visibility_errors(snapshots_by_domain, self.user)
        return [
            errors[domain_pk] if domain_pk in errors else snapshot.evaluation
            for domain_pk, snapshot in snapshots_by_domain.items()
        ]


class DeviceEndpointLoader(DataLoader):
    """Batch Device-to-endpoint projections for one request user."""

    def __init__(self, user, raw_domains):
        self.user = user
        self.raw_domains = raw_domains
        super().__init__()

    def batch_load_fn(self, device_pks):
        """Resolve requested Devices through the shared raw Domain loader."""
        requested_pks, candidates, domain_pks = discover_device_endpoint_candidates(device_pks, self.user)
        ordered_domain_pks = tuple(sorted(domain_pks, key=str))
        return self.raw_domains.load_many(ordered_domain_pks).then(
            lambda snapshots: self._map_endpoints(
                device_pks,
                requested_pks,
                candidates,
                {
                    domain_pk: snapshot.evaluation
                    for domain_pk, snapshot in zip(ordered_domain_pks, snapshots)
                    if snapshot is not None
                },
            )
        )

    @staticmethod
    def _map_endpoints(device_pks, requested_pks, candidates, evaluations):
        endpoints = project_device_endpoints(requested_pks, candidates, evaluations)
        return [endpoints.get(device_pk) for device_pk in device_pks]


class ProjectionObjectLoader(DataLoader):
    """Batch typed ORM objects referenced by transport-independent projections."""

    def __init__(self, user):
        self.user = user
        super().__init__()

    def batch_load_fn(self, references):
        """Load visible Device and Domain references without per-endpoint queries."""
        device_pks = {
            reference.object_id
            for reference in references
            if reference.object_type == Device._meta.label_lower
        }
        domain_pks = {
            reference.object_id
            for reference in references
            if reference.object_type == models.LPUC2CDomain._meta.label_lower
        }
        devices = Device.objects.restrict(self.user, "view").in_bulk(device_pks)
        domains = models.LPUC2CDomain.objects.restrict(self.user, "view").in_bulk(domain_pks)
        objects = {
            **{(Device._meta.label_lower, pk): instance for pk, instance in devices.items()},
            **{(models.LPUC2CDomain._meta.label_lower, pk): instance for pk, instance in domains.items()},
        }
        return Promise.resolve(
            [objects.get((reference.object_type, reference.object_id)) for reference in references]
        )


_REQUEST_LOADERS_ATTRIBUTE = "_nautobot_nvdatamodels_lpu_c2c_graphql_loaders"


def get_lpu_c2c_loaders(request):
    """Return loaders cached only on this GraphQL request."""
    loaders = getattr(request, _REQUEST_LOADERS_ATTRIBUTE, None)
    if loaders is None:
        raw_domains = RawDomainEvaluationLoader()
        loaders = SimpleNamespace(
            raw_domains=raw_domains,
            domains=DomainEvaluationLoader(request.user, raw_domains),
            devices=DeviceEndpointLoader(request.user, raw_domains),
            objects=ProjectionObjectLoader(request.user),
        )
        setattr(request, _REQUEST_LOADERS_ATTRIBUTE, loaders)
    return loaders
