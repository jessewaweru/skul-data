# skul_data/users/management/commands/create_school_account.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from skul_data.schools.models.school import School, SchoolSubscription
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.models.verification import AccountActivation
from django.core.mail import send_mail
from django.conf import settings
import sys

User = get_user_model()


class Command(BaseCommand):
    help = "Create a new school account with owner/admin"

    def add_arguments(self, parser):
        parser.add_argument(
            "--school-name", type=str, required=True, help="School name"
        )
        parser.add_argument("--email", type=str, required=True, help="Admin email")
        parser.add_argument(
            "--first-name", type=str, required=True, help="Admin first name"
        )
        parser.add_argument(
            "--last-name", type=str, required=True, help="Admin last name"
        )
        parser.add_argument(
            "--phone", type=str, required=False, help="Admin phone number"
        )
        parser.add_argument(
            "--school-type",
            type=str,
            default="PRI",
            choices=["PRE", "PRI", "SEC", "HS"],
            help="School type",
        )
        parser.add_argument(
            "--location", type=str, required=False, help="School location"
        )
        parser.add_argument("--city", type=str, required=False, help="School city")
        parser.add_argument(
            "--subscription-plan",
            type=str,
            default="BASIC",
            choices=["BASIC", "STANDARD", "ADVANCED"],
            help="Subscription plan",
        )
        parser.add_argument(
            "--send-email", action="store_true", help="Send activation email to admin"
        )

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                # Check if email already exists
                if User.objects.filter(email=options["email"]).exists():
                    self.stdout.write(
                        self.style.ERROR(
                            f'User with email {options["email"]} already exists!'
                        )
                    )
                    return

                # Check if school name already exists
                if School.objects.filter(name=options["school_name"]).exists():
                    self.stdout.write(
                        self.style.ERROR(
                            f'School with name {options["school_name"]} already exists!'
                        )
                    )
                    return

                # Generate username from email
                username = options["email"].split("@")[0]
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                # Create user (inactive until activated)
                self.stdout.write("Creating user account...")
                user = User.objects.create_user(
                    username=username,
                    email=options["email"],
                    first_name=options["first_name"],
                    last_name=options["last_name"],
                    user_type=User.SCHOOL_ADMIN,
                    is_active=False,  # Inactive until activation
                    is_staff=True,
                    email_verified=False,
                    password_change_required=True,
                    is_first_login=True,
                )

                # Add phone if provided
                if options.get("phone"):
                    user.phone_number = options["phone"]
                    user.save()

                # Create school
                self.stdout.write("Creating school...")
                school = School.objects.create(
                    name=options["school_name"],
                    type=options["school_type"],
                    email=options["email"],
                    location=options.get("location", ""),
                    city=options.get("city", ""),
                    phone=options.get("phone", ""),
                    schooladmin=user,
                )

                # Create SchoolAdmin profile
                self.stdout.write("Creating school admin profile...")
                SchoolAdmin.objects.create(user=user, school=school, is_primary=True)

                # Create subscription
                self.stdout.write("Creating subscription...")
                SchoolSubscription.objects.create(
                    school=school, plan=options["subscription_plan"], status="ACTIVE"
                )

                # Generate temporary password and create activation
                temp_password = AccountActivation.generate_temporary_password()
                user.set_password(temp_password)
                user.save()

                activation = AccountActivation.objects.create(
                    user=user,
                    temporary_password=temp_password,  # Store in plain text for email
                )

                # Success message
                self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
                self.stdout.write(
                    self.style.SUCCESS("School Account Created Successfully!")
                )
                self.stdout.write(self.style.SUCCESS("=" * 60))
                self.stdout.write(f"School Name: {school.name}")
                self.stdout.write(f"School Code: {school.code}")
                self.stdout.write(f"Admin Name: {user.get_full_name()}")
                self.stdout.write(f"Admin Email: {user.email}")
                self.stdout.write(f"Username: {user.username}")
                self.stdout.write(f"Temporary Password: {temp_password}")
                self.stdout.write(f"Subscription: {school.subscription.plan}")

                # Activation link
                activation_link = (
                    f"{settings.FRONTEND_URL}/activate-account/{activation.token}"
                )
                self.stdout.write(f"\nActivation Link: {activation_link}")

                # Send email if requested
                if options["send_email"]:
                    self.stdout.write("\nSending activation email...")
                    self.send_activation_email(user, temp_password, activation_link)
                    self.stdout.write(self.style.SUCCESS("Activation email sent!"))
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "\nPlease send the credentials to the school admin manually."
                        )
                    )

                self.stdout.write(self.style.SUCCESS("\n" + "=" * 60 + "\n"))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error creating school account: {str(e)}")
            )
            sys.exit(1)

    def send_activation_email(self, user, temp_password, activation_link):
        """Send activation email to new school admin"""
        subject = "Welcome to Skul Data - Activate Your Account"

        message = f"""
Dear {user.get_full_name()},

Welcome to Skul Data! Your school account has been created successfully.

LOGIN CREDENTIALS:
Username: {user.username}
Email: {user.email}
Temporary Password: {temp_password}

IMPORTANT: For security reasons, you'll be required to change your password when you first log in.

ACTIVATE YOUR ACCOUNT:
Click the link below to activate your account:
{activation_link}

This activation link will expire in 7 days.

GETTING STARTED:
1. Click the activation link above
2. Log in with your credentials
3. Set a new secure password
4. Complete your school profile
5. Start adding users and students

If you have any questions or need assistance, please contact our support team.

Best regards,
The Skul Data Team

---
This is an automated message. Please do not reply to this email.
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )


# Example usage in shell:
"""
python manage.py create_school_account \
    --school-name "Membley High School" \
    --email "admin@membley.ac.ke" \
    --first-name "John" \
    --last-name "Mwangi" \
    --phone "+254712345678" \
    --school-type "SEC" \
    --location "Kiambu Road" \
    --city "Nairobi" \
    --subscription-plan "STANDARD" \
    --send-email
"""
