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


@receiver(post_save, sender=AcademicRecord)
def check_low_performance(sender, instance, created, **kwargs):
    """Generate alerts for low academic performance"""
    if instance.score < 40:  # Failing grade
        AnalyticsAlert.objects.create(
            school=instance.student.school,
            alert_type="PERFORMANCE",
            title=f"Low Performance Alert: {instance.student.full_name}",
            message=f"Student {instance.student.full_name} scored {instance.score} in {instance.subject.name} which is below passing grade.",
            related_model="AcademicRecord",
            related_id=instance.id,
        )


@receiver(post_save, sender=TeacherAttendance)
def check_teacher_attendance(sender, instance, created, **kwargs):
    """Generate alerts for teacher attendance issues"""
    if instance.status == "ABSENT" and not instance.notes:
        AnalyticsAlert.objects.create(
            school=instance.teacher.school,
            alert_type="ATTENDANCE",
            title=f"Teacher Absent: {instance.teacher.full_name}",
            message=f"Teacher {instance.teacher.full_name} was absent on {instance.date} without notes.",
            related_model="TeacherAttendance",
            related_id=instance.id,
        )


@receiver(post_save, sender=AcademicRecord)
def check_consistently_low_performance(sender, instance, created, **kwargs):
    """Check for students with consistently low performance"""
    if instance.score < 40:  # Failing grade
        failing_count = AcademicRecord.objects.filter(
            student=instance.student, score__lt=40
        ).count()

        if failing_count >= 3:  # At least 3 failing grades
            AnalyticsAlert.objects.create(
                school=instance.student.school,
                alert_type="PERFORMANCE",
                title=f"Consistent Low Performance: {instance.student.full_name}",
                message=f"Student {instance.student.full_name} now has {failing_count} failing grades.",
                related_model="Student",
                related_id=instance.student.id,
            )


@receiver(post_save, sender=TeacherAttendance)
def check_frequent_absences(sender, instance, created, **kwargs):
    """Check for teachers with frequent absences"""
    if instance.status == "ABSENT":
        absent_count = TeacherAttendance.objects.filter(
            teacher=instance.teacher,
            status="ABSENT",
            date__gte=timezone.now() - timedelta(days=30),
        ).count()

        if absent_count >= 3:  # At least 3 absences in last month
            AnalyticsAlert.objects.create(
                school=instance.teacher.school,
                alert_type="ATTENDANCE",
                title=f"Frequent Absences: {instance.teacher.full_name}",
                message=f"Teacher {instance.teacher.full_name} has been absent {absent_count} times in the last month.",
                related_model="Teacher",
                related_id=instance.teacher.id,
            )


@receiver(post_save, sender=Document)
def check_large_document_uploads(sender, instance, created, **kwargs):
    """Alert for unusually large document uploads"""
    if created and instance.file_size > 5 * 1024 * 1024:  # 5MB
        AnalyticsAlert.objects.create(
            school=instance.school,
            alert_type="DOCUMENT",
            title=f"Large Document Uploaded: {instance.title}",
            message=f"A large document ({instance.file_size/1024/1024:.2f}MB) was uploaded by {instance.uploaded_by.get_full_name()}.",
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
    """Alert for classes with unusually low attendance"""
    if created:
        attendance_rate = instance.attendance_rate
        if attendance_rate < 70:  # Less than 70% attendance
            AnalyticsAlert.objects.create(
                school=instance.school_class.school,
                alert_type="ATTENDANCE",
                title=f"Low Class Attendance: {instance.school_class.name}",
                message=f"Class {instance.school_class.name} had only {attendance_rate:.1f}% attendance on {instance.date}.",
                related_model="ClassAttendance",
                related_id=instance.id,
            )


@receiver(pre_save, sender=Student)
def check_student_status_change(sender, instance, **kwargs):
    """Alert when student status changes significantly"""
    if instance.id:  # Only for existing students
        original = Student.objects.get(id=instance.id)
        if original.status != instance.status and instance.status in [
            "LEFT",
            "SUSPENDED",
        ]:
            AnalyticsAlert.objects.create(
                school=instance.school,
                alert_type="STUDENT",
                title=f"Student Status Changed: {instance.full_name}",
                message=f"Student {instance.full_name} status changed from {original.status} to {instance.status}.",
                related_model="Student",
                related_id=instance.id,
            )
