# NVDataModels Plugin Overview

The NVDataModels app provides advanced data modeling tools for managing high-performance compute resources in Nautobot. This app introduces two primary resource types: **NVLink Domains** and **Resource Blocks**. These models help operators logically organize, allocate, and manage compute resources particularly for environments leveraging NVIDIA's NVLink interconnect.

This overview is designed to help you understand the key models exposed by the NVDataModels app, including their attributes and the relationships between them, so you can best leverage the API, UI, or automation capabilities provided.

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
