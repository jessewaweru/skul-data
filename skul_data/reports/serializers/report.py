from rest_framework import serializers
from skul_data.reports.models.report import ReportTemplate
from skul_data.schools.serializers.school import SchoolSerializer
from skul_data.users.serializers.base_user import BaseUserSerializer
from skul_data.schools.serializers.schoolclass import SchoolClassSerializer
from skul_data.users.serializers.teacher import TeacherSerializer
from skul_data.students.serializers.student import StudentSerializer
from skul_data.reports.models.report import GeneratedReport
from skul_data.reports.models.report import (
    ReportSchedule,
    ReportNotification,
    ReportAccessLog,
    AcademicReportConfig,
    TermReportRequest,
    GeneratedReportAccess,
)
from skul_data.students.models.student import Student
from skul_data.users.models.base_user import User


class ReportTemplateSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    created_by = BaseUserSerializer(read_only=True)

    class Meta:
        model = ReportTemplate
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class GeneratedReportSerializer(serializers.ModelSerializer):
    report_type = serializers.PrimaryKeyRelatedField(
        queryset=ReportTemplate.objects.all(), required=True
    )
    school = SchoolSerializer(read_only=True)
    generated_by = BaseUserSerializer(read_only=True)
    approved_by = BaseUserSerializer(read_only=True)
    related_class = SchoolClassSerializer(read_only=True)
    related_students = StudentSerializer(many=True, read_only=True)
    related_teachers = TeacherSerializer(many=True, read_only=True)

    class Meta:
        model = GeneratedReport
        fields = "__all__"
        read_only_fields = ("generated_at",)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Convert report_type ID to full object in the response
        representation["report_type"] = ReportTemplateSerializer(
            instance.report_type
        ).data
        return representation


class ReportAccessLogSerializer(serializers.ModelSerializer):
    report = GeneratedReportSerializer(read_only=True)
    accessed_by = BaseUserSerializer(read_only=True)

    class Meta:
        model = ReportAccessLog
        fields = "__all__"
        read_only_fields = ("accessed_at",)


class GeneratedReportAccessSerializer(serializers.ModelSerializer):
    user = BaseUserSerializer(read_only=True)
    report = GeneratedReportSerializer(read_only=True)
    is_expired = serializers.ReadOnlyField()
    is_accessed = serializers.ReadOnlyField()

    class Meta:
        model = GeneratedReportAccess
        fields = "__all__"
        read_only_fields = ("granted_at", "accessed_at", "is_expired", "is_accessed")


class ReportScheduleSerializer(serializers.ModelSerializer):
    report_template = ReportTemplateSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    created_by = BaseUserSerializer(read_only=True)

    class Meta:
        model = ReportSchedule
        fields = "__all__"
        read_only_fields = ("last_run", "created_at", "updated_at")


class ReportNotificationSerializer(serializers.ModelSerializer):
    report = GeneratedReportSerializer(read_only=True)
    sent_to = BaseUserSerializer(read_only=True)

    class Meta:
        model = ReportNotification
        fields = "__all__"
        read_only_fields = ("sent_at",)


class AcademicReportConfigSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)

    class Meta:
        model = AcademicReportConfig
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class TermReportRequestSerializer(serializers.ModelSerializer):
    # Keep student as PrimaryKeyRelatedField for writing, but override to_representation for reading
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    parent = BaseUserSerializer(read_only=True)
    generated_report = GeneratedReportSerializer(read_only=True)

    class Meta:
        model = TermReportRequest
        fields = "__all__"
        read_only_fields = ("requested_at", "completed_at", "status", "parent")

    def to_representation(self, instance):
        """
        Convert the instance to a representation for reading.
        This allows us to return nested data when reading but accept IDs when writing.
        """
        ret = super().to_representation(instance)
        # Convert student ID to nested representation for reading
        if instance.student:
            ret["student"] = StudentSerializer(instance.student).data
        return ret

    def validate(self, data):
        request = self.context.get("request")

        if request and request.user.is_authenticated:
            user = request.user

            if user.user_type == User.PARENT:
                try:
                    # data["student"] is now a Student instance (thanks to PrimaryKeyRelatedField)
                    student = data.get("student")
                    parent_profile = user.parent_profile
                except AttributeError:
                    raise serializers.ValidationError(
                        "Invalid student or parent profile"
                    )

                if not student:
                    raise serializers.ValidationError("Student is required")

                # Check relationships
                is_direct_parent = student.parent == parent_profile
                is_guardian = student.guardians.filter(id=parent_profile.id).exists()

                if not (is_direct_parent or is_guardian):
                    raise serializers.ValidationError(
                        "You can only request reports for your own children"
                    )

        return data
