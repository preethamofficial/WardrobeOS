"""Enhancement pipeline tests (converted from the old root `test_enhance.py`).

The original file ran assertions and `django.setup()` at import time, which broke
`manage.py test` discovery. Same checks, now as a normal TestCase so they run
with the rest of the suite.
"""
import os
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from PIL import Image, ImageStat

from wardrobe.image_enhance import enhance_image
from wardrobe.models import Item


def _mean_luma(path):
    with Image.open(path) as im:
        return ImageStat.Stat(im.convert("L")).mean[0]


def _tmp(suffix):
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    handle.close()
    return handle.name


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class EnhancePipelineTests(TestCase):
    def setUp(self):
        self._files = []

    def tearDown(self):
        for path in self._files:
            try:
                os.remove(path)
            except OSError:
                pass

    def _path(self, suffix):
        path = _tmp(suffix)
        self._files.append(path)
        return path

    def test_dark_image_gets_brightened(self):
        path = self._path(".jpg")
        Image.new("RGB", (400, 300), (35, 30, 25)).save(path, quality=95)
        before = _mean_luma(path)
        self.assertTrue(enhance_image(path), "enhance failed on valid jpg")
        after = _mean_luma(path)
        self.assertGreater(after, before * 1.2, "dark image not brightened")

    def test_oversized_image_is_resized(self):
        path = self._path(".jpg")
        Image.new("RGB", (3000, 2000), (128, 128, 128)).save(path)
        self.assertTrue(enhance_image(path))
        with Image.open(path) as im:
            self.assertLessEqual(max(im.size), 1024, "resize did not apply")

    def test_transparency_flattened_to_rgb(self):
        path = self._path(".png")
        Image.new("RGBA", (300, 300), (200, 30, 30, 128)).save(path)
        self.assertTrue(enhance_image(path))
        with Image.open(path) as im:
            self.assertEqual(im.mode, "RGB", "transparency not flattened")

    def test_exif_orientation_is_baked_in(self):
        path = self._path(".jpg")
        im = Image.new("RGB", (600, 300), (90, 140, 200))
        exif = Image.Exif()
        exif[274] = 6  # rotate 90
        im.save(path, exif=exif)
        self.assertTrue(enhance_image(path))
        with Image.open(path) as im:
            self.assertEqual(im.size, (300, 600), "EXIF rotation not applied")

    def test_corrupt_file_untouched(self):
        path = self._path(".jpg")
        with open(path, "wb") as handle:
            handle.write(b"definitely-not-an-image")
        original = open(path, "rb").read()
        self.assertFalse(enhance_image(path), "corrupt file should return False")
        self.assertEqual(open(path, "rb").read(), original, "corrupt file was modified")

    def test_enhancement_is_idempotent(self):
        """Re-running the pipeline must not shift colours (navy -> black drift)."""
        path = self._path(".jpg")
        Image.new("RGB", (400, 300), (27, 42, 74)).save(path, quality=95)  # navy
        self.assertTrue(enhance_image(path))
        first = _mean_luma(path)
        self.assertTrue(enhance_image(path), "second run failed")
        self.assertAlmostEqual(_mean_luma(path), first, delta=1.5,
                               msg="double enhancement shifted the image")

    def test_end_to_end_upload_is_enhanced(self):
        buf = BytesIO()
        Image.new("RGB", (500, 400), (40, 35, 30)).save(buf, format="JPEG")
        upload = SimpleUploadedFile("dark_item.jpg", buf.getvalue(),
                                    content_type="image/jpeg")
        response = Client(SERVER_NAME="127.0.0.1").post("/wardrobe/add/", {
            "name": "Enhance Test Jacket", "category": "jacket",
            "formality": "casual", "status": "clean", "purchase_price": "10",
            "season": "all", "image": upload,
        })
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Enhance Test Jacket")
        self.assertTrue(item.image, "image was not stored")
        stored_luma = _mean_luma(item.image.path)
        self.assertGreater(stored_luma, 45, "stored image was not enhanced")
        item.delete()  # also exercises the post_delete file cleanup signal