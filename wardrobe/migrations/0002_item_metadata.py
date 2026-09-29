from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wardrobe", "0001_initial"),
    ]

    operations = [
        migrations.AddField(model_name="item", name="brand", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="item", name="size", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="item", name="purchase_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="item", name="care_instructions", field=models.TextField(blank=True)),
        migrations.AddField(model_name="item", name="favorite", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="item", name="tags", field=models.CharField(blank=True, max_length=255)),
    ]
