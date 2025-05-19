from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Sum, Q, F, Max
from skul_data.schools.models.school import School
from skul_data.students.models.student import Student
from skul_data.users.models.teacher import Teacher
from skul_data.analytics.models.analytics import CachedAnalytics
from skul_data.analytics.views.analytics import (
    get_most_active_teacher,
    get_student_attendance_rate,
    get_most_downloaded_document,
    get_top_performing_class,
    get_reports_generated_count,
    get_teacher_logins,
    get_reports_per_teacher,
    get_attendance_accuracy,
    get_student_attendance,
    get_student_performance,
    get_student_dropouts,
    get_class_sizes,
    get_class_average_grades,
    get_top_classes,
)
from skul_data.schools.models.schoolclass import ClassAttendance


@shared_task
def cache_daily_analytics():
    """Task to pre-compute and cache daily analytics for all schools"""
    schools = School.objects.all()

    for school in schools:
        # Pre-compute overview data
        overview_data = {
            "most_active_teacher": get_most_active_teacher(school),
            "student_attendance_rate": get_student_attendance_rate(school),
            "most_downloaded_document": get_most_downloaded_document(school),
            "top_performing_class": get_top_performing_class(school),
            "reports_generated": get_reports_generated_count(school),
        }

        CachedAnalytics.objects.update_or_create(
            school=school,
            analytics_type="overview",
            defaults={
                "data": overview_data,
                "valid_until": timezone.now() + timedelta(hours=24),
            },
        )

        # Pre-compute teacher analytics
        teacher_data = {
            "total_teachers": Teacher.objects.filter(school=school).count(),
            "logins": get_teacher_logins(school),
            "reports_per_teacher": get_reports_per_teacher(school),
            "attendance_accuracy": get_attendance_accuracy(school),
        }

        CachedAnalytics.objects.update_or_create(
            school=school,
            analytics_type="teachers",
            defaults={
                "data": teacher_data,
                "valid_until": timezone.now() + timedelta(days=1),
            },
        )

        # Pre-compute student analytics
        student_data = {
            "total_students": Student.objects.filter(school=school).count(),
            "attendance": get_student_attendance(school),
            "performance": get_student_performance(school),
            "dropouts": get_student_dropouts(school),
        }

        CachedAnalytics.objects.update_or_create(
            school=school,
            analytics_type="students",
            defaults={
                "data": student_data,
                "valid_until": timezone.now() + timedelta(days=1),
            },
        )

        # Pre-compute class analytics
        class_data = {
            "class_sizes": get_class_sizes(school),
            "average_grades": get_class_average_grades(school),
            "top_classes": get_top_classes(school),
        }

        CachedAnalytics.objects.update_or_create(
            school=school,
            analytics_type="classes",
            defaults={
                "data": class_data,
                "valid_until": timezone.now() + timedelta(days=1),
            },
        )


# Helper functions for Celery tasks (similar to viewset helpers but optimized for batch processing)
def get_most_active_teacher(school):
    last_month = timezone.now() - timedelta(days=30)
    return list(
        Teacher.objects.filter(school=school, user__last_login__gte=last_month)
        .annotate(login_count=Count("user__login_history"))
        .order_by("-login_count")
        .values("user__first_name", "user__last_name", "login_count")[:1]
    )


# def get_student_attendance_rate(school):
#     total_attendance = ClassAttendance.objects.filter(
#         school_class__school=school
#     ).aggregate(
#         total_present=Sum("present_students__count"),
#         total_possible=Sum("school_class__students__count"),
#     )

#     if total_attendance["total_possible"] and total_attendance["total_possible"] > 0:
#         return (
#             total_attendance["total_present"] / total_attendance["total_possible"]
#         ) * 100
#     return 0


@shared_task
def check_and_generate_alerts():
    """Task to check for conditions that should trigger alerts"""
    from skul_data.analytics.models.analytics import AnalyticsAlert
    from skul_data.students.models.student import Student
    from skul_data.users.models.teacher import TeacherAttendance
    from skul_data.reports.models.academic_record import AcademicRecord

    # Check for students with consistently low performance
    low_performers = (
        AcademicRecord.objects.filter(score__lt=40)  # Failing grade
        .values("student")
        .annotate(low_count=Count("id"), last_score=Max("created_at"))
        .filter(low_count__gte=3)  # At least 3 failing grades
    )

    for student in low_performers:
        AnalyticsAlert.objects.create(
            school=student["student__school"],
            alert_type="PERFORMANCE",
            title=f'Consistent Low Performance: {student["student__full_name"]}',
            message=f'Student {student["student__full_name"]} has {student["low_count"]} failing grades.',
            related_model="Student",
            related_id=student["student__id"],
        )

    # Check for teachers with frequent absences
    frequent_absentees = (
        TeacherAttendance.objects.filter(
            status="ABSENT", date__gte=timezone.now() - timedelta(days=30)
        )
        .values("teacher")
        .annotate(absent_count=Count("id"))
        .filter(absent_count__gte=3)  # At least 3 absences in last month
    )

    for teacher in frequent_absentees:
        AnalyticsAlert.objects.create(
            school=teacher["teacher__school"],
            alert_type="ATTENDANCE",
            title=f'Frequent Absences: {teacher["teacher__full_name"]}',
            message=f'Teacher {teacher["teacher__full_name"]} has been absent {teacher["absent_count"]} times in the last month.',
            related_model="Teacher",
            related_id=teacher["teacher__id"],
        )
