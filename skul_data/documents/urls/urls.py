from django.urls import path
from skul_data.documents.views.document import DocumentUploadView


urlpatterns = [
    path("documents/", DocumentUploadView.as_view(), name="document-upload"),
]
