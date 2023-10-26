from django.db import migrations


def migrate_custom_report_subscription_config(apps, schema_editor):
    custom_report_subscription = apps.get_model('metadata', 'CustomReportSubscription')
    old_custom_report_subscription = apps.get_model('metadata', 'CustomReportSubscriptionConfig')
    for i in old_custom_report_subscription.objects.all():
        custom_report_subscription.objects.update_or_create(
            bk_biz_id=i.bk_biz_id,
            subscription_id=i.subscription_id,
            defaults={"config": i.config},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('metadata', '0162_customreportsubscriptionconfig_bk_data_id'),
    ]

    operations = [migrations.RunPython(migrate_custom_report_subscription_config)]
