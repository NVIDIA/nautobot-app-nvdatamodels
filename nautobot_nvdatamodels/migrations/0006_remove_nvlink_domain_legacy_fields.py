"""Remove legacy strings after the reference data transaction commits."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("nautobot_nvdatamodels", "0005_populate_nvlink_domain_references")]

    operations = [
        migrations.RemoveField(model_name="nvlinkdomain", name="legacy_protocol"),
        migrations.RemoveField(model_name="nvlinkdomain", name="legacy_topology"),
    ]
