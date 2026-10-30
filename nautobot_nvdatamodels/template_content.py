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
"""Custom template content."""

from nautobot.apps.ui import TemplateExtension

from nautobot_nvdatamodels import models
from nautobot_nvdatamodels.lpu_c2c.evaluator import ProjectionPermissionDenied, evaluate_domain


def _coordinate_display(coordinate):
    if coordinate is None:
        return None
    parts = [f"Rack {coordinate.rack_ordinal}"]
    if coordinate.tray_slot is not None:
        parts.append(f"Tray {coordinate.tray_slot}")
    return " / ".join(parts)


class DeviceNVIDIAContent(TemplateExtension):
    """Extra content for dcim.Device view."""

    model = "dcim.device"

    def right_page(self):
        """Extra content on right panel."""
        device = self.context["object"]
        request = self.context["request"]
        configuration = (
            models.LPUC2CEndpointConfiguration.objects.filter(device=device)
            .select_related("rack_position", "rack_position__domain")
            .first()
        )
        if configuration is not None:
            candidate_domain_id = configuration.rack_position.domain_id
        elif device.rack_id:
            candidate_domain_id = (
                models.LPUC2CDomainRackPosition.objects.filter(rack_id=device.rack_id)
                .values_list("domain_id", flat=True)
                .first()
            )
        else:
            candidate_domain_id = None

        domain = None
        evaluation = None
        endpoint = None
        diagnostics = ()
        can_change_domain = False
        if candidate_domain_id:
            visible_domain = (
                models.LPUC2CDomain.objects.restrict(request.user, "view")
                .filter(pk=candidate_domain_id)
                .first()
            )
            if visible_domain is not None:
                try:
                    candidate_evaluation = evaluate_domain(
                        visible_domain, user=request.user, require_complete_visibility=True
                    )
                except ProjectionPermissionDenied:
                    candidate_evaluation = None
                if candidate_evaluation is not None:
                    candidate_endpoint = next(
                        (
                            item
                            for item in candidate_evaluation.endpoints
                            if item.device.object_id == device.pk
                        ),
                        None,
                    )
                    if candidate_endpoint is not None:
                        domain = visible_domain
                        evaluation = candidate_evaluation
                        endpoint = candidate_endpoint
                        diagnostics = candidate_evaluation.diagnostics
                        can_change_domain = (
                            models.LPUC2CDomain.objects.restrict(request.user, "change")
                            .filter(pk=visible_domain.pk)
                            .exists()
                        )

        return self.render(
            "nautobot_nvdatamodels/device_nvidia.html",
            {
                "lpu_c2c_domain": domain,
                "lpu_c2c_evaluation_state": evaluation.state if evaluation else None,
                "lpu_c2c_endpoint": endpoint,
                "lpu_c2c_can_change_domain": can_change_domain,
                "lpu_c2c_coordinate_display": _coordinate_display(endpoint.coordinate) if endpoint else None,
                "lpu_c2c_diagnostics": diagnostics,
            },
        )


template_extensions = (DeviceNVIDIAContent,)
