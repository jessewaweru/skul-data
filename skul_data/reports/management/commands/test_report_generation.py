# reports/management/commands/test_report_generation.py
# Create this file to test report generation

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from weasyprint import HTML
from django.conf import settings
import os


class Command(BaseCommand):
    help = "Test report generation with diagnostics"

    def handle(self, *args, **options):
        # Test data
        test_data = {
            "school": {
                "name": "Test High School",
                "address": "123 Test Street",
                "po_box": "12345",
                "phone": "0700000000",
                "email": "test@school.com",
                "website": "www.testschool.com",
                "logo": None,
            },
            "student": {
                "full_name": "John Doe",
                "admission_number": "2025-001",
                "class_name": "Form 2 J",
                "gender": "M",
                "upi": None,
                "kcpe_marks": 350,
                "photo": None,
            },
            "term": "Term 1",
            "school_year": "2025",
            "records": [
                {
                    "subject": "Mathematics",
                    "entry_exam": 15,
                    "mid_term": 18,
                    "end_term": 52,
                    "score": 85,
                    "grade": "A",
                    "deviation": 5.0,
                    "rank": 5,
                    "total_students": 30,
                    "comments": "Excellent performance",
                    "teacher": "Mr. Smith",
                    "class_avg": 80.0,
                    "trend": "up",
                }
            ],
            "total_marks": 85,
            "max_marks": 100,
            "mean_mark": 85.0,
            "total_points": 12,
            "max_points": 12,
            "overall_grade": "A",
            "stream_position": 5,
            "stream_total": 30,
            "overall_position": 10,
            "overall_total": 120,
            "class_teacher_name": "Mrs. Johnson",
            "class_teacher_comment": "DIAGNOSTIC TEST: This is the class teacher comment that should appear!",
            "class_teacher_signature": None,
            "head_name": "Mr. Principal",
            "head_comment": "DIAGNOSTIC TEST: This is the head comment that should appear!",
            "head_signature": None,
            "term_end_date": "05/04/2025",
            "next_term_start_date": "10/05/2025",
            "generated_date": "12/12/2024",
        }

        self.stdout.write("=" * 60)
        self.stdout.write("DIAGNOSTIC TEST: Report Generation")
        self.stdout.write("=" * 60)

        # Step 1: Test template rendering
        self.stdout.write("\n1. Testing template rendering...")
        try:
            html_string = render_to_string("reports/academic_template.html", test_data)
            self.stdout.write(self.style.SUCCESS("   ✓ Template renders successfully"))

            # Check if comments are in the HTML
            if "DIAGNOSTIC TEST: This is the class teacher comment" in html_string:
                self.stdout.write(
                    self.style.SUCCESS("   ✓ Class teacher comment found in HTML")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("   ✗ Class teacher comment NOT found in HTML")
                )
                # Show what's actually there
                import re

                match = re.search(
                    r'<div class="comment-text">(.*?)</div>', html_string, re.DOTALL
                )
                if match:
                    self.stdout.write(f"   Found instead: {match.group(1)[:100]}")

            if "DIAGNOSTIC TEST: This is the head comment" in html_string:
                self.stdout.write(self.style.SUCCESS("   ✓ Head comment found in HTML"))
            else:
                self.stdout.write(
                    self.style.ERROR("   ✗ Head comment NOT found in HTML")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ✗ Template rendering failed: {e}"))
            return

        # Step 2: Test with actual photos
        self.stdout.write("\n2. Testing with actual files...")

        # Check for student photos
        student_photos_dir = os.path.join(settings.MEDIA_ROOT, "student_photos")
        if os.path.exists(student_photos_dir):
            photos = [
                f for f in os.listdir(student_photos_dir) if f.startswith("student_")
            ]
            if photos:
                test_photo = os.path.join(
                    settings.MEDIA_ROOT, "student_photos", photos[0]
                )
                test_data["student"]["photo"] = test_photo
                self.stdout.write(
                    self.style.SUCCESS(f"   ✓ Using test photo: {photos[0]}")
                )
            else:
                self.stdout.write(self.style.WARNING("   ⚠ No student photos found"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"   ⚠ Photo directory not found: {student_photos_dir}"
                )
            )

        # Check for school logo
        logo_dir = os.path.join(settings.MEDIA_ROOT, "school_logos")
        if os.path.exists(logo_dir):
            logos = [
                f for f in os.listdir(logo_dir) if f.endswith((".png", ".jpg", ".svg"))
            ]
            if logos:
                test_logo = os.path.join(settings.MEDIA_ROOT, "school_logos", logos[0])
                test_data["school"]["logo"] = test_logo
                self.stdout.write(
                    self.style.SUCCESS(f"   ✓ Using test logo: {logos[0]}")
                )
            else:
                self.stdout.write(self.style.WARNING("   ⚠ No school logos found"))
        else:
            self.stdout.write(
                self.style.WARNING(f"   ⚠ Logo directory not found: {logo_dir}")
            )

        # Step 3: Generate PDF
        self.stdout.write("\n3. Generating PDF...")
        try:
            html_string = render_to_string("reports/academic_template.html", test_data)

            html = HTML(string=html_string, base_url=f"file://{settings.MEDIA_ROOT}/")

            output_path = os.path.join(settings.MEDIA_ROOT, "test_report.pdf")
            html.write_pdf(output_path)

            self.stdout.write(self.style.SUCCESS(f"   ✓ PDF generated: {output_path}"))
            self.stdout.write(f"\n   Open this file to check:")
            self.stdout.write(f"   {output_path}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ✗ PDF generation failed: {e}"))
            import traceback

            self.stdout.write(traceback.format_exc())

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DIAGNOSTIC COMPLETE")
        self.stdout.write("=" * 60)
