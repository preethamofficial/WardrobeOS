from django.urls import path
from . import views
urlpatterns=[path("",views.recommendations,name="recommendations"),path("shuffle/",views.shuffle,name="shuffle"),
path("save/",views.save_outfit,name="save_outfit")]
