from django.db import models
from django.db.models import (
    Count,
    Avg,
    Sum,
    Q,
    F,
    Case,
    When,
    FloatField,
    Max,
    ExpressionWrapper,
    DurationField,
    Func,
)
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.schools.models.schoolclass import ClassAttendance
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.teacher import TeacherAttendance
from skul_data.reports.models.report import GeneratedReport, ReportAccessLog
from skul_data.users.models.parent import ParentNotification
from skul_data.users.models.base_user import User
from skul_data.users.models.parent import Parent
from skul_data.users.models.teacher import Teacher
from skul_data.documents.models.document import Document
from skul_data.students.models.student import Student, StudentAttendance


# Helper methods for each analytics metric
def get_most_active_teacher(school):
    """Get most active teacher this month"""
    last_month = timezone.now() - timedelta(days=30)
    return (
        Teacher.objects.filter(school=school, user__last_login__gte=last_month)
        .annotate(login_count=Count("user__login_history"))
        .order_by("-login_count")
        .values("user__first_name", "user__last_name", "login_count")
        .first()
    )


def get_reports_generated_count(school):
    """Get number of reports generated this term"""
    current_term = get_current_term()
    return GeneratedReport.objects.filter(
        school=school,
        generated_at__gte=current_term["start_date"],
        generated_at__lte=current_term["end_date"],
    ).count()


def get_student_attendance_rate(school):
    """Get school-wide student attendance rate"""
    total_attendance = ClassAttendance.objects.filter(
        school_class__school=school
    ).aggregate(
        total_present=Sum("present_students__count"),
        total_possible=Sum("school_class__students__count"),
    )

    if total_attendance["total_possible"] > 0:
        return (
            total_attendance["total_present"] / total_attendance["total_possible"]
        ) * 100
    return 0


def get_most_downloaded_document(school):
    """Get most downloaded document type"""
    return (
        Document.objects.filter(school=school)
        .annotate(download_count=Count("access_logs"))
        .order_by("-download_count")
        .values("title", "category__name", "download_count")
        .first()
    )


def get_top_performing_class(school):
    """Get top performing class by average grade"""
    return (
        AcademicRecord.objects.filter(student__school=school)
        .values("student__school_class__name")
        .annotate(average_score=Avg("score"))
        .order_by("-average_score")
        .first()
    )


# ===== TEACHER ANALYTICS HELPERS =====
def get_teacher_logins(school, filters):
    """Get teacher login trends (daily/weekly)"""
    date_filter = get_date_filter(filters)
    return (
        Teacher.objects.filter(
            school=school,
            user__last_login__range=(date_filter["start"], date_filter["end"]),
        )
        .annotate(
            login_count=Count("user__login_history"),
            last_week_logins=Count(
                "user__login_history",
                filter=Q(
                    user__login_history__timestamp__gte=timezone.now()
                    - timedelta(days=7)
                ),
            ),
        )
        .values(
            "user__first_name", "user__last_name", "login_count", "last_week_logins"
        )
    )


