from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Max, Min
from django_filters.rest_framework import DjangoFilterBackend
from skul_data.exams.models.exam import (
    ExamType,
    GradingSystem,
    GradeRange,
    Exam,
    ExamSubject,
    ExamResult,
    TermReport,
    ExamConsolidationRule,
    ConsolidatedReport,
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
    ExamConsolidationRuleSerializer,
    ConsolidatedReportSerializer,
)
from skul_data.users.permissions.permission import (
    HasRolePermission,
    IsAdministrator,
    IsSchoolAdmin,
    IsTeacher,
)
from skul_data.students.models.student import Student
from collections import defaultdict
from django.utils import timezone


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


# class ExamViewSet(viewsets.ModelViewSet):
#     queryset = Exam.objects.all()
#     serializer_class = ExamSerializer
#     permission_classes = [IsAuthenticated, HasRolePermission]
#     required_permission = "manage_exams"
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ["term", "academic_year", "school_class", "exam_type"]

#     def get_queryset(self):
#         return super().get_queryset().filter(school=self.request.user.school)

#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user, school=self.request.user.school)

#     @action(detail=True, methods=["post"])
#     def publish(self, request, pk=None):
#         exam = self.get_object()
#         exam.is_published = True
#         exam.save()

#         # Publish all subjects if they haven't been published individually
#         exam.subjects.filter(is_published=False).update(is_published=True)

#         return Response({"status": "exam published"})

#     @action(detail=True, methods=["post"])
#     def generate_term_report(self, request, pk=None):
#         exam = self.get_object()

#         # Get all students in the class
#         students = exam.school_class.class_students.filter(
#             status="ACTIVE", is_active=True
#         )

#         for student in students:
#             term_report, created = TermReport.objects.get_or_create(
#                 student=student,
#                 school_class=exam.school_class,
#                 term=exam.term,
#                 academic_year=exam.academic_year,
#             )
#             term_report.calculate_results()

#         return Response({"status": "term reports generated"})

#     @action(detail=False, methods=["get"])
#     def terms(self, request):
#         terms = self.get_queryset().values("term", "academic_year").distinct()
#         return Response(list(terms))

#     @action(detail=False, methods=["get"])
#     def stats(self, request):
#         from django.db.models import Count, Avg

