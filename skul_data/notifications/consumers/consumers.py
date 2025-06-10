import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from skul_data.notifications.models.notification import Notification, Message

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.user_group_name = f"notifications_{self.user_id}"

        # Join user's notification group
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave user's notification group
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Send message to user's notification group
        await self.channel_layer.group_send(
            self.user_group_name, {"type": "notification_message", "message": message}
        )

    async def notification_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))


class MessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.user_group_name = f"messages_{self.user_id}"

        # Join user's message group
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave user's message group
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        sender_id = text_data_json["sender_id"]
        recipient_id = text_data_json["recipient_id"]

        # Save message to database
        await self.save_message(sender_id, recipient_id, message)

        # Send message to recipient's group
        await self.channel_layer.group_send(
            f"messages_{recipient_id}",
            {"type": "chat_message", "message": message, "sender_id": sender_id},
        )

        # Also send to sender's group for confirmation
        await self.channel_layer.group_send(
            f"messages_{sender_id}",
            {
                "type": "chat_message",
                "message": message,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "status": "delivered",
            },
        )

    async def chat_message(self, event):
        message = event["message"]
        sender_id = event.get("sender_id")
        recipient_id = event.get("recipient_id")
        status = event.get("status", "received")

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "message": message,
                    "sender_id": sender_id,
                    "recipient_id": recipient_id,
                    "status": status,
                }
            )
        )

    @database_sync_to_async
    def save_message(self, sender_id, recipient_id, content):
        sender = User.objects.get(id=sender_id)
        recipient = User.objects.get(id=recipient_id)

        message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            body=content,
            message_type="TEACHER" if sender.user_type == User.TEACHER else "PARENT",
        )

        # Create notification for the recipient
        Notification.objects.create(
            user=recipient,
            notification_type="MESSAGE",
            title=f"New message from {sender.get_full_name()}",
            message=content[:100],  # First 100 chars of message
            related_model="Message",
            related_id=message.id,
        )
