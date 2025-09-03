from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from skul_data.users.models.teacher import (
    Teacher,
    TeacherWorkload,
    TeacherAttendance,
    TeacherDocument,
)
from skul_data.users.serializers.teacher import (
    TeacherSerializer,
    TeacherCreateSerializer,
    TeacherStatusChangeSerializer,
    TeacherAssignmentSerializer,
    TeacherSubjectAssignmentSerializer,
    TeacherWorkloadSerializer,
    TeacherAttendanceSerializer,
    TeacherDocumentSerializer,
)
from skul_data.users.permissions.permission import IsAdministrator, IsTeacher
from skul_data.users.permissions.permission import HasRolePermission
from skul_data.users.models.base_user import User
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "school",
        "status",
        "is_class_teacher",
        "is_department_head",
        "subjects_taught",
        "assigned_classes",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "qualification",
        "specialization",
        "payroll_number",
    ]
    required_permission = "manage_teachers"
    # permission_classes = [IsAuthenticated, HasRolePermission]

    def get_serializer_class(self):
        if self.action == "create":
            return TeacherCreateSerializer
        return TeacherSerializer

    # def get_permissions(self):
    #     if self.action in [
    #         "create",
    #         "update",
    #         "partial_update",
    #         "destroy",
    #         "change_status",
    #         "assign_classes",
    #         "assign_subjects",
    #     ]:
    #         return [IsAdministrator()]
    #     return [IsAuthenticated()]

    # Method-specific permissions for certain actions
    required_permission_post = "create_teacher"  # Used for create action
    required_permission_put = "update_teacher"  # Used for update action
    required_permission_patch = "update_teacher"  # Used for partial_update action
    required_permission_delete = "manage_teachers"  # Used for delete action

    # def get_queryset(self):
    #     queryset = super().get_queryset()
    #     user = self.request.user

    #     if user.user_type == User.SCHOOL_ADMIN:
    #         return queryset

    #     school = getattr(user, "school", None)
    #     if not school:
    #         return Teacher.objects.none()

    #     queryset = queryset.filter(school=school)

    #     # Teachers can only see their own profile
    #     if user.user_type == "teacher":
    #         return queryset.filter(user=user)

    #     return queryset.select_related("user", "school").prefetch_related(
    #         "subjects_taught", "assigned_classes"
    #     )

    def get_queryset(self):
        print(f"TeacherViewSet request params: {self.request.query_params}")
        print(f"Authenticated user: {self.request.user}")
        print(
            f"User school admin profile: {getattr(self.request.user, 'school_admin_profile', None)}"
        )
        queryset = super().get_queryset()
        user = self.request.user

        # Get school filter from query params
        school_id = self.request.query_params.get("school")
        school_code = self.request.query_params.get("school_code")

        # First try to filter by explicit parameters
        if school_code:
            return queryset.filter(school__code=school_code)
        if school_id:
            return queryset.filter(school_id=school_id)

        # For school admins, auto-filter to their school
        if user.user_type == User.SCHOOL_ADMIN:
            if (
                hasattr(user, "school_admin_profile")
                and user.school_admin_profile.school
            ):
                return queryset.filter(school=user.school_admin_profile.school)

        # For other authenticated users, return none unless they have permissions
        return queryset.none()

    def perform_create(self, serializer):
        school = self.request.user.school
        serializer.save(school=school)

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        teacher = self.get_object()
        serializer = TeacherStatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Set the current user on the teacher instance so the signal can access it
        teacher._current_user = request.user

        teacher.status = serializer.validated_data["status"]
        if teacher.status == "TERMINATED":
            teacher.termination_date = serializer.validated_data["termination_date"]
        teacher.save()

        return Response(TeacherSerializer(teacher).data, status=status.HTTP_200_OK)

    # Add specific required permission for change_status action
    change_status.required_permission = "change_teacher_status"

    @action(detail=True, methods=["post"])
    def assign_classes(self, request, pk=None):
        teacher = self.get_object()
        serializer = TeacherAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        classes = serializer.validated_data["class_ids"]
        action = serializer.validated_data["action"]
        current_classes = list(teacher.assigned_classes.values_list("id", flat=True))

        print(f"About to log class assignment: action={action}, classes={classes}")

        if action == "ADD":
            teacher.assigned_classes.add(*classes)
            log_action(
                user=request.user,
                action="Teacher classes add operation",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "CLASS_ADD",
                    "added_classes": [c.id for c in classes],
                    "current_classes": list(
                        teacher.assigned_classes.values_list("id", flat=True)
                    ),
                    "teacher_id": teacher.id,
                },
            )
        elif action == "REMOVE":
            teacher.assigned_classes.remove(*classes)
            log_action(
                user=request.user,
                action="Teacher classes remove operation",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "CLASS_REMOVE",
                    "removed_classes": [c.id for c in classes],
                    "current_classes": list(
                        teacher.assigned_classes.values_list("id", flat=True)
                    ),
                    "teacher_id": teacher.id,
                },
            )
        elif action == "REPLACE":
            previous_classes = current_classes
            teacher.assigned_classes.set(classes)
            log_action(
                user=request.user,
                action="Teacher classes replace operation",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "CLASS_REPLACE",
                    "previous_classes": previous_classes,
                    "new_classes": [c.id for c in classes],
                    "teacher_id": teacher.id,
                },
            )

        return Response(TeacherSerializer(teacher).data, status=status.HTTP_200_OK)

    # Add specific required permission for assign_classes action
    assign_classes.required_permission = "assign_classes"

    @action(detail=True, methods=["post"])
    def assign_subjects(self, request, pk=None):
        teacher = self.get_object()
        serializer = TeacherSubjectAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subjects = serializer.validated_data["subject_ids"]
        action = serializer.validated_data["action"]
        current_subjects = list(teacher.subjects_taught.values_list("id", flat=True))

        print(f"Processing subject assignment: {action} {subjects}")

        if action == "ADD":
            teacher.subjects_taught.add(*subjects)
            log_action(
                user=request.user,
                action="Teacher subjects add operation",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "SUBJECT_ADD",
                    "added_subjects": [s.id for s in subjects],
                    "current_subjects": list(
                        teacher.subjects_taught.values_list("id", flat=True)
                    ),
                    "teacher_id": teacher.id,
                },
            )
        elif action == "REMOVE":
            teacher.subjects_taught.remove(*subjects)
            log_action(
                user=request.user,
                action="Teacher subjects remove operation",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "SUBJECT_REMOVE",
                    "removed_subjects": [s.id for s in subjects],
                    "current_subjects": list(
                        teacher.subjects_taught.values_list("id", flat=True)
                    ),
                    "teacher_id": teacher.id,
                },
            )
        elif action == "REPLACE":
            previous_subjects = current_subjects
            teacher.subjects_taught.set(subjects)
            log_action(
                user=request.user,
                action="Teacher subjects replace operation",
                category=ActionCategory.UPDATE,
                obj=teacher,
                metadata={
                    "action_type": "SUBJECT_REPLACE",
                    "previous_subjects": previous_subjects,
                    "new_subjects": [s.id for s in subjects],
                    "teacher_id": teacher.id,
                },
            )

        return Response(TeacherSerializer(teacher).data, status=status.HTTP_200_OK)

    # Add specific required permission for assign_subjects action
    assign_subjects.required_permission = "assign_subjects"

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        # Basic counts
        total_teachers = queryset.count()
        teachers_by_status = queryset.values("status").annotate(count=Count("id"))

        # Experience distribution
        experience_distribution = (
            queryset.values("years_of_experience")
            .annotate(count=Count("id"))
            .order_by("years_of_experience")
        )

        # Class assignments
        class_assignments = (
            queryset.annotate(class_count=Count("assigned_classes"))
            .values("class_count")
            .annotate(teacher_count=Count("id"))
            .order_by("class_count")
        )

        # Subject distribution
        subject_distribution = (
            queryset.annotate(subject_count=Count("subjects_taught"))
            .values("subject_count")
            .annotate(teacher_count=Count("id"))
            .order_by("subject_count")
        )

        return Response(
            {
                "total_teachers": total_teachers,
                "teachers_by_status": teachers_by_status,
                "experience_distribution": experience_distribution,
                "class_assignments": class_assignments,
                "subject_distribution": subject_distribution,
            }
        )

    # Add specific required permission for analytics action
    analytics.required_permission = "view_analytics"

    def list(self, request, *args, **kwargs):
        # Debug prints
        print("\n=== TeacherViewSet Debug ===")
        print(
            f"Authenticated User: {request.user} (ID: {request.user.id if request.user.is_authenticated else None})"
        )
        print(f"User Type: {getattr(request.user, 'user_type', None)}")
        print(f"Query Params: {request.query_params}")
        print(f"School Filter: {request.query_params.get('school')}")

        # Print SQL query that will be executed
        queryset = self.filter_queryset(self.get_queryset())
        print(f"SQL Query: {str(queryset.query)}")

        response = super().list(request, *args, **kwargs)

        # Print response data (be careful with large datasets)
        print(f"Response Data Count: {len(response.data)}")
        return response