#         stats = self.get_queryset().aggregate(
#             total=Count("id"),
#             published=Count("id", filter=Q(is_published=True)),
#             upcoming=Count("id", filter=Q(status="Upcoming")),
#         )
#         return Response(stats)


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

    def _get_time_filtered_exams(self, time_range):
        """Helper method to get exams based on time range"""
        user_school = getattr(self.request.user, "school", None)
        if not user_school:
            return Exam.objects.none()

        queryset = Exam.objects.filter(school=user_school)
        today = timezone.now().date()
        current_year = today.year

        if time_range == "current_term":
            # Get current term based on today's date
            current_month = today.month
            if current_month <= 4:
                current_term = "Term 1"
            elif current_month <= 8:
                current_term = "Term 2"
            else:
                current_term = "Term 3"

            queryset = queryset.filter(
                term=current_term, academic_year=str(current_year)
            )
        elif time_range == "last_term":
            # Get previous term
            current_month = today.month
            if current_month <= 4:
                prev_term = "Term 3"
                prev_year = str(current_year - 1)
            elif current_month <= 8:
                prev_term = "Term 1"
                prev_year = str(current_year)
            else:
                prev_term = "Term 2"
                prev_year = str(current_year)

            queryset = queryset.filter(term=prev_term, academic_year=prev_year)
        elif time_range == "current_year":
            queryset = queryset.filter(academic_year=str(current_year))
        elif time_range == "last_year":
            queryset = queryset.filter(academic_year=str(current_year - 1))
        # For "all_time", return all exams

        return queryset.filter(is_published=True)

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

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def stats(self, request):
        """Get exam statistics for dashboard"""
        try:
            from django.utils import timezone

            # Get user's school
            user_school = getattr(request.user, "school", None)
            if not user_school:
                return Response(
                    {
                        "upcomingExams": 0,
                        "examsInProgress": 0,
                        "marksEntered": 0,
                        "resultsPublished": 0,
                        "totalExams": 0,
                        "publishedExams": 0,
                        "completedExams": 0,
                    }
                )

            # Get queryset for user's school
            queryset = Exam.objects.filter(school=user_school)
            today = timezone.now().date()

            # Calculate basic exam stats
            total_exams = queryset.count()
            published_exams = queryset.filter(is_published=True).count()
            upcoming_exams = queryset.filter(start_date__gt=today).count()
            ongoing_exams = queryset.filter(
                start_date__lte=today, end_date__gte=today
            ).count()
            completed_exams = queryset.filter(end_date__lt=today).count()

            # Get exam subjects and results stats
            exam_subjects = ExamSubject.objects.filter(exam__school=user_school)
            subjects_with_marks = (
                exam_subjects.filter(results__isnull=False).distinct().count()
            )

            # Get published results count
            published_results = ExamResult.objects.filter(
                exam_subject__exam__school=user_school, exam_subject__is_published=True
            ).count()

            response_data = {
                "upcomingExams": upcoming_exams,
                "examsInProgress": ongoing_exams,
                "marksEntered": subjects_with_marks,
                "resultsPublished": published_results,
                "totalExams": total_exams,
                "publishedExams": published_exams,
                "completedExams": completed_exams,
            }

            return Response(response_data)

        except Exception as e:
            # Log the error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in exam stats endpoint: {str(e)}")

            # Return default values if there's an error
            return Response(
                {
                    "upcomingExams": 0,
                    "examsInProgress": 0,
                    "marksEntered": 0,
                    "resultsPublished": 0,
                    "totalExams": 0,
                    "publishedExams": 0,
                    "completedExams": 0,
                    "error": "Unable to fetch statistics",
                }
            )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def recent(self, request):
        """Get recent exams for dashboard table"""
        try:
            # Get user's school
            user_school = getattr(request.user, "school", None)
            if not user_school:
                return Response([])

            # Get recent exams
            queryset = (
                Exam.objects.filter(school=user_school)
                .select_related("exam_type", "school_class")
                .order_by("-created_at")[:10]
            )

            recent_exams = []
            for exam in queryset:
                recent_exams.append(
                    {
                        "id": exam.id,
                        "name": exam.name,
                        "exam_type": exam.exam_type.name if exam.exam_type else "N/A",
                        "school_class": (
                            exam.school_class.name if exam.school_class else "N/A"
                        ),
                        "status": exam.status,
                        "is_published": exam.is_published,
                        "start_date": (
                            exam.start_date.isoformat() if exam.start_date else None
                        ),
                        "end_date": (
                            exam.end_date.isoformat() if exam.end_date else None
                        ),
                        "term": exam.term,
                        "academic_year": exam.academic_year,
                    }
                )

            return Response(recent_exams)

        except Exception as e:
            # Log the error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in exam recent endpoint: {str(e)}")

            return Response([])  # Return empty list if there's an error

    @action(detail=False, methods=["get"])
    def analytics_performance(self, request):
        """Get performance analytics"""
        try:
            time_range = request.query_params.get("range", "current_term")
            exams = self._get_time_filtered_exams(time_range)

            if not exams.exists():
                return Response(
                    {"labels": [], "averages": [], "highest": [], "lowest": []}
                )

            # Get exam results for performance analysis
            exam_results_by_exam = {}

            for exam in exams.select_related("exam_type"):
                exam_subjects = ExamSubject.objects.filter(exam=exam)
                results = ExamResult.objects.filter(
                    exam_subject__in=exam_subjects, is_absent=False
                ).aggregate(
                    avg_score=Avg("score"),
                    max_score=Max("score"),
                    min_score=Min("score"),
                )

                exam_label = f"{exam.exam_type.name} - {exam.term}"
                exam_results_by_exam[exam_label] = {
                    "average": float(results["avg_score"] or 0),
                    "highest": float(results["max_score"] or 0),
                    "lowest": float(results["min_score"] or 0),
                }

            # Prepare data for frontend
            labels = list(exam_results_by_exam.keys())
            averages = [exam_results_by_exam[label]["average"] for label in labels]
            highest = [exam_results_by_exam[label]["highest"] for label in labels]
            lowest = [exam_results_by_exam[label]["lowest"] for label in labels]

            return Response(
                {
                    "labels": labels,
                    "averages": averages,
                    "highest": highest,
                    "lowest": lowest,
                }
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in performance analytics: {str(e)}")

            return Response(
                {
                    "labels": [],
                    "averages": [],
                    "highest": [],
                    "lowest": [],
                    "error": str(e),
                }
            )

    @action(detail=False, methods=["get"])
    def analytics_subject_trends(self, request):
        """Get subject trends analytics"""
        try:
            time_range = request.query_params.get("range", "current_term")
            exams = self._get_time_filtered_exams(time_range)

            if not exams.exists():
                return Response({"labels": [], "datasets": []})

            # Get subject performance over time
            subject_trends = defaultdict(list)
            exam_labels = []

            for exam in exams.order_by("start_date").select_related("exam_type"):
                exam_label = f"{exam.exam_type.name} - {exam.term}"
                exam_labels.append(exam_label)

                # Get subjects for this exam
                exam_subjects = ExamSubject.objects.filter(exam=exam).select_related(
                    "subject"
                )

                for exam_subject in exam_subjects:
                    subject_name = exam_subject.subject.name
                    avg_score = ExamResult.objects.filter(
                        exam_subject=exam_subject, is_absent=False
                    ).aggregate(avg_score=Avg("score"))["avg_score"]

                    subject_trends[subject_name].append(float(avg_score or 0))

            # Ensure all subjects have data for all exams (fill missing with 0)
            datasets = []
            colors = [
                "#6B1B9A",
                "#4A148C",
                "#311B92",
                "#1A237E",
                "#0D47A1",
                "#01579B",
                "#006064",
                "#004D40",
                "#1B5E20",
                "#33691E",
            ]

            for i, (subject_name, scores) in enumerate(subject_trends.items()):
                # Pad scores to match exam_labels length
                while len(scores) < len(exam_labels):
                    scores.append(0)

                color = colors[i % len(colors)]
                datasets.append(
                    {
                        "label": subject_name,
                        "data": scores[: len(exam_labels)],  # Ensure same length
                        "borderColor": color,
                        "backgroundColor": f"{color}1A",  # Add transparency
                        "tension": 0.1,
                    }
                )

            return Response({"labels": exam_labels, "datasets": datasets})

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in subject trends analytics: {str(e)}")

            return Response({"labels": [], "datasets": [], "error": str(e)})

    @action(detail=False, methods=["get"])
    def analytics_class_comparison(self, request):
        """Get class comparison analytics"""
        try:
            time_range = request.query_params.get("range", "current_term")
            exams = self._get_time_filtered_exams(time_range)

            if not exams.exists():
                return Response({"labels": [], "data": []})

            # Get class performance comparison
            class_performance = {}

            for exam in exams.select_related("school_class"):
                class_name = exam.school_class.name

                # Get average score for this class in this exam
                exam_subjects = ExamSubject.objects.filter(exam=exam)
                class_avg = ExamResult.objects.filter(
                    exam_subject__in=exam_subjects, is_absent=False
                ).aggregate(avg_score=Avg("score"))["avg_score"]

                if class_name not in class_performance:
                    class_performance[class_name] = []

                if class_avg is not None:
                    class_performance[class_name].append(float(class_avg))

            # Calculate overall average per class
            class_averages = {}
            for class_name, scores in class_performance.items():
                if scores:
                    class_averages[class_name] = sum(scores) / len(scores)

            # Prepare data for pie chart
            labels = list(class_averages.keys())
            data = list(class_averages.values())

            return Response({"labels": labels, "data": data})

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in class comparison analytics: {str(e)}")

            return Response({"labels": [], "data": [], "error": str(e)})


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


class ExamConsolidationRuleViewSet(viewsets.ModelViewSet):
    queryset = ExamConsolidationRule.objects.all()
    serializer_class = ExamConsolidationRuleSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_exams"

    def get_queryset(self):
        return self.queryset.filter(school=self.request.user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)

    @action(detail=False, methods=["get"])
    def defaults(self, request):
        """Returns default consolidation rules (Opener 20%, Midterm 20%, Endterm 60%)"""
        default_rules = [
            {"exam_type": "Opener", "weight": 20},
            {"exam_type": "Midterm", "weight": 20},
            {"exam_type": "Endterm", "weight": 60},
        ]
        return Response(default_rules)


class ConsolidatedReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ConsolidatedReport.objects.all()
    serializer_class = ConsolidatedReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["term", "academic_year", "school_class", "is_published"]

    def get_queryset(self):
        queryset = self.queryset.filter(school_class__school=self.request.user.school)

        # Teachers can only see their class reports
        if self.request.user.user_type == "teacher":
            queryset = queryset.filter(
                Q(school_class__class_teacher=self.request.user.teacher_profile)
                | Q(school_class__teachers=self.request.user.teacher_profile)
            )

        # Parents can only see their children's reports
        elif self.request.user.user_type == "parent":
            queryset = queryset.filter(
                Q(student__parent=self.request.user.parent_profile)
                | Q(student__guardians=self.request.user.parent_profile)
            )

        return queryset

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generates consolidated reports for a term with transaction safety"""
        term = request.data.get("term")
        academic_year = request.data.get("academic_year")

        if not term or not academic_year:
            return Response(
                {"error": "Term and academic_year are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():  # Ensure all-or-nothing operation
                school = request.user.school
                consolidation_rules = ExamConsolidationRule.objects.filter(
                    school=school, is_active=True
                ).select_related("exam_type")

                # Verify weights sum to 100%
                total_weight = sum(rule.weight for rule in consolidation_rules)
                if total_weight != 100:
                    return Response(
                        {
                            "error": f"Consolidation rules must sum to 100% (current: {total_weight}%)"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Get all active students in the school
                students = Student.objects.filter(
                    school_class__school=school, status="ACTIVE", is_active=True
                ).select_related("school_class")

                # Get all relevant exams for this term
                exams = Exam.objects.filter(
                    school=school,
                    term=term,
                    academic_year=academic_year,
                    is_published=True,
                ).prefetch_related("subjects")

                # Process each student
                for student in students:
                    student_results = []
                    total_weighted_score = 0

                    # Calculate contribution from each exam type
                    for rule in consolidation_rules:
                        exam = exams.filter(
                            exam_type=rule.exam_type, school_class=student.school_class
                        ).first()

                        if not exam:
                            continue

                        # Get student's results for this exam
                        exam_results = ExamResult.objects.filter(
                            exam_subject__exam=exam, student=student, is_absent=False
                        ).select_related("exam_subject")

                        if not exam_results.exists():
                            continue

                        # Calculate exam average
                        exam_average = (
                            exam_results.aggregate(avg_score=Avg("score"))["avg_score"]
                            or 0
                        )

                        # Apply weighting
                        weighted_score = (exam_average * rule.weight) / 100
                        total_weighted_score += weighted_score

                        student_results.append(
                            {
                                "exam_type": rule.exam_type.name,
                                "exam_id": exam.id,
                                "raw_average": float(exam_average),
                                "weight": float(rule.weight),
                                "weighted_score": float(weighted_score),
                            }
                        )

                    # Calculate class position (requires all students to be processed)
                    # This is simplified - in production you'd batch process
                    class_students = Student.objects.filter(
                        school_class=student.school_class,
                        status="ACTIVE",
                        is_active=True,
                    )
                    position = (
                        class_students.filter(
                            consolidatedreport__term=term,
                            consolidatedreport__academic_year=academic_year,
                            consolidatedreport__average_score__gt=total_weighted_score,
                        ).count()
                        + 1
                    )

                    # Get grade from grading system
                    grading_system = GradingSystem.objects.filter(
                        school=school, is_default=True
                    ).first()

                    grade = "N/A"
                    if grading_system:
                        grade_range = grading_system.grade_ranges.filter(
                            min_score__lte=total_weighted_score,
                            max_score__gte=total_weighted_score,
                        ).first()
                        grade = grade_range.grade if grade_range else "N/A"

                    # Create/update consolidated report
                    ConsolidatedReport.objects.update_or_create(
                        student=student,
                        school_class=student.school_class,
                        term=term,
                        academic_year=academic_year,
                        defaults={
                            "total_score": total_weighted_score * len(student_results),
                            "average_score": total_weighted_score,
                            "overall_grade": grade,
                            "overall_position": position,
                            "details": {
                                "breakdown": student_results,
                                "rules_used": [
                                    {"exam_type": r.exam_type.name, "weight": r.weight}
                                    for r in consolidation_rules
                                ],
                            },
                        },
                    )

                return Response(
                    {
                        "status": f"Successfully generated reports for {students.count()} students"
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return Response(
                {"error": f"Report generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
