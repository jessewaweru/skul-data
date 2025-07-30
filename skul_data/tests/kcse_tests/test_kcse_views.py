from django.db import router
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework import status
from django.contrib.auth import get_user_model
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
from skul_data.kcse.views.kcse import (
    KCSEResultViewSet,
    KCSESchoolPerformanceViewSet,
    KCSESubjectPerformanceViewSet,
)
from skul_data.kcse.models.kcse import KCSEResult

User = get_user_model()


class KCSEResultViewSetTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school, status="GRADUATED")
        self.kcse_result = create_test_kcse_result(self.student, uploaded_by=self.admin)
        self.subject = create_test_subject(self.school)
        self.subject_result = create_test_kcse_subject_result(
            self.kcse_result, self.subject
        )
        self.client.force_authenticate(user=self.admin)

    def test_list_results(self):
        response = self.client.get("/api/kcse/results/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both paginated and non-paginated responses
        if isinstance(response.data, dict) and "results" in response.data:
            self.assertEqual(len(response.data["results"]), 1)
        else:
            self.assertEqual(len(response.data), 1)

    def test_retrieve_result(self):
        response = self.client.get(f"/api/kcse/results/{self.kcse_result.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.kcse_result.id)

    def test_filter_by_year(self):
        # First delete any existing results to ensure clean state
        KCSEResult.objects.all().delete()

        # Create exactly one result for 2023
        result_2023 = create_test_kcse_result(
            self.student, year=2023, uploaded_by=self.admin
        )

        # Create one result for 2022
        create_test_kcse_result(self.student, year=2022, uploaded_by=self.admin)

        response = self.client.get("/api/kcse/results/?year=2023")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Handle paginated response format
        if isinstance(response.data, dict) and "results" in response.data:
            self.assertEqual(len(response.data["results"]), 1)
            self.assertEqual(response.data["results"][0]["year"], 2023)
        else:
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]["year"], 2023)

    def test_publish_result(self):
        response = self.client.post(
            f"/api/kcse/results/{self.kcse_result.id}/publish/", {}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.kcse_result.refresh_from_db()
        self.assertTrue(self.kcse_result.is_published)

    def test_unpublish_result(self):
        self.kcse_result.is_published = True
        self.kcse_result.save()
        response = self.client.post(
            f"/api/kcse/results/{self.kcse_result.id}/unpublish/", {}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.kcse_result.refresh_from_db()
        self.assertFalse(self.kcse_result.is_published)


class KCSESchoolPerformanceViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.performance = create_test_kcse_school_performance(self.school)
        self.client.force_authenticate(user=self.admin)

    def test_list_performances(self):
        # Use the correct URL from your router configuration
        response = self.client.get("/api/kcse/school-performance/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Handle paginated response format
        if isinstance(response.data, dict) and "results" in response.data:
            self.assertEqual(len(response.data["results"]), 1)
        else:
            self.assertEqual(len(response.data), 1)

    def test_comparison_view(self):
        create_test_kcse_school_performance(self.school, year=2022)
        # Use the correct URL
        response = self.client.get(
            "/api/kcse/school-performance/comparison/?years=2022,2023"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_trends_view(self):
        create_test_kcse_school_performance(self.school, year=2022)
        # Use the correct URL
        response = self.client.get("/api/kcse/school-performance/trends/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class KCSESubjectPerformanceViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.subject = create_test_subject(self.school)
        self.performance = create_test_kcse_school_performance(self.school)
        self.subject_performance = create_test_kcse_subject_performance(
            self.performance, self.subject
        )
        self.client.force_authenticate(user=self.admin)

    def test_subject_comparison(self):
        performance_2022 = create_test_kcse_school_performance(self.school, year=2022)
        create_test_kcse_subject_performance(performance_2022, self.subject)

        # Use the correct URL with proper path separator
        response = self.client.get(
            f"/api/kcse/subject-performance/subject_comparison/?subject={self.subject.code}&years=2022,2023"
        )
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.content}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_teacher_performance(self):
        teacher = create_test_teacher(self.school)
        self.subject_performance.subject_teacher = teacher
        self.subject_performance.save()

        # Use the correct URL with proper path separator
        response = self.client.get(
            f"/api/kcse/subject-performance/teacher_performance/?teacher_id={teacher.id}"
        )
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.content}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["subject"], self.subject.name)


# python manage.py test skul_data.tests.kcse_tests.test_kcse_views
