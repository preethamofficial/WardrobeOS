from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("trips", "0001_initial"),
    ]

    operations = [
        migrations.AddField(model_name="trip", name="lat",
                            field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name="trip", name="lon",
                            field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name="trip", name="packing",
                            field=models.JSONField(blank=True, default=list,
                                                   help_text="Generated packing checklist")),
        migrations.AddField(model_name="trip", name="created_at",
                            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
                            preserve_default=False),
    ]