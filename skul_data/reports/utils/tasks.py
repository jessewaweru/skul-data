# Run Celery Worker (for report tasks):
# celery -A skul_data.skul_data_main worker -l info -Q reports,celery
# Run Celery Beat (for scheduled tasks):
# celery -A skul_data.skul_data_main beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# start redis server
# brew services start redis
# stop redis server
# brew services stop redis

# check to see if tasks are running properly with flower which opens a dashboard for monitoring celery tasks i.e.
# celery -A edoc flower
# it will open in your browser i.e. http://localhost:5555 by default.

# Test everything is working
# 1. Start Celery Worker
# celery -A skul_data.skul_data_main worker -l info -Q reports,celery -P gevent
# 2. Start Celery Beat
# celery -A skul_data.skul_data_main beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
# 3. Trigger a Task Manually
# In Django Shell (python manage.py shell) run the following below together:
# from reports.tasks import process_pending_report_requests
# result = process_pending_report_requests.delay()
# result.get()  # Wait for and get result

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta
from skul_data.reports.models.report import TermReportRequest
from skul_data.schools.models.school import School
from skul_data.scheduler.models.scheduler import SchoolEvent
from skul_data.reports.utils.report_generator import (
    generate_class_term_reports,
    generate_student_term_report,
)
from skul_data.action_logs.utils.action_log import log_action_async
import traceback

logger = get_task_logger(__name__)


@shared_task(bind=True)
def generate_student_term_report_task(self, request_id):
    """Generate a student term report from a request"""
    try:
        # Log task initiation - using async since we're in a Celery task
        log_action_async(
            user=None,
            action=f"Starting student term report generation for request {request_id}",
            category="SYSTEM",
            metadata={
                "task_id": self.request.id,
                "request_id": request_id,
                "task_name": "generate_student_term_report_task",
            },
        )

        request = TermReportRequest.objects.get(id=request_id)

        # Add context to the request object for logging
        request._current_user = None  # Mark as system-generated

        # Log before generation - using async
        log_action_async(
            user=None,
            action=f"Processing report request for student {request.student.full_name}",
            category="SYSTEM",
            obj=request,
            metadata={
                "term": request.term,
                "school_year": request.school_year,
                "status": request.status,
                "student_id": request.student.id,
            },
        )

        # Call the actual report generation function
        generate_student_term_report(request)

        # Update request status on success
        request.status = "COMPLETED"
        request.save()

        # Log successful completion - using async
        log_action_async(
            user=None,
            action=f"Successfully generated report for request {request_id}",
            category="SYSTEM",
            obj=request.generated_report,
            metadata={
                "report_id": (
                    request.generated_report.id if request.generated_report else None
                ),
                "time_taken": (
                    self.request.tasks[self.request.id].time_taken
                    if hasattr(self.request, "tasks")
                    else None
                ),
                "file_size": (
                    request.generated_report.file.size
                    if request.generated_report and request.generated_report.file
                    else None
                ),
            },
        )

        return {
            "status": "success",
            "request_id": request_id,
            "report_id": (
                request.generated_report.id if request.generated_report else None
            ),
        }

    except TermReportRequest.DoesNotExist:
        error_msg = f"TermReportRequest with id {request_id} does not exist"
        logger.error(error_msg)
        log_action_async(
            user=None,
            action=error_msg,
            category="SYSTEM",
            metadata={
                "task_id": self.request.id,
                "request_id": request_id,
                "error": "Request not found",
                "severity": "high",
            },
        )
        raise
    except Exception as e:
        error_msg = f"Failed to generate report for request {request_id}: {str(e)}"
        logger.error(error_msg)

        # Log the error with traceback - using async
        log_action_async(
            user=None,
            action=error_msg,
            category="SYSTEM",
            metadata={
                "task_id": self.request.id,
                "request_id": request_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "retry_count": self.request.retries,
            },
        )

        # Update request status on failure
        try:
            request = TermReportRequest.objects.get(id=request_id)
            request.status = "FAILED"
            request.save()

            # Log the failure status update - using async
            log_action_async(
                user=None,
                action=f"Marked request {request_id} as FAILED",
                category="SYSTEM",
                obj=request,
                metadata={"error": str(e), "final_status": "FAILED"},
            )
        except TermReportRequest.DoesNotExist:
            pass

        # Retry the task
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task
def generate_class_term_reports_task(class_id, term, school_year, generated_by_id):
    """Generate term reports for all students in a class"""
    try:
        # Call the actual report generation function with named arguments
        result = generate_class_term_reports(
            class_id=class_id,
            term=term,
            school_year=school_year,
            generated_by_id=generated_by_id,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate class reports: {str(e)}")
        raise


@shared_task
def process_pending_report_requests():
    """Process all pending report requests"""
    requests = TermReportRequest.objects.filter(status="PENDING")
    count = 0

    for request in requests:
        # Use .delay() to call the task asynchronously
        generate_student_term_report_task.delay(request.id)
        count += 1

    return f"Processed {count} pending requests"


@shared_task
def generate_term_end_reports():
    """Generate term-end reports for all schools with auto-generation enabled"""
    from skul_data.schools.utils.school import get_current_term

    schools = School.objects.filter(
        academicreportconfig__auto_generate_term_reports=True
    )

    count = 0
    for school in schools:
        try:
            config = school.academicreportconfig
            # Get current term for the school
            term = (
                get_current_term(school.id)
                if hasattr(get_current_term, "__call__")
                else None
            )
            # Get current school year
            school_year = SchoolEvent.get_current_school_year()

            # Schedule the school report generation task
            generate_school_term_reports_task.delay(
                school.id,
                term,
                school_year,
                days_after=config.days_after_term_to_generate,
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to initiate reports for school {school.id}: {str(e)}")

    return f"Initiated term-end reports for {count} schools"


@shared_task
def generate_school_term_reports_task(school_id, term, school_year, days_after=3):
    """Generate reports for all classes in a school after term ends"""
    from skul_data.schools.models.schoolclass import SchoolClass

    # Calculate generation date
    generation_date = timezone.now() + timedelta(days=days_after)

    # Get all classes for the school
    classes = SchoolClass.objects.filter(school_id=school_id)
    scheduled_count = 0

    for school_class in classes:
        # Check if class has an assigned teacher
        if school_class.class_teacher:
            # Schedule the class report generation task
            generate_class_term_reports_task.apply_async(
                args=[
                    school_class.id,
                    term,
                    school_year,
                    school_class.class_teacher.user.id,
                ],
                eta=generation_date,
            )
            scheduled_count += 1

    return f"Scheduled term reports for {scheduled_count} classes in school {school_id}"
