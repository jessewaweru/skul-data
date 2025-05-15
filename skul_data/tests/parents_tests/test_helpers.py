from django.contrib.auth import get_user_model
from django.utils import timezone
from skul_data.schools.models.school import School
from skul_data.students.models.student import Student
from skul_data.users.models.parent import Parent
from skul_data.users.models.role import Role, Permission
from skul_data.users.models.school_admin import SchoolAdmin
import uuid
import random

User = get_user_model()


# def create_test_school(name="Test School"):
#     # Generate unique username based on school name
#     username = f"admin_{name.lower().replace(' ', '_')}"
#     admin_user = User.objects.create_user(
#         email=f"admin@{name.replace(' ', '').lower()}.com",
#         username=username,
#         password="testpass",
#         user_type=User.SCHOOL_ADMIN,
#         is_staff=True,
#     )

#     # Generate a unique code based on the school name with random suffix
#     random_suffix = random.randint(1000, 9999)
#     unique_code = f"{name.replace(' ', '')[0:3].upper()}{random_suffix}"

#     school = School.objects.create(
#         name=name,
#         email=f"contact@{name.replace(' ', '').lower()}.com",
#         schooladmin=admin_user,
#         code=unique_code,
#     )

#     SchoolAdmin.objects.create(user=admin_user, school=school, is_primary=True)

#     return school, admin_user


def create_test_school(name="Test School"):
    # First create the admin user
    admin_user = User.objects.create_user(
        email=f"admin@{name.replace(' ', '').lower()}.com",
        username=f"admin_{name.lower().replace(' ', '_')}",
        password="testpass",
        user_type=User.SCHOOL_ADMIN,
        is_staff=True,
    )

    # Generate a unique code
    random_suffix = random.randint(1000, 9999)
    unique_code = f"{name.replace(' ', '')[0:3].upper()}{random_suffix}"

    # Create the school with the admin user
    school = School.objects.create(
        name=name,
        email=f"contact@{name.replace(' ', '').lower()}.com",
        code=unique_code,
        schooladmin=admin_user,  # Set the admin user directly
    )

    # Create the SchoolAdmin profile
    SchoolAdmin.objects.create(
        user=admin_user,
        school=school,
        is_primary=True,
    )

    return school, admin_user


# def create_test_parent(school, email="parent@test.com", **kwargs):
#     """Helper to create a test parent with all required fields"""
#     user = User.objects.create_user(
#         email=email,
#         username=email.split("@")[0],
#         password="testpass",
#         user_type=User.PARENT,
#         first_name=kwargs.get("first_name", "Test"),
#         last_name=kwargs.get("last_name", "Parent"),
#     )

#     parent = Parent.objects.create(
#         user=user,
#         school=school,
#         phone_number=kwargs.get("phone_number", "+254700000000"),
#         status=kwargs.get("status", "PENDING"),
#         address=kwargs.get("address", "123 Test Street"),
#         occupation=kwargs.get("occupation", "Test Occupation"),
#         preferred_language=kwargs.get("preferred_language", "en"),
#         receive_email_notifications=kwargs.get("receive_email_notifications", True),
#     )

#     # Assign children if provided
#     if "children" in kwargs:
#         parent.children.set(kwargs["children"])

#     return parent


def create_test_parent(school, email="parent@test.com", **kwargs):
    """Helper to create a test parent with all required fields"""
    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password="testpass",
        user_type=User.PARENT,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Parent"),
    )

    parent = Parent.objects.create(
        user=user,
        school=school,
        phone_number=kwargs.get("phone_number", "+254700000000"),
        status=kwargs.get("status", "PENDING"),
        address=kwargs.get("address", "123 Test Street"),
        occupation=kwargs.get("occupation", "Test Occupation"),
        # preferred_language=kwargs.get("preferred_language", "en"),
        # receive_email_notifications=kwargs.get("receive_email_notifications", True),
    )

    # Assign children if provided
    if "children" in kwargs:
        parent.children.set(kwargs["children"])

    return parent


# def create_test_student(school, first_name="Test", last_name="Student", **kwargs):
#     """Helper to create a test student"""
#     student = Student.objects.create(
#         first_name=first_name,
#         last_name=last_name,
#         date_of_birth=kwargs.get("date_of_birth", timezone.now().date()),
#         admission_date=kwargs.get("admission_date", timezone.now().date()),
#         gender=kwargs.get("gender", "M"),
#         status=kwargs.get("status", "ACTIVE"),
#         school=school,
#     )

#     if "parent" in kwargs:
#         student.parent = kwargs["parent"]
#         student.save()

#     if "guardians" in kwargs:
#         student.guardians.set(kwargs["guardians"])

#     return student


def create_test_student(school, first_name="Test", last_name="Student", **kwargs):
    """Helper to create a test student"""
    # Create student without parent first to avoid circular reference issues
    student = Student.objects.create(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=kwargs.get("date_of_birth", timezone.now().date()),
        admission_date=kwargs.get("admission_date", timezone.now().date()),
        gender=kwargs.get("gender", "M"),
        status=kwargs.get("status", "ACTIVE"),
        school=school,
    )

    # Set parent relationship separately if provided
    if "parent" in kwargs:
        # First set the foreign key
        student.parent = kwargs["parent"]
        student.save()

        # Then add to the many-to-many relationship
        kwargs["parent"].children.add(student)

    if "guardians" in kwargs:
        student.guardians.set(kwargs["guardians"])

    return student


# def create_test_role(school, name="Test Role", **kwargs):
#     """Helper to create a test role with permissions"""
#     if name is None:
#         name = f"Test Role {uuid.uuid4().hex[:8]}"

#     role = Role.objects.create(
#         name=name,
#         school=school,
#         role_type=kwargs.get("role_type", "CUSTOM"),
#         description=kwargs.get("description", "Test role"),
#     )

#     if "permissions" in kwargs:
#         for perm_code in kwargs["permissions"]:
#             perm, _ = Permission.objects.get_or_create(
#                 code=perm_code, defaults={"name": f"Can {perm_code.replace('_', ' ')}"}
#             )
#             role.permissions.add(perm)

#     return role


def create_test_role(school, name=None, **kwargs):
    """Helper to create a test role with permissions"""
    # Generate a unique role name if not provided
    if name is None:
        # Use the school ID to make the role name unique
        name = f"Test Role {school.id}_{random.randint(1000, 9999)}"

    role = Role.objects.create(
        name=name,
        school=school,
        role_type=kwargs.get("role_type", "CUSTOM"),
        description=kwargs.get("description", "Test role"),
    )

    if "permissions" in kwargs:
        for perm_code in kwargs["permissions"]:
            perm, _ = Permission.objects.get_or_create(
                code=perm_code, defaults={"name": f"Can {perm_code.replace('_', ' ')}"}
            )
            role.permissions.add(perm)

    return role
