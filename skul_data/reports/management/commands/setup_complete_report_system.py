# reports/management/commands/setup_complete_report_system.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from skul_data.students.models.student import Student, Subject
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.reports.models.academic_record import AcademicRecord, TeacherComment
from skul_data.reports.models.report import ReportTemplate
from skul_data.reports.utils.report_generator import generate_class_term_reports
import random


class Command(BaseCommand):
    help = "Setup complete report system with realistic data for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--school-id", type=int, required=True, help="ID of the school"
        )
        parser.add_argument(
            "--class-id", type=int, required=True, help="ID of the class"
        )
        parser.add_argument("--term", type=str, default="Term 1", help="Term name")
        parser.add_argument(
            "--school-year", type=str, default="2025", help="School year"
        )

    def handle(self, *args, **options):
        school_id = options["school_id"]
        class_id = options["class_id"]
        term = options["term"]
        school_year = options["school_year"]

        try:
            school = School.objects.get(id=school_id)
            school_class = SchoolClass.objects.get(id=class_id, school=school)
        except (School.DoesNotExist, SchoolClass.DoesNotExist) as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"Setting up report system for:\n"
                f"School: {school.name}\n"
                f"Class: {school_class.name}\n"
                f"Term: {term} {school_year}\n"
                f"{'='*60}\n"
            )
        )

        # Step 1: Setup subjects with specific teachers
        subjects_config = self.setup_subjects_with_teachers(school, school_class)

        # Step 2: Get all students in the class
        students = school_class.students.filter(is_active=True)

        if students.count() == 0:
            self.stdout.write(
                self.style.ERROR(f"No active students found in {school_class.name}")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {students.count()} students in {school_class.name}"
            )
        )

        # Step 3: Generate academic records for all students
        self.generate_academic_records(students, subjects_config, term, school_year)

        # Step 4: Generate teacher comments
        self.generate_teacher_comments(students, school_class, term, school_year)

        # Step 5: Ensure report template exists
        template = self.ensure_report_template(school)

        # Step 6: Generate reports for entire class
        self.stdout.write(
            self.style.WARNING("\n📊 Generating reports for entire class...")
        )

        # Get the class teacher (or use first teacher as fallback)
        if school_class.class_teacher:
            teacher_user = school_class.class_teacher.user
        else:
            teacher_user = Teacher.objects.filter(school=school).first().user

        # Use the actual bulk generation function
        try:
            result = generate_class_term_reports(
                class_id=class_id,
                term=term,
                school_year=school_year,
                generated_by_id=teacher_user.id,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Successfully generated reports!\n"
                    f"{'='*60}\n"
                    f"Total students: {result['total_students']}\n"
                    f"Reports generated: {result['reports_generated']}\n"
                    f"Skipped: {len(result['skipped_students'])}\n"
                    f"Time taken: {result['time_taken_seconds']:.2f}s\n"
                    f"{'='*60}\n"
                )
            )

            if result["skipped_students"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped students: {', '.join(result['skipped_students'])}"
                    )
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to generate reports: {str(e)}"))

    def setup_subjects_with_teachers(self, school, school_class):
        """Setup subjects and assign specific teachers to each"""
        self.stdout.write("\n📚 Setting up subjects with teachers...")

        # Get or create teachers for different subjects
        teachers = list(Teacher.objects.filter(school=school))

        if len(teachers) < 3:
            self.stdout.write(
                self.style.WARNING(
                    f"Only {len(teachers)} teachers found. Creating more..."
                )
            )
            # Create additional teachers if needed
            teachers = self.create_sample_teachers(school, needed=8 - len(teachers))

        # Subject-teacher assignments (rotating teachers)
        subjects_data = [
            {"name": "English", "code": "ENG"},
            {"name": "Kiswahili", "code": "KIS"},
            {"name": "Mathematics", "code": "MAT"},
            {"name": "Biology", "code": "BIO"},
            {"name": "Physics", "code": "PHY"},
            {"name": "Chemistry", "code": "CHE"},
            {"name": "History", "code": "HIS"},
            {"name": "Business Studies", "code": "BUS"},
        ]

        subjects_config = []
        for idx, subject_data in enumerate(subjects_data):
            subject, created = Subject.objects.get_or_create(
                name=subject_data["name"],
                school=school,
                defaults={"code": subject_data["code"]},
            )

            # Assign a teacher (rotate through available teachers)
            teacher = teachers[idx % len(teachers)]

            subjects_config.append(
                {"subject": subject, "teacher": teacher, "name": subject.name}
            )

            status = "Created" if created else "Found"
            self.stdout.write(
                f"  {status} subject: {subject.name} "
                f"(Teacher: {teacher.user.get_full_name()})"
            )

        return subjects_config

    def generate_academic_records(self, students, subjects_config, term, school_year):
        """Generate realistic academic records for all students"""
        self.stdout.write("\n📝 Generating academic records...")

        # Clear existing records for this term
        deleted_count = AcademicRecord.objects.filter(
            student__in=students, term=term, school_year=school_year
        ).delete()[0]

        if deleted_count > 0:
            self.stdout.write(f"  Cleared {deleted_count} existing records")

        # Generate records for each student
        total_records = 0
        for student in students:
            # Create performance profile for student (some excel, some struggle)
            base_performance = random.randint(40, 85)

            for subject_config in subjects_config:
                # Vary performance by subject (+/- 15 points from base)
                variation = random.randint(-15, 15)
                score = max(30, min(95, base_performance + variation))

                # Generate component scores with proper allocation (20%, 20%, 60%)
                # Entry exam: 20% of 100 = 0-20 marks
                entry = round((score * 0.20) + random.randint(-3, 3))
                entry = max(0, min(20, entry))  # Clamp between 0-20

                # Mid exam: 20% of 100 = 0-20 marks
                mid = round((score * 0.20) + random.randint(-3, 3))
                mid = max(0, min(20, mid))  # Clamp between 0-20

                # End exam: 60% of 100 = 0-60 marks (remaining from total)
                end = score - entry - mid
                end = max(0, min(60, end))  # Clamp between 0-60

                # Generate appropriate comment based on performance
                comments = self.generate_subject_comment(score)

                AcademicRecord.objects.create(
                    student=student,
                    subject=subject_config["subject"],
                    teacher=subject_config["teacher"],
                    term=term,
                    school_year=school_year,
                    score=Decimal(str(score)),
                    subject_comments=comments,
                    is_published=True,
                )
                total_records += 1

            self.stdout.write(
                f"  ✓ Generated records for {student.full_name} "
                f"(avg: {base_performance}%)"
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nTotal records generated: {total_records}")
        )

    def generate_subject_comment(self, score):
        """Generate appropriate comment based on score"""
        if score >= 80:
            return random.choice(
                [
                    "Excellent work! Keep it up",
                    "Outstanding performance",
                    "Exceptional understanding of concepts",
                ]
            )
        elif score >= 70:
            return random.choice(
                [
                    "Very good progress",
                    "Good understanding, aim higher",
                    "Commendable effort",
                ]
            )
        elif score >= 60:
            return random.choice(
                [
                    "Satisfactory performance",
                    "Good effort, needs more practice",
                    "Fair understanding",
                ]
            )
        elif score >= 50:
            return random.choice(
                [
                    "Needs improvement",
                    "More effort required",
                    "Work harder for better results",
                ]
            )
        else:
            return random.choice(
                [
                    "Requires significant improvement",
                    "Needs extra support",
                    "Must work much harder",
                ]
            )

    def generate_teacher_comments(self, students, school_class, term, school_year):
        """Generate teacher comments for all students"""
        self.stdout.write("\n💬 Generating teacher comments...")

        # Clear existing comments
        deleted_count = TeacherComment.objects.filter(
            student__in=students, term=term, school_year=school_year
        ).delete()[0]

        if deleted_count > 0:
            self.stdout.write(f"  Cleared {deleted_count} existing comments")

        # Get class teacher or use first available teacher
        if school_class.class_teacher:
            teacher = school_class.class_teacher
        else:
            teacher = Teacher.objects.filter(school=school_class.school).first()

        for student in students:
            # Calculate student's average for appropriate comment
            records = AcademicRecord.objects.filter(
                student=student, term=term, school_year=school_year
            )

            if records.exists():
                avg_score = sum(float(r.score) for r in records) / records.count()
                comment = self.generate_general_comment(avg_score)
            else:
                comment = "No performance data available"

            TeacherComment.objects.create(
                student=student,
                teacher=teacher,
                term=term,
                school_year=school_year,
                comment_type="GENERAL",
                content=comment,
                is_approved=True,
                approved_by=teacher.user,
            )

        self.stdout.write(
            self.style.SUCCESS(f"Generated comments for {students.count()} students")
        )

    def generate_general_comment(self, avg_score):
        """Generate general teacher comment based on average"""
        if avg_score >= 75:
            return random.choice(
                [
                    "Excellent performance this term. Maintain this outstanding work.",
                    "Brilliant student who consistently demonstrates high achievement.",
                    "Exceptional results. Continue with this excellent effort.",
                ]
            )
        elif avg_score >= 65:
            return random.choice(
                [
                    "Very good performance. With more effort, can achieve excellence.",
                    "Commendable work this term. Aim higher next term.",
                    "Good progress shown. Keep working hard.",
                ]
            )
        elif avg_score >= 50:
            return random.choice(
                [
                    "Average performance. More dedication needed for improvement.",
                    "Fair results. Must work harder to achieve better grades.",
                    "Satisfactory but capable of much better. Increase effort.",
                ]
            )
        else:
            return random.choice(
                [
                    "Poor performance. Requires immediate intervention and extra support.",
                    "Serious improvement needed. Must commit to studies.",
                    "Very weak performance. Parents' involvement crucial.",
                ]
            )

    def ensure_report_template(self, school):
        """Ensure academic report template exists"""
        template, created = ReportTemplate.objects.get_or_create(
            template_type="ACADEMIC",
            school=school,
            defaults={
                "name": "Academic Performance Report",
                "description": "Standard academic term report",
                "content": {},
                "is_system": False,
                "preferred_format": "PDF",
                "created_by": User.objects.filter(user_type=User.SCHOOL_ADMIN).first(),
            },
        )

        status = "Created" if created else "Found"
        self.stdout.write(f"{status} report template: {template.name}")
        return template

    def create_sample_teachers(self, school, needed=5):
        """Create sample teachers if not enough exist"""
        self.stdout.write(f"Creating {needed} sample teachers...")

        teacher_names = [
            ("John", "Kamau"),
            ("Mary", "Njeri"),
            ("Peter", "Omondi"),
            ("Grace", "Akinyi"),
            ("David", "Ochieng"),
            ("Sarah", "Wanjiku"),
            ("James", "Mwangi"),
            ("Lucy", "Adhiambo"),
        ]

        created_teachers = []
        for i, (first_name, last_name) in enumerate(teacher_names[:needed]):
            username = f"teacher_{first_name.lower()}_{i}"

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@{school.name.lower().replace(' ', '')}.com",
                    "first_name": first_name,
                    "last_name": last_name,
                    "user_type": User.TEACHER,
                    "school": school,
                },
            )

            if user_created:
                user.set_password("teacher123")
                user.save()

            teacher, _ = Teacher.objects.get_or_create(
                user=user, defaults={"employee_id": f"T{1000 + i}", "school": school}
            )

            created_teachers.append(teacher)

        return created_teachers
