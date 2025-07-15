from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.schools.views.school import (
    SchoolViewSet,
    SchoolSubscriptionViewSet,
    SecurityLogViewSet,
)
from skul_data.schools.views.schoolclass import (
    SchoolClassViewSet,
    ClassTimetableViewSet,
    ClassDocumentViewSet,
    ClassAttendanceViewSet,
)
from skul_data.schools.views.schoolstream import SchoolStreamViewSet
from skul_data.schools.views.school import school_teachers

router = DefaultRouter()
router.register(r"students", SchoolViewSet)
router.register(r"classes", SchoolClassViewSet, basename="class")
router.register(r"streams", SchoolStreamViewSet, basename="stream")
router.register(r"class-timetables", ClassTimetableViewSet, basename="class-timetable")
router.register(r"class-documents", ClassDocumentViewSet, basename="class-document")
router.register(
    r"class-attendances", ClassAttendanceViewSet, basename="class-attendance"
)
router.register(r"subscriptions", SchoolSubscriptionViewSet, basename="subscription")
router.register(r"security-logs", SecurityLogViewSet, basename="securitylog")

urlpatterns = [
    path("", include(router.urls)),
    path("<int:school_id>/teachers/", school_teachers, name="school-teachers"),
]
