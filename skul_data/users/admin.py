from django.contrib import admin
from django.contrib import admin
from .models.role import Role, Permission
from .models.teacher import Teacher, TeacherAttendance, TeacherDocument, TeacherWorkload
from .models.school_admin import AdministratorProfile


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


class TeacherAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "status", "qualification", "years_of_experience")
    list_filter = ("status", "school", "is_class_teacher", "is_department_head")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "payroll_number",
    )
    raw_id_fields = ("user", "school")
    filter_horizontal = ("subjects_taught", "assigned_classes")


class TeacherWorkloadAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "school_class",
        "subject",
        "hours_per_week",
        "term",
        "school_year",
    )
    list_filter = ("term", "school_year", "school_class")
    raw_id_fields = ("teacher", "school_class", "subject")


class TeacherAttendanceAdmin(admin.ModelAdmin):
    list_display = ("teacher", "date", "status", "check_in", "check_out")
    list_filter = ("status", "date")
    raw_id_fields = ("teacher", "recorded_by")


class TeacherDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "title",
        "document_type",
        "uploaded_at",
        "is_confidential",
    )
    list_filter = ("document_type", "is_confidential")
    search_fields = ("title", "description")
    raw_id_fields = ("teacher", "uploaded_by")


@admin.register(AdministratorProfile)
class AdministratorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "access_level", "kcse_permissions")
    # filter_horizontal = ("permissions_granted",)

    def kcse_permissions(self, obj):
        return ", ".join(obj.permissions_granted.get("kcse", []))

    kcse_permissions.short_description = "KCSE Permissions"

    fieldsets = (
        (None, {"fields": ("user", "school", "position", "access_level")}),
        (
            "KCSE Permissions",
            {
                "fields": ("permissions_granted",),
                "description": "Manage permissions for KCSE system",
            },
        ),
        ("Additional Information", {"fields": ("notes",), "classes": ("collapse",)}),
    )


admin.site.register(Teacher, TeacherAdmin)
admin.site.register(TeacherWorkload, TeacherWorkloadAdmin)
admin.site.register(TeacherAttendance, TeacherAttendanceAdmin)
admin.site.register(TeacherDocument, TeacherDocumentAdmin)
