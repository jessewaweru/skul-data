# skul_data/users/models/verification.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets
import string


class EmailVerification(models.Model):
    """Email verification tokens for new accounts"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verifications",
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token", "is_verified"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            # Generate secure token
            self.token = secrets.token_urlsafe(32)
            # Set expiration to 48 hours from now
            self.expires_at = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if token is still valid"""
        return not self.is_verified and timezone.now() < self.expires_at

    def mark_as_verified(self):
        """Mark email as verified"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_verified", "verified_at"])

        # Mark user's email as verified
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])


class PhoneVerification(models.Model):
    """Phone number verification via SMS OTP"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phone_verifications",
    )
    phone_number = models.CharField(max_length=20)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "is_verified"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            # Generate 6-digit OTP
            self.otp_code = "".join(secrets.choice(string.digits) for _ in range(6))
            # Set expiration to 10 minutes from now
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if OTP is still valid"""
        return (
            not self.is_verified
            and timezone.now() < self.expires_at
            and self.attempts < 3
        )

    def increment_attempts(self):
        """Increment verification attempts"""
        self.attempts += 1
        self.save(update_fields=["attempts"])

    def mark_as_verified(self):
        """Mark phone as verified"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_verified", "verified_at"])

        # Mark user's phone as verified
        self.user.phone_verified = True
        self.user.phone_number = self.phone_number
        self.user.save(update_fields=["phone_verified", "phone_number"])


class AccountActivation(models.Model):
    """First-time account activation for admin-created accounts"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_activation",
    )
    token = models.CharField(max_length=64, unique=True)
    temporary_password = models.CharField(max_length=128)  # Hashed
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_activated = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.pk:
            # Generate secure token
            self.token = secrets.token_urlsafe(32)
            # Set expiration to 7 days from now
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if activation token is still valid"""
        return not self.is_activated and timezone.now() < self.expires_at

    def mark_as_activated(self):
        """Mark account as activated"""
        self.is_activated = True
        self.activated_at = timezone.now()
        self.save(update_fields=["is_activated", "activated_at"])

        # Activate user account
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    @staticmethod
    def generate_temporary_password():
        """Generate a random temporary password"""
        # 12 characters: uppercase, lowercase, digits, special chars
        chars = string.ascii_letters + string.digits + "!@#$%"
        return "".join(secrets.choice(chars) for _ in range(12))
