import csv
import io
import decimal
from decimal import Decimal
from datetime import datetime
from celery import shared_task
from django.db import transaction
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML
from skul_data.fee_management.models.fee_management import (
    FeeUploadLog,
    FeeRecord,
    FeeStructure,
    FeeReminder,
    FeeInvoiceTemplate,
)
from skul_data.students.models.student import Student
from skul_data.users.models.parent import Parent
from skul_data.notifications.utils.notification import (
    send_parent_sms,
)
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory


@shared_task(bind=True)
def process_fee_upload(self, upload_log_id):
    """Process fee upload CSV file"""
    upload_log = FeeUploadLog.objects.get(id=upload_log_id)
    upload_log.status = "processing"
    upload_log.save()

    successful = 0
    failed = 0
    errors = []
    row_num = 0

    try:
        # Read the uploaded CSV file
        with upload_log.file.open("r") as csv_file:
            # Handle both file-like objects and string content
            if hasattr(csv_file, "read"):
                content = csv_file.read()
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                csv_file = io.StringIO(content)

            reader = csv.DictReader(csv_file)

            with transaction.atomic():
                for row_num, row in enumerate(reader, start=1):
                    try:
                        # Validate required fields
                        required_fields = [
                            "Parent Name",
                            "Parent Email",
                            "Parent Phone",
                            "Student Name",
                            "Student Admission Number",
                            "Amount Due",
                            "Term",
                            "Year",
                            "Due Date (YYYY-MM-DD)",
                        ]

                        missing_fields = [
                            field
                            for field in required_fields
                            if field not in row or not row[field].strip()
                        ]
                        if missing_fields:
                            raise ValueError(
                                f"Missing required fields: {', '.join(missing_fields)}"
                            )

                        # Parse amount and date
                        try:
                            amount_due = Decimal(str(row["Amount Due"]).strip())
                            due_date = datetime.strptime(
                                row["Due Date (YYYY-MM-DD)"].strip(), "%Y-%m-%d"
                            ).date()
                        except (ValueError, decimal.InvalidOperation) as e:
                            raise ValueError(f"Invalid amount or date format: {e}")

                        # Get or create fee structure
                        fee_structure, created = FeeStructure.objects.get_or_create(
                            school=upload_log.school,
                            school_class=upload_log.school_class,
                            term=row["Term"].strip(),
                            year=row["Year"].strip(),
                            defaults={
                                "amount": amount_due,
                                "due_date": due_date,
                            },
                        )

                        if not created:
                            fee_structure.amount = amount_due
                            fee_structure.due_date = due_date
                            fee_structure.save()

                        # Find student by admission number
                        try:
                            student = Student.objects.get(
                                admission_number=row[
                                    "Student Admission Number"
                                ].strip(),
                                school=upload_log.school,
                            )
                        except Student.DoesNotExist:
                            raise ValueError(
                                f"Student with admission number '{row['Student Admission Number']}' not found"
                            )

                        # Find parent by email or phone
                        parent = Parent.objects.filter(
                            user__email=row["Parent Email"].strip(),
                            school=upload_log.school,
                        ).first()

                        if not parent:
                            parent = Parent.objects.filter(
                                phone_number=row["Parent Phone"].strip(),
                                school=upload_log.school,
                            ).first()

                        if not parent:
                            raise ValueError(
                                f"Parent with email '{row['Parent Email']}' or phone '{row['Parent Phone']}' not found"
                            )

                        # Create or update fee record
                        fee_record, created = FeeRecord.objects.get_or_create(
                            student=student,
                            fee_structure=fee_structure,
                            defaults={
                                "parent": parent,
                                "amount_owed": amount_due,
                                "due_date": due_date,
                                "amount_paid": Decimal("0.00"),
                                "balance": amount_due,
                            },
                        )

                        if not created:
                            fee_record.amount_owed = amount_due
                            fee_record.due_date = due_date
                            # Recalculate balance
                            fee_record.balance = (
                                fee_record.amount_owed - fee_record.amount_paid
                            )
                            fee_record.save()

                        successful += 1

                    except Exception as e:
                        failed += 1
                        errors.append(f"Row {row_num}: {str(e)}")

        # Update upload log with results
        upload_log.total_records = row_num
        upload_log.successful_records = successful
        upload_log.failed_records = failed
        upload_log.error_log = "\n".join(errors) if errors else None
        upload_log.status = "completed"
        upload_log.processed_at = timezone.now()
        upload_log.save()

    except Exception as e:
        upload_log.status = "failed"
        upload_log.error_log = str(e)
        upload_log.processed_at = timezone.now()
        upload_log.save()

        log_action(
            upload_log.uploaded_by,
            f"Failed processing fee upload {upload_log.id}: {str(e)}",
            ActionCategory.UPDATE,
            upload_log,
            {"error": str(e)},
        )
        raise

    # Log success
    log_action(
        upload_log.uploaded_by,
        f"Completed processing fee upload {upload_log.id}: {successful} success, {failed} failed",
        ActionCategory.UPDATE,
        upload_log,
        {"successful": successful, "failed": failed},
    )

    return {
        "upload_log_id": upload_log.id,
        "successful": successful,
        "failed": failed,
        "errors": errors,
    }


