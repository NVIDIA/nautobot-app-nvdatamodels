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
"""Test configurable NVLink reference data and its public interfaces."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from nautobot.users.models import ObjectPermission

from nautobot_nvdatamodels import filters, forms, models
from nautobot_nvdatamodels.api.serializers import NVLinkDomainSerializer
from nautobot_nvdatamodels.tests import fixtures


class NVLinkReferenceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.nvl_test_data(cls)
        cls.user = get_user_model().objects.create_superuser(username="reference-admin", password="test")

    def setUp(self):
        self.client.force_login(self.user)

    def test_manage_and_use_new_entries(self):
        for kind in ("Protocol", "Topology"):
            with self.subTest(kind=kind):
                model = getattr(models, f"NVLinkDomain{kind}")
                prefix = f"plugins-api:nautobot_nvdatamodels-api:{model._meta.model_name}"
                response = self.client.post(
                    reverse(f"{prefix}-list"),
                    {"name": f"future_{kind.lower()}", "description": f"Future {kind}"},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201, response.content)
                entry = model.objects.get(name=f"future_{kind.lower()}")
                domain = self.nvl_domains[0]
                response = self.client.patch(
                    reverse("plugins-api:nautobot_nvdatamodels-api:nvlinkdomain-detail", args=[domain.pk]),
                    {kind.lower(): entry.name},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200, response.content)
                domain = models.NVLinkDomain.objects.get(pk=domain.pk)
                self.assertEqual(getattr(domain, kind.lower()), entry)
                self.assertEqual(response.json()[kind.lower()], entry.name)
                for value in (entry.name, str(entry.pk)):
                    result = filters.NVLinkDomainFilterSet(
                        {kind.lower(): [value]}, queryset=models.NVLinkDomain.objects.all()
                    )
                    self.assertTrue(result.is_valid(), result.errors)
                    self.assertEqual(list(result.qs), [domain])
                form = forms.NVLinkDomainForm(
                    instance=domain,
                    data={
                        "name": domain.name,
                        "location": domain.location_id,
                        "status": domain.status_id,
                        kind.lower(): entry.pk,
                    },
                )
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(getattr(form.save(), kind.lower()), entry)
                with self.assertRaises(ProtectedError):
                    entry.delete()
                response = self.client.get(
                    reverse(f"plugins:nautobot_nvdatamodels:{model._meta.model_name}", args=[entry.pk])
                )
                self.assertEqual(response.status_code, 200, response.content)
                self.assertContains(response, entry.description)

    def test_reference_ui_crud(self):
        for kind in ("Protocol", "Topology"):
            model = getattr(models, f"NVLinkDomain{kind}")
            prefix = f"plugins:nautobot_nvdatamodels:{model._meta.model_name}"
            response = self.client.post(
                reverse(f"{prefix}_add"), {"name": "ui-entry", "description": "UI entry"}
            )
            self.assertEqual(response.status_code, 302, response.content)
            entry = model.objects.get(name="ui-entry")
            response = self.client.post(
                reverse(f"{prefix}_edit", args=[entry.pk]), {"name": "ui-entry", "description": "Updated"}
            )
            self.assertEqual(response.status_code, 302, response.content)
            entry.refresh_from_db()
            self.assertEqual(entry.description, "Updated")
            self.assertEqual(self.client.get(reverse(f"{prefix}_list")).status_code, 200)
            response = self.client.post(reverse(f"{prefix}_delete", args=[entry.pk]), {"confirm": True})
            self.assertEqual(response.status_code, 302, response.content)
            self.assertFalse(model.objects.filter(pk=entry.pk).exists())

    def test_unknown_names_rejected_and_null_clears_assignment(self):
        domain = self.nvl_domains[0]
        for field in ("protocol", "topology"):
            serializer = NVLinkDomainSerializer(domain, data={field: "not-configured"}, partial=True)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)
        response = self.client.patch(
            reverse("plugins-api:nautobot_nvdatamodels-api:nvlinkdomain-detail", args=[domain.pk]),
            {"protocol": None, "topology": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        domain.refresh_from_db()
        self.assertIsNone(domain.protocol)
        self.assertIsNone(domain.topology)

    def test_protocol_search(self):
        domain = self.nvl_domains[0]
        result = filters.NVLinkDomainFilterSet({"q": domain.protocol.name})
        self.assertIn(domain, result.qs)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_reference_assignment_respects_object_permissions(self):
        user = get_user_model().objects.create_user(username="domain-editor", password="test")
        permission = ObjectPermission.objects.create(name="Edit domains", actions=["view", "change"])
        permission.object_types.add(ContentType.objects.get_for_model(models.NVLinkDomain))
        permission.users.add(user)
        self.client.force_login(user)
        domain = self.nvl_domains[0]
        url = reverse("plugins-api:nautobot_nvdatamodels-api:nvlinkdomain-detail", args=[domain.pk])
        for kind in ("Protocol", "Topology"):
            model = getattr(models, f"NVLinkDomain{kind}")
            permitted = model.objects.create(name=f"permitted_{kind.lower()}")
            hidden = model.objects.create(name=f"hidden_{kind.lower()}")
            permission = ObjectPermission.objects.create(
                name=f"View selected {kind}",
                actions=["view"],
                constraints={"pk": str(permitted.pk)},
            )
            permission.object_types.add(ContentType.objects.get_for_model(model))
            permission.users.add(user)
            response = self.client.patch(url, {kind.lower(): hidden.name}, content_type="application/json")
            self.assertEqual(response.status_code, 400, response.content)
            domain.refresh_from_db()
            self.assertNotEqual(getattr(domain, kind.lower()), hidden)
            response = self.client.patch(url, {kind.lower(): permitted.name}, content_type="application/json")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()[kind.lower()], permitted.name)
