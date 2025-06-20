from django.test import TestCase
from django.utils import timezone
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.tests.teachers_tests.test_helpers import create_test_school
from datetime import date


class TeacherAdministratorTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.user = User.objects.create_user(
            email="teacher@test.com",
            username="teacher",
            password="testpass",
            first_name="Test",
            last_name="Teacher",
            user_type=User.TEACHER,
        )
        self.teacher = Teacher.objects.create(
            user=self.user,
            school=self.school,
            phone_number="+254700000000",
            status="ACTIVE",
        )

    def test_teacher_as_administrator(self):
        # Test making a teacher an administrator
        self.teacher.is_administrator = True
        self.teacher.administrator_since = timezone.now().date()
        self.teacher.save()

        self.assertTrue(self.teacher.is_administrator)
        self.assertIsNotNone(self.teacher.administrator_since)

        # Test removing administrator status
        self.teacher.is_administrator = False
        self.teacher.administrator_until = timezone.now().date()
        self.teacher.save()

        self.assertFalse(self.teacher.is_administrator)
        self.assertIsNotNone(self.teacher.administrator_until)

    def test_teacher_administrator_serializer(self):
        self.teacher.is_administrator = True
        self.teacher.administrator_since = date.today()  # Explicit date object
        self.teacher.administrator_notes = "Test notes"
        self.teacher.save()

        # Force refresh from database to catch any datetime conversion
        self.teacher.refresh_from_db()

        from skul_data.users.serializers.teacher import TeacherSerializer

        print(f"Type before serialization: {type(self.teacher.administrator_since)}")
        print(f"Value before serialization: {self.teacher.administrator_since}")

        serializer = TeacherSerializer(self.teacher)
        data = serializer.data

        self.assertTrue(data["is_administrator"])
        self.assertEqual(data["administrator_notes"], "Test notes")

        # Check the date is properly formatted
        self.assertIsNotNone(data["administrator_since"])
        self.assertRegex(data["administrator_since"], r"^\d{4}-\d{2}-\d{2}$")

    def test_teacher_administrator_permissions(self):
        from skul_data.users.permissions.permission import IsAdministrator
        from rest_framework.test import APIRequestFactory
        from django.contrib.auth.models import AnonymousUser

        factory = APIRequestFactory()

        # Create request for unauthenticated user
        unauthenticated_request = factory.get("/")
        unauthenticated_request.user = AnonymousUser()

        # Regular teacher should not have admin permissions
        self.assertFalse(
            IsAdministrator().has_permission(unauthenticated_request, None)
        )

        # Create request for regular teacher (without admin privileges)
        teacher_request = factory.get("/")
        teacher_request.user = self.teacher.user
        self.assertFalse(IsAdministrator().has_permission(teacher_request, None))

        # Make teacher an administrator
        self.teacher.is_administrator = True
        self.teacher.save()

        # Create request for teacher administrator
        admin_request = factory.get("/")
        admin_request.user = self.teacher.user
        self.assertTrue(IsAdministrator().has_permission(admin_request, None))


# python manage.py test skul_data.tests.teachers_tests.test_teachers_admins
