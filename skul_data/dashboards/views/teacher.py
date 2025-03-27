from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student
from skul_data.documents.models.document import Document


class TeacherDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Returns dashboard data for a logged-in Teacher"""
        if not hasattr(request.user, "teacher"):
            return Response({"error": "Unauthorized"}, status=403)

        teacher = request.user.teacher
        students = Student.objects.filter(student_class=teacher.assigned_class).count()
        parents = (
            Parent.objects.filter(
                children__in=Student.objects.filter(
                    student_class=teacher.assigned_class
                )
            )
            .distinct()
            .count()
        )
        documents = Document.objects.filter(category="exam").count()

        data = {
            "students_count": students,
            "parents_count": parents,
            "documents_count": documents,
        }

        return Response(data)
