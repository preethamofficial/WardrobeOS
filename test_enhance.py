import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from io import BytesIO
from PIL import Image, ImageStat
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from wardrobe.image_enhance import enhance_image
from wardrobe.models import Item


def mean_luma(path):
    with Image.open(path) as im:
        return ImageStat.Stat(im.convert("L")).mean[0]


# 1. Dark image gets brightened
Image.new("RGB", (400, 300), (35, 30, 25)).save("t_dark.jpg", quality=95)
before = mean_luma("t_dark.jpg")
assert enhance_image("t_dark.jpg") is True, "enhance failed on valid jpg"
after = mean_luma("t_dark.jpg")
print(f"1. dark image luma: {before:.1f} -> {after:.1f}")
assert after > before * 1.2, "dark image not brightened"

# 2. Oversized image is resized
Image.new("RGB", (3000, 2000), (128, 128, 128)).save("t_big.jpg")
assert enhance_image("t_big.jpg") is True
with Image.open("t_big.jpg") as im:
    print(f"2. 3000x2000 resized to: {im.size}")
    assert max(im.size) <= 1024, "resize did not apply"

# 3. RGBA transparency flattened to RGB
Image.new("RGBA", (300, 300), (200, 30, 30, 128)).save("t_alpha.png")
assert enhance_image("t_alpha.png") is True
with Image.open("t_alpha.png") as im:
    print(f"3. RGBA saved as mode: {im.mode}")
    assert im.mode == "RGB", "transparency not flattened"

# 4. EXIF orientation is baked in
im = Image.new("RGB", (600, 300), (90, 140, 200))
ex = Image.Exif(); ex[274] = 6  # orientation: rotate 90
im.save("t_exif.jpg", exif=ex)
assert enhance_image("t_exif.jpg") is True
with Image.open("t_exif.jpg") as im:
    print(f"4. EXIF 600x300 w/ orient=6 -> size {im.size}, orientation tag {im.getexif().get(274)}")
    assert im.size == (300, 600), "EXIF rotation not applied"

# 5. Corrupt file: returns False and leaves the file untouched
with open("t_bad.jpg", "wb") as f:
    f.write(b"definitely-not-an-image")
orig = open("t_bad.jpg", "rb").read()
assert enhance_image("t_bad.jpg") is False, "corrupt file should return False"
assert open("t_bad.jpg", "rb").read() == orig, "corrupt file was modified"
print("5. corrupt file left untouched: OK")

# 6. End-to-end upload through the view
buf = BytesIO()
Image.new("RGB", (500, 400), (40, 35, 30)).save(buf, format="JPEG")
buf.seek(0)
upload = SimpleUploadedFile("dark_item.jpg", buf.getvalue(), content_type="image/jpeg")
c = Client(SERVER_NAME="127.0.0.1")
r = c.post("/wardrobe/add/", {
    "name": "Enhance Test Jacket", "category": "jacket", "formality": "casual",
    "status": "clean", "purchase_price": "10", "season": "all", "image": upload,
})
print(f"6. POST /wardrobe/add/ -> {r.status_code}")
assert r.status_code == 302, f"upload did not redirect: {r.status_code}"
item = Item.objects.get(name="Enhance Test Jacket")
assert item.image, "image was not stored"
stored_luma = mean_luma(item.image.path)
print(f"   stored image luma: {stored_luma:.1f} (original was ~35)")
assert stored_luma > 45, "stored image was not enhanced"
print(f"   AI fields: category={item.category!r} ai_tagged={item.ai_tagged} ai_confidence={item.ai_confidence}")
media_path = item.image.path
item.delete()

print("ALL ENHANCEMENT TESTS PASSED")

# cleanup
for f in ["t_dark.jpg", "t_big.jpg", "t_alpha.png", "t_exif.jpg", "t_bad.jpg", media_path]:
    try:
        os.remove(f)
    except OSError:
        pass