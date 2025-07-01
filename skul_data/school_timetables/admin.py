from django.contrib import admin
from skul_data.school_timetables.models.school_timetable import (
    TimeSlot,
    TimetableStructure,
    Timetable,
    Lesson,
    TimetableConstraint,
    SubjectGroup,
    TeacherAvailability,
)


class TimeSlotAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "school",
        "day_of_week",
        "start_time",
        "end_time",
        "is_break",
        "is_active",
    )
    list_filter = ("school", "day_of_week", "is_break", "is_active")
    search_fields = ("name", "break_name")
    ordering = ("school", "day_of_week", "order")


class TimetableStructureAdmin(admin.ModelAdmin):
    list_display = ("school", "curriculum", "default_start_time", "default_end_time")
    list_filter = ("curriculum",)
    search_fields = ("school__name",)


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    fields = ("subject", "teacher", "time_slot", "is_double_period", "room", "notes")
    autocomplete_fields = ("subject", "teacher", "time_slot")


class TimetableAdmin(admin.ModelAdmin):
    list_display = ("school_class", "academic_year", "term", "is_active")
    list_filter = ("academic_year", "term", "is_active")
    search_fields = ("school_class__name",)
    inlines = [LessonInline]
    # Removed filter_horizontal = ("lessons",) because lessons is not a many-to-many field


class LessonAdmin(admin.ModelAdmin):
    list_display = ("timetable", "subject", "teacher", "time_slot", "is_double_period")
    list_filter = ("timetable__school_class__school", "subject", "teacher")
    search_fields = (
        "subject__name",
        "teacher__user__first_name",
        "teacher__user__last_name",
    )


class TimetableConstraintAdmin(admin.ModelAdmin):
    list_display = ("school", "constraint_type", "is_hard_constraint", "is_active")
    list_filter = ("school", "constraint_type", "is_hard_constraint", "is_active")
    search_fields = ("description",)


class SubjectGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "school")
    list_filter = ("school",)
    search_fields = ("name", "description")
    filter_horizontal = ("subjects",)


class TeacherAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "day_of_week",
        "is_available",
        "available_from",
        "available_to",
    )
    list_filter = ("teacher__school", "day_of_week", "is_available")
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "reason")


admin.site.register(TimeSlot, TimeSlotAdmin)
admin.site.register(TimetableStructure, TimetableStructureAdmin)
admin.site.register(Timetable, TimetableAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(TimetableConstraint, TimetableConstraintAdmin)
admin.site.register(SubjectGroup, SubjectGroupAdmin)
admin.site.register(TeacherAvailability, TeacherAvailabilityAdmin)
