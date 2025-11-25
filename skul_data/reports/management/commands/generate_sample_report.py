# reports/management/commands/generate_sample_report.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from skul_data.students.models.student import Student, Subject
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.reports.models.academic_record import AcademicRecord, TeacherComment
from skul_data.reports.models.report import  ReportTemplate
from skul_data.reports.utils.report_generator import generate_report_for_student


class Command(BaseCommand):
    help = "Generate a sample academic report with dummy data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--student-id",
            type=int,
            help="ID of existing student to generate report for",
        )
        parser.add_argument(
            "--school-id", type=int, required=True, help="ID of the school"
        )
        parser.add_argument(
            "--class-id", type=int, help="ID of existing class to use (optional)"
        )

    def handle(self, *args, **options):
        school_id = options["school_id"]
        student_id = options.get("student_id")
        class_id = options.get("class_id")

        try:
            school = School.objects.get(id=school_id)
            self.stdout.write(self.style.SUCCESS(f"Using school: {school.name}"))
        except School.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"School with ID {school_id} not found"))
            return

        # Get or create a student
        if student_id:
            try:
                student = Student.objects.get(id=student_id)
                self.stdout.write(
                    self.style.SUCCESS(f"Using existing student: {student.full_name}")
                )
            except Student.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Student with ID {student_id} not found")
                )
                return
        else:
            # Use existing class if provided, otherwise create/get one
            if class_id:
                try:
                    school_class = SchoolClass.objects.get(id=class_id)
                    self.stdout.write(
                        self.style.SUCCESS(f"Using existing class: {school_class.name}")
                    )
                except SchoolClass.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f"Class with ID {class_id} not found")
                    )
                    return
            else:
                school_class = self.get_or_create_class(school)

            student = self.create_sample_student(school, school_class)
            self.stdout.write(
                self.style.SUCCESS(f"Created sample student: {student.full_name}")
            )

        # Ensure student has a class
        if not student.student_class:
            if class_id:
                student.student_class = SchoolClass.objects.get(id=class_id)
            else:
                student.student_class = self.get_or_create_class(school)
            student.save()
            self.stdout.write(
                self.style.WARNING(
                    f"Assigned student to class: {student.student_class.name}"
                )
            )

        # Create sample academic records
        term = "Term 1"
        school_year = "2025"

        subjects_data = [
            {
                "name": "English",
                "score": 65,
                "entry": 8,
                "mid": 9,
                "end": 48,
                "comments": "Can do better, aim higher",
            },
            {
                "name": "Kiswahili",
                "score": 76,
                "entry": 10,
                "mid": 11,
                "end": 55,
                "comments": "Zaidi ya wastani",
            },
            {
                "name": "Mathematics",
                "score": 44,
                "entry": 8,
                "mid": 6,
                "end": 30,
                "comments": "Weak but has potential",
            },
            {
                "name": "Biology",
                "score": 67,
                "entry": 8,
                "mid": 10,
                "end": 48,
                "comments": "Can do better, aim higher",
            },
            {
                "name": "Physics",
                "score": 73,
                "entry": 7,
                "mid": 12,
                "end": 53,
                "comments": "Satisfactory, aim higher",
            },
            {
                "name": "Chemistry",
                "score": 65,
                "entry": 5,
                "mid": 11,
                "end": 49,
                "comments": "Can do better, aim higher",
            },
            {
                "name": "History",
                "score": 70,
                "entry": 12,
                "mid": 12,
                "end": 46,
                "comments": "Satisfactory, aim higher",
            },
            {
                "name": "Business Studies",
                "score": 59,
                "entry": 10,
                "mid": 8,
                "end": 42,
                "comments": "Below average, aim higher",
            },
        ]

        # Get or create a teacher
        teacher = self.get_or_create_teacher(school, student.student_class)

        for subject_data in subjects_data:
            # Get or create subject
            subject, created = Subject.objects.get_or_create(
                name=subject_data["name"],
                school=school,
                defaults={"code": subject_data["name"][:3].upper()},
            )
            if created:
                self.stdout.write(f"  Created subject: {subject.name}")

            # Delete existing records to avoid conflicts
            deleted_count = AcademicRecord.objects.filter(
                student=student, subject=subject, term=term, school_year=school_year
            ).delete()[0]

            if deleted_count > 0:
                self.stdout.write(
                    f"  Deleted {deleted_count} existing record(s) for {subject.name}"
                )

            # Create academic record
            AcademicRecord.objects.create(
                student=student,
                subject=subject,
                teacher=teacher,
                term=term,
                school_year=school_year,
                score=Decimal(str(subject_data["score"])),
                subject_comments=subject_data["comments"],
                is_published=True,
            )
            self.stdout.write(
                f'  ✓ Created record for {subject.name}: {subject_data["score"]}%'
            )

        # Create teacher comments
        deleted_comments = TeacherComment.objects.filter(
            student=student, term=term, school_year=school_year
        ).delete()[0]

        if deleted_comments > 0:
            self.stdout.write(f"Deleted {deleted_comments} existing comment(s)")

        TeacherComment.objects.create(
            student=student,
            teacher=teacher,
            term=term,
            school_year=school_year,
            comment_type="GENERAL",
            content="Average performance. Work harder, you can do much better than this.",
            is_approved=True,
            approved_by=teacher.user,
        )

        self.stdout.write(self.style.SUCCESS(f"Created teacher comment"))

        # Get or create academic report template
        template, created = ReportTemplate.objects.get_or_create(
            template_type="ACADEMIC",
            school=school,
            defaults={
                "name": "Academic Performance Report",
                "description": "Standard academic term report",
                "content": {},
                "is_system": False,
                "preferred_format": "PDF",
                "created_by": teacher.user,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Created academic report template"))
        else:
            self.stdout.write(
                self.style.SUCCESS("Using existing academic report template")
            )

        # Calculate class average
        from skul_data.reports.utils.report_generator import calculate_class_average

        class_average = calculate_class_average(
            student.student_class, term, school_year
        )

        # Generate the report
        self.stdout.write(self.style.WARNING("\n📊 Generating report..."))
        report = generate_report_for_student(
            student=student,
            term=term,
            school_year=school_year,
            template=template,
            teacher_user=teacher.user,
            school=school,
            class_average=class_average,
        )

        if report:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Sample report generated successfully!"
                    f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    f"\n📋 Report ID: {report.id}"
                    f"\n📄 Title: {report.title}"
                    f'\n� File: {report.file.url if report.file else "No file"}'
                    f"\n� Student: {student.full_name}"
                    f"\n� Term: {term} {school_year}"
                    f"\n🎓 Class: {student.student_class.name}"
                    f"\n📊 Mean Score: {sum(float(r.score) for r in AcademicRecord.objects.filter(student=student, term=term, school_year=school_year)) / len(subjects_data):.2f}%"
                    f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    f"\n\n✨ You can now view this report at:"
                    f"\n   /dashboard/reports/generated/{report.id}"
                )
            )
        else:
            self.stdout.write(self.style.ERROR("❌ Failed to generate report"))

    def get_or_create_class(self, school):
        """Get or create a class, checking for existing ones first"""
        # Try to find an existing class
        existing_class = SchoolClass.objects.filter(school=school).first()

        if existing_class:
            self.stdout.write(
                self.style.WARNING(f"Using existing class: {existing_class.name}")
            )
            return existing_class

        # Create a new class with proper fields based on your model
        self.stdout.write(
            self.style.WARNING("No existing class found. Creating new class...")
        )

        # Check what fields your SchoolClass model has
        from django.db import models

        model_fields = [
            f.name
            for f in SchoolClass._meta.get_fields()
            if isinstance(f, models.Field)
        ]

        # Build defaults based on available fields
        defaults = {
            "capacity": 50,
        }

        # Add optional fields if they exist
        if "grade_level" in model_fields:
            defaults["grade_level"] = "FORM_2"
        if "stream" in model_fields:
            defaults["stream"] = "J"
        if "academic_year" in model_fields:
            defaults["academic_year"] = "2025"
        if "section" in model_fields:
            defaults["section"] = "J"

        try:
            school_class, created = SchoolClass.objects.get_or_create(
                name="Form 2 J", school=school, defaults=defaults
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created new class: {school_class.name}")
                )
            return school_class

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create class: {str(e)}"))
            self.stdout.write(
                self.style.WARNING(f"Available fields in SchoolClass: {model_fields}")
            )
            raise

    def create_sample_student(self, school, school_class):
        """Create a sample student with dummy data"""
        # Check if student already exists
        existing_student = Student.objects.filter(
            admission_number="172917", school=school
        ).first()

        if existing_student:
            self.stdout.write(
                self.style.WARNING(
                    f"Student with admission number 172917 already exists"
                )
            )
            return existing_student

        # Get available fields from Student model
        from django.db import models

        student_fields = [
            f.name for f in Student._meta.get_fields() if isinstance(f, models.Field)
        ]

        # Build student data based on available fields
        student_data = {
            "school": school,
            "student_class": school_class,
            "first_name": "Angela",
            "last_name": "Nyakundi",
            "admission_number": "172917",
            "date_of_birth": timezone.now().date().replace(year=2008),
            "gender": "F",
        }

        # Add optional fields if they exist
        if "other_names" in student_fields or "middle_name" in student_fields:
            field_name = (
                "other_names" if "other_names" in student_fields else "middle_name"
            )
            student_data[field_name] = "Jepkemoi"

        if "full_name" in student_fields:
            student_data["full_name"] = "Angela Jepkemoi Nyakundi"

        try:
            student = Student.objects.create(**student_data)
            return student
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create student: {str(e)}"))
            self.stdout.write(
                self.style.WARNING(
                    f"Available fields in Student model: {student_fields}"
                )
            )
            raise

    def get_or_create_teacher(self, school, school_class=None):
        """Get or create a sample teacher"""
        # First, try to find an existing teacher at the school
        existing_teacher = Teacher.objects.filter(
            user__user_type=User.TEACHER,
        ).first()

        if existing_teacher:
            self.stdout.write(
                self.style.WARNING(
                    f"Using existing teacher: {existing_teacher.user.get_full_name()}"
                )
            )
            return existing_teacher

        # Get available fields from User model
        from django.db import models

        user_fields = [
            f.name for f in User._meta.get_fields() if isinstance(f, models.Field)
        ]

        # Build user defaults based on available fields
        user_defaults = {
            "email": "teacher@sample.school.com",
            "first_name": "Mrs",
            "last_name": "Obara",
            "user_type": User.TEACHER,
        }

        # Only add school field if it exists
        if "school" in user_fields:
            user_defaults["school"] = school

        user, created = User.objects.get_or_create(
            username="sample.teacher", defaults=user_defaults
        )

        if created:
            user.set_password("teacher123")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created sample teacher user"))

        if user.user_type != User.TEACHER:
            user.user_type = User.TEACHER
            user.save()

        # Build teacher defaults
        teacher_defaults = {"employee_id": "T001"}

        # Check if Teacher model has school field
        teacher_fields = [
            f.name for f in Teacher._meta.get_fields() if isinstance(f, models.Field)
        ]
        if "school" in teacher_fields:
            teacher_defaults["school"] = school

        teacher, created = Teacher.objects.get_or_create(
            user=user, defaults=teacher_defaults
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Created teacher profile"))

        # Assign teacher to class if provided and not already assigned
        if school_class and hasattr(school_class, "class_teacher"):
            if not school_class.class_teacher:
                school_class.class_teacher = teacher
                school_class.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Assigned teacher to class: {school_class.name}"
                    )
                )

        return teacher
