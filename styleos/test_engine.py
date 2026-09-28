from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase

from wardrobe.models import Item
from outfits.models import Outfit

from .engine import wardrobe_gaps, wardrobe_roi, style_genome


class IntelligenceEngineTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user("intel","intel@example.com","pass12345")

    def item(self, name, category, price=100, wears=0, family="blue"):
        return Item.objects.create(owner=self.user,name=name,category=category,
            formality="casual",status="clean",season="all",purchase_price=price,
            wear_count=wears,color_family=family)

    def test_genome_uses_actual_wardrobe_signal(self):
        self.item("Navy Tee","tshirt",500,4,"blue")
        self.item("Black Jeans","jeans",1800,2,"neutral")
        outfit=Outfit.objects.create(owner=self.user,name="Everyday",score=88)
        outfit.items.add(*Item.objects.filter(owner=self.user))
        self.assertEqual(style_genome(Item.objects.filter(owner=self.user), [outfit])["formality"],"casual")
        self.assertEqual(style_genome(Item.objects.filter(owner=self.user), [outfit])["feedback"]["total"],0)

    def test_roi_calculates_spend_wear_and_unused_value(self):
        self.item("Used","tshirt",1000,10)
        self.item("Unused","shirt",2000,0)
        roi=wardrobe_roi(Item.objects.filter(owner=self.user))
        self.assertEqual(roi["spend"],3000)
        self.assertEqual(roi["wears"],10)
        self.assertEqual(roi["cpw"],300)
        self.assertEqual(roi["unused_value"],2000)

    def test_gaps_are_coverage_gaps_not_products(self):
        self.item("One Tee","tshirt")
        gaps=wardrobe_gaps(Item.objects.filter(owner=self.user))
        self.assertTrue(any(x["category"]=="tshirt" and x["missing"]==2 for x in gaps))
        self.assertTrue(any(x["category"]=="shoes" for x in gaps))
