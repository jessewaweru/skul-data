# notifications/tests/test_consumers.py
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from skul_data.notifications.models.notification import Notification, Message
from skul_data.notifications.consumers.consumer import (
    NotificationConsumer,
    MessageConsumer,
)
from channels.routing import URLRouter
from django.urls import re_path
import asyncio

User = get_user_model()


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
)
class NotificationConsumerTest(TransactionTestCase):
    def setUp(self):
        # Create user synchronously for any sync tests
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

    async def asyncSetUp(self):
        # Create user asynchronously for async tests
        self.user = await database_sync_to_async(User.objects.create_user)(
            username="testuser", email="test@example.com", password="testpass"
        )

    async def get_communicator(self, user_id, consumer_class):
        application = URLRouter(
            [
                re_path(r"ws/\w+/(?P<user_id>[^/]+)/$", consumer_class.as_asgi()),
            ]
        )

        path = (
            f"/ws/notifications/{user_id}/"
            if consumer_class == NotificationConsumer
            else f"/ws/messages/{user_id}/"
        )

        communicator = WebsocketCommunicator(application, path)

        # Manually construct the full scope
        communicator.scope.update(
            {
                "type": "websocket",
                "path": path,
                "url_route": {
                    "kwargs": {"user_id": str(user_id)},
                    "args": (),
                },
            }
        )
        return communicator

    async def test_connect_and_disconnect(self):
        communicator = await self.get_communicator(self.user.id, NotificationConsumer)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_receive_notification(self):
        communicator = await self.get_communicator(self.user.id, NotificationConsumer)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Send and receive with timeout
        await communicator.send_json_to({"message": "Test notification"})
        try:
            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=1.0
            )
            self.assertEqual(response["message"], "Test notification")
        except asyncio.TimeoutError:
            self.fail("Timeout waiting for response")
        finally:
            await communicator.disconnect()

    async def test_notification_broadcast(self):
        comm1 = await self.get_communicator(self.user.id, NotificationConsumer)
        comm2 = await self.get_communicator(self.user.id, NotificationConsumer)

        await comm1.connect()
        await comm2.connect()

        await comm1.send_json_to({"message": "Broadcast test"})

        try:
            response1 = await asyncio.wait_for(comm1.receive_json_from(), timeout=1.0)
            response2 = await asyncio.wait_for(comm2.receive_json_from(), timeout=1.0)
            self.assertEqual(response1["message"], "Broadcast test")
            self.assertEqual(response2["message"], "Broadcast test")
        except asyncio.TimeoutError:
            self.fail("Timeout waiting for broadcast messages")
        finally:
            await comm1.disconnect()
            await comm2.disconnect()


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
)
class MessageConsumerTest(TransactionTestCase):
    def setUp(self):
        # Create users synchronously
        self.sender = User.objects.create_user(
            username="sender", email="sender@example.com", password="testpass"
        )
        self.recipient = User.objects.create_user(
            username="recipient", email="recipient@example.com", password="testpass"
        )

    async def asyncSetUp(self):
        # Create users asynchronously
        self.sender = await database_sync_to_async(User.objects.create_user)(
            username="sender", email="sender@example.com", password="testpass"
        )
        self.recipient = await database_sync_to_async(User.objects.create_user)(
            username="recipient", email="recipient@example.com", password="testpass"
        )

    async def get_communicator(self, user_id):
        application = URLRouter(
            [
                re_path(r"ws/messages/(?P<user_id>[^/]+)/$", MessageConsumer.as_asgi()),
            ]
        )

        communicator = WebsocketCommunicator(application, f"/ws/messages/{user_id}/")

        communicator.scope.update(
            {
                "type": "websocket",
                "path": f"/ws/messages/{user_id}/",
                "url_route": {
                    "kwargs": {"user_id": str(user_id)},
                    "args": (),
                },
            }
        )
        return communicator

    async def test_connect_and_disconnect(self):
        communicator = await self.get_communicator(self.sender.id)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_send_and_receive_message(self):
        sender_comm = await self.get_communicator(self.sender.id)
        recipient_comm = await self.get_communicator(self.recipient.id)

        await sender_comm.connect()
        await recipient_comm.connect()

        message_data = {
            "message": "Hello there!",
            "sender_id": str(self.sender.id),
            "recipient_id": str(self.recipient.id),
        }

        await sender_comm.send_json_to(message_data)

        try:
            # Recipient should receive the message
            recipient_response = await asyncio.wait_for(
                recipient_comm.receive_json_from(), timeout=1.0
            )
            self.assertEqual(recipient_response["message"], "Hello there!")

            # Sender should receive delivery confirmation
            sender_response = await asyncio.wait_for(
                sender_comm.receive_json_from(), timeout=1.0
            )
            self.assertEqual(sender_response["status"], "delivered")

        except asyncio.TimeoutError:
            self.fail("Timeout waiting for message responses")
        finally:
            await sender_comm.disconnect()
            await recipient_comm.disconnect()

    async def test_message_saved_correctly(self):
        communicator = await self.get_communicator(self.sender.id)
        await communicator.connect()

        test_message = "This should be saved"
        await communicator.send_json_to(
            {
                "message": test_message,
                "sender_id": str(self.sender.id),
                "recipient_id": str(self.recipient.id),
            }
        )

        try:
            # Wait for delivery confirmation
            await asyncio.wait_for(communicator.receive_json_from(), timeout=1.0)

            # Verify database using helper functions
            message = await self.get_first_message()
            await self.verify_message(message, test_message)

        except asyncio.TimeoutError:
            self.fail("Timeout waiting for message confirmation")
        finally:
            await communicator.disconnect()

    @database_sync_to_async
    def get_first_message(self):
        return Message.objects.first()

    @database_sync_to_async
    def verify_message(self, message, expected_content):
        self.assertEqual(message.body, expected_content)
        self.assertEqual(str(message.sender.id), str(self.sender.id))
        self.assertEqual(str(message.recipient.id), str(self.recipient.id))


# python manage.py test skul_data.tests.notifications_tests.test_notifications_consumers
