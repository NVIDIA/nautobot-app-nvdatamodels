"""Transport-independent LPU C2C domain projections."""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID


class ProjectionState(str, Enum):
    """Evaluation readiness states."""

    READY = "ready"
    INVALID = "invalid"

    def __str__(self):
        """Match StrEnum's value-based string representation on Python 3.10."""
        return self.value


class DiagnosticSeverity(str, Enum):
    """Diagnostic severity levels."""

    ERROR = "error"
    WARNING = "warning"

    def __str__(self):
        """Match StrEnum's value-based string representation on Python 3.10."""
        return self.value


@dataclass(frozen=True)
class ObjectReference:
    """Stable reference to a Nautobot object."""

    object_type: str
    object_id: UUID


@dataclass(frozen=True)
class Diagnostic:
    """A machine-readable evaluation diagnostic."""

    severity: DiagnosticSeverity
    code: str
    message: str
    affected_objects: tuple[ObjectReference, ...] = ()


@dataclass(frozen=True, order=True)
class EndpointCoordinate:
    """Absolute LPU C2C endpoint coordinate."""

    rack_ordinal: int
    tray_slot: int | None = None


@dataclass(frozen=True)
class RackPositionProjection:
    """Projection of an LPU C2C domain rack position."""

    position: ObjectReference
    rack: ObjectReference | None


@dataclass(frozen=True)
class EndpointProjection:
    """Projection of an installed LPU C2C endpoint."""

    device: ObjectReference
    domain: ObjectReference
    coordinate: EndpointCoordinate | None = None


@dataclass(frozen=True)
class DomainEvaluation:
    """Live evaluation result for one LPU C2C domain."""

    domain: ObjectReference
    state: ProjectionState
    rack_positions: tuple[RackPositionProjection, ...]
    endpoints: tuple[EndpointProjection, ...]
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
