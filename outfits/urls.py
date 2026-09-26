from django.urls import path
from . import views
urlpatterns=[path("",views.recommendations,name="recommendations"),path("shuffle/",views.shuffle,name="shuffle"),
path("save/",views.save_outfit,name="save_outfit"),
# Saved-outfit history and the actions that make it useful
path("history/",views.outfit_history,name="outfit_history"),
path("<int:pk>/favorite/",views.favorite_outfit,name="favorite_outfit"),
path("<int:pk>/worn/",views.mark_outfit_worn,name="mark_outfit_worn"),
path("<int:pk>/delete/",views.delete_outfit,name="delete_outfit"),
path("<int:pk>/feedback/",views.outfit_feedback,name="outfit_feedback")]
