from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wardrobe", "0001_initial"),
    ]

    operations = [
        migrations.AddField(model_name="item", name="palette",
                            field=models.JSONField(blank=True, default=list,
                                                   help_text="Dominant colours extracted from the photo")),
    ]