from django.conf import settings
from django.db import models


class Plan(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,
                            related_name="plans",blank=True,null=True)
    date=models.DateField(); occasion=models.CharField(max_length=80,default="casual")
    location=models.CharField(max_length=120,blank=True); notes=models.TextField(blank=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["owner","date"],name="uniq_plan_owner_date")]
    def __str__(self):return f"{self.date} - {self.occasion}"