@shared_task(bind=True)
def send_fee_reminders(self, fee_record_ids, send_via, message, user_id):
    """Send fee reminders via email and/or SMS"""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    user = User.objects.get(id=user_id)
    fee_records = FeeRecord.objects.filter(id__in=fee_record_ids).select_related(
        "parent",
        "parent__user",
        "student",
        "fee_structure",
        "fee_structure__school_class",
    )

    successful = 0
    failed = 0
    errors = []

    for record in fee_records:
        try:
            parent = record.parent
            student = record.student
            fee_structure = record.fee_structure

            # Get term display value BEFORE template rendering
            term_display = fee_structure.get_term_display()

            context = {
                "parent": parent,
                "student": student,
                "fee_record": record,
                "fee_structure": fee_structure,
                "message": message,
                "school": parent.school,
                "term_display": term_display,  # Add pre-rendered term display
            }

            # Use the pre-rendered term in subject
            subject = f"Fee Reminder: {fee_structure.school_class} {term_display} {fee_structure.year}"

            email_sent = False
            sms_sent = False

            # Send via email if requested and parent has email
            if send_via in ["email", "both"] and parent.user.email:
                try:
                    # subject = f"Fee Reminder: {fee_structure.school_class} {fee_structure.get_term_display()} {fee_structure.year}"
                    subject = f"Fee Reminder: {fee_structure.school_class} {fee_structure.get_term_display} {fee_structure.year}"
                    email_message = render_to_string("fee_reminder_email.txt", context)

                    email = EmailMessage(
                        subject,
                        email_message,
                        None,  # Use DEFAULT_FROM_EMAIL
                        [parent.user.email],
                    )
                    email.send()
                    email_sent = True
                except Exception as e:
                    errors.append(f"Email failed for record {record.id}: {str(e)}")

            # Send via SMS if requested and parent has phone
            if send_via in ["sms", "both"] and parent.phone_number:
                try:
                    sms_message = render_to_string("fee_reminder_sms.txt", context)
                    send_parent_sms(parent, sms_message)
                    sms_sent = True
                except Exception as e:
                    errors.append(f"SMS failed for record {record.id}: {str(e)}")

            # Consider successful if at least one method worked or if only email was requested and sent
            success = False
            if send_via == "email" and email_sent:
                success = True
            elif send_via == "sms" and sms_sent:
                success = True
            elif send_via == "both" and (email_sent or sms_sent):
                success = True

            # Create reminder record
            FeeReminder.objects.create(
                fee_record=record,
                sent_via=send_via,
                message=message,
                sent_by=user,
                is_successful=success,
                error_message=(
                    None if success else "Failed to send via requested method(s)"
                ),
            )

            if success:
                successful += 1
            else:
                failed += 1

        except Exception as e:
            failed += 1
            errors.append(f"Record {record.id}: {str(e)}")

            # Create failed reminder record
            try:
                FeeReminder.objects.create(
                    fee_record=record,
                    sent_via=send_via,
                    message=message,
                    sent_by=user,
                    is_successful=False,
                    error_message=str(e),
                )
            except Exception:
                pass  # Don't fail the whole task if we can't create the reminder record

    # Log the action
    log_action(
        user,
        f"Completed sending fee reminders: {successful} success, {failed} failed",
        ActionCategory.UPDATE,
        None,
        {"successful": successful, "failed": failed, "errors": errors},
    )

    return {"successful": successful, "failed": failed, "errors": errors}


