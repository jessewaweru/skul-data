# Run Celery Worker (for report tasks):
# celery -A skul_data.skul_data_main worker -l info -Q reports,celery -P gevent
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

logger = get_task_logger(__name__)


@shared_task(bind=True)
def generate_student_term_report_task(self, request_id):
    try:
        request = TermReportRequest.objects.get(id=request_id)
        generate_student_term_report(request)
    except Exception as e:
        logger.error(f"Failed to generate report for request {request_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task
def generate_class_term_reports_task(class_id, term, school_year, generated_by_id):
    try:
        generate_class_term_reports(class_id, term, school_year, generated_by_id)
    except Exception as e:
        logger.error(f"Failed to generate class reports: {str(e)}")
        raise


@shared_task
def process_pending_report_requests():
    """Process all pending report requests"""
    requests = TermReportRequest.objects.filter(status="PENDING")
    for request in requests:
        generate_student_term_report_task.delay(request.id)
    return f"Processed {len(requests)} pending requests"


@shared_task
def generate_term_end_reports():
    """Generate term-end reports for all schools with auto-generation enabled"""
    schools = School.objects.filter(
        academicreportconfig__auto_generate_term_reports=True
    )

    for school in schools:
        config = school.academicreportconfig
        term = SchoolEvent.get_current_term()
        school_year = SchoolEvent.get_current_school_year()

        generate_school_term_reports_task.delay(
            school.id, term, school_year, days_after=config.days_after_term_to_generate
        )

    return f"Initiated term-end reports for {len(schools)} schools"


@shared_task
def generate_school_term_reports_task(school_id, term, school_year, days_after=3):
    """Generate reports for all classes in a school after term ends"""
    from schools.models import SchoolClass

    # Calculate generation date
    generation_date = timezone.now() + timedelta(days=days_after)

    classes = SchoolClass.objects.filter(school_id=school_id)
    for school_class in classes:
        if school_class.teacher_assigned:
            generate_class_term_reports_task.apply_async(
                args=[
                    school_class.id,
                    term,
                    school_year,
                    school_class.teacher_assigned.user.id,
                ],
                eta=generation_date,
            )

    return f"Scheduled term reports for {len(classes)} classes in school {school_id}"
