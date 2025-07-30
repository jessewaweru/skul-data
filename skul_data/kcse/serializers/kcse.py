from rest_framework import serializers
from skul_data.kcse.models.kcse import (
    KCSEResult,
    KCSESubjectResult,
    KCSESchoolPerformance,
    KCSESubjectPerformance,
)
from skul_data.students.models.student import Student
from skul_data.students.models.student import Subject
from skul_data.users.models.teacher import Teacher
from skul_data.students.serializers.student import SimpleStudentSerializer
from skul_data.students.serializers.student import SubjectSerializer
from skul_data.users.serializers.teacher import TeacherSerializer
from skul_data.schools.serializers.school import SchoolSerializer
import pandas as pd
from io import StringIO
from django.utils import timezone
from django.db import transaction
import csv


class KCSESubjectResultSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_teacher = TeacherSerializer(read_only=True)

    class Meta:
        model = KCSESubjectResult
        fields = "__all__"


class KCSEResultSerializer(serializers.ModelSerializer):
    student = SimpleStudentSerializer(read_only=True)
    subject_results = KCSESubjectResultSerializer(many=True, read_only=True)
    school = SchoolSerializer(read_only=True)

    class Meta:
        model = KCSEResult
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "uploaded_by"]


class KCSESubjectPerformanceSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_teacher = TeacherSerializer(read_only=True)

    class Meta:
        model = KCSESubjectPerformance
        fields = "__all__"


class KCSESchoolPerformanceSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    subject_performances = KCSESubjectPerformanceSerializer(many=True, read_only=True)

    class Meta:
        model = KCSESchoolPerformance
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class KCSEResultUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    year = serializers.IntegerField()
    publish = serializers.BooleanField(default=False)

    def validate_year(self, value):
        current_year = timezone.now().year
        if value < 1989 or value > current_year:
            raise serializers.ValidationError(
                f"Year must be between 1989 and {current_year}"
            )
        return value

    def validate(self, data):
        file = data["file"]
        year = data["year"]
        school = self.context["request"].user.school

        # Check if results already exist for this year
        if KCSEResult.objects.filter(school=school, year=year).exists():
            raise serializers.ValidationError(
                f"KCSE results for {year} already exist. Please update existing records instead."
            )

        # Read the file to validate its structure
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            required_columns = {
                "Index Number",
                "Admission Number",
                "Name",
                "ENG",
                "KIS",
                "MAT",
                "Mean Grade",
                "Total Points",
            }
            if not required_columns.issubset(df.columns):
                missing = required_columns - set(df.columns)
                raise serializers.ValidationError(
                    f"Missing required columns: {', '.join(missing)}"
                )
        except Exception as e:
            raise serializers.ValidationError(f"Error reading file: {str(e)}")

        return data

    @transaction.atomic
    def create(self, validated_data):
        file = validated_data["file"]
        year = validated_data["year"]
        publish = validated_data["publish"]
        user = self.context["request"].user
        school = user.school

        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            # Process each row
            for _, row in df.iterrows():
                index_number = row["Index Number"]
                admission_number = row["Admission Number"]

                try:
                    student = Student.objects.get(
                        admission_number=admission_number,
                        school=school,
                        status="GRADUATED",
                    )
                except Student.DoesNotExist:
                    continue  # Skip if student not found

                # Create KCSE result
                kcse_result = KCSEResult.objects.create(
                    school=school,
                    student=student,
                    year=year,
                    index_number=index_number,
                    mean_grade=row["Mean Grade"],
                    mean_points=row["Total Points"],
                    division=self.calculate_division(row["Mean Grade"]),
                    uploaded_by=user,
                    is_published=publish,
                    published_at=timezone.now() if publish else None,
                )

                # Process subject results
                subject_columns = [
                    col
                    for col in df.columns
                    if col
                    not in [
                        "Index Number",
                        "Admission Number",
                        "Name",
                        "Mean Grade",
                        "Total Points",
                    ]
                ]

                for subject_code in subject_columns:
                    grade = row[subject_code]
                    if pd.isna(grade) or not str(grade).strip():
                        continue

                    try:
                        subject = Subject.objects.get(code=subject_code, school=school)
                    except Subject.DoesNotExist:
                        continue

                    points = self.grade_to_points(grade)

                    # Find subject teacher (assuming teacher taught this subject in student's class)
                    subject_teacher = None
                    if student.student_class:
                        subject_teacher = Teacher.objects.filter(
                            subjects_taught=subject,
                            assigned_classes=student.student_class,
                        ).first()

                    KCSESubjectResult.objects.create(
                        kcse_result=kcse_result,
                        subject=subject,
                        subject_code=subject_code,
                        grade=grade,
                        points=points,
                        subject_teacher=subject_teacher,
                    )

            # Calculate school performance
            self.calculate_school_performance(school, year)

            return {"status": "success", "processed": len(df)}
        except Exception as e:
            raise serializers.ValidationError(f"Error processing file: {str(e)}")

    def grade_to_points(self, grade):
        grade_points = {
            "A": 12,
            "A-": 11,
            "B+": 10,
            "B": 9,
            "B-": 8,
            "C+": 7,
            "C": 6,
            "C-": 5,
            "D+": 4,
            "D": 3,
            "D-": 2,
            "E": 1,
        }
        return grade_points.get(grade.upper(), 0)

    def calculate_division(self, mean_grade):
        if mean_grade in ["A", "A-", "B+", "B"]:
            return 1
        elif mean_grade in ["B-", "C+", "C"]:
            return 2
        elif mean_grade in ["C-", "D+", "D"]:
            return 3
        else:
            return 4

    def calculate_school_performance(self, school, year):
        results = KCSEResult.objects.filter(school=school, year=year)
        if not results.exists():
            return None

        # Calculate mean points
        total_points = sum(float(result.mean_points) for result in results)
        mean_points = total_points / results.count()

        # Calculate mean grade
        grade_points = {
            "A": 12,
            "A-": 11,
            "B+": 10,
            "B": 9,
            "B-": 8,
            "C+": 7,
            "C": 6,
            "C-": 5,
            "D+": 4,
            "D": 3,
            "D-": 2,
            "E": 1,
        }
        total_grade_points = sum(
            grade_points.get(result.mean_grade, 0) for result in results
        )
        mean_grade_point = total_grade_points / results.count()

        # Map mean grade point back to grade
        mean_grade = self.points_to_grade(mean_grade_point)

        # Calculate university qualified (C+ and above)
        university_qualified = results.filter(
            mean_grade__in=["A", "A-", "B+", "B", "B-", "C+"]
        ).count()

        # Create school performance record
        school_performance = KCSESchoolPerformance.objects.create(
            school=school,
            year=year,
            mean_grade=mean_grade,
            mean_points=mean_points,
            total_students=results.count(),
            university_qualified=university_qualified,
        )

        # Calculate subject performances
        subject_results = KCSESubjectResult.objects.filter(
            kcse_result__school=school, kcse_result__year=year
        )

        for subject in Subject.objects.filter(school=school):
            subject_code = subject.code
            subject_res = subject_results.filter(subject=subject)

            if not subject_res.exists():
                continue

            # Calculate mean score and grade
            total_points = sum(res.points for res in subject_res)
            mean_points = total_points / subject_res.count()
            mean_grade = self.points_to_grade(mean_points)

            # Count students who passed (D+ and above)
            passed = subject_res.exclude(grade__in=["D", "D-", "E"]).count()

            # Get most common subject teacher
            from django.db.models import Count

            teacher_counts = (
                subject_res.exclude(subject_teacher=None)
                .values("subject_teacher")
                .annotate(count=Count("subject_teacher"))
                .order_by("-count")
            )

            subject_teacher = (
                teacher_counts[0]["subject_teacher"] if teacher_counts else None
            )

            KCSESubjectPerformance.objects.create(
                school_performance=school_performance,
                subject=subject,
                subject_code=subject_code,
                mean_score=mean_points,
                mean_grade=mean_grade,
                total_students=subject_res.count(),
                entered=subject_res.count(),
                passed=passed,
                subject_teacher_id=subject_teacher,
            )

        return school_performance

    def points_to_grade(self, points):
        grade_ranges = [
            (11.5, "A"),
            (10.5, "A-"),
            (9.5, "B+"),
            (8.5, "B"),
            (7.5, "B-"),
            (6.5, "C+"),
            (5.5, "C"),
            (4.5, "C-"),
            (3.5, "D+"),
            (2.5, "D"),
            (1.5, "D-"),
            (0, "E"),
        ]
        for min_points, grade in grade_ranges:
            if points >= min_points:
                return grade
        return "E"


class KCSEStudentTemplateSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    class_name = serializers.CharField()

    def validate_year(self, value):
        current_year = timezone.now().year
        if value < 1989 or value > current_year:
            raise serializers.ValidationError(
                f"Year must be between 1989 and {current_year}"
            )
        return value

    def create(self, validated_data):
        year = validated_data["year"]
        class_name = validated_data["class_name"].strip()  # Remove any whitespace
        school = self.context["request"].user.school
        print(f"\nFiltering for school: {school.name}")

        print(f"\nSearching for:")
        print(f"- School: {school.name} (ID: {school.id})")
        print(f"- Class name: '{class_name}'")
        print(f"- Status: GRADUATED")

        # Use select_for_update to ensure we see latest data
        students = (
            Student.objects.filter(
                school=school, status="GRADUATED", student_class__name=class_name
            )
            .select_related("student_class")
            .order_by("admission_number")
        )

        # Debug output
        print(f"\nSerializer found {students.count()} students")
        for s in students:
            print(f"- {s.admission_number} in {s.student_class.name}")

        # Generate CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Index Number", "Admission Number", "Name", "Stream"])

        for student in students:
            writer.writerow(
                [
                    "",
                    student.admission_number,
                    student.full_name,
                    student.student_class.name,
                ]
            )

        csv_content = output.getvalue()
        return {"csv_data": csv_content}


class KCSEResultExportSerializer(serializers.Serializer):
    year = serializers.IntegerField(required=False)
    format = serializers.ChoiceField(choices=["csv", "excel", "pdf"], default="csv")

    def validate_year(self, value):
        if value is not None:
            current_year = timezone.now().year
            if value < 1989 or value > current_year:
                raise serializers.ValidationError(
                    f"Year must be between 1989 and {current_year}"
                )
        return value
