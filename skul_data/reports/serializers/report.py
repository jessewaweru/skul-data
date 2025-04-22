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


class ReportTemplateSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    created_by = BaseUserSerializer(read_only=True)

    class Meta:
        model = ReportTemplate
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class GeneratedReportSerializer(serializers.ModelSerializer):
    report_type = ReportTemplateSerializer(read_only=True)
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
    student = StudentSerializer(read_only=True)
    parent = BaseUserSerializer(read_only=True)
    generated_report = GeneratedReportSerializer(read_only=True)

    class Meta:
        model = TermReportRequest
        fields = "__all__"
        read_only_fields = ("requested_at", "completed_at", "status")