class TeacherWorkloadViewSet(viewsets.ModelViewSet):
    queryset = TeacherWorkload.objects.all()
    serializer_class = TeacherWorkloadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["teacher", "school_class", "subject", "term", "school_year"]
    permission_classes = [IsAdministrator | IsTeacher]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == User.SCHOOL_ADMIN:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return TeacherWorkload.objects.none()

        queryset = queryset.filter(teacher__school=school)

        if user.user_type == "teacher":
            return queryset.filter(teacher__user=user)

        return queryset


class TeacherAttendanceViewSet(viewsets.ModelViewSet):
    queryset = TeacherAttendance.objects.all()
    serializer_class = TeacherAttendanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["teacher", "date", "status"]
    permission_classes = [IsAdministrator]

    # def get_queryset(self):
    #     queryset = super().get_queryset()
    #     user = self.request.user

    #     if user.user_type == User.SCHOOL_ADMIN:
    #         return queryset

    #     school = getattr(user, "school", None)
    #     if not school:
    #         return TeacherAttendance.objects.none()

    #     return queryset.filter(teacher__school=school)

    def get_queryset(self):
        user = self.request.user
        school = user.school

        if not school:
            return Teacher.objects.none()

        # Always filter by school
        return Teacher.objects.filter(school=school)


# class TeacherDocumentViewSet(viewsets.ModelViewSet):
#     queryset = TeacherDocument.objects.all()
#     serializer_class = TeacherDocumentSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter]
#     filterset_fields = ["teacher", "document_type", "is_confidential"]
#     search_fields = ["title", "description"]

