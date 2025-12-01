# Overview

!!! note
    This document (and all of Nautobot, really) uses the terms "app" and "plugin" interchangeably.

The NVDataModels app adds two main resource types to Nautobot: NVLink Domains and Resource Blocks.

An **NVLink Domain** is a logical grouping of resources or devices connected and managed together via NVLink technology. In Nautobot with NVDataModels, an NVLink Domain represents a collection of hardware resources such as GPUs, servers, or switches that communicate using NVLink interconnects. The domain enables centralized management, visualization, and configuration of these interconnected devices.

A **Resource Block** is a reusable, abstract grouping of resources (devices, interfaces, or other objects) that can be reserved, allocated, or managed as a unit. Resource Blocks enable administrators and automated systems to define a consistent set of resources that can be applied or assigned to different projects, workflows, or services as needed.

