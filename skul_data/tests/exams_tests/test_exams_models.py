from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from skul_data.tests.exams_tests.test_helpers import (
    create_test_exam_type,
    create_test_grading_system,
    create_test_grade_range,
    create_test_exam,
    create_test_exam_subject,
    create_test_exam_result,
    create_test_term_report,
    create_default_grading_system,
    create_test_school,
    create_test_class,
    create_test_teacher,
    create_test_subject,
    create_test_student,
)
from skul_data.exams.models.exam import (
    Exam,
    ExamSubject,
    TermReport,
    GradeRange,
    ExamResult,
)


class ExamTypeModelTest(TestCase):
    def setUp(self):
        self.exam_type = create_test_exam_type()

    def test_create_exam_type(self):
        self.assertEqual(str(self.exam_type), "Test Exam Type")
        self.assertFalse(self.exam_type.is_default)

    def test_default_exam_type(self):
        default_type = create_test_exam_type("Default Type", True)
        self.assertTrue(default_type.is_default)


class GradingSystemModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.grading_system = create_test_grading_system(self.school)

    def test_create_grading_system(self):
        self.assertEqual(str(self.grading_system), "Test Grading System (Test School)")
        self.assertFalse(self.grading_system.is_default)

    def test_default_grading_system(self):
        default_system = create_test_grading_system(self.school, "Default System", True)
        self.assertTrue(default_system.is_default)

        # Only one default per school
        with self.assertRaises(ValidationError):
            another_default = create_test_grading_system(
                self.school, "Another Default", True
            )
            another_default.full_clean()


class GradeRangeModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.grading_system = create_test_grading_system(self.school)
        self.grade_range = create_test_grade_range(self.grading_system)

    def test_create_grade_range(self):
        self.assertEqual(str(self.grade_range), "A (0-100)")
        self.assertEqual(self.grade_range.points, Decimal("12.0"))

    def test_score_validation(self):
        with self.assertRaises(ValidationError):
            invalid_range = create_test_grade_range(
                self.grading_system, min_score=60, max_score=50, grade="B"
            )
            invalid_range.full_clean()

    def test_unique_together(self):
        # First create should work
        grade_range = create_test_grade_range(
            self.grading_system, min_score=10, max_score=20, grade="B"
        )

        # Second create with same parameters should raise ValidationError
        with self.assertRaises(ValidationError):
            duplicate_range = GradeRange(
                grading_system=grade_range.grading_system,
                min_score=grade_range.min_score,
                max_score=grade_range.max_score,
                grade="C",  # Different grade but same scores
            )
            duplicate_range.full_clean()  # This should raise ValidationError


class ExamModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_test_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            created_by=self.admin,
        )

    def test_create_exam(self):
        self.assertTrue(str(self.exam).startswith("Test Exam"))
        self.assertEqual(self.exam.term, "Term 1")
        self.assertEqual(self.exam.academic_year, "2023")
        self.assertFalse(self.exam.is_published)

    def test_exam_status(self):
        today = timezone.now().date()

        # Upcoming exam
        upcoming_exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=14),
        )
        self.assertEqual(upcoming_exam.status, "Upcoming")

        # Ongoing exam
        ongoing_exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
        )
        self.assertEqual(ongoing_exam.status, "Ongoing")

        # Completed exam
        completed_exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            start_date=today - timedelta(days=7),
            end_date=today - timedelta(days=1),
        )
        self.assertEqual(completed_exam.status, "Completed")

    def test_unique_together(self):
        # First create should work
        exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            name="Unique Test Exam",
            term="Term 2",  # Different term to avoid conflict
            academic_year="2024",  # Different year to avoid conflict
        )

        # Second create with same parameters should raise ValidationError
        with self.assertRaises(ValidationError):
            duplicate_exam = Exam(
                name=exam.name,
                exam_type=exam.exam_type,
                school=exam.school,
                school_class=exam.school_class,
                term=exam.term,
                academic_year=exam.academic_year,
                start_date=exam.start_date,
                end_date=exam.end_date,
                grading_system=exam.grading_system,
            )
            duplicate_exam.full_clean()  # This should raise ValidationError

    def test_date_validation(self):
        with self.assertRaises(ValidationError):
            invalid_exam = create_test_exam(
                self.school_class,
                self.exam_type,
                self.grading_system,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() - timedelta(days=1),
            )
            invalid_exam.full_clean()


class ExamSubjectModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_test_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class, self.exam_type, self.grading_system
        )
        self.subject = create_test_subject(self.school)
        self.teacher = create_test_teacher(self.school)
        self.exam_subject = create_test_exam_subject(
            self.exam, self.subject, self.teacher
        )

    def test_create_exam_subject(self):
        self.assertEqual(
            str(self.exam_subject), f"{self.subject.name} ({self.exam.name})"
        )
        self.assertEqual(self.exam_subject.max_score, 100)
        self.assertEqual(self.exam_subject.pass_score, 50)
        self.assertFalse(self.exam_subject.is_published)

    def test_average_score(self):
        # Create students and results
        student1 = create_test_student(self.school)
        student2 = create_test_student(self.school)

        create_test_exam_result(self.exam_subject, student1, score=Decimal("80.0"))
        create_test_exam_result(self.exam_subject, student2, score=Decimal("70.0"))

        self.assertEqual(self.exam_subject.average_score, 75.0)

    def test_pass_rate(self):
        # Create students and results
        student1 = create_test_student(self.school)
        student2 = create_test_student(self.school)
        student3 = create_test_student(self.school)

        # 2 passing scores out of 3 students (1 absent)
        create_test_exam_result(
            self.exam_subject, student1, score=Decimal("80.0")
        )  # Pass
        create_test_exam_result(
            self.exam_subject, student2, score=Decimal("40.0")
        )  # Fail
        create_test_exam_result(
            self.exam_subject, student3, is_absent=True
        )  # Doesn't count

        # Should be 50% pass rate (1 pass out of 2 non-absent students)
        self.assertEqual(self.exam_subject.pass_rate, 50.0)

    def test_unique_together(self):
        # Create a new subject to avoid conflict
        new_subject = create_test_subject(self.school, name="New Subject")

        # First create should work
        exam_subject = create_test_exam_subject(self.exam, new_subject, self.teacher)

        # Second create with same parameters should raise ValidationError
        with self.assertRaises(ValidationError):
            duplicate_subject = ExamSubject(
                exam=exam_subject.exam,
                subject=exam_subject.subject,
                teacher=exam_subject.teacher,
                max_score=exam_subject.max_score,
            )
            duplicate_subject.full_clean()  # This should raise ValidationError


class ExamResultModelTest(TestCase):

    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_default_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class, self.exam_type, self.grading_system
        )
        self.subject = create_test_subject(self.school)
        self.teacher = create_test_teacher(self.school)
        self.exam_subject = create_test_exam_subject(
            self.exam, self.subject, self.teacher
        )
        self.student = create_test_student(self.school)

    def test_create_exam_result(self):
        # Create fresh test data
        student = create_test_student(self.school)
        exam_result = create_test_exam_result(
            self.exam_subject, student, score=Decimal("75.0")
        )

        # Verify the string representation
        expected_str = f"{student} - {self.subject.name} (75.0)"
        self.assertEqual(str(exam_result), expected_str)

        # Verify other attributes
        self.assertEqual(exam_result.score, Decimal("75.0"))
        self.assertEqual(
            exam_result.grade, "B"
        )  # Verify this matches your grading system
        self.assertEqual(exam_result.remark, "Good")  # Verify expected remark
        self.assertFalse(exam_result.is_absent)

    def test_absent_result(self):
        # Create fresh exam result for this test
        exam_result = create_test_exam_result(
            self.exam_subject,
            create_test_student(self.school),  # New student
            is_absent=True,
        )
        self.assertTrue(exam_result.is_absent)

    def test_grade_calculation(self):
        # Create fresh student and exam result for each test case
        test_cases = [
            (95, "A", "Excellent"),
            (87, "A-", "Very Good"),
            (82, "B+", "Good Plus"),
            (77, "B", "Good"),
            (72, "B-", "Above Average"),
            (67, "C+", "Average Plus"),
            (62, "C", "Average"),
            (57, "C-", "Below Average"),
            (52, "D+", "Pass Plus"),
            (47, "D", "Pass"),
            (42, "D-", "Marginal"),
            (35, "E", "Fail"),
        ]

        for score, expected_grade, expected_remark in test_cases:
            student = create_test_student(self.school)  # New student for each case
            result = create_test_exam_result(
                self.exam_subject, student, score=Decimal(str(score))
            )
            self.assertEqual(result.grade, expected_grade)
            self.assertEqual(result.remark, expected_remark)

    def test_unique_together(self):
        student = create_test_student(self.school)
        create_test_exam_result(self.exam_subject, student)

        with self.assertRaises(ValidationError):
            duplicate = ExamResult(
                exam_subject=self.exam_subject, student=student, score=Decimal("85.0")
            )
            duplicate.full_clean()


class TermReportModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.student = create_test_student(self.school)

    def test_create_term_report(self):
        term_report = create_test_term_report(
            create_test_student(self.school), self.school_class
        )
        self.assertEqual(str(term_report), f"{term_report.student} - Term 1 2023")
        self.assertEqual(term_report.total_score, Decimal("450.0"))
        self.assertEqual(term_report.average_score, Decimal("75.0"))
        self.assertEqual(term_report.overall_grade, "B+")
        self.assertEqual(term_report.overall_position, 5)
        self.assertEqual(term_report.class_average, Decimal("65.0"))
        self.assertFalse(term_report.is_published)

    def test_calculate_results(self):
        # Create fresh data for this test
        student = create_test_student(self.school)
        term_report = TermReport.objects.create(
            student=student,
            school_class=self.school_class,
            term="Term 1",
            academic_year="2023",
        )
        # Create exam, subjects and results
        exam_type = create_test_exam_type()
        grading_system = create_default_grading_system(self.school)
        exam = create_test_exam(
            self.school_class,
            exam_type,
            grading_system,
            term="Term 1",
            academic_year="2023",
        )

        # Create subjects
        math = create_test_subject(self.school, name="Mathematics")
        english = create_test_subject(self.school, name="English")

        math_subject = create_test_exam_subject(exam, math, max_score=100, weight=30)
        english_subject = create_test_exam_subject(
            exam, english, max_score=100, weight=20
        )

        # Create results for our student
        create_test_exam_result(math_subject, self.student, score=Decimal("80.0"))
        create_test_exam_result(english_subject, self.student, score=Decimal("70.0"))

        # Create results for other students to calculate position
        other_student = create_test_student(self.school)
        create_test_exam_result(math_subject, other_student, score=Decimal("90.0"))
        create_test_exam_result(english_subject, other_student, score=Decimal("80.0"))

        # Create term report and calculate results
        term_report = TermReport.objects.create(
            student=self.student,
            school_class=self.school_class,
            term="Term 1",
            academic_year="2023",
        )
        term_report.calculate_results()

        # Verify calculations
        self.assertEqual(term_report.total_score, Decimal("150.0"))  # 80 + 70
        # Weighted average: (80/100)*30 + (70/100)*20 = 24 + 14 = 38 / 50 * 100 = 76
        self.assertEqual(term_report.average_score, Decimal("76.0"))
        self.assertEqual(term_report.overall_grade, "B")
        self.assertEqual(term_report.overall_position, 2)  # Second position
        self.assertEqual(
            term_report.class_average, Decimal("80.0")
        )  # (80+70+90+80)/4 = 80
        self.assertEqual(term_report.class_highest, Decimal("85.0"))  # (90+80)/2 = 85
        self.assertEqual(term_report.class_lowest, Decimal("75.0"))  # (80+70)/2 = 75


# python manage.py test skul_data.tests.exams_tests.test_exams_models
