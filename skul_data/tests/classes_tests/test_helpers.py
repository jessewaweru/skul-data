from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.schools.models.school import School
from skul_data.students.models.student import Student
from django.utils import timezone
import random
from skul_data.users.models.role import Role, Permission
from skul_data.action_logs.models.action_log import ActionLog
from django.contrib.contenttypes.models import ContentType


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
        # Add other permissions as needed
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
        is_superuser=True,  # Temporary for testing
    )
    admin_user.save()  # Explicitly save first

    # Generate a unique code
    import random

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
    admin_user.save()  # Save again after role assignment

    return school, admin_user


def create_test_student(school, first_name=None, last_name=None):
    """
    Creates a student with all required fields
    Returns student instance
    """
    if first_name is None:
        first_name = f"Student{random.randint(1000,9999)}"
    if last_name is None:
        last_name = f"Doe{random.randint(1000,9999)}"

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
    user = User.objects.create_user(
        email=email, password="testpass", user_type=User.TEACHER
    )
    teacher = Teacher.objects.create(user=user, school=school)

    role, created = Role.objects.get_or_create(
        name="Class Teacher",
        school=school,
        defaults={"role_type": "CUSTOM"},
    )

    # FIXED: Add all necessary permissions for teachers
    teacher_permissions = [
        ("view_classes", "View classes"),
        ("view_class_timetables", "View class timetables"),
        ("manage_attendance", "Manage attendance"),
        ("view_attendance", "View attendance"),
        # ADD THESE MISSING PERMISSIONS:
        ("mark_attendance", "Mark attendance"),  # If this exists
        ("update_attendance", "Update attendance"),  # If this exists
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
    return Parent.objects.create(user=user, school=school)


def get_logs_for_instance(instance):
    """Helper to get all logs for a specific model instance"""
    content_type = ContentType.objects.get_for_model(instance)
    return ActionLog.objects.filter(
        content_type=content_type, object_id=instance.pk
    ).order_by("-timestamp")


def assert_log_exists(action, category, obj=None, user=None, metadata_contains=None):
    """Assert that a log entry exists with given parameters"""
    filters = {
        "action": action,
        "category": category,
    }

    if obj:
        content_type = ContentType.objects.get_for_model(obj)
        filters.update({"content_type": content_type, "object_id": obj.pk})

    if user:
        filters["user"] = user

    logs = ActionLog.objects.filter(**filters)

    if metadata_contains:
        from django.db.models import Q

        query = Q()
        for key, value in metadata_contains.items():
            query &= Q(**{f"metadata__{key}": value})
        logs = logs.filter(query)

    assert logs.exists(), f"No log found matching: {filters}"
