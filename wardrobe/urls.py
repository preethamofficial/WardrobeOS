from django.urls import path

from . import views

urlpatterns = [path("", views.wardrobe_list, name="wardrobe_list"), path("add/", views.item_add, name="item_add"), path("scan/", views.quick_scan, name="quick_scan"),
    path("<int:pk>/edit/", views.item_edit, name="item_edit"), path("<int:pk>/delete/", views.item_delete, name="item_delete"),
    path("<int:pk>/wear/", views.item_wear, name="item_wear"), path("<int:pk>/rescan/", views.item_rescan, name="item_rescan")]
