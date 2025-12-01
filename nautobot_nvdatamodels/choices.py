#  SPDX-FileCopyrightText: Copyright (c) "2025" NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License")
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Choices for NVIDIA app."""

from nautobot.core.choices import ChoiceSet


class NVLinkDomainDefaultStatusChoices(ChoiceSet):
    """Choice set for default statuses for NVLink domains."""

    ACTIVE = "Active"
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    PLANNED = "Planned"
    OFFLINE = "Offline"

    CHOICES = (
        (ACTIVE, "Active"),
        (HEALTHY, "Healthy"),
        (DEGRADED, "Degraded"),
        (PLANNED, "Planned"),
        (OFFLINE, "Offline"),
    )


class NVLinkDomainTopologyChoices(ChoiceSet):
    """Choice set for NVLink domain topologies."""

    GB200_NVL36R1_C2G4 = "gb200_nvl36r1_c2g4"
    GB200_NVL72R2_C2G4 = "gb200_nvl72r2_c2g4"
    GB200_NVL72R1_C2G4 = "gb200_nvl72r1_c2g4"

    CHOICES = (
        (GB200_NVL36R1_C2G4, "GB200 NVL36x1, single rack, 2U compute tray, 2x CPU / 4x GPU"),
        (GB200_NVL72R2_C2G4, "GB200 NVL36x2, dual rack, 2U compute tray, 2x CPU / 4x GPU"),
        (GB200_NVL72R1_C2G4, "GB200 NVL72x1, single rack, 1U compute tray, 2x CPU / 4x GPU"),
    )


class NVLinkDomainProtocolChoices(ChoiceSet):
    """Choice set for NVLink domain protocols."""

    NVLINK_V2 = "nvlink_v2"
    NVLINK_V3 = "nvlink_v3"
    NVLINK_V5 = "nvlink_v5"
    NVLINK_BRIDGE = "nvlink_bridge"
    INFINIBAND = "infiniband"
    CPU_GPU = "cpu_gpu"

    CHOICES = (
        (NVLINK_V2, "NVLink v2"),
        (NVLINK_V3, "NVLink v3"),
        (NVLINK_V5, "NVLink v5"),
        (NVLINK_BRIDGE, "NVLink Bridge"),
        (INFINIBAND, "InfiniBand"),
        (CPU_GPU, "NVLink CPU-GPU"),
    )


class ResourceBlockProtocolChoices(ChoiceSet):
    """Choice set for resource block protocols."""

    ETHERNET = "ethernet"
    INFINIBAND = "infiniband"
    RDMA = "rdma"
    SPECTRUMX = "spectrumx"

    CHOICES = (
        (ETHERNET, "Ethernet"),
        (INFINIBAND, "InfiniBand"),
        (RDMA, "RDMA"),
        (SPECTRUMX, "SpectrumX"),
    )
