from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from skul_data.documents.models.document import Document
from skul_data.documents.serializers.document import DocumentSerializer


class DocumentUploadView(generics.CreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [
        permissions.IsAuthenticated
    ]  # Ensure only logged-in users can upload

    def perform_create(self, serializer):
        """Ensure only SuperUser or Teacher can upload, and assign correct user field."""
        user = self.request.user

        if user.user_type == "Superuser":
            serializer.save(uploaded_by_superuser=user)
        elif user.user_type == "Teacher":
            serializer.save(uploaded_by_teacher=user)
        else:
            PermissionDenied("Only SuperUsers and Teachers can upload documents.")
