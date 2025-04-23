from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.students.views.student import (
    StudentViewSet,
    StudentDocumentViewSet,
    StudentNoteViewSet,
)
from skul_data.students.views.student import SubjectViewSet

router = DefaultRouter()
router.register(r"students", StudentViewSet)
router.register(r"student-documents", StudentDocumentViewSet)
router.register(r"student-notes", StudentNoteViewSet)
router.register(r"subjects", SubjectViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
