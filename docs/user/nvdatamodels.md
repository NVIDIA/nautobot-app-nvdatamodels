# NVDataModels Plugin Overview

The NVDataModels app provides advanced data modeling tools for managing high-performance compute resources in Nautobot. Its primary capabilities are **LPU C2C Domains**, **NVLink Domains**, and **Resource Blocks**. These models help operators describe physical LPU fabrics and logically organize, allocate, and manage compute resources.

This overview is designed to help you understand the key models exposed by the NVDataModels app, including their attributes and the relationships between them, so you can best leverage the API, UI, or automation capabilities provided.

## LPU C2C Domains

An **LPU C2C Domain** represents one whole connected LPU physical chip-to-chip fabric as an ordered arc of racks. The goal of modeling the LPU C2C domain is to correlate machine identity with the functional position within the fabric so that this metadata can be known ahead of model scheduling on an LPX cluster.

The Domain may contain an arbitrary number of rack positions which form one ordered, open chain with zero-based ordinals. Each position may contain one Rack or remain vacant. Vacating a position preserves its ordinal and the coordinates of later racks; it does not make the next occupied Rack implicitly adjacent. Partial racks and vacant positions are valid sparse inventory and do not by themselves make a Domain invalid.

Endpoint membership is derived live from the Rack occupying each ordered position and the Devices installed in that Rack. A Rack can occupy at most one Domain, and all occupied Racks must be within the Domain's Location hierarchy.

### Endpoint prerequisites and coordinates

The app provisions the `LPU Tray` Device Role automatically. A Device is a candidate endpoint only when it uses that role and is installed in a Rack that occupies a Domain position. Its DeviceType must also have an `LPUC2CDeviceTypeCompatibility` mapping for the Domain topology. Ordinary endpoints do not need explicit membership records; an endpoint-configuration record is used only for an exclusion or coordinate override.

Native coordinates come from `Device.position`:

| Topology | Valid native positions | Rack-local coordinate |
| :------- | :--------------------- | :-------------------- |
| LP30 Chip-to-Chip | U8 through U38 in 2U steps | `tray_slot` 1–16, numbered bottom-to-top across the whole Rack |

Coordinates retain the rack-position ordinal and are never compressed around vacant positions or missing Devices. Incompatible DeviceTypes, positions outside the native sequence, malformed overrides, and coordinate collisions are reported as errors instead of silently excluding the Device.

### Planned and Maintenance workflows

Physical topology inputs may be changed only while the Domain is in `Planned` or `Maintenance`. An Active Domain must first enter Maintenance before operators change rack ordering or occupancy, exclusions, or coordinate overrides. Rack-position workflows support append, fill, vacate, remove-and-compact, insert, and reorder operations. Remove-and-compact, insert, and reorder require explicit confirmation. Removing a middle Rack therefore requires an intentional choice between preserving the vacant ordinal and compacting later ordinals.

Returning a Domain to `Active` runs the canonical evaluation and succeeds only when its projection is `READY`. Core Nautobot Rack and Device edits remain authoritative and are not blocked; if one makes the fabric inconsistent, the next evaluation reports the problem instead of automatically repairing inventory or changing Domain status.

### Invalid projections and diagnostics

Evaluation returns either `READY` or `INVALID` plus structured diagnostics. Each diagnostic has a severity, stable code, message, and references to the affected Nautobot objects. Typical errors include incompatible DeviceTypes, invalid native positions or overrides, and duplicate coordinates.

When any error exists, candidate endpoints remain visible for troubleshooting, but every public endpoint coordinate is suppressed and the projection is `INVALID`. Warnings do not cause invalidity, and vacancies or partial occupancy are not errors. Correct the referenced Rack, Device, compatibility, or endpoint-configuration data and reevaluate the Domain before returning it to Active.

## NVLink Domain Model

An **NVLink domain** represents a logical grouping of hardware resources (such as GPUs, servers, or switches) that communicate via NVLink technology. NVLink domains facilitate consolidated management of devices interconnected using NVLink.

**Attributes:**

| Attribute | Type | Description |
| :-------- | :--- | :---------- |
| `name` | string (unique) | Unique name for the NVLink domain. |
| `status` | status choice | Operational status for the NVLink domain. |
| `role` | foreign key (Role) | Optional functional or organizational role for this domain. |
| `tenant` | foreign key (Tenant) | Optional tenant assignment for this domain. |
| `location` | foreign key | Nautobot location object to which this domain belongs (required). |
| `rack_group` | foreign key | Optional rack group to which the domain is associated. |
| `rack` | foreign key | Optional rack where the domain is associated. |
| `cluster_id` | string | Optional cluster ID for this domain. |
| `protocol` | string choice | NVLink protocol version/type for the domain. |
| `members` | many-to-many | Devices assigned as members of this NVLink domain. |
| `topology` | string choice | The NVLink topology in use for this domain. |
| `created` | datetime | Timestamp for creation. |
| `last_updated` | datetime | Timestamp for last modification. |

## Resource Block Model

A **resource block** is a reusable, abstract set of resources (such as devices, device components, or interfaces) that can be reserved, allocated, or managed as a single logical unit. This enables repeatable, modular assignments for projects or workflows.

**Attributes:**

| Attribute | Type | Description |
| :-------- | :--- | :---------- |
| `name` | string (unique) | Unique name for the resource block. |
| `status` | status choice | Operational status for the resource block. |
| `role` | foreign key (Role) | Optional functional or organizational role for this resource. |
| `tenant` | foreign key (Tenant) | Optional tenant assignment for this resource. |
| `location` | foreign key | Nautobot Location object to which this resource belongs (required). |
| `protocol` | string choice | NVLink protocol version/type for the domain. |
| `devices` | many-to-many | Devices assigned as members of this resource block. |
| `dynamic_group` | foreign key | Optional Dynamic Group to automatically include devices based on filter criteria. |
| `created` | datetime | Timestamp for creation. |
| `last_updated` | datetime | Timestamp for last modification. |
