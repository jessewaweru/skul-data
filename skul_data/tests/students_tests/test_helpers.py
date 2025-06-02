# students/tests/test_helpers.py
import random
from datetime import date
from django.utils import timezone
from django.contrib.auth import get_user_model
from skul_data.users.models.role import Permission
from skul_data.students.models.student import Student, Subject
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.role import Role
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.users.models.school_admin import SchoolAdmin


User = get_user_model()


def create_school_admin_role(school):
    """Create a role with ALL permissions for testing"""
    admin_role = Role.objects.create(
        name="Super Admin", school=school, role_type="SYSTEM"
    )

    # Add all required permissions
    permissions = [
        ("view_classes", "View classes"),
        ("manage_classes", "Manage classes"),
        ("view_class_timetables", "View class timetables"),
        ("manage_class_timetables", "Manage class timetables"),
        ("view_attendance", "View attendance"),
        ("manage_attendance", "Manage attendance"),
        ("manage_students", "Manage students"),
        ("view_students", "View students"),
    ]

    for code, name in permissions:
        perm, _ = Permission.objects.get_or_create(code=code, name=name)
        admin_role.permissions.add(perm)

    return admin_role


def create_test_school(name="Test School"):
    # Generate unique username based on school name
    username = f"admin_{name.lower().replace(' ', '_')}"
    admin_user = User.objects.create_user(
        email=f"admin@{name.replace(' ', '').lower()}.com",
        username=username,
        password="testpass",
        user_type=User.SCHOOL_ADMIN,
        is_staff=True,
    )

    # Generate a unique code based on the school name with random suffix
    random_suffix = random.randint(1000, 9999)
    unique_code = f"{name.replace(' ', '')[0:3].upper()}{random_suffix}"

    school = School.objects.create(
        name=name,
        email=f"contact@{name.replace(' ', '').lower()}.com",
        schooladmin=admin_user,
        code=unique_code,
    )

    SchoolAdmin.objects.create(user=admin_user, school=school, is_primary=True)

    # Assign full permissions
    admin_role = create_school_admin_role(school)
    admin_user.role = admin_role
    admin_user.save()

    return school, admin_user


def create_test_student(school, first_name="John", last_name="Doe", **kwargs):
    """
    Creates a student with all required fields
    Returns student instance
    """
    today = timezone.now().date()
    birth_date = date(today.year - 10, today.month, today.day)

    defaults = {
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": birth_date,  # Exactly 10 years old today
        "admission_date": today,
        "admission_number": f"STU{random.randint(1000,9999)}",
        "gender": "M",
        "school": school,
        "status": "ACTIVE",
    }
    if "student_class" not in kwargs:
        kwargs["student_class"] = create_test_class(school)
    defaults.update(kwargs)
    return Student.objects.create(**defaults)


def create_test_teacher(school, email="teacher@test.com"):
    user = User.objects.create_user(
        email=email, password="testpass", user_type=User.TEACHER
    )
    teacher = Teacher.objects.create(user=user, school=school)

    # Get or create the role to avoid duplicates
    role, created = Role.objects.get_or_create(
        name=f"Class Teacher-{school.id}",  # Make unique per school
        school=school,
        defaults={
            "role_type": "CUSTOM",
        },
    )

    if created:
        # Add teacher-specific permissions only if newly created
        teacher_permissions = [
            ("view_classes", "View classes"),
            ("view_class_timetables", "View class timetables"),
            ("manage_attendance", "Manage attendance"),
            ("view_students", "View students"),
        ]

        for code, name in teacher_permissions:
            perm, _ = Permission.objects.get_or_create(code=code, name=name)
            role.permissions.add(perm)

    user.role = role
    user.save()

    return teacher


def create_test_parent(school, email="parent@test.com"):
    """Creates a parent with all required fields"""
    user = User.objects.create_user(
        email=email, password="testpass", user_type=User.PARENT
    )
    return Parent.objects.create(
        user=user,
        school=school,
        phone_number="+1234567890",
        address="123 Test Street",
    )


def create_test_class(school, name=None, grade_level=None, **kwargs):
    """
    Create a test school class with unique name to avoid unique constraint violations
    """
    import random

    # Generate a unique name if not provided
    if name is None:
        random_suffix = random.randint(1000, 9999)
        name = f"Form 1-{random_suffix}"

    if grade_level is None:
        grade_level = name.split("-")[0].strip()  # Use the base part of the name

    defaults = {
        "name": name,
        "grade_level": grade_level,
        "school": school,
        "academic_year": "2023",
    }
    defaults.update(kwargs)

    # Try to get an existing class or create a new one
    from django.db import IntegrityError

    try:
        return SchoolClass.objects.create(**defaults)
    except IntegrityError:
        # Add random suffix to make the name unique if there's a conflict
        random_suffix = random.randint(1000, 9999)
        defaults["name"] = f"{name}-{random_suffix}"
        return SchoolClass.objects.create(**defaults)


def create_test_subject(school, name="Mathematics", code="MATH"):
    return Subject.objects.create(
        name=name,
        code=code,
        school=school,
    )


def get_last_action_log():
    """Helper to get the most recent action log"""
    from skul_data.action_logs.models.action_log import ActionLog

    # Add some debugging
    log = ActionLog.objects.last()
    if log is None:
        print("No action logs found in database")
        print(f"Total logs: {ActionLog.objects.count()}")
    else:
        print(
            f"Last log: user={log.user}, action={log.action}, content_object={log.content_object}"
        )

    return log


def assert_action_log_exists(**kwargs):
    """Assert that an action log exists with the given parameters"""
    from skul_data.action_logs.models.action_log import ActionLog

    logs = ActionLog.objects.filter(**kwargs)
    if not logs.exists():
        print(f"No logs found for: {kwargs}")
        print(
            f"Available logs: {list(ActionLog.objects.values('user', 'action', 'category'))}"
        )

    assert logs.exists(), f"No action log found matching: {kwargs}"
    return logs.first()
