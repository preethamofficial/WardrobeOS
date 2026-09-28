from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from wardrobe.models import Item

from .views import _capsule


class StyleCommandCenterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="style-user", password="pass12345"
        )
        self.client.force_login(self.user)

    def _item(self, name, category, family, wear_count=0):
        return Item.objects.create(
            owner=self.user,
            name=name,
            category=category,
            color=family.title(),
            color_family=family,
            status="clean",
            wear_count=wear_count,
            season="all",
        )

    def test_capsule_covers_categories_and_stays_within_limit(self):
        for idx, (category, family) in enumerate([
            ("tshirt", "blue"), ("shirt", "neutral"), ("jeans", "denim"),
            ("pant", "black"), ("shoes", "brown"), ("jacket", "green"),
            ("hoodie", "red"), ("shorts", "beige"), ("dress", "purple"),
            ("sweater", "grey"), ("accessory", "gold"),
        ]):
            self._item(f"Piece {idx}", category, family, idx % 4)

        capsule = _capsule(list(Item.objects.filter(owner=self.user)), 10)
        self.assertEqual(len(capsule), 10)
        self.assertGreaterEqual(len({x.category for x in capsule}), 7)
        self.assertEqual(len({x.pk for x in capsule}), 10)
        self.assertNotIn("accessory", {x.category for x in capsule})

    @patch("config.context_processors.get_weather")
    @patch("config.context_processors.summarize")
    @patch("styleos.views.get_weather")
    @patch("styleos.views.summarize")
    def test_command_center_renders_without_weather_dependency(
        self, style_summarize, style_weather, context_summarize, context_weather
    ):
        payload = {
            "temp": 24, "kind": None, "label": "Clear", "emoji": "☀️",
            "rainy": False, "hot": False, "cold": False, "precip_prob": 5,
        }
        style_summarize.return_value = dict(payload)
        style_weather.return_value = {}
        context_summarize.return_value = dict(payload)
        context_weather.return_value = {}
        self._item("Navy Tee", "tshirt", "blue", 2)
        self._item("Denim", "jeans", "denim", 1)
        response = self.client.get("/style/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your wardrobe, thinking ahead")
        self.assertContains(response, "STYLE PULSE")
        self.assertContains(response, "10-PIECE CAPSULE")
