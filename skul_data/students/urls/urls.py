from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.students.views.student import (
    StudentViewSet,
    StudentDocumentViewSet,
    StudentNoteViewSet,
    StudentAttendanceViewSet,
)
from skul_data.students.views.student import SubjectViewSet


router = DefaultRouter()
router.register(r"students", StudentViewSet, basename="students")
router.register(
    r"student-documents", StudentDocumentViewSet, basename="student-documents"
)
router.register(r"student-notes", StudentNoteViewSet, basename="student-notes")
router.register(r"subjects", SubjectViewSet, basename="subjects")
router.register(
    r"student-attendance", StudentAttendanceViewSet, basename="student-attendance"
)

urlpatterns = [
    path("", include(router.urls)),
]
