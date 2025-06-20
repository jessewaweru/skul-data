from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
import random
from django.utils import timezone
from django.contrib.auth import get_user_model
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.role import Role, Permission
from skul_data.users.models.school_admin import SchoolAdmin, AdministratorProfile
from skul_data.schools.models.school import School

User = get_user_model()


def create_test_teacher(school, email="teacher@test.com", **kwargs):
    """Helper to create a test teacher with all required fields"""
    if email is None:
        # Generate unique email and username
        random_suffix = random.randint(1000, 9999)
        email = f"teacher{random_suffix}@test.com"

    username = email.split("@")[0]

    user = User.objects.create_user(
        email=email,
        # username=email.split("@")[0],
        username=username,
        password="testpass",
        user_type=User.TEACHER,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Teacher"),
    )

    teacher = Teacher.objects.create(
        user=user,
        school=school,
        phone_number=kwargs.get("phone_number", "+254700000000"),
        status=kwargs.get("status", "ACTIVE"),
        hire_date=kwargs.get("hire_date", timezone.now().date()),
        qualification=kwargs.get("qualification", "B.Ed"),
        specialization=kwargs.get("specialization", "Mathematics"),
        years_of_experience=kwargs.get("years_of_experience", 5),
        is_class_teacher=kwargs.get("is_class_teacher", False),
        is_department_head=kwargs.get("is_department_head", False),
        payroll_number=kwargs.get("payroll_number", f"T{random.randint(1000,9999)}"),
    )

    # Assign subjects if provided
    if "subjects" in kwargs:
        teacher.subjects_taught.set(kwargs["subjects"])

    # Assign classes if provided
    if "classes" in kwargs:
        teacher.assigned_classes.set(kwargs["classes"])

    return teacher


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

    # Add specific teacher-related permissions
    teacher_perms = [
        ("manage_teacher_attendance", "Manage teacher attendance"),
        ("manage_teacher_documents", "Manage teacher documents"),
        ("manage_teacher_workload", "Manage teacher workload"),
    ]
    for code, name in teacher_perms:
        perm, _ = Permission.objects.get_or_create(code=code, name=name)
        admin_role.permissions.add(perm)

    return school, admin_user


def create_test_administrator(school, email="admin@test.com", **kwargs):
    """Helper to create a test administrator with all required fields"""
    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password="testpass",
        user_type=User.ADMINISTRATOR,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Admin"),
    )

    admin_profile = AdministratorProfile.objects.create(
        user=user,
        school=school,
        position=kwargs.get("position", "Administrator"),
        access_level=kwargs.get("access_level", "standard"),
        permissions_granted=kwargs.get("permissions_granted", []),
        is_active=kwargs.get("is_active", True),
    )

    return admin_profile


def create_administrator_role(school):
    """Create a role with administrator permissions for testing"""
    admin_role = Role.objects.create(
        name="Administrator Role", school=school, role_type="CUSTOM"
    )

    # Add administrator permissions
    permissions = [
        ("manage_users", "Manage users"),
        ("manage_teachers", "Manage teachers"),
        ("manage_students", "Manage students"),
        ("manage_parents", "Manage parents"),
        ("view_analytics", "View analytics"),
    ]

    for code, name in permissions:
        perm, _ = Permission.objects.get_or_create(code=code, name=name)
        admin_role.permissions.add(perm)

    return admin_role