#     def get_permissions(self):
#         if self.action in ["create", "update", "destroy"]:
#             return [IsAdministrator()]
#         return [IsAuthenticated()]

#     def get_queryset(self):
#         queryset = super().get_queryset()
#         user = self.request.user

#         if user.user_type == User.SCHOOL_ADMIN:
#             return queryset

#         school = getattr(user, "school", None)
#         if not school:
#             return TeacherDocument.objects.none()

#         queryset = queryset.filter(teacher__school=school)

#         if user.user_type == "teacher":
#             return queryset.filter(Q(teacher__user=user) | Q(is_confidential=False))

#         return queryset

#     def perform_create(self, serializer):
#         serializer.save(uploaded_by=self.request.user)

#     def destroy(self, request, *args, **kwargs):
#         instance = self.get_object()

#         # Log before deletion
#         log_action(
#             user=request.user,
#             action=f"Deleted teacher document: {instance.title}",
#             category=ActionCategory.DELETE,
#             obj=instance,
#             metadata={
#                 "document_type": instance.document_type,
#                 "teacher_id": instance.teacher.id,
#                 "was_confidential": instance.is_confidential,
#             },
#         )

#         try:
#             self.perform_destroy(instance)
#             return Response(status=status.HTTP_204_NO_CONTENT)
#         except Exception as e:
#             # Ensure log exists even if deletion fails
#             return Response(
#                 {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


