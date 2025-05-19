import json
from datetime import datetime
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string
from weasyprint import HTML
import pandas as pd
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from skul_data.reports.models.report import (
    GeneratedReport,
    ReportAccessLog,
    ReportTemplate,
    ReportNotification,
    GeneratedReportAccess,
)
from rest_framework.exceptions import PermissionDenied
from skul_data.users.models.base_user import User
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.reports.models.academic_record import AcademicRecord, TeacherComment
from django.conf import settings


import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    @staticmethod
    def generate_pdf_report(template, data, title, user, school):
        """
        Generate a PDF report from a template and data
        Returns: GeneratedReport instance
        """
        # Render HTML template with data
        context = {
            "data": data,
            "title": title,
            "school": school,
            "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "generated_by": user.get_full_name() or user.username,
            "logo_url": school.logo.url if school.logo else None,
        }

        html_string = render_to_string(
            f"reports/{template.template_type.lower()}_template.html", context
        )

        # Convert to PDF
        html = HTML(string=html_string)
        pdf_bytes = html.write_pdf()

        # Create report instance
        report = GeneratedReport(
            title=title,
            report_type=template,
            school=school,
            generated_by=user,
            data=json.dumps(data),
            parameters={},
            file_format="PDF",
        )

        # Save PDF file
        filename = (
            f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        report.file.save(filename, ContentFile(pdf_bytes))
        report.save()

        return report

    @staticmethod
    def generate_excel_report(template, data, title, user, school):
        """
        Generate an Excel report from data
        Returns: GeneratedReport instance
        """
        # Flatten nested data if needed
        flat_data = ReportGenerator._flatten_report_data(data)

        # Create DataFrame
        df = pd.DataFrame(flat_data)

        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Report", index=False)
            workbook = writer.book
            worksheet = writer.sheets["Report"]

            # Add some basic formatting
            header_format = workbook.add_format(
                {
                    "bold": True,
                    "text_wrap": True,
                    "valign": "top",
                    "fg_color": "#5a1b5d",  # Your purple color
                    "font_color": "white",
                    "border": 1,
                }
            )

            # Write the column headers with the defined format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Auto-adjust columns' width
            for i, col in enumerate(df.columns):
                max_len = (
                    max(
                        (
                            df[col]
                            .astype(str)
                            .map(len)
                            .max(),  # Length of largest item
                            len(col),  # Length of column header/name
                        )
                    )
                    + 1
                )  # Adding a little extra space
                worksheet.set_column(i, i, max_len)

        excel_data = output.getvalue()

        # Create report instance
        report = GeneratedReport(
            title=title,
            report_type=template,
            school=school,
            generated_by=user,
            data=json.dumps(data),
            parameters={},
            file_format="EXCEL",
        )

        # Save Excel file
        filename = (
            f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        report.file.save(filename, ContentFile(excel_data))
        report.save()

        return report

    @staticmethod
    def _flatten_report_data(data):
        """
        Helper to flatten nested report data for Excel export
        """
        flat_data = []

        # Handle student report data structure
        if "student" in data and "records" in data:
            student_data = data["student"]
            for record in data["records"]:
                flat_record = {**student_data, **record}
                if "teacher_comments" in data:
                    flat_record["teacher_comments"] = data["teacher_comments"]
                if "class_average" in data:
                    flat_record["class_average"] = data["class_average"]
                flat_data.append(flat_record)

        return flat_data or data

    @staticmethod
    def log_report_access(report, user, action="VIEWED", request=None):
        """Log when a report is accessed"""
        ip_address = request.META.get("REMOTE_ADDR") if request else None
        user_agent = request.META.get("HTTP_USER_AGENT") if request else None

        ReportAccessLog.objects.create(
            report=report,
            accessed_by=user,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Update access record if this is a parent viewing
        if user.user_type == "parent":
            access_grant = GeneratedReportAccess.objects.filter(
                report=report, user=user
            ).first()
            if access_grant and not access_grant.accessed_at:
                access_grant.accessed_at = timezone.now()
                access_grant.save()


def generate_report_for_student(
    student, term, school_year, template, teacher_user, school, class_average
):
    """Generate a report for a single student"""
    try:
        # Get academic records with related data
        academic_records = AcademicRecord.objects.filter(
            student=student, term=term, school_year=school_year, is_published=True
        ).select_related("teacher", "subject")

        if not academic_records.exists():
            return None

        # Get teacher comments
        comments = TeacherComment.objects.filter(
            student=student, term=term, school_year=school_year, is_approved=True
        )

        # Prepare report data
        report_data = {
            # "student": {
            #     "full_name": student.full_name,
            #     "admission_number": student.admission_number,
            #     "class_name": student.student_class.name,
            # },
            "student": {
                "full_name": student.full_name,
                "admission_number": student.admission_number or "N/A",
                "class_name": (
                    student.student_class.name if student.student_class else "N/A"
                ),
            },
            "term": term,
            "school_year": school_year,
            "records": [
                {
                    "subject": record.subject.name,
                    "score": float(record.score),
                    "grade": record.grade,
                    "comments": record.subject_comments,
                    # "teacher": record.teacher.user.full_name if record.teacher else "",
                    "teacher": (
                        record.teacher.user.get_full_name() if record.teacher else ""
                    ),
                }
                for record in academic_records
            ],
            "teacher_comments": [
                {
                    "type": comment.get_comment_type_display(),
                    "content": comment.content,
                    # "teacher": comment.teacher.user.full_name,
                    "teacher": comment.teacher.user.get_full_name(),
                }
                for comment in comments
            ],
            "class_average": float(class_average) if class_average else None,
        }

        # Generate the report based on template preference
        title = f"{student.full_name} - {term} {school_year} Academic Report"

        if template.preferred_format == "PDF":
            return ReportGenerator.generate_pdf_report(
                template=template,
                data=report_data,
                title=title,
                user=teacher_user,
                school=school,
            )
        else:
            return ReportGenerator.generate_excel_report(
                template=template,
                data=report_data,
                title=title,
                user=teacher_user,
                school=school,
            )

    except Exception as e:
        logger.error(f"Failed to generate report for student {student.id}: {str(e)}")
        return None


def generate_student_term_report(request_instance):
    """
    Handle generation of a single student's term report using the core generator function.
    Updates the request instance and sends notification.
    """
    try:
        student = request_instance.student
        term = request_instance.term
        school_year = request_instance.school_year
        teacher_user = request_instance.requested_at
        school = student.school

        # Get template
        template = ReportTemplate.objects.get(template_type="ACADEMIC", school=school)

        # Get class average
        class_average = calculate_class_average(
            student.student_class, term, school_year
        )

        # Generate the report
        generated_report = generate_report_for_student(
            student=student,
            term=term,
            school_year=school_year,
            template=template,
            teacher_user=teacher_user,
            school=school,
            class_average=class_average,
        )

        if not generated_report:
            request_instance.status = "FAILED"
            request_instance.save()
            return

        # Update request instance
        request_instance.generated_report = generated_report
        request_instance.status = "COMPLETED"
        request_instance.completed_at = timezone.now()
        request_instance.save()

        # Notify the parent
        send_report_notification(student.parent.user, generated_report)

    except Exception as e:
        request_instance.status = "FAILED"
        request_instance.save()
        raise e


def generate_class_term_reports(class_id, term, school_year, generated_by_id):
    """Generate academic reports for all students in a class."""
    try:
        school_class = (
            SchoolClass.objects.select_related("school__academicreportconfig")
            .prefetch_related("students__guardians")
            .get(id=class_id)
        )

        teacher = (
            User.objects.select_related("teacher_profile")
            .get(id=generated_by_id)
            .teacher_profile
        )

        # if teacher.assigned_classes != school_class:
        if school_class not in teacher.assigned_classes.all():
            raise PermissionDenied(
                "You can only generate reports for your assigned class"
            )

        students = school_class.students.all()
        school = school_class.school

        try:
            template = ReportTemplate.objects.get(
                template_type="ACADEMIC", school=school
            )
        except ReportTemplate.DoesNotExist:
            raise ValueError(
                f"No academic report template found for school: {school.name}"
            )

        # Optimization: calculate once per class
        class_average = calculate_class_average(school_class, term, school_year)

        generated_reports = []
        skipped_students = []

        for student in students:
            report = generate_report_for_student(
                student=student,
                term=term,
                school_year=school_year,
                template=template,
                teacher_user=teacher.user,
                school=school,
                class_average=class_average,
            )

            if not report:
                skipped_students.append(student.full_name)
                continue

            generated_reports.append(report)

            for parent in student.guardians.all():
                GeneratedReportAccess.objects.create(
                    report=report,
                    user=parent.user,
                    expires_at=timezone.now()
                    + timedelta(
                        days=school.academicreportconfig.parent_access_expiry_days
                    ),
                )
                send_report_notification(parent, report)

        return {
            "class": school_class.name,
            "term": term,
            "school_year": school_year,
            "total_students": students.count(),
            "reports_generated": len(generated_reports),
            "skipped_students": skipped_students,
            "successful_reports": generated_reports,
        }

    except SchoolClass.DoesNotExist:
        raise ValueError(f"Class with ID {class_id} does not exist")

    except User.DoesNotExist:
        raise ValueError(f"User with ID {generated_by_id} does not exist")


def calculate_class_average(school_class, term, school_year):
    """Calculate class average for a term"""
    from django.db.models import Avg

    average = AcademicRecord.objects.filter(
        student__student_class=school_class, term=term, school_year=school_year
    ).aggregate(average=Avg("score"))["average"]

    return round(average, 2) if average else None


def get_term_start_date(term, school_year):
    """Get start date for a term"""
    from skul_data.scheduler.models.scheduler import SchoolEvent

    try:
        calendar = SchoolEvent.objects.get(term=term, school_year=school_year)
        return calendar.start_date
    except SchoolEvent.DoesNotExist:
        # Fallback logic
        year = int(school_year.split("-")[0])
        if term == "Term 1":
            return datetime(year, 1, 10).date()
        elif term == "Term 2":
            return datetime(year, 5, 10).date()
        else:  # Term 3
            return datetime(year, 9, 10).date()


def get_term_end_date(term, school_year):
    """Get end date for a term"""
    from skul_data.scheduler.models.scheduler import SchoolEvent

    try:
        calendar = SchoolEvent.objects.get(term=term, school_year=school_year)
        return calendar.end_date
    except SchoolEvent.DoesNotExist:
        # Fallback logic
        year = int(school_year.split("-")[0])
        if term == "Term 1":
            return datetime(year, 4, 5).date()
        elif term == "Term 2":
            return datetime(year, 8, 5).date()
        else:  # Term 3
            return datetime(year, 12, 15).date()


def get_teacher_comments(student, term, school_year):
    """Get teacher comments for a student"""
    try:
        comment = TeacherComment.objects.get(
            student=student, term=term, school_year=school_year
        )
        return comment.comments
    except TeacherComment.DoesNotExist:
        return None


def send_report_notification(user, report):
    """Send notification about a generated report"""
    if user.email:
        send_report_email_notification(user, report)

    # Create in-app notification
    ReportNotification.objects.create(
        report=report,
        sent_to=user,
        method="BOTH" if user.email else "IN_APP",
        message=f"New academic report available: {report.title}",
        notification_type="REPORT_AVAILABLE",
    )


def send_report_email_notification(user, report):
    """Send email notification about a report"""
    try:
        access = GeneratedReportAccess.objects.get(report=report, user=user)

        subject = f"New Report Available: {report.title}"
        message = render_to_string(
            "reports/email/report_notification.txt",
            {
                "user": user,
                "report": report,
                "expiry_date": access.expires_at.strftime("%Y-%m-%d"),
                "school": report.school,
            },
        )

        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            reply_to=[report.school.contact_email],
        )

        # Attach the report if small enough
        if report.file.size < 5 * 1024 * 1024:  # 5MB
            email.attach_file(report.file.path)
        else:
            email.body += f"\n\nNote: The report is too large to attach. Please download it from the portal."

        email.send(fail_silently=False)

    except Exception as e:
        logger.error(f"Failed to send email notification to {user.email}: {str(e)}")
