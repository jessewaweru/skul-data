from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.documents.views.document import (
    DocumentViewSet,
    DocumentCategoryViewSet,
    DocumentShareLinkViewSet,
)

# app_name = "documents"

router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"categories", DocumentCategoryViewSet, basename="category")
router.register(r"share-links", DocumentShareLinkViewSet, basename="share-link")

urlpatterns = [
    path("", include(router.urls)),
    # Public download endpoint (no auth required)
    path(
        "download/<uuid:token>/",
        DocumentShareLinkViewSet.as_view({"get": "download"}),
        name="document-download",
    ),
]
