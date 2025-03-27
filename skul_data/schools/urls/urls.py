from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.schools.views.school import SchoolViewSet

router = DefaultRouter()
router.register(r"students", SchoolViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
