from django.db import migrations


class Migration(migrations.Migration):
    """Merge the parallel wardrobe metadata and ownership migration branches."""

    dependencies = [
        ("wardrobe", "0002_item_metadata"),
        ("wardrobe", "0005_item_owner"),
    ]

    operations = []
