from django.contrib import admin
from django.contrib import admin
from .models.role import Role, Permission
from .models.teacher import Teacher, TeacherAttendance, TeacherDocument, TeacherWorkload
from .models.school_admin import AdministratorProfile
from django.utils.html import format_html
from django.utils import timezone
from .models.password_reset import PasswordResetOTP


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


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Password Reset OTPs.
    Provides viewing and filtering capabilities for OTP records.
    """

    list_display = [
        "id",
        "user_email",
        "masked_otp",
        "status_badge",
        "created_at",
        "expires_at",
        "time_remaining",
        "ip_address",
    ]

    list_filter = [
        "is_used",
        "created_at",
        "expires_at",
    ]

    search_fields = [
        "user__email",
        "user__username",
        "user__first_name",
        "user__last_name",
        "otp_code",
        "ip_address",
    ]

    readonly_fields = [
        "user",
        "otp_code",
        "created_at",
        "expires_at",
        "is_used",
        "used_at",
        "ip_address",
        "user_agent",
        "time_remaining",
        "status_badge",
    ]

    ordering = ["-created_at"]

    date_hierarchy = "created_at"

    # Prevent adding/editing OTPs through admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Allow superusers to delete old OTPs
        return request.user.is_superuser

    def user_email(self, obj):
        """Display user's email with link to user admin"""
        if obj.user:
            return format_html(
                '<a href="/admin/users/user/{}/change/">{}</a>',
                obj.user.id,
                obj.user.email,
            )
        return "-"

    user_email.short_description = "User Email"
    user_email.admin_order_field = "user__email"

    def masked_otp(self, obj):
        """Display OTP with some digits masked for security"""
        if obj.otp_code:
            return f"••••{obj.otp_code[-2:]}"
        return "-"

    masked_otp.short_description = "OTP Code"

    def status_badge(self, obj):
        """Display status as colored badge"""
        if obj.is_used:
            color = "gray"
            text = "Used"
        elif timezone.now() > obj.expires_at:
            color = "red"
            text = "Expired"
        else:
            color = "green"
            text = "Active"

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            text,
        )

    status_badge.short_description = "Status"

    def time_remaining(self, obj):
        """Display time remaining until expiration"""
        if obj.is_used:
            return format_html('<span style="color: gray;">Used</span>')

        now = timezone.now()
        if now > obj.expires_at:
            return format_html('<span style="color: red;">Expired</span>')

        remaining = obj.expires_at - now
        minutes = int(remaining.total_seconds() / 60)
        seconds = int(remaining.total_seconds() % 60)

        return format_html(
            '<span style="color: green;">{}m {}s</span>', minutes, seconds
        )

    time_remaining.short_description = "Time Remaining"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related("user")

    # Custom actions
    actions = ["mark_as_expired", "cleanup_old_otps"]

    def mark_as_expired(self, request, queryset):
        """Mark selected OTPs as used (expired)"""
        updated = queryset.update(is_used=True, used_at=timezone.now())
        self.message_user(request, f"{updated} OTP(s) marked as expired.")

    mark_as_expired.short_description = "Mark selected OTPs as expired"

    def cleanup_old_otps(self, request, queryset):
        """Delete OTPs older than 24 hours"""
        cutoff_time = timezone.now() - timezone.timedelta(hours=24)
        old_otps = queryset.filter(created_at__lt=cutoff_time)
        count = old_otps.count()
        old_otps.delete()

        self.message_user(request, f"{count} old OTP(s) deleted.")

    cleanup_old_otps.short_description = "Delete OTPs older than 24 hours"

    # Fieldsets for detail view
    fieldsets = (
        ("User Information", {"fields": ("user", "user_email")}),
        (
            "OTP Details",
            {
                "fields": (
                    "otp_code",
                    "status_badge",
                    "created_at",
                    "expires_at",
                    "time_remaining",
                )
            },
        ),
        ("Usage Information", {"fields": ("is_used", "used_at")}),
        (
            "Security Information",
            {"fields": ("ip_address", "user_agent"), "classes": ("collapse",)},
        ),
    )


admin.site.register(Teacher, TeacherAdmin)
admin.site.register(TeacherWorkload, TeacherWorkloadAdmin)
admin.site.register(TeacherAttendance, TeacherAttendanceAdmin)
admin.site.register(TeacherDocument, TeacherDocumentAdmin)
