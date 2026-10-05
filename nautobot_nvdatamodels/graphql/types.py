#  SPDX-FileCopyrightText: Copyright (c) "2026" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""GraphQL types for the live LPU C2C endpoint projection."""

from inspect import getattr_static

import graphene
from nautobot.core.graphql.types import OptimizedNautobotObjectType
from nautobot.dcim.graphql.types import DeviceType

from nautobot_nvdatamodels import filters, models
from nautobot_nvdatamodels.lpu_c2c.evaluator import object_reference
from nautobot_nvdatamodels.lpu_c2c.types import DiagnosticSeverity, ProjectionState

from .loaders import get_lpu_c2c_loaders

LPUC2CProjectionState = graphene.Enum(
    "LPUC2CProjectionState",
    [(member.name, member.value) for member in ProjectionState],
)
LPUC2CDiagnosticSeverity = graphene.Enum(
    "LPUC2CDiagnosticSeverity",
    [(member.name, member.value) for member in DiagnosticSeverity],
)


class LPUC2CCoordinateType(graphene.ObjectType):
    """An absolute coordinate in an LPU C2C Domain."""

    rack_ordinal = graphene.Int(required=True, name="rackOrdinal")
    tray_slot = graphene.Int(name="traySlot")


class LPUC2CObjectReferenceType(graphene.ObjectType):
    """A transport-independent reference to a Nautobot object."""

    object_type = graphene.String(required=True, name="objectType")
    object_id = graphene.ID(required=True, name="objectId")


class LPUC2CDiagnosticType(graphene.ObjectType):
    """A machine-readable Domain evaluation diagnostic."""

    code = graphene.String(required=True)
    severity = graphene.Field(LPUC2CDiagnosticSeverity, required=True)
    message = graphene.String(required=True)
    affected_objects = graphene.List(
        graphene.NonNull(LPUC2CObjectReferenceType),
        required=True,
        name="affectedObjects",
    )

    def resolve_severity(self, _info):
        """Map the transport enum value onto the GraphQL enum."""
        return self.severity.value


class LPUC2CEndpointProjectionType(graphene.ObjectType):
    """The symmetric Device/Domain/coordinate endpoint projection."""

    device = graphene.Field("nautobot.dcim.graphql.types.DeviceType", required=True)
    domain = graphene.Field(lambda: LPUC2CDomainType, required=True)
    coordinate = graphene.Field(LPUC2CCoordinateType)

    def resolve_device(self, info):
        """Resolve the projected Device through a request-scoped batch loader."""
        return get_lpu_c2c_loaders(info.context).objects.load(self.device)

    def resolve_domain(self, info):
        """Resolve the projected Domain through a request-scoped batch loader."""
        return get_lpu_c2c_loaders(info.context).objects.load(self.domain)


class LPUC2CDomainType(OptimizedNautobotObjectType):
    """LPU C2C Domain plus its live, derived projection."""

    projection_state = graphene.Field(LPUC2CProjectionState, name="projectionState")
    diagnostics = graphene.List(graphene.NonNull(LPUC2CDiagnosticType))
    endpoints = graphene.List(graphene.NonNull(LPUC2CEndpointProjectionType))

    class Meta:
        """Bind the custom GraphQL type to the normalized Domain model."""

        model = models.LPUC2CDomain
        filterset_class = filters.LPUC2CDomainFilterSet

    def resolve_projection_state(self, info):
        """Resolve projection state from the shared Domain evaluation promise."""
        return (
            get_lpu_c2c_loaders(info.context)
            .domains.load(self.pk)
            .then(lambda evaluation: evaluation.state.value)
        )

    def resolve_diagnostics(self, info):
        """Resolve diagnostics once at Domain scope."""
        return (
            get_lpu_c2c_loaders(info.context)
            .domains.load(self.pk)
            .then(lambda evaluation: evaluation.diagnostics)
        )

    def resolve_endpoints(self, info):
        """Resolve endpoint projections from the shared Domain evaluation promise."""
        return (
            get_lpu_c2c_loaders(info.context)
            .domains.load(self.pk)
            .then(lambda evaluation: evaluation.endpoints)
        )


_SHIM_MARKER = "_nautobot_nvdatamodels_lpu_c2c_shim"
_QUERY_ALIAS_MARKER = "_nautobot_nvdatamodels_lpu_c2c_query_alias"
_QUERY_FACTORY_MARKER = "_nautobot_nvdatamodels_lpu_c2c_query_factory"
_ATTRIBUTE_MISSING = object()


