# documents/management/commands/seed_categories.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seeds the database with predefined document categories using the existing utility function"

    def handle(self, *args, **options):
        from skul_data.documents.utils.document_categories import (
            seed_document_categories,
        )

        seed_document_categories()
        self.stdout.write(
            self.style.SUCCESS(
                "Successfully seeded document categories using existing utility function"
            )
        )
