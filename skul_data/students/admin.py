from django.contrib import admin
from skul_data.students.models.student import (
    Student,
    StudentDocument,
    StudentNote,
    StudentStatusChange,
)
from skul_data.students.models.student import Subject


class StudentStatusChangeInline(admin.TabularInline):
    model = StudentStatusChange
    extra = 0
    readonly_fields = ("changed_at", "changed_by")

    def has_add_permission(self, request, obj=None):
        return False


class StudentDocumentInline(admin.TabularInline):
    model = StudentDocument
    extra = 0
    readonly_fields = ("uploaded_at", "uploaded_by")


class StudentNoteInline(admin.TabularInline):
    model = StudentNote
    extra = 0
    readonly_fields = ("created_at", "created_by")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "admission_number",
        "student_class",
        "status",
        "is_active",
    )
    list_filter = ("is_active", "status", "student_class", "gender")
    search_fields = ("first_name", "last_name", "admission_number")
    inlines = [StudentStatusChangeInline, StudentDocumentInline, StudentNoteInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.school = request.user.school
        super().save_model(request, obj, form, change)

    # Disable hard deletion in admin
    def delete_model(self, request, obj):
        obj.deactivate(reason="Deleted via admin interface")
        obj.save()

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "document_type", "uploaded_at")
    list_filter = ("document_type",)
    search_fields = ("title", "student__first_name", "student__last_name")


@admin.register(StudentNote)
class StudentNoteAdmin(admin.ModelAdmin):
    list_display = ("student", "note_type", "created_at", "is_private")
    list_filter = ("note_type", "is_private")
    search_fields = ("content", "student__first_name", "student__last_name")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "school")
    list_filter = ("school",)
    search_fields = ("name", "code")