def get_reports_per_teacher(school, filters):
    """Get reports submitted per teacher"""
    date_filter = get_date_filter(filters)
    return (
        GeneratedReport.objects.filter(
            school=school,
            generated_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values(
            "generated_by__teacher_profile__id",
            "generated_by__first_name",
            "generated_by__last_name",
        )
        .annotate(report_count=Count("id"))
        .order_by("-report_count")
    )


def get_attendance_accuracy(school, filters):
    """Calculate roll call accuracy for teachers"""
    date_filter = get_date_filter(filters)
    return (
        TeacherAttendance.objects.filter(
            teacher__school=school,
            date__range=(date_filter["start"], date_filter["end"]),
        )
        .values("teacher__user__first_name", "teacher__user__last_name")
        .annotate(
            accuracy=Avg(
                Case(
                    When(status="PRESENT", then=1),
                    When(status="ABSENT", then=0),
                    When(status="LATE", then=0.5),
                    default=0,
                    output_field=models.FloatField(),
                )
            )
        )
        .order_by("-accuracy")
    )


def get_performance_per_teacher(school, filters):
    """Get average student performance per teacher"""
    date_filter = get_date_filter(filters)
    return (
        AcademicRecord.objects.filter(
            student__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("teacher__user__first_name", "teacher__user__last_name")
        .annotate(avg_score=Avg("score"), student_count=Count("student", distinct=True))
        .order_by("-avg_score")
    )


def get_response_times(school, filters):
    """Get average response time to parent concerns"""
    date_filter = get_date_filter(filters)
    return (
        ParentNotification.objects.filter(
            parent__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
            notification_type="BEHAVIOR",
        )
        .annotate(
            response_time=ExpressionWrapper(
                F("read_at") - F("created_at"), output_field=DurationField()
            )
        )
        .values("sent_by__first_name", "sent_by__last_name")
        .annotate(avg_response=Avg("response_time"))
        .order_by("avg_response")
    )


# ===== STUDENT ANALYTICS HELPERS =====
def get_student_attendance(school, filters):
    """Get student attendance percentages"""
    date_filter = get_date_filter(filters)
    class_filter = get_class_filter(filters)

    attendance = (
        StudentAttendance.objects.filter(
            student__school=school,
            date__range=(date_filter["start"], date_filter["end"]),
            **class_filter,
        )
        .values(
            "student__first_name",
            "student__last_name",
            "student__school_class__name",
        )
        .annotate(
            present_days=Count("id", filter=Q(status="PRESENT")),
            total_days=Count("id"),
        )
    )

    return [
        {
            "student": f"{a['student__first_name']} {a['student__last_name']}",
            "class": a["student__school_class__name"],
            "attendance_rate": (
                (a["present_days"] / a["total_days"]) * 100
                if a["total_days"] > 0
                else 0
            ),
        }
        for a in attendance
    ]


def get_student_performance(school, filters):
    """Get student performance trends"""
    date_filter = get_date_filter(filters)
    class_filter = get_class_filter(filters)

    return (
        AcademicRecord.objects.filter(
            student__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
            **class_filter,
        )
        .values(
            "student__first_name",
            "student__last_name",
            "student__school_class__name",
        )
        .annotate(
            avg_score=Avg("score"),
            improvement=Avg("score")
            - Avg(
                Case(
                    When(
                        student__academic_records__created_at__lt=date_filter["start"],
                        then="student__academic_records__score",
                    ),
                    default=None,
                    output_field=models.FloatField(),
                )
            ),
        )
        .order_by("-avg_score")
    )


def get_student_dropouts(school, filters):
    """Get student dropout/transfer rates"""
    date_filter = get_date_filter(filters)
    return (
        Student.objects.filter(
            school=school,
            status__in=["LEFT", "SUSPENDED"],
            updated_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_document_access(school, filters):
    """Get document access frequency by students"""
    date_filter = get_date_filter(filters)
    return (
        Document.objects.filter(
            school=school,
            access_logs__timestamp__range=(
                date_filter["start"],
                date_filter["end"],
            ),
            related_students__isnull=False,
        )
        .values("title")
        .annotate(
            access_count=Count("access_logs"),
            student_count=Count("related_students", distinct=True),
        )
        .order_by("-access_count")
    )


# ===== CLASS ANALYTICS HELPERS =====
def get_class_sizes(school):
    """Get class size distribution"""
    return (
        SchoolClass.objects.filter(school=school)
        .values("name", "grade_level")
        .annotate(student_count=Count("students"))
        .order_by("grade_level", "name")
    )


def get_class_average_grades(school, filters):
    """Get class average grades per term"""
    date_filter = get_date_filter(filters)
    return (
        AcademicRecord.objects.filter(
            student__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("student__school_class__name", "term")
        .annotate(avg_score=Avg("score"))
        .order_by("student__school_class__name", "term")
    )


def get_top_classes(school, filters):
    """Get top performing classes"""
    date_filter = get_date_filter(filters)
    return (
        AcademicRecord.objects.filter(
            student__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("student__school_class__name")
        .annotate(avg_score=Avg("score"), top_student=Max("score"))
        .order_by("-avg_score")
    )


def get_class_attendance_rates(school, filters):
    """Get class attendance rates"""
    date_filter = get_date_filter(filters)
    return (
        ClassAttendance.objects.filter(
            school_class__school=school,
            date__range=(date_filter["start"], date_filter["end"]),
        )
        .values("school_class__name")
        .annotate(
            attendance_rate=Avg(
                Case(
                    When(present_students__isnull=False, then=1),
                    default=0,
                    output_field=models.FloatField(),
                )
            )
        )
        .order_by("-attendance_rate")
    )


def get_teacher_ratios(school):
    """Get teacher-to-student ratios"""
    return (
        SchoolClass.objects.filter(school=school)
        .values("name")
        .annotate(
            student_count=Count("students"),
            teacher_count=Count("teachers", distinct=True),
        )
        .annotate(
            ratio=Case(
                When(teacher_count=0, then=0),
                default=F("student_count") / F("teacher_count"),
                output_field=models.FloatField(),
            )
        )
        .order_by("name")
    )


# ===== DOCUMENT ANALYTICS HELPERS =====
def get_document_download_frequency(school, filters):
    """Get document download frequency"""
    date_filter = get_date_filter(filters)
    return (
        Document.objects.filter(
            school=school,
            access_logs__timestamp__range=(
                date_filter["start"],
                date_filter["end"],
            ),
        )
        .values("title", "category__name")
        .annotate(download_count=Count("access_logs"))
        .order_by("-download_count")
    )


def get_document_types_distribution(school):
    """Get distribution of document types"""
    return (
        Document.objects.filter(school=school)
        .values("category__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_document_access_by_role(school, filters):
    """Get document access by user role"""
    date_filter = get_date_filter(filters)
    return (
        Document.objects.filter(
            school=school,
            access_logs__timestamp__range=(
                date_filter["start"],
                date_filter["end"],
            ),
        )
        .values("access_logs__accessed_by__user_type")
        .annotate(access_count=Count("access_logs"))
        .order_by("-access_count")
    )


def get_uploads_by_user(school, filters):
    """Get document uploads by user"""
    date_filter = get_date_filter(filters)
    return (
        Document.objects.filter(
            school=school,
            uploaded_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values(
            "uploaded_by__first_name",
            "uploaded_by__last_name",
            "uploaded_by__user_type",
        )
        .annotate(upload_count=Count("id"))
        .order_by("-upload_count")
    )


# ===== REPORT ANALYTICS HELPERS =====
def get_reports_generated(school, filters):
    """Get reports generated by type and class"""
    date_filter = get_date_filter(filters)
    return (
        GeneratedReport.objects.filter(
            school=school,
            generated_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("report_type__name", "related_class__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_most_accessed_reports(school, filters):
    """Get most accessed report types"""
    date_filter = get_date_filter(filters)
    return (
        ReportAccessLog.objects.filter(
            report__school=school,
            accessed_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("report__report_type__name")
        .annotate(access_count=Count("id"))
        .order_by("-access_count")
    )


def get_missing_reports(school, filters):
    """Get teachers with missing reports"""
    date_filter = get_date_filter(filters)
    current_term = get_current_term()

    # Get all teachers expected to submit reports
    teachers = Teacher.objects.filter(school=school)

    # Get teachers who have submitted reports this term
    reporters = (
        GeneratedReport.objects.filter(
            school=school,
            generated_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values_list("generated_by", flat=True)
        .distinct()
    )

    missing = teachers.exclude(user__id__in=reporters)

    return [
        {
            "teacher": f"{t.user.first_name} {t.user.last_name}",
            "expected_reports": (
                t.assigned_class.count() if hasattr(t, "assigned_class") else 0
            ),
        }
        for t in missing
    ]


def get_top_students_from_reports(school, filters):
    """Get top performing students highlighted in reports"""
    date_filter = get_date_filter(filters)
    return (
        GeneratedReport.objects.filter(
            school=school,
            generated_at__range=(date_filter["start"], date_filter["end"]),
            data__top_students__isnull=False,
        )
        .annotate(
            top_student_name=Func(
                F("data__top_students__0__name"),
                function="jsonb_array_elements_text",
            ),
            top_student_score=Func(
                F("data__top_students__0__score"),
                function="jsonb_array_elements_text",
            ),
        )
        .values("top_student_name", "top_student_score")
        .order_by("-top_student_score")
    )


def get_parent_report_views(school, filters):
    """Get parent report view/download rates"""
    date_filter = get_date_filter(filters)
    return (
        ReportAccessLog.objects.filter(
            report__school=school,
            accessed_at__range=(date_filter["start"], date_filter["end"]),
            accessed_by__user_type="parent",
        )
        .values("action")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


# ===== PARENT ANALYTICS HELPERS =====
def get_most_engaged_parents(school, filters):
    """Get most engaged parents by activity"""
    date_filter = get_date_filter(filters)
    return (
        Parent.objects.filter(
            school=school,
            user__last_login__range=(date_filter["start"], date_filter["end"]),
        )
        .annotate(
            activity_score=Count("user__login_history")
            + Count("notifications", filter=Q(notifications__is_read=True))
            + Count(
                "children__academic_records",
                filter=Q(children__academic_records__is_published=True),
            )
        )
        .order_by("-activity_score")
        .values("user__first_name", "user__last_name", "activity_score")[:10]
    )


def get_students_per_parent(school):
    """Get distribution of number of students per parent"""
    return (
        Parent.objects.filter(school=school)
        .annotate(child_count=Count("children"))
        .values("child_count")
        .annotate(parent_count=Count("id"))
        .order_by("child_count")
    )


def get_parent_feedback(school, filters):
    """Get parent feedback statistics"""
    date_filter = get_date_filter(filters)
    return (
        ParentNotification.objects.filter(
            parent__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
            notification_type="FEEDBACK",
        )
        .values("sent_by__first_name", "sent_by__last_name")
        .annotate(
            feedback_count=Count("id"),
            avg_sentiment=Avg(
                Case(
                    When(message__icontains="happy", then=1),
                    When(message__icontains="sad", then=-1),
                    default=0,
                    output_field=models.FloatField(),
                )
            ),
        )
        .order_by("-feedback_count")
    )


def get_parent_login_trends(school, filters):
    """Get parent login trends"""
    date_filter = get_date_filter(filters)
    return (
        Parent.objects.filter(
            school=school,
            user__last_login__range=(date_filter["start"], date_filter["end"]),
        )
        .extra({"login_date": "date(user__last_login)"})
        .values("login_date")
        .annotate(login_count=Count("id"))
        .order_by("login_date")
    )


# ===== NOTIFICATION ANALYTICS HELPERS =====
def get_notification_open_rates(school, filters):
    """Get notification open rates by type"""
    date_filter = get_date_filter(filters)
    return (
        ParentNotification.objects.filter(
            parent__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("notification_type")
        .annotate(
            total=Count("id"),
            read=Count("id", filter=Q(is_read=True)),
            open_rate=ExpressionWrapper(
                Count("id", filter=Q(is_read=True)) * 100.0 / Count("id"),
                output_field=models.FloatField(),
            ),
        )
        .order_by("-open_rate")
    )


def get_message_types(school, filters):
    """Get distribution of message types"""
    date_filter = get_date_filter(filters)
    return (
        ParentNotification.objects.filter(
            parent__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        )
        .values("notification_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_click_through_rates(school, filters):
    """Get notification click-through rates"""
    date_filter = get_date_filter(filters)
    return (
        ParentNotification.objects.filter(
            parent__school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
            notification_type__in=["REPORT", "EVENT"],
        )
        .annotate(
            has_action=Case(
                When(message__icontains="action=", then=1),
                default=0,
                output_field=models.IntegerField(),
            )
        )
        .values("notification_type")
        .annotate(
            ctr=ExpressionWrapper(
                Sum("has_action") * 100.0 / Count("id"),
                output_field=models.FloatField(),
            )
        )
        .order_by("-ctr")
    )


def get_unread_notifications(school):
    """Get count of unread notifications"""
    return (
        ParentNotification.objects.filter(parent__school=school, is_read=False)
        .values("notification_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


# ===== SCHOOL-WIDE ANALYTICS HELPERS =====
def get_active_users(school, filters):
    """Get count of active users by type"""
    date_filter = get_date_filter(filters)
    return (
        User.objects.filter(
            school=school,
            last_login__range=(date_filter["start"], date_filter["end"]),
        )
        .values("user_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_engagement_rates(school, filters):
    """Get engagement rates (logins over time)"""
    date_filter = get_date_filter(filters)
    return (
        User.objects.filter(
            school=school,
            last_login__range=(date_filter["start"], date_filter["end"]),
        )
        .extra({"login_week": "date_trunc('week', last_login)"})
        .values("login_week", "user_type")
        .annotate(login_count=Count("id"))
        .order_by("login_week", "user_type")
    )


def get_report_generation_stats(school, filters):
    """Get report generation rate vs deadlines"""
    date_filter = get_date_filter(filters)
    return (
        GeneratedReport.objects.filter(
            school=school,
            generated_at__range=(date_filter["start"], date_filter["end"]),
        )
        .annotate(
            on_time=Case(
                When(generated_at__lte=F("valid_until"), then=1),
                default=0,
                output_field=models.IntegerField(),
            )
        )
        .values("report_type__name")
        .annotate(
            total=Count("id"),
            on_time_count=Sum("on_time"),
            on_time_rate=ExpressionWrapper(
                Sum("on_time") * 100.0 / Count("id"),
                output_field=models.FloatField(),
            ),
        )
        .order_by("-on_time_rate")
    )


def get_school_growth(school, filters):
    """Get school growth metrics (new users, classes)"""
    date_filter = get_date_filter(filters)
    return {
        "new_students": Student.objects.filter(
            school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        ).count(),
        "new_teachers": Teacher.objects.filter(
            school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        ).count(),
        "new_parents": Parent.objects.filter(
            school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        ).count(),
        "new_classes": SchoolClass.objects.filter(
            school=school,
            created_at__range=(date_filter["start"], date_filter["end"]),
        ).count(),
    }


# ===== COMMON HELPER METHODS =====
def get_date_filter(filters):
    """Convert date filters to actual dates"""
    if "date_range" in filters:
        if filters["date_range"] == "daily":
            return {
                "start": timezone.now() - timedelta(days=1),
                "end": timezone.now(),
            }
        elif filters["date_range"] == "weekly":
            return {
                "start": timezone.now() - timedelta(days=7),
                "end": timezone.now(),
            }
        elif filters["date_range"] == "monthly":
            return {
                "start": timezone.now() - timedelta(days=30),
                "end": timezone.now(),
            }
        elif filters["date_range"] == "termly":
            term = get_current_term()
            return {"start": term["start_date"], "end": term["end_date"]}

    return {
        "start": filters.get("start_date", timezone.now() - timedelta(days=30)),
        "end": filters.get("end_date", timezone.now()),
    }


def get_class_filter(filters):
    """Get class filter if specified"""
    if "class_id" in filters:
        return {"student__school_class__id": filters["class_id"]}
    return {}


def get_current_term():
    """Helper to get current term dates"""
    now = timezone.now()
    if now.month in [1, 2, 3, 4]:
        return {
            "name": "Term 1",
            "start_date": timezone.datetime(now.year, 1, 1).date(),
            "end_date": timezone.datetime(now.year, 4, 30).date(),
        }
    elif now.month in [5, 6, 7, 8]:
        return {
            "name": "Term 2",
            "start_date": timezone.datetime(now.year, 5, 1).date(),
            "end_date": timezone.datetime(now.year, 8, 31).date(),
        }
    else:
        return {
            "name": "Term 3",
            "start_date": timezone.datetime(now.year, 9, 1).date(),
            "end_date": timezone.datetime(now.year, 12, 31).date(),
        }
