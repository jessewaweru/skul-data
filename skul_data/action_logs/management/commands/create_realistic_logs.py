# skul_data/action_logs/management/commands/create_realistic_logs.py
from django.core.management.base import BaseCommand
from skul_data.users.models import User
from skul_data.students.models.student import Student
from skul_data.documents.models.document import Document
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from django.utils import timezone
from datetime import timedelta
import random


class Command(BaseCommand):
    help = "Creates realistic test action logs"

    def handle(self, *args, **kwargs):
        try:
            # Get users
            school_admin = User.objects.filter(user_type=User.SCHOOL_ADMIN).first()
            teachers = list(User.objects.filter(user_type=User.TEACHER)[:3])

            if not school_admin:
                self.stdout.write(self.style.ERROR("No school admin found"))
                return

            users_to_test = [school_admin] + teachers if teachers else [school_admin]

            # Get some actual objects from your database
            students = list(Student.objects.all()[:5])
            documents = (
                list(Document.objects.all()[:3]) if Document.objects.exists() else []
            )

            log_count = 0

            # Create varied logs
            for days_ago in range(30):
                timestamp = timezone.now() - timedelta(days=days_ago)
                user = random.choice(users_to_test)

                # Login logs
                if random.random() < 0.3:
                    log = log_action(
                        user=user,
                        action=f"{user.get_full_name()} logged in",
                        category=ActionCategory.LOGIN,
                        metadata={"ip_address": f"192.168.1.{random.randint(1, 255)}"},
                    )
                    if log:
                        log.timestamp = timestamp
                        log.save()
                        log_count += 1

                # Student operations
                if students and random.random() < 0.4:
                    student = random.choice(students)
                    operations = [
                        (
                            ActionCategory.VIEW,
                            f"Viewed student: {student.first_name} {student.last_name}",
                        ),
                        (
                            ActionCategory.UPDATE,
                            f"Updated student: {student.first_name} {student.last_name}",
                        ),
                    ]
                    category, action = random.choice(operations)
                    log = log_action(
                        user=user,
                        action=action,
                        category=category,
                        obj=student,
                        metadata={"student_id": str(student.id)},
                    )
                    if log:
                        log.timestamp = timestamp
                        log.save()
                        log_count += 1

                # Document operations
                if documents and random.random() < 0.3:
                    doc = random.choice(documents)
                    operations = [
                        (ActionCategory.VIEW, f"Viewed document: {doc.title}"),
                        (ActionCategory.DOWNLOAD, f"Downloaded document: {doc.title}"),
                    ]
                    category, action = random.choice(operations)
                    log = log_action(
                        user=user,
                        action=action,
                        category=category,
                        obj=doc,
                        metadata={"document_id": str(doc.id)},
                    )
                    if log:
                        log.timestamp = timestamp
                        log.save()
                        log_count += 1

            self.stdout.write(
                self.style.SUCCESS(f"Created {log_count} realistic test logs")
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback

            self.stdout.write(traceback.format_exc())
