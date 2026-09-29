from django.urls import path
from . import views
urlpatterns=[path("",views.weekly,name="weekly"),path("add/",views.add_plan,name="add_plan"),path("<int:pk>/delete/",views.delete_plan,name="delete_plan")]
