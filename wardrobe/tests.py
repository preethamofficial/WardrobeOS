"""Integration tests: upload pipeline, colour auto-detection, views, API."""
import os
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from ai.matching import recommend
from wardrobe.models import Item

from PIL import Image


def _image_bytes(garment_rgb, bg_rgb=(250, 250, 250), size=(240, 240)):
    im = Image.new("RGB", size, bg_rgb)
    for y in range(size[1] // 4, size[1] - size[1] // 4):
        for x in range(size[0] // 4, size[0] - size[0] // 4):
            im.putpixel((x, y), garment_rgb)
    buf = BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UploadDetectionTests(TestCase):
    def _post_item(self, name="Navy Tee", garment=(27, 42, 74), **extra):
        upload = SimpleUploadedFile("garment.jpg", _image_bytes(garment),
                                    content_type="image/jpeg")
        payload = {"name": name, "category": "tshirt", "formality": "casual",
                   "status": "clean", "purchase_price": "10", "season": "all",
                   "image": upload}
        payload.update(extra)
        return self.client.post("/wardrobe/add/", payload)

    def test_upload_auto_detects_colour(self):
        response = self._post_item()
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Navy Tee")
        self.assertEqual(item.color, "Navy")
        self.assertEqual(item.color_family, "blue")
        self.assertTrue(item.palette)
        self.assertEqual(item.palette[0]["family"], "blue")
        self.assertTrue(item.pattern)  # auto-detected "solid"
        self.assertTrue(item.thumbnail)
        self.assertTrue(os.path.exists(item.thumbnail.path))
        self.assertTrue(item.display_image)

    def test_manual_colour_is_respected(self):
        self._post_item(name="Manual Tee", color="Cobalt Blue")
        item = Item.objects.get(name="Manual Tee")
        self.assertEqual(item.color, "Cobalt Blue")  # never overwritten
        self.assertEqual(item.color_family, "blue")  # derived field still set

    def test_image_replacement_reanalyses(self):
        first = self._post_item(name="Swap Tee", garment=(200, 16, 46))  # red
        item = Item.objects.get(name="Swap Tee")
        self.assertEqual(item.color_family, "red")
        upload = SimpleUploadedFile("swap.jpg", _image_bytes((27, 42, 74)),
                                    content_type="image/jpeg")
        response = self.client.post(f"/wardrobe/{item.pk}/edit/", {
            "name": "Swap Tee", "category": "tshirt", "formality": "casual",
            "status": "clean", "purchase_price": "10", "season": "all", "image": upload})
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.color_family, "blue")
        self.assertEqual(item.palette[0]["name"], "Navy")

    def test_rescan_endpoint(self):
        self._post_item(name="Rescan Tee")
        item = Item.objects.get(name="Rescan Tee")
        response = self.client.post(f"/wardrobe/{item.pk}/rescan/")
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.color_family, "blue")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ViewsAndApiTests(TestCase):
    def _make(self, n=1, **kwargs):
        fields = dict(category="tshirt", formality="casual", status="clean",
                      season="all", occasions="", purchase_price=10)
        fields.update(kwargs)
        base_name = fields.pop("name", "Item")
        return [Item.objects.create(name=base_name if n == 1 else f"{base_name} {i}",
                                    **fields) for i in range(n)]

    def test_list_pagination_and_filters(self):
        self._make(30)
        response = self.client.get("/wardrobe/")
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.context["items"]), 24)
        response = self.client.get("/wardrobe/?page=2")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/wardrobe/?status=clean")
        self.assertEqual(response.status_code, 200)

    def test_api_items_payload(self):
        self._make(1)
        data = self.client.get("/api/items/").json()
        self.assertEqual(data["count"], 1)
        self.assertIn("color_family", data["items"][0])

    def test_health_endpoint(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_model_behaviour(self):
        item = self._make(1, name="WearTest", purchase_price=100)[0]
        item.wear()
        item.refresh_from_db()
        self.assertEqual(item.wear_count, 1)
        self.assertEqual(item.status, "worn")
        self.assertEqual(item.cost_per_wear, 100.0)
        self.assertEqual(item.display_image, "")  # no image -> safe empty URL

    def test_recommend_smoke(self):
        top = self._make(1, name="Top", category="tshirt",
                         palette=[{"hex": "#1b2a4a", "name": "Navy", "family": "blue", "share": 1}],
                         color="Navy", color_family="blue")[0]
        bottom = self._make(1, name="Bottom", category="jeans",
                            palette=[{"hex": "#e8dcc8", "name": "Beige", "family": "neutral", "share": 1}],
                            color="Beige", color_family="neutral")[0]
        shoes = self._make(1, name="Shoes", category="shoes",
                           palette=[{"hex": "#8b5a2b", "name": "Brown", "family": "brown", "share": 1}],
                           color="Brown", color_family="brown")[0]
        outfits = recommend(Item.objects.all(), "casual", 25, None)
        self.assertTrue(outfits)
        best = outfits[0]
        self.assertTrue(best["why"])
        self.assertTrue(0 <= best["score"] <= 100)
        ids = {x.id for x in best["items"]}
        self.assertTrue({top.id, bottom.id} <= ids)


class MultiUserTests(TestCase):
    def _user(self, username):
        from django.contrib.auth.models import User
        return User.objects.create_user(username, f"{username}@example.com", "pass12345")

    def _names(self, client):
        page = client.get("/wardrobe/").context["items"]
        return sorted(x.name for x in page.object_list)

    def test_ownership_isolation(self):
        from django.contrib.auth.models import User
        a, b = self._user("alice"), self._user("bob")
        ia = Item.objects.create(name="Alice Top", owner=a, category="tshirt", status="clean")
        Item.objects.create(name="Bob Top", owner=b, category="tshirt", status="clean")
        Item.objects.create(name="Local Top", owner=None, category="tshirt", status="clean")
        ca, cb, anon = Client(), Client(), Client()
        ca.force_login(a)
        cb.force_login(b)
        self.assertEqual(self._names(ca), ["Alice Top"])
        self.assertEqual(self._names(cb), ["Bob Top"])
        self.assertEqual(self._names(anon), ["Local Top"])
        # Foreign records are invisible: edit/wear/rescan all 404.
        self.assertEqual(cb.get(f"/wardrobe/{ia.pk}/edit/").status_code, 404)
        self.assertEqual(cb.post(f"/wardrobe/{ia.pk}/rescan/").status_code, 404)
        self.assertEqual(anon.post(f"/wardrobe/{ia.pk}/wear/").status_code, 404)
        # Ownership is assigned at creation.
        payload = {"name": "Owner Add", "category": "tshirt", "formality": "casual",
                   "status": "clean", "purchase_price": "0", "season": "all"}
        anon.post("/wardrobe/add/", payload)
        self.assertIsNone(Item.objects.get(name="Owner Add").owner)
        ca.post("/wardrobe/add/", dict(payload, name="Alice Add"))
        self.assertEqual(Item.objects.get(name="Alice Add").owner, a)
        self.assertTrue(User.objects.filter(username="bob").exists())

    def test_login_and_signup_pages(self):
        anon = Client()
        self.assertEqual(anon.get("/accounts/login/").status_code, 200)
        self.assertEqual(anon.get("/accounts/signup/").status_code, 200)

    def test_signup_then_email_login(self):
        from django.contrib.auth.models import User
        c = Client()
        c.post("/accounts/signup/", {"username": "carol", "email": "carol@example.com",
                                     "password1": "sunny-day-42", "password2": "sunny-day-42"})
        self.assertTrue(User.objects.filter(username="carol").exists())
        c2 = Client()
        c2.post("/accounts/login/", {"login": "carol@example.com", "password": "sunny-day-42"})
        self.assertIn("_auth_user_id", c2.session)
        # carol's wardrobe starts empty (no shared items leak in)
        self.assertEqual(self._names(c2), [])