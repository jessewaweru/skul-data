from rest_framework import serializers
from skul_data.documents.models.document import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file",
            "uploaded_at",
            "uploaded_by_superuser",
            "uploaded_by_teacher",
        ]
        read_only_fields = ["uploaded_by_superuser", "uploaded_by_teacher"]
