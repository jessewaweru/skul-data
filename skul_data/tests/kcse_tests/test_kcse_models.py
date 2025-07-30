from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date
from skul_data.tests.kcse_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_subject,
    create_test_kcse_result,
    create_test_kcse_subject_result,
    create_test_kcse_school_performance,
    create_test_kcse_subject_performance,
    create_test_teacher,
)


class KCSEResultModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)
        self.year = 2023

    def test_create_kcse_result(self):
        result = create_test_kcse_result(self.student, year=self.year)
        self.assertEqual(result.school, self.school)
        self.assertEqual(result.student, self.student)
        self.assertEqual(result.year, self.year)
        self.assertEqual(result.mean_grade, "B+")
        self.assertEqual(result.division, 1)
        self.assertFalse(result.is_published)
        self.assertEqual(str(result), f"{self.student.full_name} - 2023 (B+)")

    def test_unique_together_constraint(self):
        create_test_kcse_result(self.student, year=self.year)
        with self.assertRaises(Exception):
            create_test_kcse_result(self.student, year=self.year)

    def test_year_validation(self):
        with self.assertRaises(ValidationError):
            result = create_test_kcse_result(self.student, year=1988)
            result.full_clean()

    def test_grade_validation(self):
        with self.assertRaises(ValidationError):
            result = create_test_kcse_result(self.student, mean_grade="X")
            result.full_clean()


class KCSESubjectResultModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)
        self.subject = create_test_subject(self.school)
        self.kcse_result = create_test_kcse_result(self.student)
        self.teacher = create_test_teacher(self.school)

    def test_create_subject_result(self):
        subject_result = create_test_kcse_subject_result(
            self.kcse_result, self.subject, subject_teacher=self.teacher
        )
        self.assertEqual(subject_result.kcse_result, self.kcse_result)
        self.assertEqual(subject_result.subject, self.subject)
        self.assertEqual(subject_result.grade, "B+")
        self.assertEqual(subject_result.points, 10)
        self.assertEqual(subject_result.subject_teacher, self.teacher)
        self.assertEqual(
            str(subject_result),
            f"{self.student.full_name} - {self.subject.name} (B+)",
        )

    def test_unique_together_constraint(self):
        create_test_kcse_subject_result(self.kcse_result, self.subject)
        with self.assertRaises(Exception):
            create_test_kcse_subject_result(self.kcse_result, self.subject)


class KCSESchoolPerformanceModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.year = 2023

    def test_create_school_performance(self):
        performance = create_test_kcse_school_performance(self.school, year=self.year)
        self.assertEqual(performance.school, self.school)
        self.assertEqual(performance.year, self.year)
        self.assertEqual(performance.mean_grade, "B")
        self.assertEqual(performance.total_students, 100)
        self.assertEqual(performance.university_qualified, 70)
        self.assertEqual(
            str(performance),
            f"{self.school.name} - 2023 (B)",
        )

    def test_unique_together_constraint(self):
        create_test_kcse_school_performance(self.school, year=self.year)
        with self.assertRaises(Exception):
            create_test_kcse_school_performance(self.school, year=self.year)


class KCSESubjectPerformanceModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.subject = create_test_subject(self.school)
        self.teacher = create_test_teacher(self.school)
        self.school_performance = create_test_kcse_school_performance(self.school)

    def test_create_subject_performance(self):
        subject_performance = create_test_kcse_subject_performance(
            self.school_performance, self.subject, subject_teacher=self.teacher
        )
        self.assertEqual(
            subject_performance.school_performance, self.school_performance
        )
        self.assertEqual(subject_performance.subject, self.subject)
        self.assertEqual(subject_performance.mean_score, 8.5)
        self.assertEqual(subject_performance.total_students, 100)
        self.assertEqual(subject_performance.passed, 80)
        self.assertEqual(subject_performance.subject_teacher, self.teacher)
        self.assertEqual(
            str(subject_performance),
            f"{self.school.name} - {self.subject.name} (B-)",
        )

    def test_unique_together_constraint(self):
        create_test_kcse_subject_performance(self.school_performance, self.subject)
        with self.assertRaises(Exception):
            create_test_kcse_subject_performance(self.school_performance, self.subject)


# python manage.py test skul_data.tests.kcse_tests.test_kcse_models
