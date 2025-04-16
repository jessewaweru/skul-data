from django.contrib import admin
from django.contrib import admin
from .models.role import Role, Permission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "role_type")
    list_filter = ("school",)
    search_fields = ("name",)
    filter_horizontal = ("permissions",)
