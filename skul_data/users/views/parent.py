from rest_framework import generics
from skul_data.users.models.parent import Parent
from skul_data.users.serializers.parent import ParentSerializer


class ParentCreateView(generics.CreateAPIView):
    queryset = Parent.objects.all()
    serializer_class = ParentSerializer