def _resolve_device_lpu_c2c(device, info):
    """Resolve a Device's derived LPU C2C endpoint without stored membership."""
    loaders = get_lpu_c2c_loaders(info.context)
    loaders.objects.prime(object_reference(device), device)
    return loaders.devices.load(device.pk)


def install_device_type_lpu_c2c_shim(device_type=DeviceType):
    """Defensively add the compatibility field to Nautobot's Device GraphQL type."""
    existing = device_type._meta.fields.get("lpu_c2c")
    if existing is not None:
        if getattr(existing, _SHIM_MARKER, False):
            if getattr_static(device_type, "lpu_c2c", _ATTRIBUTE_MISSING) is not existing:
                raise RuntimeError("Owned DeviceType.lpu_c2c GraphQL field has been replaced.")
            if (
                getattr_static(device_type, "resolve_lpu_c2c", _ATTRIBUTE_MISSING)
                is not _resolve_device_lpu_c2c
            ):
                raise RuntimeError("Owned DeviceType.resolve_lpu_c2c resolver has been replaced.")
            return existing
        raise RuntimeError("Refusing to overwrite an existing DeviceType.lpu_c2c GraphQL field.")

    for python_name, field in device_type._meta.fields.items():
        effective_name = getattr(field, "name", None) or python_name
        if effective_name == "lpuC2c":
            raise RuntimeError(
                f"Refusing to overwrite existing effective GraphQL field lpuC2c ({python_name})."
            )
    for attribute_name in ("lpu_c2c", "resolve_lpu_c2c"):
        if getattr_static(device_type, attribute_name, _ATTRIBUTE_MISSING) is not _ATTRIBUTE_MISSING:
            raise RuntimeError(f"Refusing to overwrite existing DeviceType.{attribute_name} attribute.")

    field = graphene.Field(LPUC2CEndpointProjectionType, name="lpuC2c")
    setattr(field, _SHIM_MARKER, True)
    device_type._meta.fields["lpu_c2c"] = field
    setattr(device_type, "lpu_c2c", field)
    setattr(device_type, "resolve_lpu_c2c", _resolve_device_lpu_c2c)
    return field


def install_lpu_c2c_query_aliases(query_mixin):
    """Add collision-safe camelCase aliases to Nautobot's generated root fields."""
    aliases = (
        ("lpu_c2c_domain", "lpuC2cDomain"),
        ("lpu_c2c_domains", "lpuC2cDomains"),
    )
    for source_name, alias_name in aliases:
        source = getattr(query_mixin, source_name, None)
        if source is None:
            raise RuntimeError(f"Generated GraphQL root field {source_name} is missing.")

        existing = query_mixin.__dict__.get(alias_name)
        if existing is not None:
            if existing is source and getattr(existing, _QUERY_ALIAS_MARKER, False):
                continue
            raise RuntimeError(f"Refusing to overwrite existing GraphQL root field {alias_name}.")

        source_resolver_name = f"resolve_{source_name}"
        alias_resolver_name = f"resolve_{alias_name}"
        source_resolver = getattr(query_mixin, source_resolver_name, None)
        existing_resolver = query_mixin.__dict__.get(alias_resolver_name)
        if existing_resolver is not None and existing_resolver is not source_resolver:
            raise RuntimeError(f"Refusing to overwrite existing GraphQL resolver {alias_resolver_name}.")

        setattr(source, _QUERY_ALIAS_MARKER, True)
        setattr(query_mixin, alias_name, source)
        if source_resolver is not None:
            setattr(query_mixin, alias_resolver_name, source_resolver)
    return query_mixin


def install_lpu_c2c_query_factory_shim():
    """Decorate Nautobot's schema factory before it creates the root Query type."""
    from nautobot.core.graphql import schema as nautobot_schema

    current_factory = nautobot_schema.generate_query_mixin
    if getattr(current_factory, _QUERY_FACTORY_MARKER, False):
        return current_factory

    def generate_query_mixin_with_lpu_c2c_aliases():
        query_mixin = current_factory()
        return install_lpu_c2c_query_aliases(query_mixin)

    setattr(generate_query_mixin_with_lpu_c2c_aliases, _QUERY_FACTORY_MARKER, True)
    nautobot_schema.generate_query_mixin = generate_query_mixin_with_lpu_c2c_aliases
    return generate_query_mixin_with_lpu_c2c_aliases


install_device_type_lpu_c2c_shim()
install_lpu_c2c_query_factory_shim()

graphql_types = [LPUC2CDomainType]
