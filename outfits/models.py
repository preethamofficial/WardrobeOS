from django.conf import settings
from django.db import models


class Outfit(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,
                            related_name="outfits",blank=True,null=True)
    name=models.CharField(max_length=120); occasion=models.CharField(max_length=80,blank=True)
    score=models.FloatField(default=0); favorite=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    items=models.ManyToManyField("wardrobe.Item",blank=True)


class Feedback(models.Model):
    outfit=models.ForeignKey(Outfit,on_delete=models.CASCADE)
    value=models.IntegerField(choices=[(-1,"Reject"),(1,"Like")]); reason=models.CharField(max_length=120,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
