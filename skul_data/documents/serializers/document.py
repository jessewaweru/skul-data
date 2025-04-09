from rest_framework import serializers
from skul_data.documents.models.document import Document, DocumentCategory


class DocumentSerializer(serializers.ModelSerializer):
    category = serializers.CharField(
        write_only=True, required=True, help_text="Existing category or a new one."
    )

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file",
            "uploaded_at",
            "uploaded_by_superuser",
            "uploaded_by_teacher",
            "category",
        ]
        read_only_fields = ["uploaded_by_superuser", "uploaded_by_teacher"]

    def validate_category(self, value):
        # Check if category exists in DB, otherwise, treat it as a new custom category
        if DocumentCategory.objects.filter(name=value).exists():
            return value  # Existing category
        else:
            # Treat it as a new custom category
            return value.strip()  # No need to validate here, handled in create method

    def create(self, validated_data):
        category_name = validated_data.pop("category").strip()
        request = self.context.get("request")

        # Check if it's an existing category or create a new one
        category, created = DocumentCategory.objects.get_or_create(
            name=category_name,
            defaults={"is_custom": True},  # Mark as custom if newly created
        )

        validated_data["category"] = category
        validated_data["uploaded_by"] = request.user

        return Document.objects.create(**validated_data)
