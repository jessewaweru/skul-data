from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import PermissionDenied
from skul_data.tests.documents_tests.documents_factories import (
    DocumentCategoryFactory,
    DocumentFactory,
    DocumentShareLinkFactory,
    SchoolFactory,
    UserFactory,
)
from skul_data.documents.serializers.document import (
    DocumentCategorySerializer,
    DocumentSerializer,
    DocumentShareLinkSerializer,
)
from django.utils import timezone
from datetime import timedelta
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.models.base_user import User


class DocumentCategorySerializerTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.user = UserFactory()
        self.category = DocumentCategoryFactory(school=self.school)

    def test_serialization(self):
        serializer = DocumentCategorySerializer(instance=self.category)
        data = serializer.data
        self.assertEqual(data["name"], self.category.name)
        self.assertEqual(data["description"], self.category.description)
        self.assertEqual(data["is_custom"], self.category.is_custom)

    def test_deserialization(self):
        data = {"name": "New Category", "description": "Test description"}
        serializer = DocumentCategorySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        category = serializer.save(school=self.school, is_custom=True)
        self.assertEqual(category.name, "New Category")
        self.assertEqual(category.school, self.school)
        self.assertTrue(category.is_custom)


class DocumentSerializerTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.user = UserFactory()
        # Set user_type to SCHOOL_ADMIN
        self.user.user_type = User.SCHOOL_ADMIN
        self.user.save()

        # Make sure we have a school_admin_profile
        SchoolAdmin.objects.create(user=self.user, school=self.school)

        self.category = DocumentCategoryFactory(school=self.school)
        self.test_file = SimpleUploadedFile(
            "test_file.pdf", b"file_content", content_type="application/pdf"
        )

    def test_serialization(self):
        doc = DocumentFactory(
            school=self.school, category=self.category, uploaded_by=self.user
        )

        # Create a proper mock request object
        class MockRequest:
            def build_absolute_uri(self, path):
                return f"http://testserver{path}"

        mock_request = MockRequest()
        serializer = DocumentSerializer(instance=doc, context={"request": mock_request})
        data = serializer.data
        self.assertEqual(data["title"], doc.title)
        self.assertEqual(data["school_name"], self.school.name)
        self.assertEqual(data["uploaded_by_name"], self.user.get_full_name())
        self.assertIn("file_url", data)

    def test_deserialization(self):
        data = {
            "title": "Test Document",
            "description": "Test description",
            "category_id": self.category.id,
            "school": self.school.id,
            "is_public": False,
        }

        # Create a proper request object with user attribute
        # Changed MockRequest to be dict-like with user attribute
        mock_request = type("MockRequest", (), {"user": self.user})()

        serializer = DocumentSerializer(data=data, context={"request": mock_request})
        self.assertTrue(
            serializer.is_valid(), f"Serializer errors: {serializer.errors}"
        )
        document = serializer.save(uploaded_by=self.user)
        self.assertEqual(document.title, "Test Document")
        self.assertEqual(document.school, self.school)
        self.assertEqual(document.uploaded_by, self.user)

    def test_school_permission_validation(self):
        # Create a user from a different school
        other_school = SchoolFactory()
        other_user = UserFactory(user_type=User.SCHOOL_ADMIN)

        # Create SchoolAdmin for other_user
        other_admin = SchoolAdmin.objects.create(user=other_user, school=other_school)

        data = {
            "title": "Test Document",
            "description": "Test description",
            "category_id": self.category.id,
            "school": self.school.id,
            "is_public": False,
        }

        # Changed MockRequest to be dict-like with user attribute
        mock_request = type("MockRequest", (), {"user": other_user})()

        serializer = DocumentSerializer(data=data, context={"request": mock_request})
        with self.assertRaises(PermissionDenied):
            serializer.is_valid(raise_exception=True)


class DocumentShareLinkSerializerTest(TestCase):
    def setUp(self):
        self.document = DocumentFactory()
        self.user = UserFactory()

    def test_serialization(self):
        # Create a share link with timezone-aware expires_at
        share_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.user,
            expires_at=timezone.now() + timedelta(days=30),
        )

        # Create a proper mock request object
        class MockRequest:
            def build_absolute_uri(self, path):
                return f"http://testserver{path}"

        mock_request = MockRequest()

        serializer = DocumentShareLinkSerializer(
            instance=share_link, context={"request": mock_request}
        )
        data = serializer.data
        self.assertEqual(data["document_title"], self.document.title)
        self.assertIn("document_url", data)
        self.assertIn("expires_in", data)

    def test_deserialization(self):
        data = {
            "document": self.document.id,
            "password": "secret",
            "download_limit": 5,
            # Provide timezone-aware expires_at
            "expires_at": timezone.now() + timedelta(days=14),
        }

        # Create a proper request object - no need for get() method in this test
        mock_request = type("MockRequest", (), {"user": self.user})()

        serializer = DocumentShareLinkSerializer(
            data=data, context={"request": mock_request}
        )
        self.assertTrue(
            serializer.is_valid(), f"Serializer errors: {serializer.errors}"
        )
        share_link = serializer.save(created_by=self.user)
        self.assertEqual(share_link.document, self.document)
        self.assertEqual(share_link.password, "secret")
        self.assertEqual(share_link.download_limit, 5)
        self.assertIsNotNone(share_link.expires_at)


# python manage.py test skul_data.tests.documents_tests.test_documents_serializers
