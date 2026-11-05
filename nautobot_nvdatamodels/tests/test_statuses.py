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
"""Native Nautobot statuses remain administrator-managed."""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from nautobot.apps import nautobot_database_ready
from nautobot.extras.models import Status

from nautobot_nvdatamodels import filters, forms, models
from nautobot_nvdatamodels.tests import fixtures


class NativeStatusTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.common_test_data(cls)
        cls.user = get_user_model().objects.create_superuser(username="status-admin", password="test")

    def test_custom_status_in_forms_api_and_filters(self):
        self.client.force_login(self.user)
        for model in (models.NVLinkDomain, models.ResourceBlock):
            with self.subTest(model=model.__name__):
                status = Status.objects.create(name=f"Custom {model.__name__} State", color="123456")
                status.content_types.add(ContentType.objects.get_for_model(model))
                form_class = getattr(forms, f"{model.__name__}Form")
                form = form_class(
                    data={"name": "Custom state object", "location": self.location.pk, "status": status.pk}
                )
                self.assertTrue(form.is_valid(), form.errors)
                instance = form.save()
                self.assertEqual(instance.status, status)
                response = self.client.post(
                    reverse(f"plugins-api:nautobot_nvdatamodels-api:{model._meta.model_name}-list"),
                    {"name": "API custom state", "location": str(self.location.pk), "status": str(status.pk)},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201, response.content)
                self.assertEqual(model.objects.get(pk=response.json()["id"]).status, status)
                filterset = getattr(filters, f"{model.__name__}FilterSet")({"status": [str(status.pk)]})
                self.assertTrue(filterset.is_valid(), filterset.errors)
                self.assertEqual(filterset.qs.count(), 2)
                unrelated = Status.objects.create(name=f"Unrelated {model.__name__}")
                form = form_class(
                    data={"name": "Invalid state", "location": self.location.pk, "status": unrelated.pk}
                )
                self.assertFalse(form.is_valid())
                self.assertIn("status", form.errors)

    def test_default_seeding_is_idempotent_and_preserves_native_statuses(self):
        nvl_type = ContentType.objects.get_for_model(models.NVLinkDomain)
        rb_type = ContentType.objects.get_for_model(models.ResourceBlock)
        active = Status.objects.get(name="Active")
        active.color = "123456"
        active.save()
        active.content_types.remove(nvl_type, rb_type)
        custom = Status.objects.create(name="Operator defined", color="abcdef")
        custom.content_types.add(nvl_type)
        # Exercise creation of missing defaults as well as reuse of an existing one.
        Status.objects.filter(name="Healthy").delete()
        sender = apps.get_app_config("nautobot_nvdatamodels")
        nautobot_database_ready.send(sender=sender)
        before = set(Status.objects.values_list("pk", "name", "color"))
        nautobot_database_ready.send(sender=sender)
        self.assertEqual(set(Status.objects.values_list("pk", "name", "color")), before)
        active.refresh_from_db()
        self.assertEqual(active.color, "123456")
        self.assertTrue(active.content_types.filter(pk=nvl_type.pk).exists())
        self.assertTrue(active.content_types.filter(pk=rb_type.pk).exists())
        self.assertTrue(active.content_types.filter(pk=self.device_ct.pk).exists())
        self.assertTrue(Status.objects.get_for_model(models.NVLinkDomain).filter(pk=custom.pk).exists())
        self.assertTrue(
            {"Active", "Healthy", "Degraded", "Planned", "Offline"}.issubset(
                set(Status.objects.get_for_model(models.NVLinkDomain).values_list("name", flat=True))
            )
        )
