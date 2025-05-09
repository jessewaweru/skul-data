from django.test import TestCase
from skul_data.documents.utils.document_categories import seed_document_categories
from skul_data.documents.models.document import DocumentCategory


class DocumentCategoriesUtilsTest(TestCase):
    def test_seed_document_categories(self):
        # Initial count should be 0
        self.assertEqual(DocumentCategory.objects.count(), 0)

        # Seed the categories
        seed_document_categories()

        # Check that categories were created
        self.assertGreater(DocumentCategory.objects.count(), 0)

        # Check some sample categories
        self.assertTrue(
            DocumentCategory.objects.filter(
                name="Staff Contracts & Employment Letters"
            ).exists()
        )
        self.assertTrue(DocumentCategory.objects.filter(name="Report Cards").exists())
        self.assertTrue(
            DocumentCategory.objects.filter(name="PTA Meeting Minutes").exists()
        )

        # Check that they are system categories
        category = DocumentCategory.objects.get(
            name="Staff Contracts & Employment Letters"
        )
        self.assertFalse(category.is_custom)
        self.assertIsNone(category.school)

    def test_seed_idempotent(self):
        # First seeding
        seed_document_categories()
        initial_count = DocumentCategory.objects.count()

        # Second seeding shouldn't create duplicates
        seed_document_categories()
        self.assertEqual(DocumentCategory.objects.count(), initial_count)


# python manage.py test skul_data.tests.documents_tests.test_documents_utils
