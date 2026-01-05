# Generated manually to fix related_name collision

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_nvdatamodels", "0002_resourceblock_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="nvlinkdomainmembership",
            name="domain",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="nvlink_domain_memberships",
                to="nautobot_nvdatamodels.nvlinkdomain",
            ),
        ),
    ]
