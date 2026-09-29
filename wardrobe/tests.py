"""Integration tests: upload pipeline, colour auto-detection, views, API."""
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path

from django.conf import settings
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


class DeployConfigTests(TestCase):
    """Guard render.yaml, because a mistake in it only shows up on a live deploy.

    Nothing in the test suite exercises the deploy config, so a typo here fails
    silently until Render reports "Deploy failed". These assertions encode the
    parts that are easy to get wrong and expensive to debug remotely.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import yaml

        cls.render_path = Path(settings.BASE_DIR) / "render.yaml"
        cls.data = yaml.safe_load(cls.render_path.read_text(encoding="utf-8"))
        cls.service = cls.data["services"][0]
        cls.env = {e["key"]: e for e in cls.service.get("envVars", [])}

    def test_yaml_declares_a_python_web_service(self):
        self.assertEqual(self.service["type"], "web")
        self.assertEqual(self.service["runtime"], "python")

    def test_build_command_installs_dependencies(self):
        # Render REPLACES its default `pip install -r requirements.txt` when a
        # buildCommand is set, so the install must be spelled out or nothing is
        # installed and the app cannot import Django at all.
        self.assertIn("pip install", self.service["buildCommand"])
        self.assertIn("requirements.txt", self.service["buildCommand"])

    def test_migrations_run_at_start_not_build(self):
        # The build container has a throwaway disk, so migrating at build time
        # is wasted work; the live instance needs it on every start because a
        # free-tier disk is wiped on restart.
        self.assertNotIn("migrate", self.service["buildCommand"])
        self.assertIn("migrate", self.service["startCommand"])

    def test_start_command_binds_the_render_port(self):
        start = self.service["startCommand"]
        self.assertIn("gunicorn", start)
        self.assertIn("config.wsgi:application", start)
        self.assertIn("$PORT", start)

    def test_python_version_is_fully_qualified(self):
        # Render requires a patch number in PYTHON_VERSION ("3.12" is rejected).
        value = self.env["PYTHON_VERSION"]["value"]
        self.assertRegex(value, r"^\d+\.\d+\.\d+$")

    def test_python_version_matches_dot_python_version_file(self):
        pinned_file = Path(settings.BASE_DIR) / ".python-version"
        self.assertTrue(pinned_file.exists(),
                        ".python-version keeps local dev, CI and Render in step")
        self.assertEqual(self.env["PYTHON_VERSION"]["value"],
                         pinned_file.read_text(encoding="utf-8").strip())

    def test_secret_key_is_generated_not_hardcoded(self):
        entry = self.env["SECRET_KEY"]
        self.assertIs(entry.get("generateValue"), True)
        self.assertNotIn("value", entry,
                         "a literal SECRET_KEY in render.yaml would be public")

    def test_production_security_env_vars_are_set(self):
        for key in ("DEBUG", "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS", "FORCE_HTTPS"):
            self.assertIn(key, self.env, f"{key} is required in production")
        self.assertEqual(self.env["DEBUG"]["value"].lower(), "false")

    def test_csrf_trusted_origins_uses_https(self):
        origins = self.env["CSRF_TRUSTED_ORIGINS"]["value"]
        self.assertTrue(origins.startswith("https://"),
                        "Render terminates TLS, so an http:// origin breaks all POSTs")

    def test_allowed_hosts_covers_the_render_domain(self):
        self.assertIn("onrender.com", self.env["ALLOWED_HOSTS"]["value"])


class StaticAssetTests(TestCase):
    """Guard the production `collectstatic` step, which is a build gate.

    Manifest storage resolves every reference inside a stylesheet and raises
    MissingFileError when one is absent. `static/vendor/bootstrap.min.css` shipped
    with a `sourceMappingURL` comment pointing at a .map file that was never
    committed, so `collectstatic` aborted and every Render/Docker deploy failed
    before the app could start. These tests fail early and clearly instead.
    """

    @staticmethod
    def _static_root() -> Path:
        dirs = settings.STATICFILES_DIRS
        return Path(dirs[0] if dirs else settings.BASE_DIR / "static")

    def test_no_dangling_sourcemap_references(self):
        offenders = []
        root = self._static_root()
        for css in root.rglob("*.css"):
            text = css.read_text(encoding="utf-8", errors="ignore")
            for target in re.findall(r"sourceMappingURL=([^\s*]+)", text):
                if not (css.parent / target).exists():
                    offenders.append(f"{css.name} -> {target}")
        self.assertEqual(offenders, [],
                         f"CSS files reference missing source maps: {offenders}")

    def test_stylesheet_references_all_resolve(self):
        """Every url()/@import target in our own CSS must exist on disk."""
        static_root = self._static_root()
        # STATIC_URL is the prefix that gets served at the site root, so
        # "/static/vendor/x.woff2" maps to "<static root>/vendor/x.woff2".
        url_prefix = settings.STATIC_URL.lstrip("/")
        missing = []
        for css in static_root.rglob("*.css"):
            text = css.read_text(encoding="utf-8", errors="ignore")
            for target in re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", text):
                if target.startswith(("data:", "http:", "https:", "//", "#")):
                    continue
                clean = target.split("?")[0].split("#")[0].lstrip("/")
                if url_prefix and clean.startswith(url_prefix):
                    # "/static/vendor/x.woff2" -> "vendor/x.woff2", relative to
                    # the static root, not to this stylesheet's directory.
                    clean = clean[len(url_prefix):]
                    candidate = static_root / clean
                else:
                    # A bare relative path is relative to the stylesheet itself.
                    candidate = css.parent / clean
                if not candidate.exists():
                    missing.append(f"{css.name} -> {target}")
        self.assertEqual(missing, [],
                         f"CSS files reference missing assets: {missing}")


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
        c.post("/accounts/signup/", {"email": "carol@example.com",
                                     "password1": "sunny-day-42", "password2": "sunny-day-42"})
        self.assertTrue(User.objects.filter(email="carol@example.com").exists())
        from allauth.account.models import EmailAddress
        address = EmailAddress.objects.get(email="carol@example.com")
        address.verified = True
        address.save(update_fields=["verified"])
        c2 = Client()
        c2.post("/accounts/login/", {"login": "carol@example.com", "password": "sunny-day-42"})
        self.assertIn("_auth_user_id", c2.session)
        # carol's wardrobe starts empty (no shared items leak in)
        self.assertEqual(self._names(c2), [])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MediaPrivacyTests(TestCase):
    """P0 #2/#4: /media/ is ownership-checked, in dev AND production mode."""

    def _upload(self, user, name, rgb):
        client = Client()
        if user is not None:
            client.force_login(user)
        upload = SimpleUploadedFile(f"{name}.jpg", _image_bytes(rgb),
                                    content_type="image/jpeg")
        client.post("/wardrobe/add/", {"name": name, "category": "tshirt",
                                       "formality": "casual", "status": "clean",
                                       "purchase_price": "0", "season": "all",
                                       "image": upload})
        return client, Item.objects.get(name=name)

    def test_owner_can_view_but_strangers_cannot(self):
        from django.contrib.auth.models import User

        alice = User.objects.create_user("alice-m", password="pw12345!")
        bob = User.objects.create_user("bob-m", password="pw12345!")
        _, item = self._upload(alice, "Private Navy", (27, 42, 74))
        url = f"/media/{item.image.name}"

        owner = Client(); owner.force_login(alice)
        intruder = Client(); intruder.force_login(bob)
        anon = Client()

        self.assertEqual(owner.get(url).status_code, 200)     # owner: 200 + bytes
        self.assertEqual(intruder.get(url).status_code, 404)  # other user: 404
        self.assertEqual(anon.get(url).status_code, 404)      # anonymous: 404
        # The thumbnail is protected too.
        thumb = f"/media/{item.thumbnail.name}"
        self.assertEqual(owner.get(thumb).status_code, 200)
        self.assertEqual(intruder.get(thumb).status_code, 404)

    def test_shared_local_workspace_still_serves_anonymous_files(self):
        """Local-first mode (owner = NULL) keeps working for offline visitors."""
        _, item = self._upload(None, "Shared Local", (120, 30, 30))
        self.assertEqual(Client().get(f"/media/{item.image.name}").status_code, 200)

    def test_path_traversal_is_rejected(self):
        for bad in ("/etc/passwd", "../../config/settings.py", "..\\..\\db.sqlite3"):
            self.assertEqual(Client().get(f"/media/{bad.lstrip('/')}").status_code, 404,
                             msg=f"traversal not blocked: {bad}")

    @override_settings(DEBUG=False)
    def test_images_work_with_debug_false(self):
        """Production mode: media still resolves (P0 #4)."""
        from django.contrib.auth.models import User

        dana = User.objects.create_user("dana-m", password="pw12345!")
        _, item = self._upload(dana, "Prod Navy", (27, 42, 74))
        c = Client(); c.force_login(dana)
        self.assertEqual(c.get(f"/media/{item.image.name}").status_code, 200)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UploadLimitTests(TestCase):
    """P1 #11: size / corruption / dimensions are validated before saving."""

    def _post(self, upload, name="Lim"):
        return self.client.post("/wardrobe/add/", {"name": name, "category": "tshirt",
                                                   "formality": "casual", "status": "clean",
                                                   "purchase_price": "0", "season": "all",
                                                   "image": upload})

    def test_oversized_file_is_rejected(self):
        blob = b"\xff\xd8\xff\xe0" + os.urandom(int(9 * 1024 * 1024))  # > 8 MB cap
        upload = SimpleUploadedFile("huge.jpg", blob, content_type="image/jpeg")
        response = self._post(upload)
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertContains(response, "limit is", status_code=200)
        self.assertFalse(Item.objects.filter(name="Lim").exists())

    def test_corrupt_image_is_rejected(self):
        upload = SimpleUploadedFile("broken.jpg", b"not an image at all",
                                    content_type="image/jpeg")
        self.assertEqual(self._post(upload).status_code, 200)
        self.assertFalse(Item.objects.filter(name="Lim").exists())

    def test_tiny_image_is_rejected(self):
        buf = BytesIO()
        Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="JPEG")
        upload = SimpleUploadedFile("tiny.jpg", buf.getvalue(), content_type="image/jpeg")
        response = self._post(upload)
        self.assertContains(response, "too small", status_code=200)
        self.assertFalse(Item.objects.filter(name="Lim").exists())

    def test_heic_hint_is_shown(self):
        upload = SimpleUploadedFile("photo.heic", b"ftypheic....data",
                                    content_type="image/heic")
        self.assertContains(self._post(upload), "HEIC", status_code=200)
        self.assertFalse(Item.objects.filter(name="Lim").exists())

    def test_decompression_bomb_pixels_are_rejected(self):
        """Refuse absurd dimensions before the pixels are ever touched."""
        from django.core.exceptions import ValidationError

        import wardrobe.validators as validators
        from wardrobe.validators import validate_image_upload

        class FakeUpload:
            size = 1024
            name = "bomb.png"

            def seek(self, *_a):
                pass

        class Bomb:
            format = "PNG"
            size = (90000, 90000)  # 8.1 GPix >> 40 MP default ceiling

            def verify(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        original_open = validators.Image.open
        validators.Image.open = lambda *_a, **_k: Bomb()
        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_image_upload(FakeUpload())
            self.assertIn("MP", str(ctx.exception))          # pixel-ceiling error
            self.assertIn("90000", str(ctx.exception))       # reports true dimensions
        finally:
            validators.Image.open = original_open