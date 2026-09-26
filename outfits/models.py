from django.conf import settings
from django.db import models
from django.utils import timezone


class Outfit(models.Model):
    """A saved combination of wardrobe items.

    Saving a recommendation used to be a dead end: there was nowhere to see it
    again, no way to favourite or delete it, and wearing it was not tracked - so
    the wardrobe's own rotation data ignored every saved outfit. The fields and
    actions added here (favourite, worn tracking, notes) make the saved-outfit
    list a usable part of the rotation loop.
    """
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,
                            related_name="outfits",blank=True,null=True)
    name=models.CharField(max_length=120); occasion=models.CharField(max_length=80,blank=True)
    score=models.FloatField(default=0); favorite=models.BooleanField(default=False)
    notes=models.CharField(max_length=240,blank=True)
    wear_count=models.PositiveIntegerField(default=0)
    last_worn=models.DateTimeField(blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    items=models.ManyToManyField("wardrobe.Item",blank=True,related_name="outfits")

    class Meta:
        ordering=["-favorite","-created_at"]

    def __str__(self):
        return self.name

    @property
    def item_count(self):
        return self.items.count()

    def mark_worn(self, when=None):
        """Record a wear of the whole combination (bumps each item too)."""
        when = when or timezone.now()
        self.wear_count += 1
        self.last_worn = when
        self.save(update_fields=["wear_count", "last_worn"])
        for item in self.items.all():
            item.wear_count += 1
            item.last_worn = when
            item.status = "worn"
            item.save(update_fields=["wear_count", "last_worn", "status"])

    @property
    def feedback_summary(self):
        likes = self.feedback_set.filter(value=1).count()
        dislikes = self.feedback_set.filter(value=-1).count()
        return {"likes": likes, "dislikes": dislikes, "total": likes + dislikes}


class Feedback(models.Model):
    """Thumbs up/down on a saved outfit, with an optional reason (feeds the
    stylist: disliked outfits are penalised in later recommendations)."""
    REASONS = [("fit", "Fit"), ("colour", "Colour"), ("occasion", "Wrong occasion"),
               ("comfort", "Comfort"), ("repetition", "Too repetitive"), ("other", "Other")]

    outfit=models.ForeignKey(Outfit,on_delete=models.CASCADE,related_name="feedback_set")
    value=models.IntegerField(choices=[(-1,"Reject"),(1,"Like")]); reason=models.CharField(max_length=120,blank=True)
    note=models.CharField(max_length=240,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=["-created_at"]
        verbose_name_plural="feedback"

    def __str__(self):
        return f"{'like' if self.value == 1 else 'dislike'} {self.outfit.name}"
