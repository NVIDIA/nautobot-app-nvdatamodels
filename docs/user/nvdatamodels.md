# NVDataModels Plugin Overview

The NVDataModels app provides advanced data modeling tools for managing high-performance compute resources in Nautobot. This app introduces two primary resource types: **NVLink Domains** and **Resource Blocks**. These models help operators logically organize, allocate, and manage compute resources particularly for environments leveraging NVIDIA's NVLink interconnect.

This overview is designed to help you understand the key models exposed by the NVDataModels app, including their attributes and the relationships between them, so you can best leverage the API, UI, or automation capabilities provided.

## NVLink Domain Model

An **NVLink domain** represents a logical grouping of hardware resources (such as GPUs, servers, or switches) that communicate via NVLink technology. NVLink domains facilitate consolidated management of devices interconnected using NVLink.

**Attributes:**

| Attribute | Type | Description |
| :-------- | :--- | :---------- |
| `name` | string (unique) | Unique name for the NVLink domain. |
| `status` | foreign key (Nautobot Status) | Operational status for the NVLink domain. |
| `role` | foreign key (Role) | Optional functional or organizational role for this domain. |
| `tenant` | foreign key (Tenant) | Optional tenant assignment for this domain. |
| `location` | foreign key | Nautobot location object to which this domain belongs (required). |
| `rack_group` | foreign key | Optional rack group to which the domain is associated. |
| `rack` | foreign key | Optional rack where the domain is associated. |
| `cluster_id` | string | Optional cluster ID for this domain. |
| `protocol` | foreign key (NVLinkDomainProtocol) | Optional configured protocol for the domain. |
| `members` | many-to-many | Devices assigned as members of this NVLink domain. |
| `topology` | foreign key (NVLinkDomainTopology) | Optional configured topology for the domain. |
| `created` | datetime | Timestamp for creation. |
| `last_updated` | datetime | Timestamp for last modification. |

### Configurable NVLink protocols and topologies

Use **NVIDIA → NVLink Protocols** or **NVIDIA → NVLink Topologies** to create,
edit, or delete entries. Each entry has a unique `name` (the API identifier), an
optional `description` (the display label), and tags. New entries become
available in NVLink domain forms immediately, without an application release.
The usual Nautobot view/add/change/delete permissions apply to each table.
When upgrading, grant domain editors view permission on the protocol and topology
entries they may select or assign, including through the API.
Entries referenced by a domain cannot be deleted until those assignments are cleared.

The upgrade seeds all previously built-in choices and migrates existing domain
assignments, including previously stored custom values. Empty strings and nulls
become unassigned references. Rolling back restores the assigned names as strings.

The REST endpoints are `nvlink-domain-protocols/` and
`nvlink-domain-topologies/` under `/api/plugins/nvdatamodels/`.
Domain API requests and responses continue to use names, for example
`{"protocol": "nvlink_v5"}`. Create a reference entry before assigning its name;
use `null` to clear an assignment. Domain filters accept reference names or UUIDs.
HTML forms use reference UUIDs. Python callers now assign model instances to
`domain.protocol` and `domain.topology`, and read their `.name` for API identifiers.
Renaming an entry updates the identifier returned for all domains using it.

## Resource Block Model

A **resource block** is a reusable, abstract set of resources (such as devices, device components, or interfaces) that can be reserved, allocated, or managed as a single logical unit. This enables repeatable, modular assignments for projects or workflows.

**Attributes:**

| Attribute | Type | Description |
| :-------- | :--- | :---------- |
| `name` | string (unique) | Unique name for the resource block. |
| `status` | foreign key (Nautobot Status) | Operational status for the resource block. |
| `role` | foreign key (Role) | Optional functional or organizational role for this resource. |
| `tenant` | foreign key (Tenant) | Optional tenant assignment for this resource. |
| `location` | foreign key | Nautobot Location object to which this resource belongs (required). |
| `protocol` | string choice | NVLink protocol version/type for the domain. |
| `devices` | many-to-many | Devices assigned as members of this resource block. |
| `dynamic_group` | foreign key | Optional Dynamic Group to automatically include devices based on filter criteria. |
| `created` | datetime | Timestamp for creation. |
| `last_updated` | datetime | Timestamp for last modification. |

## Configuring statuses

NVLink domains and Resource Blocks use Nautobot's native **Status** objects.
Create or edit statuses in Nautobot and enable the **NVLink Domain** and/or
**resource block** content types to make them available for these models.
On database initialization, the app seeds Active, Healthy, Degraded, Planned,
and Offline for NVLink domains, and Active, Planned, and Decommissioned for
Resource Blocks. Seeding reuses native Status objects by name and associates
these content types without overwriting existing colors or other associations.
These are initial defaults only: forms, API validation, and filters accept any
native Status configured for the relevant content type. No status-name enum
restricts the models.
Existing statuses and assignments are preserved when upgrading.
