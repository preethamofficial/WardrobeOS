from django.conf import settings
from django.db import models
from django.utils import timezone


class Item(models.Model):
    CATEGORIES=[("shirt","Shirt"),("tshirt","T-Shirt"),("pant","Pant"),("jeans","Jeans"),("shorts","Shorts"),
    ("jacket","Jacket"),("hoodie","Hoodie"),("sweater","Sweater"),("dress","Dress"),("skirt","Skirt"),
    ("shoes","Shoes"),("accessory","Accessory"),("other","Other")]
    FORMALITY=[("formal","Formal"),("smart_casual","Smart Casual"),("casual","Casual"),("sport","Sport")]
    STATUS=[("clean","Clean"),("worn","Worn"),("laundry","In Laundry"),("unavailable","Unavailable")]
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,verbose_name="Owner",on_delete=models.CASCADE,
                            related_name="items",blank=True,null=True,
                            help_text="Signed-in owner. NULL = the shared local wardrobe (anonymous/local-first mode).")
    name=models.CharField(max_length=120); category=models.CharField(max_length=30,choices=CATEGORIES,default="other")
    color=models.CharField(max_length=50,blank=True)
    color_family=models.CharField(max_length=30,blank=True,help_text="Colour family (blue, neutral, red...) derived from the photo - drives outfit rules")
    pattern=models.CharField(max_length=50,blank=True)
    material=models.CharField(max_length=80,blank=True); formality=models.CharField(max_length=30,choices=FORMALITY,default="casual")
    season=models.CharField(max_length=80,default="all",blank=True); occasions=models.CharField(max_length=255,blank=True)
    image=models.ImageField(upload_to="wardrobe/",blank=True,null=True)
    thumbnail=models.ImageField(upload_to="wardrobe/thumbs/",blank=True,null=True,help_text="Small web preview generated on upload")
    status=models.CharField(max_length=20,choices=STATUS,default="clean"); wear_count=models.PositiveIntegerField(default=0)
    last_worn=models.DateTimeField(blank=True,null=True); purchase_price=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    notes=models.TextField(blank=True); ai_tagged=models.BooleanField(default=False); ai_confidence=models.FloatField(default=0)
    palette=models.JSONField(default=list,blank=True,help_text="Dominant colours extracted from the photo: [{hex,name,family,share}]")
    created_at=models.DateTimeField(auto_now_add=True)
    def wear(self):
        self.wear_count+=1; self.last_worn=timezone.now(); self.status="worn"; self.save()
    @property
    def cost_per_wear(self):
        return float(self.purchase_price)/self.wear_count if self.wear_count else float(self.purchase_price)
    @property
    def display_image(self):
        """Fastest available image URL (thumbnail first); file-safe."""
        try:
            if self.thumbnail: return self.thumbnail.url
        except Exception:
            pass
        try:
            if self.image: return self.image.url
        except Exception:
            pass
        return ""
    @property
    def primary_color(self):
        """(hex, name) of the dominant colour, or (None, color field)."""
        from ai.colors import normalize_palette
        entries=normalize_palette(self.palette)
        if entries: return entries[0]["hex"], entries[0]["name"]
        return None, (self.color or "")
    def __str__(self): return self.name
