from rest_framework import viewsets
from skul_data.students.models.student import Student
from skul_data.students.serializers.student import StudentSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
