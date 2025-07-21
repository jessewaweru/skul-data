from rest_framework import serializers
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from skul_data.schools.serializers.schoolclass import SchoolClassSerializer
from skul_data.students.serializers.student import SimpleStudentSerializer
from skul_data.users.serializers.parent import ParentSerializer
from skul_data.fee_management.models.fee_management import (
    FeeStructure,
    FeeRecord,
    FeePayment,
    FeeUploadLog,
    FeeInvoiceTemplate,
    FeeReminder,
)
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student


class FeeStructureSerializer(serializers.ModelSerializer):
    school_class = SchoolClassSerializer(read_only=True)
    school_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), source="school_class", write_only=True
    )
    total_students = serializers.IntegerField(read_only=True)
    expected_revenue = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "school",
            "school_class",
            "school_class_id",
            "term",
            "year",
            "amount",
            "due_date",
            "is_active",
            "total_students",
            "expected_revenue",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["school", "created_at", "updated_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value

    def validate_due_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Due date cannot be in the past")
        return value

    def create(self, validated_data):
        # Set the school from context or passed data
        if "school" not in validated_data:
            request = self.context.get("request")
            if (
                request
                and hasattr(request, "user")
                and hasattr(request.user, "schooladmin_set")
            ):
                # If user is a school admin
                school = request.user.schooladmin_set.first()
                if school:
                    validated_data["school"] = school
            elif "school" in self.context:
                validated_data["school"] = self.context["school"]

        return super().create(validated_data)


class FeePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeePayment
        fields = [
            "id",
            "fee_record",
            "amount",
            "payment_method",
            "transaction_reference",
            "receipt_number",
            "receipt_image",
            "confirmed_by",
            "is_confirmed",
            "notes",
            "payment_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["confirmed_by", "created_at", "updated_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than zero"
            )
        return value


class FeeRecordSerializer(serializers.ModelSerializer):
    student = SimpleStudentSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), source="student", write_only=True
    )
    parent = ParentSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Parent.objects.all(), source="parent", write_only=True
    )
    fee_structure = FeeStructureSerializer(read_only=True)
    fee_structure_id = serializers.PrimaryKeyRelatedField(
        queryset=FeeStructure.objects.all(), source="fee_structure", write_only=True
    )
    payments = FeePaymentSerializer(many=True, read_only=True)
    payment_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = FeeRecord
        fields = [
            "id",
            "student",
            "student_id",
            "parent",
            "parent_id",
            "fee_structure",
            "fee_structure_id",
            "amount_owed",
            "amount_paid",
            "balance",
            "payment_status",
            "due_date",
            "is_overdue",
            "last_payment_date",
            "payment_percentage",
            "payments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "balance",
            "payment_status",
            "is_overdue",
            "last_payment_date",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        # Ensure student belongs to parent
        student = data.get("student")
        parent = data.get("parent")

        if student and parent:
            # Check if student belongs to parent
            if hasattr(parent, "children") and student not in parent.children.all():
                raise serializers.ValidationError(
                    {
                        "student_id": "This student is not associated with the selected parent"
                    }
                )
            elif hasattr(student, "parent") and student.parent != parent:
                raise serializers.ValidationError(
                    {
                        "student_id": "This student is not associated with the selected parent"
                    }
                )

        # Ensure student is in the class specified by fee_structure
        fee_structure = data.get("fee_structure")
        if student and fee_structure:
            # Check different possible field names for student's class
            student_class = None
            if hasattr(student, "student_class"):
                student_class = student.student_class
            elif hasattr(student, "school_class"):
                student_class = student.school_class
            elif hasattr(student, "class"):
                student_class = getattr(student, "class", None)

            if student_class and student_class != fee_structure.school_class:
                raise serializers.ValidationError(
                    {
                        "student_id": "Student is not in the class specified by the fee structure"
                    }
                )

        return data


class FeeUploadLogSerializer(serializers.ModelSerializer):
    school_class = SchoolClassSerializer(read_only=True)
    school_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(),
        source="school_class",
        write_only=True,
        required=False,
    )

    class Meta:
        model = FeeUploadLog
        fields = [
            "id",
            "school",
            "uploaded_by",
            "file",
            "school_class",
            "school_class_id",
            "term",
            "year",
            "status",
            "total_records",
            "successful_records",
            "failed_records",
            "error_log",
            "created_at",
            "processed_at",
        ]
        read_only_fields = [
            "school",
            "uploaded_by",
            "status",
            "total_records",
            "successful_records",
            "failed_records",
            "error_log",
            "created_at",
            "processed_at",
        ]


class FeeInvoiceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeInvoiceTemplate
        fields = [
            "id",
            "school",
            "name",
            "template_file",
            "is_active",
            "header_html",
            "footer_html",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["school", "created_at", "updated_at"]


class FeeReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeReminder
        fields = [
            "id",
            "fee_record",
            "sent_via",
            "message",
            "sent_at",
            "sent_by",
            "is_successful",
            "error_message",
        ]
        read_only_fields = ["sent_at", "sent_by", "is_successful", "error_message"]


class FeePaymentConfirmationSerializer(serializers.ModelSerializer):
    receipt_image = serializers.ImageField(required=True)
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),  # Use Decimal instead of float
    )

    class Meta:
        model = FeePayment
        fields = [
            "amount",
            "payment_method",
            "transaction_reference",
            "receipt_number",
            "receipt_image",
            "notes",
            "payment_date",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than zero"
            )
        return value


class FeeSummarySerializer(serializers.Serializer):
    term = serializers.CharField()
    year = serializers.CharField()
    school_class = (
        serializers.DictField()
    )  # Changed from SchoolClassSerializer to DictField
    total_students = serializers.IntegerField()
    total_expected = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    unpaid_count = serializers.IntegerField()
    partially_paid_count = serializers.IntegerField()
    fully_paid_count = serializers.IntegerField()
    overdue_count = serializers.IntegerField()


class FeeCSVTemplateSerializer(serializers.Serializer):
    school_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), required=True
    )
    term = serializers.CharField(required=True)
    year = serializers.CharField(required=True)
