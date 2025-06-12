# notifications/tests/test_views.py
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, override_settings
from rest_framework import status
from skul_data.notifications.models.notification import Message, Notification
from skul_data.tests.notifications_tests.test_helpers import (
    create_test_notification,
    create_test_message,
)
from channels.layers import get_channel_layer
from unittest.mock import patch, MagicMock

User = get_user_model()


class NotificationViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )
        self.client.force_authenticate(user=self.user)
        self.notification = create_test_notification(user=self.user)
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="testpass"
        )
        self.other_notification = create_test_notification(user=self.other_user)

    def test_list_notifications(self):
        # Clear any existing notifications for the test user
        Notification.objects.filter(user=self.user).delete()

        # Create exactly one notification for the test user
        self.notification = create_test_notification(user=self.user)

        url = reverse("notification-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Handle both paginated and non-paginated responses
        notifications = response.data.get("results", response.data)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["id"], self.notification.id)

    def test_retrieve_notification(self):
        url = reverse("notification-detail", args=[self.notification.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.notification.id)

    def test_cannot_retrieve_other_user_notification(self):
        url = reverse("notification-detail", args=[self.other_notification.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_as_read(self):
        url = reverse("notification-mark-as-read", args=[self.notification.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_unread_count(self):
        # Create another unread notification
        create_test_notification(user=self.user, is_read=False)

        url = reverse("notification-unread-count")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 2)


class MessageViewSetTest(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="sender", email="sender@example.com", password="testpass"
        )
        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@example.com", password="testpass"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="testpass"
        )

        self.message1 = create_test_message(
            sender=self.sender, recipient=self.recipient, is_read=False
        )
        self.message2 = create_test_message(
            sender=self.sender, recipient=self.recipient, is_read=True
        )
        self.message3 = create_test_message(
            sender=self.recipient, recipient=self.sender, is_read=False
        )
        # Patch the channel layer for all tests
        self.channel_layer_patcher = patch(
            "channels.layers.get_channel_layer",
            return_value=get_channel_layer(),
        )
        self.mock_channel_layer = self.channel_layer_patcher.start()

    def tearDown(self):
        self.channel_layer_patcher.stop()
        super().tearDown()

    def test_inbox_list_as_recipient(self):
        self.client.force_authenticate(user=self.recipient)
        url = reverse("message-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        message_ids = [msg["id"] for msg in response.data["results"]]
        self.assertIn(self.message1.id, message_ids)
        self.assertIn(self.message2.id, message_ids)

    def test_sent_list_as_sender(self):
        self.client.force_authenticate(user=self.sender)
        url = reverse("message-sent")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        message_ids = [msg["id"] for msg in response.data["results"]]
        self.assertIn(self.message1.id, message_ids)
        self.assertIn(self.message2.id, message_ids)

    def test_mark_as_read(self):
        self.client.force_authenticate(user=self.recipient)
        url = reverse("message-mark-as-read", args=[self.message1.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.message1.refresh_from_db()
        self.assertTrue(self.message1.is_read)

    def test_unread_count(self):
        self.client.force_authenticate(user=self.recipient)
        url = reverse("message-unread-count")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 1)

    def test_bulk_mark_as_read(self):
        self.client.force_authenticate(user=self.recipient)
        url = reverse("message-bulk-mark-as-read")
        data = {"message_ids": [self.message1.id, self.message2.id]}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.message1.refresh_from_db()
        self.message2.refresh_from_db()
        self.assertTrue(self.message1.is_read)
        self.assertTrue(self.message2.is_read)

    def test_recipients_list(self):
        self.client.force_authenticate(user=self.sender)
        url = reverse("message-recipients")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Update the expected count based on your actual test data
        self.assertEqual(
            len(response.data), 2
        )  # Or adjust test setup to create only 1 recipient

    def test_create_message(self):
        initial_count = Message.objects.count()
        self.client.force_authenticate(user=self.sender)
        url = reverse("message-list")
        data = {
            "recipient": self.recipient.id,
            "subject": "New Test Message",
            "body": "This is a new test message",
            "message_type": "TEACHER",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.count(), initial_count + 1)
        self.assertEqual(
            response.data["subject"], "New Test Message"
        )  # Check response data

    def test_filter_messages(self):
        self.client.force_authenticate(user=self.recipient)
        url = reverse("message-list") + "?is_read=false"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.message1.id)

    @override_settings(
        CHANNEL_LAYERS={
            "default": {
                "BACKEND": "channels.layers.InMemoryChannelLayer",
            },
        }
    )
    def test_create_message_triggers_notification(self):
        self.client.force_authenticate(user=self.sender)
        url = reverse("message-list")
        data = {
            "recipient": self.recipient.id,
            "subject": "New Test Message",
            "body": "This is a new test message",
            "message_type": "TEACHER",
        }

        # Patch at the module where it's actually used
        with patch(
            "skul_data.notifications.views.notification.MessageViewSet._send_notifications"
        ) as mock_send_notifications:
            response = self.client.post(url, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            # Verify the notification method was called
            mock_send_notifications.assert_called_once()

            # Get the message that was passed to _send_notifications
            message_passed = mock_send_notifications.call_args[0][0]
            self.assertEqual(message_passed.subject, "New Test Message")


# python manage.py test skul_data.tests.notifications_tests.test_notifications_views
