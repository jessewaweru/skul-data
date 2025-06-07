from django.test import TestCase
from django.contrib.auth import get_user_model
from skul_data.users.serializers.parent import (
    ParentSerializer,
    ParentCreateSerializer,
    ParentChildAssignmentSerializer,
    ParentNotificationPreferenceSerializer,
    ParentNotificationSerializer,
    ParentStatusUpdateSerializer,
)
from skul_data.tests.parents_tests.test_helpers import (
    create_test_school,
    create_test_parent,
    create_test_student,
)
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from skul_data.users.serializers.parent import ParentBulkImportSerializer

User = get_user_model()


class ParentSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)
        self.context = {"request": None}

    def test_serializer_data(self):
        serializer = ParentSerializer(instance=self.parent, context=self.context)
        data = serializer.data
        self.assertEqual(data["email"], "parent@test.com")
        self.assertEqual(data["first_name"], "Test")
        self.assertEqual(data["last_name"], "Parent")
        self.assertEqual(data["phone_number"], "+254700000000")
        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(len(data["children_details"]), 1)

    def test_children_details_method(self):
        serializer = ParentSerializer(instance=self.parent, context=self.context)
        children_data = serializer.get_children_details(self.parent)
        self.assertEqual(len(children_data), 1)
        self.assertEqual(children_data[0]["first_name"], "Test")
        self.assertEqual(children_data[0]["last_name"], "Student")


class ParentCreateSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.valid_data = {
            "email": "newparent@test.com",
            "first_name": "New",
            "last_name": "Parent",
            "phone_number": "+254722222222",
            "school": self.school.id,
            "address": "123 New Street",
            "occupation": "New Occupation",
        }

    def test_valid_creation(self):
        serializer = ParentCreateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        parent = serializer.save()
        self.assertEqual(parent.user.email, "newparent@test.com")
        self.assertEqual(parent.user.first_name, "New")
        self.assertEqual(parent.user.last_name, "Parent")
        self.assertEqual(parent.phone_number, "+254722222222")
        self.assertEqual(parent.school, self.school)

    def test_creation_with_password(self):
        data = {**self.valid_data, "password": "testpassword123"}
        serializer = ParentCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        parent = serializer.save()
        self.assertTrue(parent.user.check_password("testpassword123"))

    def test_creation_without_password(self):
        serializer = ParentCreateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        parent = serializer.save()
        self.assertTrue(parent.user.has_usable_password())


class ParentChildAssignmentSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student1 = create_test_student(self.school)
        self.student2 = create_test_student(self.school, first_name="Another")

    def test_valid_assignment(self):
        data = {"student_ids": [self.student1.id, self.student2.id], "action": "ADD"}
        serializer = ParentChildAssignmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["action"], "ADD")
        self.assertEqual(len(serializer.validated_data["student_ids"]), 2)

    def test_invalid_action(self):
        data = {"student_ids": [self.student1.id], "action": "INVALID"}
        serializer = ParentChildAssignmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("action", serializer.errors)


class ParentNotificationPreferenceSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)

    def test_update_preferences(self):
        data = {"receive_email_notifications": False, "preferred_language": "sw"}
        serializer = ParentNotificationPreferenceSerializer(
            instance=self.parent, data=data
        )
        self.assertTrue(serializer.is_valid())
        parent = serializer.save()
        self.assertFalse(parent.receive_email_notifications)
        self.assertEqual(parent.preferred_language, "sw")


class ParentNotificationSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.parent = create_test_parent(self.school)
        self.student = create_test_student(self.school, parent=self.parent)

    def test_notification_serialization(self):
        notification = self.parent.send_notification(
            message="Test message",
            notification_type="ACADEMIC",
            related_student=self.student,
            sender=self.admin,
        )
        serializer = ParentNotificationSerializer(instance=notification)
        data = serializer.data
        self.assertEqual(data["message"], "Test message")
        self.assertEqual(data["notification_type"], "ACADEMIC")
        self.assertEqual(data["is_read"], False)
        self.assertEqual(data["sent_by"]["email"], self.admin.email)
        self.assertEqual(data["related_student"]["first_name"], "Test")


class ParentStatusChangeSerializerTest(TestCase):
    def test_status_change_validation(self):
        data = {"status": "ACTIVE", "reason": "Approved by admin"}
        serializer = ParentStatusUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["status"], "ACTIVE")
        self.assertEqual(serializer.validated_data["reason"], "Approved by admin")

    def test_invalid_status(self):
        data = {"status": "INVALID", "reason": "Invalid status"}
        serializer = ParentStatusUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)


class ParentBulkImportSerializerTest(APITestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_valid_data(self):
        # Create a test CSV file
        csv_content = (
            "email,first_name,last_name,children_ids\nparent1@test.com,John,Doe,1"
        )
        file = SimpleUploadedFile(
            "parents.csv", csv_content.encode(), content_type="text/csv"
        )

        data = {"file": file, "send_welcome_email": True, "default_status": "ACTIVE"}

        serializer = ParentBulkImportSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_file_type(self):
        # Create a test PDF file (invalid type)
        pdf_content = b"%PDF-1.3 invalid pdf content"
        file = SimpleUploadedFile(
            "parents.pdf", pdf_content, content_type="application/pdf"
        )

        data = {"file": file}
        serializer = ParentBulkImportSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)

    def test_file_size_limit(self):
        # Create a large test file (>5MB)
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        file = SimpleUploadedFile("large.csv", large_content, content_type="text/csv")

        data = {"file": file}
        serializer = ParentBulkImportSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)

    def test_missing_required_fields(self):
        # CSV missing required first_name column
        csv_content = "email,last_name\nparent1@test.com,Doe"
        file = SimpleUploadedFile(
            "parents.csv", csv_content.encode(), content_type="text/csv"
        )

        data = {"file": file}
        serializer = ParentBulkImportSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)


# python manage.py test skul_data.tests.parents_tests.test_parents_serializers
