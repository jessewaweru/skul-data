from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.schools.views.school import SchoolViewSet
from skul_data.schools.views.schoolclass import (
    SchoolClassViewSet,
    ClassTimetableViewSet,
    ClassDocumentViewSet,
    ClassAttendanceViewSet,
)
from skul_data.schools.views.schoolstream import SchoolStreamViewSet


router = DefaultRouter()
router.register(r"students", SchoolViewSet)
router.register(r"classes", SchoolClassViewSet, basename="class")
router.register(r"streams", SchoolStreamViewSet, basename="stream")
router.register(r"class-timetables", ClassTimetableViewSet, basename="class-timetable")
router.register(r"class-documents", ClassDocumentViewSet, basename="class-document")
router.register(
    r"class-attendances", ClassAttendanceViewSet, basename="class-attendance"
)

urlpatterns = [
    path("", include(router.urls)),
]
