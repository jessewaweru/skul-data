from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters
from django.db.models import Q, Count, Avg, Sum
from django.http import HttpResponse
from django.utils import timezone
from skul_data.kcse.models.kcse import (
    KCSEResult,
    KCSESchoolPerformance,
    KCSESubjectPerformance,
)
from skul_data.kcse.serializers.kcse import (
    KCSEResultSerializer,
    KCSESchoolPerformanceSerializer,
    KCSEResultUploadSerializer,
    KCSEStudentTemplateSerializer,
    KCSEResultExportSerializer,
    KCSESubjectPerformanceSerializer,
)
from skul_data.users.permissions.permission import (
    IsAdministrator,
    HasRolePermission,
    IsKCSEAdministrator,
)
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


class KCSEResultFilter(filters.FilterSet):
    year = filters.NumberFilter(field_name="year")
    mean_grade = filters.CharFilter(field_name="mean_grade")
    stream = filters.CharFilter(
        field_name="student__student_class__name", lookup_expr="icontains"
    )
    student_name = filters.CharFilter(method="filter_student_name")

    class Meta:
        model = KCSEResult
        fields = ["year", "mean_grade", "is_published"]

    def filter_student_name(self, queryset, name, value):
        return queryset.filter(
            Q(student__first_name__icontains=value)
            | Q(student__last_name__icontains=value)
        )


class KCSEResultViewSet(viewsets.ModelViewSet):
    queryset = KCSEResult.objects.all()
    serializer_class = KCSEResultSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = KCSEResultFilter
    permission_classes = [IsAuthenticated, IsKCSEAdministrator]

    # Set required permissions per action
    required_permission_create = "enter_exam_results"
    required_permission_update = "enter_exam_results"
    required_permission_publish = "publish_exam_results"
    required_permission_view = "view_exam_results"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            return queryset.filter(school=user.school_admin_profile.school)
        elif hasattr(user, "school"):
            return queryset.filter(school=user.school)

        return queryset.none()

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update"]:
            self.required_permission = self.required_permission_create
        elif self.action == "publish":
            self.required_permission = self.required_permission_publish
        else:
            self.required_permission = self.required_permission_view

        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=False, methods=["post"], url_path="upload-results")
    def upload_results(self, request):
        serializer = KCSEResultUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        result = serializer.save()
        log_action(
            request.user,
            f"Uploaded KCSE results for {serializer.validated_data['year']}",
            ActionCategory.CREATE,
            None,
            {
                "year": serializer.validated_data["year"],
                "publish": serializer.validated_data["publish"],
            },
        )

        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="download-template")
    def download_template(self, request):
        serializer = KCSEStudentTemplateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        result = serializer.save()
        response = HttpResponse(result["csv_data"], content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="kcse_template_{serializer.validated_data["year"]}.csv"'
        )

        log_action(
            request.user,
            f"Downloaded KCSE template for {serializer.validated_data['class_name']} {serializer.validated_data['year']}",
            ActionCategory.VIEW,
            None,
            {
                "year": serializer.validated_data["year"],
                "class_name": serializer.validated_data["class_name"],
            },
        )

        return response

    @action(detail=False, methods=["post"], url_path="export-results")
    def export_results(self, request):
        serializer = KCSEResultExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        year = serializer.validated_data.get("year")
        export_format = serializer.validated_data["format"]
        queryset = self.filter_queryset(self.get_queryset())

        if year:
            queryset = queryset.filter(year=year)

        if export_format == "csv":
            return self.export_to_csv(queryset)
        elif export_format == "excel":
            return self.export_to_excel(queryset)
        elif export_format == "pdf":
            return self.export_to_pdf(queryset)

        return Response(
            {"error": "Invalid export format"}, status=status.HTTP_400_BAD_REQUEST
        )

    def export_to_csv(self, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="kcse_results.csv"'

        # Create a CSV writer
        import csv

        writer = csv.writer(response)

        # Write header
        writer.writerow(
            [
                "Index Number",
                "Admission Number",
                "Name",
                "Year",
                "Mean Grade",
                "Mean Points",
                "Division",
            ]
        )

        # Write data
        for result in queryset:
            writer.writerow(
                [
                    result.index_number,
                    result.student.admission_number,
                    result.student.full_name,
                    result.year,
                    result.mean_grade,
                    result.mean_points,
                    result.division,
                ]
            )

        log_action(
            self.request.user,
            "Exported KCSE results to CSV",
            ActionCategory.VIEW,
            None,
            {"count": queryset.count()},
        )

        return response

    def export_to_excel(self, queryset):
        import pandas as pd
        from io import BytesIO

        data = []
        for result in queryset:
            data.append(
                {
                    "Index Number": result.index_number,
                    "Admission Number": result.student.admission_number,
                    "Name": result.student.full_name,
                    "Year": result.year,
                    "Mean Grade": result.mean_grade,
                    "Mean Points": result.mean_points,
                    "Division": result.division,
                }
            )

        df = pd.DataFrame(data)
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine="xlsxwriter")
        df.to_excel(writer, sheet_name="KCSE Results", index=False)
        writer.close()
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="kcse_results.xlsx"'

        log_action(
            self.request.user,
            "Exported KCSE results to Excel",
            ActionCategory.VIEW,
            None,
            {"count": queryset.count()},
        )

        return response

    def export_to_pdf(self, queryset):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="kcse_results.pdf"'

        doc = SimpleDocTemplate(response, pagesize=letter)
        elements = []

        # Add title
        styles = getSampleStyleSheet()
        title = Paragraph("KCSE Examination Results", styles["Title"])
        elements.append(title)

        # Prepare data
        data = [
            [
                "Index",
                "Admission No",
                "Name",
                "Year",
                "Mean Grade",
                "Points",
                "Division",
            ]
        ]

        for result in queryset:
            data.append(
                [
                    result.index_number,
                    result.student.admission_number,
                    result.student.full_name,
                    str(result.year),
                    result.mean_grade,
                    str(result.mean_points),
                    str(result.division),
                ]
            )

        # Create table
        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        elements.append(table)
        doc.build(elements)

        log_action(
            self.request.user,
            "Exported KCSE results to PDF",
            ActionCategory.VIEW,
            None,
            {"count": queryset.count()},
        )

        return response

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        result = self.get_object()
        result.is_published = True
        result.published_at = timezone.now()
        result.save()

        log_action(
            request.user,
            f"Published KCSE result for {result.student.full_name}",
            ActionCategory.UPDATE,
            result,
            {"year": result.year, "mean_grade": result.mean_grade},
        )

        return Response({"status": "published"})

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        result = self.get_object()
        result.is_published = False
        result.published_at = None
        result.save()

        log_action(
            request.user,
            f"Unpublished KCSE result for {result.student.full_name}",
            ActionCategory.UPDATE,
            result,
            {"year": result.year, "mean_grade": result.mean_grade},
        )

        return Response({"status": "unpublished"})


class KCSESchoolPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = KCSESchoolPerformance.objects.all()
    serializer_class = KCSESchoolPerformanceSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ["year"]
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "view_exam_results"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            return queryset.filter(school=user.school_admin_profile.school)
        elif hasattr(user, "school"):
            return queryset.filter(school=user.school)

        return queryset.none()

    @action(detail=False, methods=["get"])
    def comparison(self, request):
        years = request.query_params.get("years", "")
        if not years:
            return Response(
                {"error": "Please specify years parameter (comma-separated)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year_list = [int(year) for year in years.split(",")]
        except ValueError:
            return Response(
                {"error": "Invalid years format. Use comma-separated integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school = (
            request.user.school_admin_profile.school
            if hasattr(request.user, "school_admin_profile")
            else request.user.school
        )
        performances = self.queryset.filter(school=school, year__in=year_list).order_by(
            "year"
        )

        if not performances.exists():
            return Response(
                {"error": "No performance data for the specified years"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Prepare comparison data
        comparison_data = []
        for performance in performances:
            comparison_data.append(
                {
                    "year": performance.year,
                    "mean_grade": performance.mean_grade,
                    "mean_points": float(performance.mean_points),
                    "total_students": performance.total_students,
                    "university_qualified": performance.university_qualified,
                    "qualification_rate": (
                        round(
                            (
                                performance.university_qualified
                                / performance.total_students
                            )
                            * 100,
                            2,
                        )
                        if performance.total_students > 0
                        else 0
                    ),
                }
            )

        log_action(
            request.user,
            f"Viewed KCSE performance comparison for years: {years}",
            ActionCategory.VIEW,
            None,
            {"years": years},
        )

        return Response(comparison_data)

    @action(detail=False, methods=["get"])
    def trends(self, request):
        school = (
            request.user.school_admin_profile.school
            if hasattr(request.user, "school_admin_profile")
            else request.user.school
        )
        performances = self.queryset.filter(school=school).order_by("year")

        if not performances.exists():
            return Response(
                {"error": "No performance data available"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Prepare trend data
        trend_data = []
        for performance in performances:
            trend_data.append(
                {
                    "year": performance.year,
                    "mean_points": float(performance.mean_points),
                    "university_qualified": performance.university_qualified,
                    "total_students": performance.total_students,
                }
            )

        log_action(
            request.user,
            "Viewed KCSE performance trends",
            ActionCategory.VIEW,
            None,
            {"count": performances.count()},
        )

        return Response(trend_data)


class KCSESubjectPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = KCSESubjectPerformance.objects.all()
    serializer_class = KCSESubjectPerformanceSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ["year", "subject"]
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "view_exam_results"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == "school_admin":
            return queryset.filter(
                school_performance__school=user.school_admin_profile.school
            )
        elif hasattr(user, "school"):
            return queryset.filter(school_performance__school=user.school)

        return queryset.none()

    @action(detail=False, methods=["get"])
    def subject_comparison(self, request):
        subject_code = request.query_params.get("subject")
        years = request.query_params.get("years", "")

        if not subject_code or not years:
            return Response(
                {"error": "Please specify subject and years parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year_list = [int(year) for year in years.split(",")]
        except ValueError:
            return Response(
                {"error": "Invalid years format. Use comma-separated integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school = (
            request.user.school_admin_profile.school
            if hasattr(request.user, "school_admin_profile")
            else request.user.school
        )
        performances = (
            self.queryset.filter(
                subject__code=subject_code,
                school_performance__school=school,
                school_performance__year__in=year_list,
            )
            .select_related("school_performance")
            .order_by("school_performance__year")
        )

        if not performances.exists():
            return Response(
                {"error": "No performance data for the specified subject and years"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Prepare comparison data
        comparison_data = []
        for performance in performances:
            comparison_data.append(
                {
                    "year": performance.school_performance.year,
                    "subject": performance.subject.name,
                    "mean_score": float(performance.mean_score),
                    "mean_grade": performance.mean_grade,
                    "total_students": performance.total_students,
                    "passed": performance.passed,
                    "pass_rate": (
                        round(
                            (performance.passed / performance.total_students) * 100, 2
                        )
                        if performance.total_students > 0
                        else 0
                    ),
                    "subject_teacher": (
                        performance.subject_teacher.user.get_full_name()
                        if performance.subject_teacher
                        else None
                    ),
                }
            )

        log_action(
            request.user,
            f"Viewed subject comparison for {subject_code} across years: {years}",
            ActionCategory.VIEW,
            None,
            {"subject": subject_code, "years": years},
        )

        return Response(comparison_data)

    @action(detail=False, methods=["get"])
    def teacher_performance(self, request):
        teacher_id = request.query_params.get("teacher_id")
        if not teacher_id:
            return Response(
                {"error": "Please specify teacher_id parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school = (
            request.user.school_admin_profile.school
            if hasattr(request.user, "school_admin_profile")
            else request.user.school
        )
        performances = (
            self.queryset.filter(
                subject_teacher_id=teacher_id, school_performance__school=school
            )
            .select_related("subject", "school_performance")
            .order_by("school_performance__year")
        )

        if not performances.exists():
            return Response(
                {"error": "No performance data for the specified teacher"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Prepare performance data
        performance_data = []
        for performance in performances:
            performance_data.append(
                {
                    "year": performance.school_performance.year,
                    "subject": performance.subject.name,
                    "mean_score": float(performance.mean_score),
                    "mean_grade": performance.mean_grade,
                    "total_students": performance.total_students,
                    "passed": performance.passed,
                    "pass_rate": (
                        round(
                            (performance.passed / performance.total_students) * 100, 2
                        )
                        if performance.total_students > 0
                        else 0
                    ),
                }
            )

        log_action(
            request.user,
            f"Viewed teacher performance for teacher ID: {teacher_id}",
            ActionCategory.VIEW,
            None,
            {"teacher_id": teacher_id},
        )

        return Response(performance_data)
