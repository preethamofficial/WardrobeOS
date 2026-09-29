from django.contrib import admin
from django.urls import include,path
from wardrobe import media_views
from wardrobe import views as wardrobe_views
from config import api
from accounts_app import views as account_views
urlpatterns=[
path("admin/",admin.site.urls),path("",wardrobe_views.dashboard,name="dashboard"),
path("api/items/",api.items),path("api/weather/",api.weather_now),path("api/outfits/today/",api.outfit_today),
path("api/health/",api.health),path("health/",api.health),
# Uploaded photos are personal data, so /media/ is served by an ownership-checking
# view in EVERY environment (dev, Docker, Render, PythonAnywhere). This also fixes
# images 404ing under DEBUG=False, where Django serves no media at all.
path("media/<path:path>",media_views.serve_media,name="serve_media"),
path("wardrobe/",include("wardrobe.urls")),path("outfits/",include("outfits.urls")),
path("accounts/verification-sent/",account_views.verification_sent,name="account_email_verification_sent_landing"),
# Override allauth's anonymous verification landing view with our actionable
# page. The keyed /confirm-email/<key>/ route below still belongs to allauth.
path("accounts/confirm-email/",account_views.verification_sent,name="account_email_verification_sent_confirm_landing"),
path("accounts/resend-verification/",account_views.resend_verification,name="resend_verification"),
path("accounts/",include("allauth.urls")),
path("profile/",include("accounts_app.urls")),
path("planner/",include("planner.urls")),path("laundry/",include("laundry.urls")),
path("analytics/",include("analytics_app.urls")),path("trips/",include("trips.urls")),path("style/",include("styleos.urls")),
path("lab/",include("promptlab.urls"))]
