from django.urls import path


from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.reports.views.academic_record import AcademicRecordViewSet
from skul_data.reports.views.salary_record import SalaryRecordViewSet

router = DefaultRouter()
router.register(r"academic-records", AcademicRecordViewSet, basename="academicrecord")
router.register(r"salary-records", SalaryRecordViewSet, basename="salaryrecord")

urlpatterns = [
    path("", include(router.urls)),
]
