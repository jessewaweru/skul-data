from django.core.management.base import BaseCommand
from skul_data.users.models import User
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from django.utils import timezone
from datetime import timedelta
import random


class Command(BaseCommand):
    help = "Creates test action logs for development"

    def handle(self, *args, **kwargs):
        # Get a user to attribute actions to
        try:
            user = User.objects.filter(is_staff=True).first()
            if not user:
                self.stdout.write(self.style.ERROR("No staff user found"))
                return

            # Create various test logs
            actions = [
                (f"Created Teacher: Jane Doe", ActionCategory.CREATE),
                (f"Updated Student: John Smith", ActionCategory.UPDATE),
                (f"Deleted Document: Old Report", ActionCategory.DELETE),
                (f"Viewed Analytics Dashboard", ActionCategory.VIEW),
                (f"Downloaded Report: Term 1 Results", ActionCategory.DOWNLOAD),
                (f"Uploaded Document: Syllabus 2025", ActionCategory.UPLOAD),
                (f"User Login", ActionCategory.LOGIN),
                (f"User Logout", ActionCategory.LOGOUT),
            ]

            for i, (action, category) in enumerate(actions):
                # Create logs with varying timestamps
                timestamp = timezone.now() - timedelta(days=random.randint(0, 30))

                log = log_action(
                    user=user,
                    action=action,
                    category=category,
                    metadata={
                        "test_data": True,
                        "index": i,
                        "timestamp_offset": f"{random.randint(0, 30)} days ago",
                    },
                )

                # Manually set timestamp for variety
                if log:
                    log.timestamp = timestamp
                    log.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {len(actions)} test action logs"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
