# Overview

!!! note
    This document (and all of Nautobot, really) uses the terms "app" and "plugin" interchangeably.

The NVDataModels app adds three main resource types to Nautobot: LPU C2C Domains, NVLink Domains, and Resource Blocks.

An **LPU C2C Domain** is an ordered grouping of racks that are connected via the LPU chip-to-chip fabric. The domain enables centralized management and visualization of the LPU C2C fabric. Participating devices in those racks receive positional metadata useful for scheduling inference workloads on the fabric.

An **NVLink Domain** is a logical grouping of resources or devices connected and managed together via NVLink technology. In Nautobot with NVDataModels, an NVLink Domain represents a collection of hardware resources such as GPUs, servers, or switches that communicate using NVLink interconnects. The domain enables centralized management, visualization, and configuration of these interconnected devices.

A **Resource Block** is a reusable, abstract grouping of resources (devices, interfaces, or other objects) that can be reserved, allocated, or managed as a unit. Resource Blocks enable administrators and automated systems to define a consistent set of resources that can be applied or assigned to different projects, workflows, or services as needed.
