from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.students.views.student import StudentViewSet

router = DefaultRouter()
router.register(r"students", StudentViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
