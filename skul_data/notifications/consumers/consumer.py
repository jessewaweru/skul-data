import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from skul_data.notifications.models.notification import Notification, Message

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.user_id = str(self.scope["url_route"]["kwargs"]["user_id"])
            self.user_group_name = f"notifications_{self.user_id}"

            await self.channel_layer.group_add(self.user_group_name, self.channel_name)
            await self.accept()
        except Exception as e:
            print(f"Connection failed: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json["message"]

            await self.channel_layer.group_send(
                self.user_group_name,
                {"type": "notification.message", "message": message},
            )
        except Exception as e:
            print(f"Error processing message: {str(e)}")

    async def notification_message(self, event):
        await self.send(text_data=json.dumps({"message": event["message"]}))


class MessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.user_id = str(self.scope["url_route"]["kwargs"]["user_id"])
            self.user_group_name = f"messages_{self.user_id}"

            await self.channel_layer.group_add(self.user_group_name, self.channel_name)
            await self.accept()
        except Exception as e:
            print(f"Connection failed: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data["message"]
            sender_id = data["sender_id"]
            recipient_id = data["recipient_id"]

            # Save message to database
            await self.save_message(sender_id, recipient_id, message)

            # Send to recipient
            await self.channel_layer.group_send(
                f"messages_{recipient_id}",
                {"type": "chat.message", "message": message, "sender_id": sender_id},
            )

            # Send confirmation to sender
            await self.channel_layer.group_send(
                f"messages_{sender_id}",
                {
                    "type": "chat.message",
                    "message": message,
                    "sender_id": sender_id,
                    "recipient_id": recipient_id,
                    "status": "delivered",
                },
            )
        except Exception as e:
            print(f"Error processing message: {str(e)}")

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "sender_id": event.get("sender_id"),
                    "recipient_id": event.get("recipient_id"),
                    "status": event.get("status", "received"),
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

        Notification.objects.create(
            user=recipient,
            notification_type="MESSAGE",
            title=f"New message from {sender.get_full_name()}",
            message=content[:100],
            related_model="Message",
            related_id=message.id,
        )
