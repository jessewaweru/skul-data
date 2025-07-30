from django.contrib import admin

from django.contrib import admin
from skul_data.kcse.models.kcse import (
    KCSEResult,
    KCSESubjectResult,
    KCSESchoolPerformance,
    KCSESubjectPerformance,
)


class KCSESubjectResultInline(admin.TabularInline):
    model = KCSESubjectResult
    extra = 0


@admin.register(KCSEResult)
class KCSEResultAdmin(admin.ModelAdmin):
    list_display = ("student", "year", "mean_grade", "mean_points", "is_published")
    list_filter = ("year", "mean_grade", "is_published", "school")
    search_fields = ("student__first_name", "student__last_name", "index_number")
    inlines = [KCSESubjectResultInline]


class KCSESubjectPerformanceInline(admin.TabularInline):
    model = KCSESubjectPerformance
    extra = 0


@admin.register(KCSESchoolPerformance)
class KCSESchoolPerformanceAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "year",
        "mean_grade",
        "mean_points",
        "university_qualified",
    )
    list_filter = ("year", "mean_grade", "school")
    search_fields = ("school__name",)
    inlines = [KCSESubjectPerformanceInline]


@admin.register(KCSESubjectResult)
class KCSESubjectResultAdmin(admin.ModelAdmin):
    list_display = ("kcse_result", "subject", "grade", "points")
    list_filter = ("grade", "subject")
    search_fields = (
        "kcse_result__student__first_name",
        "kcse_result__student__last_name",
    )


@admin.register(KCSESubjectPerformance)
class KCSESubjectPerformanceAdmin(admin.ModelAdmin):
    list_display = (
        "school_performance",
        "subject",
        "mean_grade",
        "mean_score",
        "passed",
    )
    list_filter = ("mean_grade", "subject")
    search_fields = ("subject__name",)
