from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.schools.models.school import School
from skul_data.students.models.student import Student
from django.utils import timezone
import random
from skul_data.users.models.role import Role, Permission


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

    # Generate a unique code based on the school name with random suffix
    import random

    random_suffix = random.randint(1000, 9999)
    unique_code = f"{name.replace(' ', '')[0:3].upper()}{random_suffix}"

    school = School.objects.create(
        name=name,
        email=f"contact@{name.replace(' ', '').lower()}.com",
        schooladmin=admin_user,
        code=unique_code,  # Add the unique code here
    )

    SchoolAdmin.objects.create(user=admin_user, school=school, is_primary=True)

    # Assign full permissions
    admin_role = create_school_admin_role(school)
    admin_user.role = admin_role
    admin_user.save()

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
    user = User.objects.create_user(
        email=email, password="testpass", user_type=User.TEACHER
    )
    teacher = Teacher.objects.create(user=user, school=school)

    # Create a role with teacher permissions
    role = Role.objects.create(
        name="Class Teacher",
        school=school,
        role_type="CUSTOM",
    )

    # Add teacher-specific permissions
    teacher_permissions = [
        ("view_classes", "View classes"),
        ("view_class_timetables", "View class timetables"),
        ("manage_attendance", "Manage attendance"),
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
