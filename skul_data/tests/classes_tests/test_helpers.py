from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.schools.models.school import School
from skul_data.students.models.student import Student
from django.utils import timezone
import random


def create_test_school(name="Test School", motto="Test Motto"):
    """
    Creates a school with all required relationships
    Returns (school, admin_user)
    """
    # Create admin user
    admin_user = User.objects.create_user(
        email=f"admin@{name.replace(' ', '').lower()}.com",
        password="testpass",
        user_type=User.SCHOOL_ADMIN,
    )

    # Create school with admin
    school = School.objects.create(
        name=name,
        motto=motto,
        email=f"contact@{name.replace(' ', '').lower()}.com",
        schooladmin=admin_user,
    )

    # Create school admin profile
    SchoolAdmin.objects.create(user=admin_user, school=school, is_primary=True)

    return school, admin_user


def create_test_student(school, first_name="John", last_name="Doe"):
    """
    Creates a student with all required fields
    Returns student instance
    """
    return Student.objects.create(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=timezone.now().date()
        - timezone.timedelta(days=365 * 10),  # 10 years old
        admission_date=timezone.now().date(),
        admission_number=f"STU{random.randint(1000,9999)}",
        gender="M",
        school=school,
        status="ACTIVE",
    )


def create_test_teacher(school, email="teacher@test.com"):
    """
    Creates a teacher with all required fields
    Returns teacher instance
    """
    user = User.objects.create_user(
        email=email, password="testpass", user_type=User.TEACHER
    )
    return Teacher.objects.create(user=user, school=school)
