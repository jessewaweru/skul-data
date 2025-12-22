from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets
import string


class PasswordResetOTP(models.Model):
    """
    Model to store OTP tokens for password reset.
    OTPs are time-limited and single-use.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_otps",
    )
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Password Reset OTP"
        verbose_name_plural = "Password Reset OTPs"
        indexes = [
            models.Index(fields=["user", "is_used"]),
            models.Index(fields=["otp_code", "expires_at"]),
        ]

    def __str__(self):
        return f"OTP for {self.user.email} - {'Used' if self.is_used else 'Active'}"

    def save(self, *args, **kwargs):
        if not self.pk:
            # Generate 6-digit OTP
            self.otp_code = "".join(secrets.choice(string.digits) for _ in range(6))
            # Set expiration to 10 minutes from now
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if OTP is still valid (not used and not expired)"""
        return not self.is_used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Mark OTP as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=["is_used", "used_at"])

    @classmethod
    def create_for_user(cls, user, ip_address=None, user_agent=None):
        """
        Create a new OTP for a user.
        Invalidates all previous unused OTPs for this user.
        """
        # Invalidate all previous unused OTPs
        cls.objects.filter(user=user, is_used=False).update(is_used=True)

        # Create new OTP
        return cls.objects.create(
            user=user, ip_address=ip_address, user_agent=user_agent
        )

    @classmethod
    def verify_otp(cls, email, otp_code):
        """
        Verify an OTP code for a given email.
        Returns the user if valid, None otherwise.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            user = User.objects.get(email=email)
            otp = cls.objects.filter(
                user=user, otp_code=otp_code, is_used=False
            ).first()

            if otp and otp.is_valid():
                return otp
            return None
        except User.DoesNotExist:
            return None
