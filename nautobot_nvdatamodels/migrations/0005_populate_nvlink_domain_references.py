"""Populate references separately from schema changes for PostgreSQL deferred constraints."""

from django.db import migrations

PROTOCOLS = (
    ("nvlink_v2", "NVLink v2"),
    ("nvlink_v3", "NVLink v3"),
    ("nvlink_v5", "NVLink v5"),
    ("nvlink_v6", "NVLink v6"),
    ("nvlink_bridge", "NVLink Bridge"),
    ("infiniband", "InfiniBand"),
    ("cpu_gpu", "NVLink CPU-GPU"),
)
TOPOLOGIES = (
    ("gb200_nvl36r1_c2g4", "GB200 NVL36x1, single rack, 2U compute tray, 2x CPU / 4x GPU"),
    ("gb200_nvl72r2_c2g4", "GB200 NVL36x2, dual rack, 2U compute tray, 2x CPU / 4x GPU"),
    ("gb200_nvl72r1_c2g4", "GB200 NVL72x1, single rack, 1U compute tray, 2x CPU / 4x GPU"),
    ("gb300_nvl36r1_c2g4", "GB300 NVL36x1, single rack, 1U compute tray, 2x CPU / 4x GPU"),
    ("gb300_nvl36r2_c2g4", "GB300 NVL36x2, dual rack, 2U compute tray, 2x CPU / 4x GPU"),
    ("gb300_nvl72r1_c2g4", "GB300 NVL72x1, single rack, 1U compute tray, 2x CPU / 4x GPU"),
    ("gb300_nvl72r2_c2g4", "GB300 NVL72x2, dual rack, 2U compute tray, 2x CPU / 4x GPU"),
)


def migrate_references(apps, schema_editor):
    alias = schema_editor.connection.alias
    domains = apps.get_model("nautobot_nvdatamodels", "NVLinkDomain").objects.using(alias)
    for field, model_name, defaults in (
        ("protocol", "NVLinkDomainProtocol", PROTOCOLS),
        ("topology", "NVLinkDomainTopology", TOPOLOGIES),
    ):
        entries = apps.get_model("nautobot_nvdatamodels", model_name).objects.using(alias)
        for name, description in defaults:
            entries.get_or_create(name=name, defaults={"description": description})
        # Preserve previously stored values even if they weren't in the choice set.
        for value in domains.order_by().values_list(f"legacy_{field}", flat=True).distinct():
            if value:
                entry, _ = entries.get_or_create(name=value)
                domains.filter(**{f"legacy_{field}": value}).update(**{f"{field}_id": entry.pk})


def restore_strings(apps, schema_editor):
    alias = schema_editor.connection.alias
    domains = apps.get_model("nautobot_nvdatamodels", "NVLinkDomain").objects.using(alias)
    for field, model_name in (("protocol", "NVLinkDomainProtocol"), ("topology", "NVLinkDomainTopology")):
        entries = apps.get_model("nautobot_nvdatamodels", model_name).objects.using(alias)
        for entry in entries.all():
            domains.filter(**{f"{field}_id": entry.pk}).update(**{f"legacy_{field}": entry.name})


class Migration(migrations.Migration):
    dependencies = [("nautobot_nvdatamodels", "0004_nvlink_domain_reference_tables")]

    operations = [migrations.RunPython(migrate_references, restore_strings)]
