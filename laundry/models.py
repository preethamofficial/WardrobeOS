from django.db import models
class WashLog(models.Model):
    item=models.ForeignKey("wardrobe.Item",on_delete=models.CASCADE,related_name="wash_logs")
    washed_at=models.DateTimeField(auto_now_add=True); notes=models.TextField(blank=True)
