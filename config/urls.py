from django.contrib import admin
from django.urls import include,path
from django.conf import settings
from django.conf.urls.static import static
from wardrobe import views as wardrobe_views
from config import api
urlpatterns=[
path("admin/",admin.site.urls),path("",wardrobe_views.dashboard,name="dashboard"),
path("api/items/",api.items),path("api/weather/",api.weather_now),path("api/outfits/today/",api.outfit_today),
path("health/",api.health),
path("wardrobe/",include("wardrobe.urls")),path("outfits/",include("outfits.urls")),
path("accounts/",include("allauth.urls")),
path("planner/",include("planner.urls")),path("laundry/",include("laundry.urls")),
path("analytics/",include("analytics_app.urls")),path("trips/",include("trips.urls")),
path("lab/",include("promptlab.urls"))]
if settings.DEBUG: urlpatterns+=static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