class TeacherDocumentViewSet(viewsets.ModelViewSet):
    queryset = TeacherDocument.objects.all()
    serializer_class = TeacherDocumentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["teacher", "document_type", "is_confidential"]
    search_fields = ["title", "description"]

    def get_permissions(self):
        if self.action in ["create", "update", "destroy"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Fixed queryset method to properly handle school filtering and permissions"""
        print(f"=== TeacherDocumentViewSet get_queryset DEBUG ===")
        print(f"User: {self.request.user}")
        print(f"User type: {getattr(self.request.user, 'user_type', 'None')}")
        print(f"Query params: {self.request.query_params}")

        queryset = super().get_queryset()
        user = self.request.user

        # Debug: Print total documents in system
        total_docs = queryset.count()
        print(f"Total documents in system: {total_docs}")

        # Handle different user types
        if user.user_type == User.SCHOOL_ADMIN:
            print("User is SCHOOL_ADMIN, getting school...")

            # Get school from user's profile
            school = None
            if hasattr(user, "school_admin_profile") and user.school_admin_profile:
                school = user.school_admin_profile.school
                print(f"School from admin profile: {school}")

            if school:
                # Filter documents to only show documents for teachers in this school
                school_queryset = queryset.filter(teacher__school=school)
                print(f"Documents for school {school.id}: {school_queryset.count()}")

                # Debug: Show some examples
                for doc in school_queryset[:3]:
                    print(f"  - Doc {doc.id}: {doc.title} (Teacher: {doc.teacher.id})")

                return school_queryset
            else:
                print("No school found for admin user - returning empty queryset")
                return TeacherDocument.objects.none()

        elif user.user_type == User.TEACHER:
            print("User is TEACHER")
            # Teachers can see their own documents and non-confidential documents
            teacher_profile = getattr(user, "teacher_profile", None)
            if teacher_profile:
                school = teacher_profile.school
                school_queryset = queryset.filter(teacher__school=school)
                # Filter to own documents OR non-confidential documents
                filtered_queryset = school_queryset.filter(
                    Q(teacher=teacher_profile) | Q(is_confidential=False)
                )
                print(f"Documents for teacher: {filtered_queryset.count()}")
                return filtered_queryset
            else:
                print("No teacher profile found - returning empty queryset")
                return TeacherDocument.objects.none()

        elif user.is_superuser:
            print("User is superuser - returning all documents")
            return queryset

        else:
            print(f"Unknown user type: {user.user_type} - returning empty queryset")
            return TeacherDocument.objects.none()

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    def list(self, request, *args, **kwargs):
        """Override list to add debugging"""
        print(f"\n=== TeacherDocumentViewSet LIST DEBUG ===")
        print(f"Request params: {request.query_params}")
        print(f"User: {request.user}")

        # Get the queryset
        queryset = self.filter_queryset(self.get_queryset())
        print(f"Filtered queryset count: {queryset.count()}")

        # Check for teacher filter specifically
        teacher_filter = request.query_params.get("teacher")
        if teacher_filter:
            print(f"Teacher filter applied: {teacher_filter}")
            teacher_docs = queryset.filter(teacher=teacher_filter)
            print(f"Documents for teacher {teacher_filter}: {teacher_docs.count()}")

            for doc in teacher_docs:
                print(
                    f"  - Doc {doc.id}: {doc.title} (Teacher: {doc.teacher.id}, School: {doc.teacher.school.id})"
                )

        response = super().list(request, *args, **kwargs)
        print(f"Response data type: {type(response.data)}")

        if isinstance(response.data, dict) and "results" in response.data:
            print(f"Response contains {len(response.data['results'])} results")
        elif isinstance(response.data, list):
            print(f"Response contains {len(response.data)} items")

        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Log before deletion
        log_action(
            user=request.user,
            action=f"Deleted teacher document: {instance.title}",
            category=ActionCategory.DELETE,
            obj=instance,
            metadata={
                "document_type": instance.document_type,
                "teacher_id": instance.teacher.id,
                "was_confidential": instance.is_confidential,
            },
        )

        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
