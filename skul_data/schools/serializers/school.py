from rest_framework import serializers
from skul_data.schools.models.school import School
from skul_data.users.models.base_user import User
from skul_data.schools.models.school import SchoolSubscription, SecurityLog
from skul_data.users.serializers.base_user import UserDetailSerializer


class SchoolSerializer(serializers.ModelSerializer):
    administrators = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    primary_admin = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            "id",
            "name",
            "code",
            "type",
            "motto",
            "location",
            "city",
            "country",
            "phone",
            "email",
            "website",
            "academic_year_structure",
            "is_active",
            "administrators",
            "current_term",
            "current_school_year",
            "term_start_date",
            "term_end_date",
            "primary_admin",
            "stats",
            "subscription",
        ]
        read_only_fields = ["code", "is_active"]

    def get_subscription(self, obj):
        from skul_data.schools.serializers.school import SchoolSubscriptionSerializer

        subscription = getattr(obj, "subscription", None)
        if subscription:
            return SchoolSubscriptionSerializer(subscription).data
        return None

    def get_administrators(self, obj):
        from skul_data.users.serializers.base_user import UserDetailSerializer

        admin_users = User.objects.filter(school_admin_profile__school=obj)
        return UserDetailSerializer(admin_users, many=True, context=self.context).data

    def get_primary_admin(self, obj):
        primary_admin = obj.administrators.filter(is_primary=True).first()
        if primary_admin:
            return {
                "id": primary_admin.user.id,
                "name": primary_admin.user.get_full_name(),
                "email": primary_admin.user.email,
            }
        return None

    def get_stats(self, obj):
        return {
            "teachers": obj.teachers.count(),
            "students": obj.students.count(),
            "classes": obj.classes.count(),
            "active_since": obj.registration_date.strftime("%Y-%m-%d"),
        }


class SchoolSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolSubscription
        fields = [
            "id",
            "plan",
            "status",
            "start_date",
            "end_date",
            "auto_renew",
            "last_payment_date",
            "next_payment_date",
            "payment_method",
        ]
        read_only_fields = ["status", "start_date", "end_date", "last_payment_date"]


class SecurityLogSerializer(serializers.ModelSerializer):
    user = UserDetailSerializer(read_only=True)

    class Meta:
        model = SecurityLog
        fields = [
            "id",
            "user",
            "action_type",
            "ip_address",
            "user_agent",
            "location",
            "timestamp",
            "details",
        ]
