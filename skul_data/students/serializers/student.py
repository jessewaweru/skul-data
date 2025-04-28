from rest_framework import serializers
from skul_data.students.models.student import (
    Student,
    Subject,
    StudentDocument,
    StudentNote,
    StudentStatusChange,
)
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.schools.models.school import School
from skul_data.users.models.parent import Parent
from skul_data.users.models.teacher import Teacher
from skul_data.users.serializers.parent import ParentSerializer
from django.utils import timezone
from skul_data.students.models.student import AttendanceStatus, StudentAttendance


class StudentDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = StudentDocument
        fields = "__all__"
        read_only_fields = ("uploaded_at",)


class StudentNoteSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = StudentNote
        fields = "__all__"
        read_only_fields = ("created_at",)


class StudentStatusChangeSerializer(serializers.ModelSerializer):
    changed_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = StudentStatusChange
        fields = "__all__"
        read_only_fields = ("changed_at",)


class StudentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "gender",
            "student_class",
            "parent",
            "guardians",
            "address",
            "phone_number",
            "email",
            "medical_notes",
            "special_needs",
        ]

    def create(self, validated_data):
        # Generate admission number
        school = validated_data.get("school")
        year = timezone.now().year
        last_student = (
            Student.objects.filter(school=school, admission_date__year=year)
            .order_by("-admission_number")
            .first()
        )

        if last_student:
            last_number = int(last_student.admission_number.split("-")[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        validated_data["admission_number"] = f"{school.code}-{year}-{new_number:04d}"
        return super().create(validated_data)


class StudentBulkCreateSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith(".csv"):
            raise serializers.ValidationError("Only CSV files are allowed")
        return value


class StudentPromoteSerializer(serializers.Serializer):
    new_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all()
    )

    def validate(self, data):
        student = self.context["student"]
        new_class = data["new_class_id"]

        if student.student_class == new_class:
            raise serializers.ValidationError("Student is already in this class")

        return data


class StudentTransferSerializer(serializers.Serializer):
    new_school_id = serializers.PrimaryKeyRelatedField(queryset=School.objects.all())
    transfer_date = serializers.DateField(default=timezone.now)
    reason = serializers.CharField(max_length=255)


class StudentStatusChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentStatusChange
        fields = "__all__"
        read_only_fields = ("changed_at", "changed_by")


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"


class StudentSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()
    full_name = serializers.ReadOnlyField()
    student_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(),
        source="student_class",
        write_only=True,
        required=False,
        allow_null=True,
    )
    parent = ParentSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Parent.objects.all(),
        source="parent",
        write_only=True,
        required=False,
        allow_null=True,
    )
    # teacher = TeacherSerializer(read_only=True)
    teacher_name = serializers.SerializerMethodField()
    teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(),
        source="teacher",
        write_only=True,
        required=False,
        allow_null=True,
    )
    guardians = ParentSerializer(many=True, read_only=True)
    guardian_ids = serializers.PrimaryKeyRelatedField(
        queryset=Parent.objects.all(),
        source="guardians",
        write_only=True,
        many=True,
        required=False,
    )
    documents = StudentDocumentSerializer(many=True, read_only=True)
    notes = StudentNoteSerializer(many=True, read_only=True)
    status_changes = StudentStatusChangeSerializer(many=True, read_only=True)
    phone_number = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "updated_at",
            "admission_number",
            "is_active",
            "deleted_at",
            "deletion_reason",
            "phone_number",
            "email",
            "address",
        ]

    def get_teacher_name(self, obj):
        if obj.teacher:
            return f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}"
        return None

    def get_teacher_details(self, obj):
        # Import inside method to avoid circular dependency
        from skul_data.users.serializers.teacher import TeacherSerializer

        if obj.teacher:
            return TeacherSerializer(obj.teacher).data
        return None

    def to_representation(self, instance):
        # Import here to avoid circular import of student_class
        from skul_data.schools.serializers.schoolclass import SchoolClassSerializer

        ret = super().to_representation(instance)
        ret["student_class"] = (
            SchoolClassSerializer(instance.student_class).data
            if instance.student_class
            else None
        )
        return ret

    def validate_admission_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Admission date cannot be in the future")
        return value

    def validate_status(self, value):
        # Only apply this check on creation
        if self.instance is None and value != "ACTIVE":
            raise serializers.ValidationError("New students must be ACTIVE by default")
        return value

    def validate(self, data):
        # Ensure student class belongs to the same school
        student_class = data.get("student_class")
        school = data.get("school")

        if student_class and student_class.school != school:
            raise serializers.ValidationError(
                {"student_class_id": "Class must belong to the same school"}
            )

        return data

    def get_phone_number(self, obj):
        return obj.phone_number

    def get_email(self, obj):
        return obj.email

    def get_address(self, obj):
        return obj.address


class StudentAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentAttendance
        fields = [
            "id",
            "student",
            "student_name",
            "date",
            "status",
            "recorded_by",
            "recorded_by_name",
            "reason",
            "time_in",
            "notes",
            "created_at",
            "updated_at",
            "class_name",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_student_name(self, obj):
        return obj.student.full_name

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}"
        return None

    def get_class_name(self, obj):
        if obj.student.student_class:
            return obj.student.student_class.name
        return None

    def validate(self, data):
        # Validate that date is not in the future
        if data.get("date") and data["date"] > timezone.now().date():
            raise serializers.ValidationError(
                {"date": "Attendance date cannot be in the future"}
            )

        # Validate that time_in is provided for LATE status
        if data.get("status") == AttendanceStatus.LATE and not data.get("time_in"):
            raise serializers.ValidationError(
                {"time_in": "Time in is required for late attendance"}
            )

        # Validate that reason is provided for EXCUSED status
        if data.get("status") == AttendanceStatus.EXCUSED and not data.get("reason"):
            raise serializers.ValidationError(
                {"reason": "Reason is required for excused absence"}
            )

        return data


class BulkAttendanceSerializer(serializers.Serializer):
    date = serializers.DateField(default=timezone.now)
    class_id = serializers.IntegerField(required=False)
    student_statuses = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())
    )

    def validate_student_statuses(self, value):
        for student_status in value:
            if "student_id" not in student_status:
                raise serializers.ValidationError(
                    "student_id is required for each entry"
                )
            if "status" not in student_status:
                raise serializers.ValidationError("status is required for each entry")
            if student_status["status"] not in dict(AttendanceStatus.choices):
                raise serializers.ValidationError(
                    f"Invalid status: {student_status['status']}"
                )

        return value
