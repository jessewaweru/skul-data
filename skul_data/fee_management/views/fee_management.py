import csv
import io
from datetime import datetime
from decimal import Decimal
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from skul_data.users.permissions.permission import (
    HasRolePermission,
)
from skul_data.fee_management.models.fee_management import (
    FeeStructure,
    FeeRecord,
    FeePayment,
    FeeUploadLog,
    FeeInvoiceTemplate,
    FeeReminder,
)
from skul_data.fee_management.serializers.fee_management import (
    FeeStructureSerializer,
    FeeRecordSerializer,
    FeePaymentSerializer,
    FeeUploadLogSerializer,
    FeeInvoiceTemplateSerializer,
    FeeReminderSerializer,
    FeePaymentConfirmationSerializer,
    FeeSummarySerializer,
    FeeCSVTemplateSerializer,
)
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Student
from skul_data.users.models.parent import Parent
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.users.permissions.permission import IsParent
from skul_data.schools.serializers.schoolclass import SchoolClassSerializer


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_fees"

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return FeeStructure.objects.none()
        school = self.request.user.school

        if school:
            queryset = queryset.filter(school=school)

        # Filter by class if provided
        class_id = self.request.query_params.get("class_id")
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)

        # Filter by term if provided
        term = self.request.query_params.get("term")
        if term:
            queryset = queryset.filter(term=term)

        # Filter by year if provided
        year = self.request.query_params.get("year")
        if year:
            queryset = queryset.filter(year=year)

        return queryset

    def perform_create(self, serializer):
        school = self.request.user.school
        if not school:
            school = self.request.user.school_admin_profile.school
        serializer.save(school=school)
        log_action(
            self.request.user,
            f"Created fee structure: {serializer.instance}",
            ActionCategory.CREATE,
            serializer.instance,
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        log_action(
            self.request.user,
            f"Updated fee structure: {serializer.instance}",
            ActionCategory.UPDATE,
            serializer.instance,
        )

    def perform_destroy(self, instance):
        log_action(
            self.request.user,
            f"Deleted fee structure: {instance}",
            ActionCategory.DELETE,
            instance,
        )
        super().perform_destroy(instance)


class FeeRecordViewSet(viewsets.ModelViewSet):
    queryset = FeeRecord.objects.all()
    serializer_class = FeeRecordSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_fees"

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return FeeRecord.objects.none()
        school = self.request.user.school

        if school:
            queryset = queryset.filter(fee_structure__school=school)

        # Filter by student if provided
        student_id = self.request.query_params.get("student_id")
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        # Filter by parent if provided
        parent_id = self.request.query_params.get("parent_id")
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)

        # Filter by class if provided
        class_id = self.request.query_params.get("class_id")
        if class_id:
            queryset = queryset.filter(fee_structure__school_class_id=class_id)

        # Filter by term if provided
        term = self.request.query_params.get("term")
        if term:
            queryset = queryset.filter(fee_structure__term=term)

        # Filter by year if provided
        year = self.request.query_params.get("year")
        if year:
            queryset = queryset.filter(fee_structure__year=year)

        # Filter by payment status if provided
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(payment_status=status)

        # Filter by overdue if provided
        overdue = self.request.query_params.get("overdue")
        if overdue and overdue.lower() == "true":
            queryset = queryset.filter(is_overdue=True)

        return queryset

    @action(detail=True, methods=["post"], serializer_class=FeePaymentSerializer)
    def add_payment(self, request, pk=None):
        fee_record = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = serializer.save(
            fee_record=fee_record,
            confirmed_by=request.user if request.user.is_staff else None,
            is_confirmed=request.user.is_staff,
        )

        # Update fee record
        fee_record.amount_paid += payment.amount
        fee_record.last_payment_date = payment.payment_date
        fee_record.save()

        log_action(
            request.user,
            f"Added payment of {payment.amount} for fee record {fee_record}",
            ActionCategory.CREATE,
            fee_record,
            {"payment_id": payment.id},
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        school = request.user.school
        if not school:
            return Response(
                {"detail": "No school associated with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get filter parameters
        term = request.query_params.get("term")
        year = request.query_params.get("year")
        class_id = request.query_params.get("class_id")

        # Base queryset
        fee_records = FeeRecord.objects.filter(fee_structure__school=school)

        # Apply filters
        if term:
            fee_records = fee_records.filter(fee_structure__term=term)
        if year:
            fee_records = fee_records.filter(fee_structure__year=year)
        if class_id:
            fee_records = fee_records.filter(fee_structure__school_class_id=class_id)

        # Group by term, year and class
        summaries = fee_records.values(
            "fee_structure__term",
            "fee_structure__year",
            "fee_structure__school_class",
            "fee_structure__school_class__name",
        ).annotate(
            total_students=Count("id"),
            total_expected=Sum("amount_owed"),
            total_paid=Sum("amount_paid"),
            total_balance=Sum("balance"),
            unpaid_count=Count("id", filter=Q(payment_status="unpaid")),
            partially_paid_count=Count("id", filter=Q(payment_status="partial")),
            fully_paid_count=Count("id", filter=Q(payment_status="paid")),
            overdue_count=Count("id", filter=Q(is_overdue=True)),
        )

        # Calculate percentages and prepare response
        result = []
        for summary in summaries:
            total_expected = summary["total_expected"] or Decimal("0")
            total_paid = summary["total_paid"] or Decimal("0")

            paid_percentage = (
                (total_paid / total_expected * 100) if total_expected > 0 else 0
            )

            school_class = SchoolClass.objects.get(
                id=summary["fee_structure__school_class"]
            )

            result.append(
                {
                    "term": summary["fee_structure__term"],
                    "year": summary["fee_structure__year"],
                    "school_class": SchoolClassSerializer(school_class).data,
                    "total_students": summary["total_students"],
                    "total_expected": total_expected,
                    "total_paid": total_paid,
                    "total_balance": summary["total_balance"] or Decimal("0"),
                    "paid_percentage": round(paid_percentage, 2),
                    "unpaid_count": summary["unpaid_count"],
                    "partially_paid_count": summary["partially_paid_count"],
                    "fully_paid_count": summary["fully_paid_count"],
                    "overdue_count": summary["overdue_count"],
                }
            )

        serializer = FeeSummarySerializer(result, many=True)
        return Response(serializer.data)


class FeePaymentViewSet(viewsets.ModelViewSet):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_fees"

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return FeePayment.objects.none()
        school = self.request.user.school

        if school:
            queryset = queryset.filter(fee_record__fee_structure__school=school)

        # Filter by fee_record if provided
        fee_record_id = self.request.query_params.get("fee_record_id")
        if fee_record_id:
            queryset = queryset.filter(fee_record_id=fee_record_id)

        # Filter by student if provided
        student_id = self.request.query_params.get("student_id")
        if student_id:
            queryset = queryset.filter(fee_record__student_id=student_id)

        # Filter by parent if provided
        parent_id = self.request.query_params.get("parent_id")
        if parent_id:
            queryset = queryset.filter(fee_record__parent_id=parent_id)

        # Filter by payment method if provided
        payment_method = self.request.query_params.get("payment_method")
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        # Filter by confirmation status if provided
        is_confirmed = self.request.query_params.get("is_confirmed")
        if is_confirmed:
            queryset = queryset.filter(is_confirmed=is_confirmed.lower() == "true")

        # Filter by date range if provided
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)

        return queryset

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        payment = self.get_object()

        if payment.is_confirmed:
            return Response(
                {"detail": "Payment is already confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.is_confirmed = True
        payment.confirmed_by = request.user
        payment.save()

        log_action(
            request.user,
            f"Confirmed payment {payment.id} for {payment.fee_record}",
            ActionCategory.UPDATE,
            payment,
        )

        return Response(
            {"detail": "Payment confirmed successfully."}, status=status.HTTP_200_OK
        )


class FeeUploadLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = FeeUploadLog.objects.all()
    serializer_class = FeeUploadLogSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_fees"
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        school = self.request.user.school

        if school:
            queryset = queryset.filter(school=school)

        # Filter by class if provided
        class_id = self.request.query_params.get("class_id")
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)

        # Filter by term if provided
        term = self.request.query_params.get("term")
        if term:
            queryset = queryset.filter(term=term)

        # Filter by year if provided
        year = self.request.query_params.get("year")
        if year:
            queryset = queryset.filter(year=year)

        # Filter by status if provided
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def perform_create(self, serializer):
        school = self.request.user.school
        if not school:
            school = self.request.user.school_admin_profile.school
        serializer.save(school=school, uploaded_by=self.request.user, status="pending")

        # Trigger async processing of the CSV file
        from skul_data.fee_management.utils.tasks import process_fee_upload

        process_fee_upload.delay(serializer.instance.id)

        log_action(
            self.request.user,
            f"Uploaded fee CSV for processing: {serializer.instance}",
            ActionCategory.CREATE,
            serializer.instance,
        )


class FeeInvoiceTemplateViewSet(viewsets.ModelViewSet):
    queryset = FeeInvoiceTemplate.objects.all()
    serializer_class = FeeInvoiceTemplateSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_fees"

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return FeeInvoiceTemplate.objects.none()
        school = self.request.user.school

        if school:
            queryset = queryset.filter(school=school)

        return queryset

    def perform_create(self, serializer):
        school = self.request.user.school
        serializer.save(school=school)

        log_action(
            self.request.user,
            f"Created fee invoice template: {serializer.instance.name}",
            ActionCategory.CREATE,
            serializer.instance,
        )

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        template = self.get_object()

        # Deactivate all other templates for this school
        FeeInvoiceTemplate.objects.filter(school=template.school).update(
            is_active=False
        )

        # Activate this template
        template.is_active = True
        template.save()

        log_action(
            request.user,
            f"Set fee invoice template {template.name} as default",
            ActionCategory.UPDATE,
            template,
        )

        return Response(
            {"detail": "Template set as default successfully."},
            status=status.HTTP_200_OK,
        )


class FeeReminderViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = FeeReminder.objects.all()
    serializer_class = FeeReminderSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_fees"

    def get_queryset(self):
        queryset = super().get_queryset()
        school = self.request.user.school

        if school:
            queryset = queryset.filter(fee_record__fee_structure__school=school)

        # Filter by fee_record if provided
        fee_record_id = self.request.query_params.get("fee_record_id")
        if fee_record_id:
            queryset = queryset.filter(fee_record_id=fee_record_id)

        # Filter by student if provided
        student_id = self.request.query_params.get("student_id")
        if student_id:
            queryset = queryset.filter(fee_record__student_id=student_id)

        # Filter by parent if provided
        parent_id = self.request.query_params.get("parent_id")
        if parent_id:
            queryset = queryset.filter(fee_record__parent_id=parent_id)

        # Filter by date range if provided
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(sent_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(sent_at__lte=end_date)

        return queryset

    @action(detail=False, methods=["post"])
    def send_reminders(self, request):
        # Get filter parameters
        fee_record_ids = request.data.get("fee_record_ids", [])
        class_id = request.data.get("class_id")
        term = request.data.get("term")
        year = request.data.get("year")
        status = request.data.get("status", "unpaid")
        send_via = request.data.get("send_via", "both")
        message = request.data.get("message", "")

        # Validate parameters
        if not fee_record_ids and not (class_id and term and year):
            return Response(
                {"detail": "Either provide fee_record_ids or class_id, term and year"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get fee records to send reminders for
        fee_records = FeeRecord.objects.filter(
            fee_structure__school=request.user.school
        )

        if fee_record_ids:
            fee_records = fee_records.filter(id__in=fee_record_ids)
        else:
            fee_records = fee_records.filter(
                fee_structure__school_class_id=class_id,
                fee_structure__term=term,
                fee_structure__year=year,
            )

        if status:
            fee_records = fee_records.filter(payment_status=status)

        # Trigger async task to send reminders
        from skul_data.fee_management.utils.tasks import send_fee_reminders

        task_id = send_fee_reminders.delay(
            [str(record.id) for record in fee_records],
            send_via,
            message,
            request.user.id,
        )

        log_action(
            request.user,
            f"Initiated sending fee reminders for {fee_records.count()} records",
            ActionCategory.CREATE,
            None,
            {
                "fee_record_count": fee_records.count(),
                "send_via": send_via,
                "task_id": str(task_id),
            },
        )

        return Response(
            {
                "detail": "Reminders are being sent in the background.",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class FeeCSVTemplateViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permission = "manage_fees"

    @action(detail=False, methods=["post"])
    def download(self, request):
        serializer = FeeCSVTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        school_class = serializer.validated_data["school_class_id"]
        term = serializer.validated_data["term"]
        year = serializer.validated_data["year"]

        # Get all students in the class
        students = Student.objects.filter(student_class=school_class)

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="fee_template_{school_class.name}_{term}_{year}.csv"'
        )

        writer = csv.writer(response)

        # Write header
        writer.writerow(
            [
                "Parent Name",
                "Parent Email",
                "Parent Phone",
                "Student Name",
                "Student Admission Number",
                "Amount Due",
                "Term",
                "Year",
                "Due Date (YYYY-MM-DD)",
                "Notes",
            ]
        )

        # Write sample rows for each student
        for student in students:
            parent = student.parent
            if parent:
                writer.writerow(
                    [
                        parent.user.get_full_name(),
                        parent.user.email,
                        parent.phone_number,
                        student.full_name,
                        student.admission_number,
                        "",  # Amount due - to be filled by admin
                        term,
                        year,
                        "",  # Due date - to be filled by admin
                        "",  # Notes
                    ]
                )

        log_action(
            request.user,
            f"Downloaded fee CSV template for {school_class.name} {term} {year}",
            ActionCategory.READ,
            school_class,
            {"term": term, "year": year},
        )

        return response

    @action(detail=False, methods=["get"])
    def sample(self, request):
        # Return a sample CSV structure as JSON for frontend reference
        sample_data = {
            "headers": [
                "Parent Name",
                "Parent Email",
                "Parent Phone",
                "Student Name",
                "Student Admission Number",
                "Amount Due",
                "Term",
                "Year",
                "Due Date (YYYY-MM-DD)",
                "Notes",
            ],
            "sample_rows": [
                {
                    "Parent Name": "John Doe",
                    "Parent Email": "john@example.com",
                    "Parent Phone": "+254712345678",
                    "Student Name": "Jane Doe",
                    "Student Admission Number": "SCH-2023-0042",
                    "Amount Due": "15000.00",
                    "Term": "term_1",
                    "Year": "2023",
                    "Due Date (YYYY-MM-DD)": "2023-03-15",
                    "Notes": "Includes activity fee",
                },
                {
                    "Parent Name": "Mary Smith",
                    "Parent Email": "mary@example.com",
                    "Parent Phone": "+254712345679",
                    "Student Name": "Peter Smith",
                    "Student Admission Number": "SCH-2023-0043",
                    "Amount Due": "16000.00",
                    "Term": "term_1",
                    "Year": "2023",
                    "Due Date (YYYY-MM-DD)": "2023-03-15",
                    "Notes": "",
                },
            ],
            "notes": [
                "Do not modify the header row",
                "Leave empty fields as empty strings",
                "Term values must be one of: term_1, term_2, term_3",
                "Year should be in YYYY format",
                "Due date should be in YYYY-MM-DD format",
            ],
        }

        return Response(sample_data)


class ParentFeeViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsParent]

    @action(detail=False, methods=["get"])
    def records(self, request):
        parent = request.user.parent_profile
        fee_records = (
            FeeRecord.objects.filter(parent=parent)
            .select_related("fee_structure", "fee_structure__school_class", "student")
            .order_by("-fee_structure__year", "-fee_structure__term")
        )

        serializer = FeeRecordSerializer(fee_records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def current(self, request):
        parent = request.user.parent_profile
        school = parent.school

        if not school.current_term or not school.current_school_year:
            return Response(
                {"detail": "School has not set current term/year."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fee_records = FeeRecord.objects.filter(
            parent=parent,
            fee_structure__term=school.current_term,
            fee_structure__year=school.current_school_year,
        ).select_related("fee_structure", "fee_structure__school_class", "student")

        serializer = FeeRecordSerializer(fee_records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def confirm_payment(self, request, pk=None):
        fee_record = FeeRecord.objects.filter(
            parent=request.user.parent_profile, id=pk
        ).first()

        if not fee_record:
            return Response(
                {"detail": "Fee record not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = FeePaymentConfirmationSerializer(
            data=request.data
        )  # Directly use the serializer
        serializer.is_valid(raise_exception=True)

        payment = serializer.save(
            fee_record=fee_record, is_confirmed=False  # Needs admin confirmation
        )

        log_action(
            request.user,
            f"Submitted payment confirmation for {fee_record}",
            ActionCategory.CREATE,
            fee_record,
            {"payment_id": payment.id},
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
