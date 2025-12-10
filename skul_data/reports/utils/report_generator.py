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
from django.db.models import Avg
from rest_framework.exceptions import PermissionDenied
from skul_data.users.models.base_user import User
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.reports.models.academic_record import AcademicRecord, TeacherComment
from django.conf import settings
from skul_data.action_logs.utils.action_log import log_action_async, log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.students.models.student import Student
from datetime import datetime, timedelta
import logging
import traceback

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
            **data,  # Spread all data
            "generated_date": datetime.now().strftime("%d/%m/%Y"),
        }

        html_string = render_to_string(
            f"reports/{template.template_type.lower()}_template.html", context
        )

        # Convert to PDF
        html = HTML(string=html_string, base_url=settings.MEDIA_ROOT)
        pdf_bytes = html.write_pdf()

        # Create report instance
        report = GeneratedReport(
            title=title,
            report_type=template,
            school=school,
            generated_by=user,
            data=json.dumps(data, default=str),
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


def get_previous_term(current_term):
    """Get the previous term name"""
    terms = ["Term 1", "Term 2", "Term 3"]
    try:
        idx = terms.index(current_term)
        if idx > 0:
            return terms[idx - 1]
    except ValueError:
        pass
    return None


def get_term_start_date(term, school_year):
    """Get start date for a term"""
    year = int(school_year.split("-")[0]) if "-" in school_year else int(school_year)

    if term == "Term 1":
        return datetime(year, 1, 10).date()
    elif term == "Term 2":
        return datetime(year, 5, 10).date()
    else:  # Term 3
        return datetime(year, 9, 10).date()


def get_term_end_date(term, school_year):
    """Get end date for a term"""
    year = int(school_year.split("-")[0]) if "-" in school_year else int(school_year)

    if term == "Term 1":
        return datetime(year, 4, 5).date()
    elif term == "Term 2":
        return datetime(year, 8, 5).date()
    else:  # Term 3
        return datetime(year, 12, 15).date()


def get_next_term_start_date(term, school_year):
    """Get start date for next term"""
    year = int(school_year.split("-")[0]) if "-" in school_year else int(school_year)

    if term == "Term 1":
        return datetime(year, 5, 10).date()
    elif term == "Term 2":
        return datetime(year, 9, 10).date()
    else:  # Term 3
        return datetime(year + 1, 1, 10).date()


def generate_report_for_student(
    student, term, school_year, template, teacher_user, school, class_average
):
    """Generate a comprehensive academic report for a single student"""
    try:
        # Get academic records with related data
        academic_records = (
            AcademicRecord.objects.filter(
                student=student, term=term, school_year=school_year, is_published=True
            )
            .select_related("teacher", "subject")
            .order_by("subject__name")
        )

        if not academic_records.exists():
            logger.warning(
                f"No published academic records found for student {student.id}"
            )
            return None

        # Calculate statistics
        total_marks = sum(float(record.score) for record in academic_records)
        max_marks = len(academic_records) * 100
        mean_mark = round(total_marks / len(academic_records), 2)

        # Calculate total points (A=12, A-=11, B+=10, etc.)
        grade_points = {
            "A": 12,
            "A-": 11,
            "B+": 10,
            "B": 9,
            "B-": 8,
            "C+": 7,
            "C": 6,
            "C-": 5,
            "D+": 4,
            "D": 3,
            "D-": 2,
            "E": 1,
            "F": 0,
        }
        total_points = sum(
            grade_points.get(record.grade, 0) for record in academic_records
        )
        max_points = len(academic_records) * 12

        # Calculate overall grade based on mean
        if mean_mark >= 80:
            overall_grade = "A"
        elif mean_mark >= 75:
            overall_grade = "A-"
        elif mean_mark >= 70:
            overall_grade = "B+"
        elif mean_mark >= 65:
            overall_grade = "B"
        elif mean_mark >= 60:
            overall_grade = "B-"
        elif mean_mark >= 55:
            overall_grade = "C+"
        elif mean_mark >= 50:
            overall_grade = "C"
        elif mean_mark >= 45:
            overall_grade = "C-"
        elif mean_mark >= 40:
            overall_grade = "D+"
        elif mean_mark >= 35:
            overall_grade = "D"
        elif mean_mark >= 30:
            overall_grade = "D-"
        else:
            overall_grade = "E"

        # Get teacher comments
        comments = TeacherComment.objects.filter(
            student=student, term=term, school_year=school_year, is_approved=True
        ).select_related("teacher__user")

        class_teacher_comment = ""
        head_comment = ""
        for comment in comments:
            if comment.comment_type == "GENERAL":
                class_teacher_comment = comment.content
            elif comment.comment_type == "RECOMMENDATION":
                head_comment = comment.content

        # Calculate rankings
        class_students = (
            student.student_class.students.all() if student.student_class else []
        )

        # Calculate stream position
        stream_rankings = []
        for s in class_students:
            s_records = AcademicRecord.objects.filter(
                student=s, term=term, school_year=school_year
            )
            if s_records.exists():
                s_mean = sum(float(r.score) for r in s_records) / len(s_records)
                stream_rankings.append((s.id, s_mean))

        stream_rankings.sort(key=lambda x: x[1], reverse=True)
        stream_position = next(
            (i + 1 for i, (sid, _) in enumerate(stream_rankings) if sid == student.id),
            0,
        )
        stream_total = len(stream_rankings)

        # Overall position (across all students in the year)
        all_students = Student.objects.filter(
            school=school, student_class__isnull=False
        )
        overall_rankings = []
        for s in all_students:
            s_records = AcademicRecord.objects.filter(
                student=s, term=term, school_year=school_year
            )
            if s_records.exists():
                s_mean = sum(float(r.score) for r in s_records) / len(s_records)
                overall_rankings.append((s.id, s_mean))

        overall_rankings.sort(key=lambda x: x[1], reverse=True)
        overall_position = next(
            (i + 1 for i, (sid, _) in enumerate(overall_rankings) if sid == student.id),
            0,
        )
        overall_total = len(overall_rankings)

        # Prepare records data with rankings, deviations, and trends
        records_data = []
        for record in academic_records:
            # Calculate subject-specific rankings
            subject_records = AcademicRecord.objects.filter(
                subject=record.subject,
                term=term,
                school_year=school_year,
                student__student_class=student.student_class,
            ).order_by("-score")

            subject_rank = (
                list(subject_records.values_list("student_id", flat=True)).index(
                    student.id
                )
                + 1
            )
            subject_total = subject_records.count()

            # Calculate deviation and class average for this subject
            subject_class_avg = (
                subject_records.aggregate(Avg("score"))["score__avg"] or 0
            )
            deviation = round(float(record.score) - float(subject_class_avg), 1)

            # Calculate trend (compare to previous term if available)
            trend = "stable"
            previous_term = get_previous_term(term)
            if previous_term:
                try:
                    prev_record = AcademicRecord.objects.get(
                        student=student,
                        subject=record.subject,
                        term=previous_term,
                        school_year=school_year,
                    )
                    if float(record.score) > float(prev_record.score) + 5:
                        trend = "up"
                    elif float(record.score) < float(prev_record.score) - 5:
                        trend = "down"
                except AcademicRecord.DoesNotExist:
                    trend = "stable"

            records_data.append(
                {
                    "subject": record.subject.name,
                    # Calculate component scores (20%, 20%, 60%)
                    "entry_exam": int(record.score * 0.20),  # 20% of total
                    "mid_term": int(record.score * 0.20),  # 20% of total
                    "end_term": int(record.score * 0.60),  # 60% of total
                    "score": int(record.score),
                    "grade": record.grade,
                    "deviation": deviation,
                    "rank": subject_rank,
                    "total_students": subject_total,
                    "comments": record.subject_comments or "Good progress",
                    "teacher": (
                        record.teacher.user.get_full_name() if record.teacher else "N/A"
                    ),
                    "class_avg": round(float(subject_class_avg), 1),
                    "trend": trend,
                }
            )

        # Get term dates
        term_end_date = get_term_end_date(term, school_year)
        next_term_start = get_next_term_start_date(term, school_year)

        # Get class teacher info
        class_teacher_name = ""
        class_teacher_signature = None
        if student.student_class and student.student_class.class_teacher:
            ct = student.student_class.class_teacher
            class_teacher_name = ct.user.get_full_name()
            if hasattr(ct, "signature") and ct.signature:
                class_teacher_signature = ct.signature.url

        # Get head of institution info
        head_name = ""
        head_signature = None
        # Try to get primary admin first
        if hasattr(school, "primary_admin") and school.primary_admin:
            head_name = (
                school.primary_admin.name
                if hasattr(school.primary_admin, "name")
                else f"{school.primary_admin.first_name} {school.primary_admin.last_name}"
            )
            # Check for signature in different possible locations
            if hasattr(school.primary_admin, "schooladmin") and hasattr(
                school.primary_admin.schooladmin, "signature"
            ):
                if school.primary_admin.schooladmin.signature:
                    head_signature = school.primary_admin.schooladmin.signature.url
            elif hasattr(school.primary_admin, "administratorprofile") and hasattr(
                school.primary_admin.administratorprofile, "signature"
            ):
                if school.primary_admin.administratorprofile.signature:
                    head_signature = (
                        school.primary_admin.administratorprofile.signature.url
                    )

        # Prepare report data
        report_data = {
            "school": {
                "name": school.name,
                "address": getattr(school, "address", ""),
                "po_box": getattr(school, "po_box", ""),
                "phone": getattr(school, "phone", "N/A"),
                "email": getattr(school, "email", "N/A"),
                "website": getattr(school, "website", ""),
                "logo": school.logo.url if school.logo else None,
            },
            "student": {
                "full_name": student.full_name,
                "admission_number": student.admission_number or "N/A",
                "class_name": (
                    student.student_class.name if student.student_class else "N/A"
                ),
                "gender": getattr(student, "gender", "N/A"),
                "upi": getattr(student, "upi", None),
                "kcpe_marks": getattr(student, "kcpe_marks", None),
                "vap": getattr(student, "vap", None),
                "photo": (
                    student.photo.url
                    if hasattr(student, "photo") and student.photo
                    else None
                ),
            },
            "term": term,
            "school_year": school_year,
            "records": records_data,
            "total_marks": int(total_marks),
            "max_marks": max_marks,
            "mean_mark": mean_mark,
            "total_points": total_points,
            "max_points": max_points,
            "overall_grade": overall_grade,
            "stream_position": stream_position,
            "stream_total": stream_total,
            "overall_position": overall_position,
            "overall_total": overall_total,
            "class_teacher_name": class_teacher_name,
            "class_teacher_comment": class_teacher_comment,
            "class_teacher_signature": class_teacher_signature,
            "head_name": head_name,
            "head_comment": head_comment,
            "head_signature": head_signature,
            "term_end_date": (
                term_end_date.strftime("%d/%m/%Y") if term_end_date else ""
            ),
            "next_term_start_date": (
                next_term_start.strftime("%d/%m/%Y") if next_term_start else ""
            ),
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
        logger.error(traceback.format_exc())
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
    """Generate academic reports for all students in a class using async logging."""
    try:
        # Get the user who initiated the generation
        from skul_data.users.models import User

        user = User.objects.get(id=generated_by_id)

        # Log bulk operation start - async
        log_action_async(
            user=user,
            action=f"Starting bulk report generation for class {class_id}",
            category="CREATE",
            metadata={
                "term": term,
                "school_year": school_year,
                "class_id": class_id,
                "initiated_at": timezone.now().isoformat(),
                "operation": "bulk_report_generation",
                "scope": "class_level",
            },
        )

        start_time = timezone.now()

        school_class = (
            SchoolClass.objects.select_related("school__academicreportconfig")
            .prefetch_related("students__guardians")
            .get(id=class_id)
        )

        teacher = user.teacher_profile

        if school_class not in teacher.assigned_classes.all():
            error_msg = "Permission denied: Not assigned to this class"
            log_action_async(
                user=user,
                action=error_msg,
                category="SYSTEM",
                metadata={
                    "attempted_class": class_id,
                    "teacher_classes": [c.id for c in teacher.assigned_classes.all()],
                    "severity": "high",
                },
            )
            raise PermissionDenied(error_msg)

        students = school_class.students.all()
        # Add safety check for empty class
        if students.count() == 0:
            error_msg = f"No students found in class {school_class.name}"
            log_action_async(
                user=user,
                action=error_msg,
                category="SYSTEM",
                metadata={
                    "class_id": class_id,
                    "class_name": school_class.name,
                    "severity": "medium",
                    "resolution": "Ensure students are assigned to the class",
                },
            )
            return {
                "class": school_class.name,
                "term": term,
                "school_year": school_year,
                "total_students": 0,
                "reports_generated": 0,
                "skipped_students": [],
                "successful_reports": [],
                "time_taken_seconds": 0,
                "average_time_per_report": 0,
                "error": "No students in class",
            }

        school = school_class.school

        try:
            template = ReportTemplate.objects.get(
                template_type="ACADEMIC", school=school
            )
            log_action_async(
                user=user,
                action=f"Using report template {template.name}",
                category="VIEW",
                obj=template,
                metadata={
                    "template_id": template.id,
                    "preferred_format": template.preferred_format,
                },
            )
        except ReportTemplate.DoesNotExist:
            error_msg = f"No academic report template found for school: {school.name}"
            log_action_async(
                user=user,
                action=error_msg,
                category="SYSTEM",
                metadata={
                    "school_id": school.id,
                    "template_type": "ACADEMIC",
                    "severity": "critical",
                },
            )
            raise ValueError(error_msg)

        # Calculate class average and log - async
        class_average = calculate_class_average(school_class, term, school_year)
        log_action_async(
            user=user,
            action=f"Calculated class average: {class_average}",
            category="SYSTEM",
            metadata={
                "class": school_class.name,
                "term": term,
                "school_year": school_year,
                "average_score": class_average,
                "calculation_time": timezone.now().isoformat(),
            },
        )

        generated_reports = []
        skipped_students = []

        for student in students:
            student_start_time = timezone.now()
            try:
                # Log individual student report start - async
                log_action_async(
                    user=user,
                    action=f"Generating report for {student.full_name}",
                    category="CREATE",
                    obj=student,
                    metadata={
                        "student_id": student.id,
                        "sequence_num": len(generated_reports) + 1,
                        "batch_size": students.count(),
                        "start_time": student_start_time.isoformat(),
                    },
                )

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
                    log_action_async(
                        user=user,
                        action=f"Skipped report for {student.full_name}",
                        category="SYSTEM",
                        obj=student,
                        metadata={
                            "reason": "No academic records found",
                            "processing_time": (
                                timezone.now() - student_start_time
                            ).total_seconds(),
                        },
                    )
                    continue

                generated_reports.append(report)
                report_duration = (timezone.now() - student_start_time).total_seconds()

                # Log successful generation - async
                log_action_async(
                    user=user,
                    action=f"Generated report for {student.full_name}",
                    category="CREATE",
                    obj=report,
                    metadata={
                        "report_id": report.id,
                        "format": report.file_format,
                        "processing_time": report_duration,
                        "file_size_bytes": report.file.size if report.file else None,
                        "student_sequence": f"{len(generated_reports)}/{students.count()}",
                    },
                )

                # Create access records for parents with async logging
                for parent in student.guardians.all():
                    access_expiry = timezone.now() + timedelta(
                        days=school.academicreportconfig.parent_access_expiry_days
                    )
                    access = GeneratedReportAccess.objects.create(
                        report=report,
                        user=parent.user,
                        expires_at=access_expiry,
                    )

                    log_action_async(
                        user=user,
                        action=f"Granted access to {parent.user.get_full_name()}",
                        category="SHARE",
                        obj=access,
                        metadata={
                            "expires_at": access_expiry.isoformat(),
                            "relationship": (
                                "Parent" if student.parent == parent else "Guardian"
                            ),
                            "access_duration_days": school.academicreportconfig.parent_access_expiry_days,
                        },
                    )

                    send_report_notification(parent, report)

            except Exception as e:
                error_duration = (timezone.now() - student_start_time).total_seconds()
                logger.error(
                    f"Failed to generate report for student {student.id}: {str(e)}"
                )
                skipped_students.append(student.full_name)
                log_action_async(
                    user=user,
                    action=f"Failed to generate report for {student.full_name}",
                    category="SYSTEM",
                    obj=student,
                    metadata={
                        "error": str(e),
                        "processing_time": error_duration,
                        "traceback": traceback.format_exc(),
                        "retry_possible": False,
                        "severity": "medium",
                    },
                )
                continue

        # Log bulk operation completion - async
        total_duration = (timezone.now() - start_time).total_seconds()
        success_rate = (
            (len(generated_reports) / students.count()) * 100
            if students.count() > 0
            else 0
        )
        log_action_async(
            user=user,
            action=f"Completed bulk report generation for {school_class.name}",
            category="SYSTEM",
            metadata={
                "class_id": class_id,
                "term": term,
                "school_year": school_year,
                "total_students": students.count(),
                "successful_reports": len(generated_reports),
                "skipped_students": len(skipped_students),
                # "success_rate": f"{(len(generated_reports)/students.count())*100:.1f}%",
                "success_rate": f"{success_rate:.1f}%",
                "total_time_seconds": total_duration,
                "avg_time_per_report": (
                    total_duration / len(generated_reports) if generated_reports else 0
                ),
                "completion_time": timezone.now().isoformat(),
                "performance": (
                    "good"
                    if (len(generated_reports) / students.count()) > 0.9
                    else (
                        "acceptable"
                        if (len(generated_reports) / students.count()) > 0.7
                        else "poor"
                    )
                ),
            },
        )

        return {
            "class": school_class.name,
            "term": term,
            "school_year": school_year,
            "total_students": students.count(),
            "reports_generated": len(generated_reports),
            "skipped_students": skipped_students,
            "successful_reports": [r.id for r in generated_reports],
            "time_taken_seconds": total_duration,
            "average_time_per_report": (
                total_duration / len(generated_reports) if generated_reports else 0
            ),
        }

    except SchoolClass.DoesNotExist as e:
        error_msg = f"Class {class_id} not found"
        log_action_async(
            user=user if "user" in locals() else None,
            action=error_msg,
            category="SYSTEM",
            metadata={
                "class_id": class_id,
                "error": str(e),
                "severity": "critical",
                "resolution": "Check class existence before operation",
            },
        )
        raise ValueError(error_msg)
    except User.DoesNotExist as e:
        error_msg = f"User {generated_by_id} not found"
        log_action_async(
            user=None,
            action=error_msg,
            category="SYSTEM",
            metadata={
                "user_id": generated_by_id,
                "error": str(e),
                "severity": "critical",
                "resolution": "Validate user before operation",
            },
        )
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Bulk report generation failed for class {class_id}"
        logger.error(f"{error_msg}: {str(e)}")
        log_action_async(
            user=user if "user" in locals() else None,
            action=error_msg,
            category="SYSTEM",
            metadata={
                "class_id": class_id,
                "term": term,
                "school_year": school_year,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "severity": "critical",
                "processing_time": (
                    (timezone.now() - start_time).total_seconds()
                    if "start_time" in locals()
                    else None
                ),
                "completed_reports": (
                    len(generated_reports) if "generated_reports" in locals() else 0
                ),
            },
        )
        raise


def calculate_class_average(school_class, term, school_year):
    """Calculate class average for a term"""
    from django.db.models import Avg

    average = AcademicRecord.objects.filter(
        student__student_class=school_class, term=term, school_year=school_year
    ).aggregate(average=Avg("score"))["average"]

    return round(average, 2) if average else None


def get_term_start_date(term, school_year):
    """Get start date for a term"""
    year = int(school_year.split("-")[0]) if "-" in school_year else int(school_year)

    if term == "Term 1":
        return datetime(year, 1, 10).date()
    elif term == "Term 2":
        return datetime(year, 5, 10).date()
    else:  # Term 3
        return datetime(year, 9, 10).date()


def get_term_end_date(term, school_year):
    """Get end date for a term"""
    # Since SchoolEvent doesn't have term/school_year fields,
    # use fallback logic directly
    year = int(school_year.split("-")[0]) if "-" in school_year else int(school_year)

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
    log_action(
        user=None,  # or the system user if you have one
        action=f"Shared report {report.title} with {user.email or user.username}",
        category=ActionCategory.SHARE,
        obj=report,
        metadata={"notification_method": "BOTH" if user.email else "IN_APP"},
    )
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
