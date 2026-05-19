# Generated manually for PR #10383 graph relation binding hot-query indexes

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0259_surrealdb_binding"),
        ("metadata", "0263_vmshortlinkrecord_data_labels"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="graphrelationbindingconfig",
            index=models.Index(
                fields=["bk_tenant_id", "namespace", "data_link_name"],
                name="grbc_tenant_ns_dl_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="surrealdbbindingconfig",
            index=models.Index(
                fields=["bk_tenant_id", "namespace", "data_link_name"],
                name="sdbc_tenant_ns_dl_idx",
            ),
        ),
    ]
