from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.kcse.views.kcse import (
    KCSEResultViewSet,
    KCSESchoolPerformanceViewSet,
    KCSESubjectPerformanceViewSet,
)

router = DefaultRouter()
router.register(r"results", KCSEResultViewSet, basename="kcse-results")
router.register(
    r"school-performance",
    KCSESchoolPerformanceViewSet,
    basename="kcse-school-performance",
)
router.register(
    r"subject-performance",
    KCSESubjectPerformanceViewSet,
    basename="kcse-subject-performance",
)

urlpatterns = [
    path("", include(router.urls)),
]
