from django.urls import path
from . import views
urlpatterns=[path("",views.weekly,name="weekly"),path("add/",views.add_plan,name="add_plan")]
