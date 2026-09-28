from django.urls import path
from . import views

urlpatterns=[
    path("",views.command_center,name="style_command_center"),
    path("coach/",views.style_coach,name="style_coach"),
    path("remix/<int:pk>/",views.remix,name="style_remix"),
]
