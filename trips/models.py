from django.conf import settings
from django.db import models


class Trip(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,
                            related_name="trips",blank=True,null=True)
    name=models.CharField(max_length=120); destination=models.CharField(max_length=120)
    start_date=models.DateField(); end_date=models.DateField(); notes=models.TextField(blank=True)
    lat=models.FloatField(blank=True,null=True); lon=models.FloatField(blank=True,null=True)
    packing=models.JSONField(default=list,blank=True,help_text="Generated packing checklist")
    created_at=models.DateTimeField(auto_now_add=True)
    @property
    def nights(self): return max(1,(self.end_date-self.start_date).days)
    @property
    def packed_count(self): return sum(1 for x in self.packing if x.get("packed"))
    @property
    def pack_progress(self):
        return round(100*self.packed_count/len(self.packing)) if self.packing else 0
    def __str__(self): return f"{self.name} ({self.destination})"
