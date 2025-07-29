from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.exams.models.exam import (
    ExamType,
    GradingSystem,
    GradeRange,
    Exam,
    ExamSubject,
    ExamResult,
    TermReport,
)
from skul_data.exams.serializers.exam import (
    ExamTypeSerializer,
    GradingSystemSerializer,
    GradeRangeSerializer,
    ExamSerializer,
    ExamSubjectSerializer,
    ExamResultSerializer,
    ExamResultBulkSerializer,
    ExamSubjectResultsSerializer,
    TermReportSerializer,
)
from skul_data.users.permissions.permission import (
    HasRolePermission,
    IsAdministrator,
    IsSchoolAdmin,
    IsTeacher,
)


class ExamTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExamType.objects.all()
    serializer_class = ExamTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(is_default=True)


class GradingSystemViewSet(viewsets.ModelViewSet):
    queryset = GradingSystem.objects.all()
    serializer_class = GradingSystemSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_grading_systems"

    def get_queryset(self):
        return super().get_queryset().filter(school=self.request.user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        grading_system = self.get_object()

        # Remove default from other grading systems
        GradingSystem.objects.filter(school=request.user.school).update(
            is_default=False
        )

        # Set this one as default
        grading_system.is_default = True
        grading_system.save()

        return Response({"status": "default grading system set"})


class GradeRangeViewSet(viewsets.ModelViewSet):
    queryset = GradeRange.objects.all()
    serializer_class = GradeRangeSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_grading_systems"

    def get_queryset(self):
        grading_system_id = self.request.query_params.get("grading_system")
        if grading_system_id:
            return self.queryset.filter(grading_system_id=grading_system_id)
        return self.queryset.none()

    def perform_create(self, serializer):
        grading_system = get_object_or_404(
            GradingSystem,
            pk=self.request.data.get("grading_system"),
            school=self.request.user.school,
        )
        serializer.save(grading_system=grading_system)


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_exams"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["term", "academic_year", "school_class", "exam_type"]

    def get_queryset(self):
        return super().get_queryset().filter(school=self.request.user.school)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, school=self.request.user.school)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        exam = self.get_object()
        exam.is_published = True
        exam.save()

        # Publish all subjects if they haven't been published individually
        exam.subjects.filter(is_published=False).update(is_published=True)

        return Response({"status": "exam published"})

    @action(detail=True, methods=["post"])
    def generate_term_report(self, request, pk=None):
        exam = self.get_object()

        # Get all students in the class
        students = exam.school_class.class_students.filter(
            status="ACTIVE", is_active=True
        )

        for student in students:
            term_report, created = TermReport.objects.get_or_create(
                student=student,
                school_class=exam.school_class,
                term=exam.term,
                academic_year=exam.academic_year,
            )
            term_report.calculate_results()

        return Response({"status": "term reports generated"})

    @action(detail=False, methods=["get"])
    def terms(self, request):
        terms = self.get_queryset().values("term", "academic_year").distinct()
        return Response(list(terms))

    @action(detail=False, methods=["get"])
    def stats(self, request):
        from django.db.models import Count, Avg

        stats = self.get_queryset().aggregate(
            total=Count("id"),
            published=Count("id", filter=Q(is_published=True)),
            upcoming=Count("id", filter=Q(status="Upcoming")),
        )
        return Response(stats)


class ExamSubjectViewSet(viewsets.ModelViewSet):
    queryset = ExamSubject.objects.all()
    serializer_class = ExamSubjectSerializer
    # permission_classes = [IsAuthenticated, (IsAdministrator | IsTeacher)]
    permission_classes = [
        IsAuthenticated,
        (IsSchoolAdmin | IsAdministrator | IsTeacher),
    ]

    def get_queryset(self):
        queryset = self.queryset

        # Filter by exam if provided
        exam_id = self.request.query_params.get("exam")
        if exam_id:
            queryset = queryset.filter(exam_id=exam_id)

        # Teachers can only see subjects they teach
        if self.request.user.user_type == "teacher":
            queryset = queryset.filter(
                Q(teacher=self.request.user.teacher_profile)
                | Q(exam__school_class__class_teacher=self.request.user.teacher_profile)
            )

        return queryset.select_related("exam", "subject", "teacher")

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        exam_subject = self.get_object()
        exam_subject.is_published = True
        exam_subject.save()
        return Response({"status": "subject results published"})

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        exam_subject = self.get_object()
        serializer = ExamSubjectResultsSerializer(exam_subject)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def bulk_update_results(self, request, pk=None):
        exam_subject = self.get_object()
        serializer = ExamResultBulkSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            for result_data in serializer.validated_data:
                student_id = result_data["student_id"]
                defaults = {
                    "score": result_data.get("score"),
                    "is_absent": result_data["is_absent"],
                    "teacher_comment": result_data.get("teacher_comment", ""),
                }

                ExamResult.objects.update_or_create(
                    exam_subject=exam_subject, student_id=student_id, defaults=defaults
                )

        return Response({"status": "results updated"})

    @action(detail=True, methods=["post"])
    def upload_marks(self, request, pk=None):
        exam_subject = self.get_object()
        # Process file upload here
        return Response({"status": "marks uploaded"})


class ExamResultViewSet(viewsets.ModelViewSet):
    queryset = ExamResult.objects.all()
    serializer_class = ExamResultSerializer
    # permission_classes = [IsAuthenticated, (IsAdministrator | IsTeacher)]
    permission_classes = [
        IsAuthenticated,
        (IsSchoolAdmin | IsAdministrator | IsTeacher),
    ]

    def get_queryset(self):
        queryset = self.queryset

        # Filter by exam subject if provided
        exam_subject_id = self.request.query_params.get("exam_subject")
        if exam_subject_id:
            queryset = queryset.filter(exam_subject_id=exam_subject_id)

        # Teachers can only see results for subjects they teach
        if self.request.user.user_type == "teacher":
            queryset = queryset.filter(
                Q(exam_subject__teacher=self.request.user.teacher_profile)
                | Q(
                    exam_subject__exam__school_class__class_teacher=self.request.user.teacher_profile
                )
            )

        return queryset.select_related("exam_subject", "student")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if hasattr(self, "exam_subject"):
            context["exam_subject"] = self.exam_subject
        return context


class TermReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TermReport.objects.all()
    serializer_class = TermReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["term", "academic_year", "school_class", "is_published"]

    def get_queryset(self):
        queryset = self.queryset.filter(school_class__school=self.request.user.school)

        # Parents can only see their children's reports
        if self.request.user.user_type == "parent":
            queryset = queryset.filter(
                Q(student__parent=self.request.user.parent_profile)
                | Q(student__guardians=self.request.user.parent_profile)
            ).distinct()

        # Teachers can only see reports for their classes
        elif self.request.user.user_type == "teacher":
            queryset = queryset.filter(
                Q(school_class__class_teacher=self.request.user.teacher_profile)
                | Q(school_class__teachers=self.request.user.teacher_profile)
            ).distinct()

        return queryset

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        term_report = self.get_object()
        term_report.is_published = True
        term_report.save()
        return Response({"status": "term report published"})
