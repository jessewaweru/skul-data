from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from skul_data.analytics.models.analytics import AnalyticsAlert
from skul_data.students.models.student import Student
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.users.models.teacher import TeacherAttendance
from skul_data.documents.models.document import Document
from skul_data.reports.models.report import GeneratedReport
from skul_data.schools.models.schoolclass import ClassAttendance


@receiver(post_save, sender=Student)
def check_student_status(sender, instance, created, **kwargs):
    """Generate alerts for student status changes"""
    if instance.status == "SUSPENDED":
        AnalyticsAlert.objects.create(
            school=instance.school,
            alert_type="ATTENDANCE",
            title=f"Student Suspended: {instance.full_name}",
            message=f"Student {instance.full_name} has been suspended.",
            related_model="Student",
            related_id=instance.id,
        )


# @receiver(post_save, sender=AcademicRecord)
# def check_low_performance(sender, instance, created, **kwargs):
#     """Generate alerts for low academic performance"""
#     if instance.score < 40:
#         # Ensure we have access to the related subject
#         if not instance.subject:
#             return

#         AnalyticsAlert.objects.create(
#             school=instance.student.school,
#             alert_type="PERFORMANCE",
#             title=f"Low Performance: {instance.student.full_name}",
#             message=f"{instance.student.full_name} scored {instance.score} in {instance.subject.name}",
#             related_model="AcademicRecord",
#             related_id=instance.id,
#         )


@receiver(post_save, sender=AcademicRecord)
def check_low_performance(sender, instance, created, **kwargs):
    """Alert for a single failing grade (score < 40)."""
    if instance.score < 40 and created:  # Only on creation (not updates)
        AnalyticsAlert.objects.update_or_create(
            school=instance.student.school,
            alert_type="PERFORMANCE_SINGLE",  # Different from task's "PERFORMANCE"
            related_model="AcademicRecord",  # Points to specific record
            related_id=instance.id,
            resolved_at__isnull=True,  # Only match unresolved alerts
            defaults={
                "title": f"Low Score: {instance.student.full_name} in {instance.subject.name}",
                "message": f"Scored {instance.score} (below passing grade)",
            },
        )


@receiver(post_save, sender=TeacherAttendance)
def check_teacher_attendance(sender, instance, created, **kwargs):
    """Generate alerts for teacher absences"""
    if instance.status == "ABSENT" and not instance.notes:
        # Check if alert already exists
        if not AnalyticsAlert.objects.filter(
            related_model="TeacherAttendance",
            related_id=instance.id,
            alert_type="ATTENDANCE",
        ).exists():
            AnalyticsAlert.objects.create(
                school=instance.teacher.school,
                alert_type="ATTENDANCE",
                title=f"Teacher Absence: {instance.teacher.full_name}",
                message=f"Absent on {instance.date} without notes",
                related_model="TeacherAttendance",
                related_id=instance.id,
            )


@receiver(post_save, sender=AcademicRecord)
def check_consistently_low_performance(sender, instance, created, **kwargs):
    """Check for consistent low performance"""
    if instance.score < 40 and instance.student:
        # Get count within the same academic year
        failing_count = AcademicRecord.objects.filter(
            student=instance.student, score__lt=40, school_year=instance.school_year
        ).count()

        if failing_count >= 3:
            AnalyticsAlert.objects.create(
                school=instance.student.school,
                alert_type="PERFORMANCE",
                title=f"Consistent Low Performance: {instance.student.full_name}",
                message=f"{instance.student.full_name} has {failing_count} failing grades",
                related_model="Student",
                related_id=instance.student.id,
            )


@receiver(post_save, sender=TeacherAttendance)
def check_frequent_absences(sender, instance, created, **kwargs):
    """Check for frequent absences"""
    if instance.status == "ABSENT" and created:
        # Calculate 30 days back from today
        thirty_days_ago = timezone.now().date() - timedelta(days=30)

        absent_count = TeacherAttendance.objects.filter(
            teacher=instance.teacher, status="ABSENT", date__gte=thirty_days_ago
        ).count()

        if absent_count >= 3:
            AnalyticsAlert.objects.update_or_create(
                title=f"Frequent Absences: {instance.teacher.full_name}",
                school=instance.teacher.school,
                defaults={
                    "alert_type": "ATTENDANCE",
                    "message": f"{absent_count} absences in last 30 days",
                    "related_model": "Teacher",
                    "related_id": instance.teacher.id,
                },
            )


@receiver(post_save, sender=Document)
def check_large_document_uploads(sender, instance, created, **kwargs):
    """Check for large document uploads"""
    if created:
        # Convert bytes to MB
        size_mb = instance.file_size / (1024 * 1024)
        if size_mb > 5:
            AnalyticsAlert.objects.create(
                school=instance.school,
                alert_type="DOCUMENT",
                title=f"Large Document: {instance.title}",
                message=f"Uploaded {size_mb:.1f}MB document",
                related_model="Document",
                related_id=instance.id,
            )


@receiver(post_save, sender=GeneratedReport)
def check_late_report_generation(sender, instance, created, **kwargs):
    """Alert for reports generated after their deadline"""
    if (
        created
        and instance.valid_until
        and instance.generated_at > instance.valid_until
    ):
        AnalyticsAlert.objects.create(
            school=instance.school,
            alert_type="REPORT",
            title=f"Late Report Generated: {instance.title}",
            message=f'Report "{instance.title}" was generated { (instance.generated_at - instance.valid_until).days } days after its deadline.',
            related_model="GeneratedReport",
            related_id=instance.id,
        )


@receiver(post_save, sender=ClassAttendance)
def check_low_class_attendance(sender, instance, created, **kwargs):
    if created:
        total = instance.school_class.students.count()
        present = instance.present_students.count()
        if total == 0:
            return

        attendance_rate = (present / total) * 100
        if attendance_rate < 70:
            AnalyticsAlert.objects.create(
                school=instance.school_class.school,
                alert_type="ATTENDANCE",
                title=f"Low Class Attendance: {instance.school_class.name}",  # Changed here
                message=f"{attendance_rate:.1f}% attendance on {instance.date}",
                related_model="ClassAttendance",
                related_id=instance.id,
            )


@receiver(pre_save, sender=Student)
def check_student_status_change(sender, instance, **kwargs):
    """Handle status changes"""
    if not instance.pk:
        return  # New student, no previous status

    try:
        original = Student.objects.get(pk=instance.pk)
    except Student.DoesNotExist:
        return

    if original.status != instance.status:
        if instance.status in ["SUSPENDED", "LEFT"]:
            AnalyticsAlert.objects.create(
                school=instance.school,
                alert_type="STUDENT",
                title=f"Status Change: {instance.full_name}",
                message=f"Changed from {original.status} to {instance.status}",
                related_model="Student",
                related_id=instance.id,
            )