@shared_task
def check_overdue_fees():
    """Daily task to check for overdue fees and send reminders"""
    today = timezone.now().date()

    # Debug statements
    print(f"Querying records with due_date < {today}")
    print(
        f"Found records: {list(FeeRecord.objects.filter(due_date__lt=today).values_list('id', flat=True))}"
    )

    # Modified query to find records that SHOULD be overdue
    overdue_records = FeeRecord.objects.filter(
        due_date__lt=today,  # Past due date
        balance__gt=0,  # With outstanding balance
        payment_status__in=["unpaid", "partial"],  # Not fully paid
    ).select_related(
        "parent",
        "parent__user",
        "student",
        "fee_structure",
        "fee_structure__school_class",
        "fee_structure__school_class__school",
    )

    processed_count = 0

    for record in overdue_records:
        print(f"PROCESSING RECORD {record.id}")
        try:
            # Check if record needs to be updated
            needs_update = False

            # If payment status isn't overdue, update it
            if record.payment_status != "overdue":
                record.payment_status = "overdue"
                needs_update = True

            # If not marked overdue, update it (even if model auto-set it)
            if not record.is_overdue:
                record.is_overdue = True
                needs_update = True

            # Save only if changes were made
            if needs_update:
                print("Updating overdue status...")
                record.save()

            # Prepare context for templates
            context = {
                "parent": record.parent,
                "student": record.student,
                "fee_record": record,
                "fee_structure": record.fee_structure,
                "school": record.parent.school,
            }

            email_sent = False
            sms_sent = False

            # Send email if parent has email
            if record.parent.user.email:
                try:
                    subject = f"Overdue Fee Notice: {record.fee_structure.school_class} {record.fee_structure.get_term_display()} {record.fee_structure.year}"
                    email_message = render_to_string("fee_overdue_email.txt", context)

                    email = EmailMessage(
                        subject,
                        email_message,
                        None,  # Use DEFAULT_FROM_EMAIL
                        [record.parent.user.email],
                    )
                    email.send()
                    email_sent = True
                except Exception as e:
                    print(f"Email failed for record {record.id}: {str(e)}")

            # Send SMS if parent has phone number
            if record.parent.phone_number:
                try:
                    message = render_to_string("fee_overdue_reminder.txt", context)
                    send_parent_sms(record.parent, message)
                    sms_sent = True
                except Exception as e:
                    print(f"SMS failed for record {record.id}: {str(e)}")

            # Create reminder record
            FeeReminder.objects.create(
                fee_record=record,
                sent_via="both",
                message=render_to_string("fee_overdue_reminder.txt", context),
                sent_by=None,  # System-generated
                is_successful=email_sent or sms_sent,
                error_message=(
                    None
                    if (email_sent or sms_sent)
                    else "Failed to send via email or SMS"
                ),
            )

            processed_count += 1

        except Exception as e:
            print(f"Error processing record {record.id}: {str(e)}")
            # Log error but continue with other records
            try:
                FeeReminder.objects.create(
                    fee_record=record,
                    sent_via="both",
                    message="Failed to send overdue reminder",
                    sent_by=None,  # System-generated
                    is_successful=False,
                    error_message=str(e),
                )
            except Exception as e:
                print(f"Failed to create reminder for record {record.id}: {str(e)}")

    return {"overdue_records_processed": processed_count}


@shared_task
def generate_fee_invoices(fee_record_ids, user_id):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    user = User.objects.get(id=user_id)
    fee_records = FeeRecord.objects.filter(id__in=fee_record_ids).select_related(
        "parent",
        "parent__user",
        "student",
        "fee_structure",
        "fee_structure__school_class",
        "fee_structure__school_class__school",
    )

    successful = 0
    failed = 0
    errors = []

    for record in fee_records:
        try:
            school = record.fee_structure.school_class.school
            template = FeeInvoiceTemplate.objects.filter(
                school=school, is_active=True
            ).first()

            if not template:
                raise ValueError("No active invoice template found for school")

            context = {
                "school": school,
                "parent": record.parent,
                "student": record.student,
                "fee_record": record,
                "fee_structure": record.fee_structure,
                "header_html": template.header_html,
                "footer_html": template.footer_html,
                "date": timezone.now().strftime("%Y-%m-%d"),
            }

            # Render HTML
            html_string = render_to_string("fee_invoice_template.html", context)

            # Generate PDF
            pdf_file = HTML(string=html_string).write_pdf()

            # Create email with PDF attachment
            subject = f"Fee Invoice: {record.fee_structure.school_class} {record.fee_structure.get_term_display()} {record.fee_structure.year}"
            email_message = render_to_string("fee_invoice_email.txt", context)

            email = EmailMessage(
                subject,
                email_message,
                None,  # Use DEFAULT_FROM_EMAIL
                [record.parent.user.email],
            )

            # Attach PDF
            email.attach(
                f"fee_invoice_{record.student.admission_number}_{record.fee_structure.term}_{record.fee_structure.year}.pdf",
                pdf_file,
                "application/pdf",
            )

            email.send()
            successful += 1

        except Exception as e:
            failed += 1
            errors.append(f"Record {record.id}: {str(e)}")

    log_action(
        user,
        f"Generated fee invoices: {successful} success, {failed} failed",
        ActionCategory.CREATE,
        None,
        {"successful": successful, "failed": failed, "errors": errors},
    )

    return {"successful": successful, "failed": failed, "errors": errors}
