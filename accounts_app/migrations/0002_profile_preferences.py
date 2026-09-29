from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="display_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="profile",
            name="timezone",
            field=models.CharField(default="Asia/Kolkata", max_length=64),
        ),
        migrations.AddField(
            model_name="profile",
            name="currency",
            field=models.CharField(default="INR", max_length=3),
        ),
        migrations.AddField(
            model_name="profile",
            name="theme",
            field=models.CharField(
                choices=[("light", "Light"), ("dark", "Dark"), ("system", "System")],
                default="system",
                max_length=10,
            ),
        ),
    ]
