from django.urls import path
from . import views
urlpatterns=[path("",views.laundry_list,name="laundry"),path("wash-all/",views.mark_all_washed,name="wash_all"),
path("<int:pk>/wash/",views.mark_washed,name="mark_washed")]
