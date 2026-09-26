from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "country", "temperature_unit", "updated_at")
    list_filter = ("temperature_unit", "country")
    search_fields = ("user__username", "user__email", "city", "country")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ()