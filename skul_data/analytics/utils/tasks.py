from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import datetime
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
from django.db.models.query import QuerySet


@shared_task
def cache_daily_analytics():
    """Task to pre-compute and cache daily analytics for all schools"""
    schools = School.objects.all()

    for school in schools:
        filters = {"date_range": "daily"}

        def serialize_data(data):
            if isinstance(data, QuerySet):
                return list(data.values())
            if isinstance(data, dict):
                return {k: serialize_data(v) for k, v in data.items()}
            if isinstance(data, (list, tuple)):
                return [serialize_data(item) for item in data]
            if isinstance(data, (datetime.date, datetime.datetime)):
                return data.isoformat()
            return data

        # Overview data
        overview_data = {
            "most_active_teacher": serialize_data(get_most_active_teacher(school)),
            "student_attendance_rate": get_student_attendance_rate(school),
            "most_downloaded_document": serialize_data(
                get_most_downloaded_document(school)
            ),
            "top_performing_class": serialize_data(get_top_performing_class(school)),
            "reports_generated": get_reports_generated_count(school),
        }

        # Teacher data
        teacher_data = {
            "total_teachers": Teacher.objects.filter(school=school).count(),
            "logins": serialize_data(get_teacher_logins(school, filters)),
            "reports_per_teacher": serialize_data(
                get_reports_per_teacher(school, filters)
            ),
            "attendance_accuracy": serialize_data(
                get_attendance_accuracy(school, filters)
            ),
        }

        # Student data
        student_data = {
            "total_students": Student.objects.filter(school=school).count(),
            "attendance": serialize_data(get_student_attendance(school, filters)),
            "performance": serialize_data(get_student_performance(school, filters)),
            "dropouts": serialize_data(get_student_dropouts(school, filters)),
        }

        # Class data
        class_data = {
            "class_sizes": serialize_data(get_class_sizes(school)),
            "average_grades": serialize_data(get_class_average_grades(school, filters)),
            "top_classes": serialize_data(get_top_classes(school, filters)),
        }

        # Create/update cached analytics
        for analytics_type, data in [
            ("overview", overview_data),
            ("teachers", teacher_data),
            ("students", student_data),
            ("classes", class_data),
        ]:
            # Ensure all data is fully serialized before storing
            serialized_data = serialize_data(data)

            CachedAnalytics.objects.update_or_create(
                school=school,
                analytics_type=analytics_type,
                defaults={
                    "data": serialized_data,
                    "valid_until": timezone.now() + timedelta(days=1),
                },
            )


@shared_task
def check_and_generate_alerts():
    """Task to check for conditions that should trigger alerts"""
    from skul_data.analytics.models.analytics import AnalyticsAlert
    from skul_data.users.models.teacher import TeacherAttendance
    from skul_data.reports.models.academic_record import AcademicRecord
    from skul_data.schools.models.schoolclass import ClassAttendance
    from django.db.models import Count, Max, Value, Q
    from django.db.models.functions import Concat

    print("DEBUG: Starting check_and_generate_alerts task")

    # 1. Students with 3+ failing grades
    print("DEBUG: Checking for students with low performance")
    low_performers = (
        AcademicRecord.objects.filter(score__lt=40)
        .values("student", "student__school")
        .annotate(
            low_count=Count("id"),
            student_name=Concat(
                "student__first_name", Value(" "), "student__last_name"
            ),
        )
        .filter(low_count__gte=3)
    )

    print(f"DEBUG: Found {low_performers.count()} students with low performance")
    for student in low_performers:
        if not AnalyticsAlert.objects.filter(
            school_id=student["student__school"],
            alert_type="PERFORMANCE",
            related_id=student["student"],
            resolved_at__isnull=True,
        ).exists():
            print(
                f"DEBUG: Creating low performance alert for student {student['student']}"
            )
            AnalyticsAlert.objects.create(
                school_id=student["student__school"],
                alert_type="PERFORMANCE",
                title=f"Consistent Low Performance: {student['student_name']}",
                message=f"Student {student['student_name']} has {student['low_count']} failing grades.",
                related_model="Student",
                related_id=student["student"],
            )

    # 2. Teacher absences without notes
    print("DEBUG: Checking for absences without notes")
    absences_without_notes = TeacherAttendance.objects.filter(status="ABSENT").filter(
        Q(notes__isnull=True) | Q(notes__exact="") | Q(notes__regex=r"^\s*$")
    )

    print(f"DEBUG: Found {absences_without_notes.count()} absences without notes")
    for absence in absences_without_notes:
        teacher_name = (
            f"{absence.teacher.user.first_name} {absence.teacher.user.last_name}"
        )
        print(f"DEBUG: Processing absence for teacher {teacher_name} on {absence.date}")
        if not AnalyticsAlert.objects.filter(
            school_id=absence.teacher.school.id,
            alert_type="ABSENCE_NO_NOTES",
            related_id=absence.teacher.id,
            message__contains=str(absence.date),
            resolved_at__isnull=True,
        ).exists():
            print(
                f"DEBUG: Creating absence without notes alert for teacher {absence.teacher.id}"
            )
            AnalyticsAlert.objects.create(
                school_id=absence.teacher.school.id,
                alert_type="ABSENCE_NO_NOTES",
                title=f"Absence without explanation: {teacher_name}",
                message=f"Teacher {teacher_name} was absent on {absence.date} with no explanation provided.",
                related_model="Teacher",
                related_id=absence.teacher.id,
            )

    # 3. Teachers with 3+ absences in the last 30 days
    print("DEBUG: Checking for frequent absences")
    frequent_absentees = (
        TeacherAttendance.objects.filter(
            status="ABSENT", date__gte=timezone.now() - timedelta(days=30)
        )
        .values("teacher", "teacher__school")
        .annotate(
            absent_count=Count("id"),
            teacher_name=Concat(
                "teacher__user__first_name", Value(" "), "teacher__user__last_name"
            ),
        )
        .filter(absent_count__gte=3)
    )

    print(f"DEBUG: Found {frequent_absentees.count()} teachers with frequent absences")
    for teacher in frequent_absentees:
        if not AnalyticsAlert.objects.filter(
            school_id=teacher["teacher__school"],
            alert_type="ATTENDANCE",
            related_id=teacher["teacher"],
            resolved_at__isnull=True,
        ).exists():
            print(
                f"DEBUG: Creating frequent absence alert for teacher {teacher['teacher']}"
            )
            AnalyticsAlert.objects.create(
                school_id=teacher["teacher__school"],
                alert_type="ATTENDANCE",
                title=f"Frequent Absences: {teacher['teacher_name']}",
                message=f"Teacher {teacher['teacher_name']} has been absent {teacher['absent_count']} times in the last month.",
                related_model="Teacher",
                related_id=teacher["teacher"],
            )

    # 4. Classes with low attendance (<70%)
    print("DEBUG: Checking for classes with low attendance")
    class_attendances = ClassAttendance.objects.all()
    for attendance in class_attendances:
        present_count = attendance.present_students.count()
        if attendance.total_students <= 1:
            continue

        attendance_rate = (present_count / attendance.total_students) * 100
        print(
            f"DEBUG: Class {attendance.school_class.id} attendance: {attendance_rate:.1f}%"
        )

        if attendance_rate < 70:
            if not AnalyticsAlert.objects.filter(
                school_id=attendance.school_class.school.id,
                alert_type="ATTENDANCE",
                related_id=attendance.school_class.id,
                related_model="schoolclass",
                resolved_at__isnull=True,
            ).exists():
                print(
                    f"DEBUG: Creating low attendance alert for class {attendance.school_class.id}"
                )
                AnalyticsAlert.objects.create(
                    school_id=attendance.school_class.school.id,
                    alert_type="ATTENDANCE",
                    title=f"Low class attendance: {attendance.school_class.name}",
                    message=f"Class {attendance.school_class.name} had only {attendance_rate:.1f}% attendance on {attendance.date}.",
                    related_model="schoolclass",
                    related_id=attendance.school_class.id,
                )

    print("DEBUG: Completed check_and_generate_alerts task")
    return True
