# notifications/tests/test_routing.py
from django.test import TestCase
from skul_data.notifications.routers.routing import websocket_urlpatterns


class RoutingTest(TestCase):
    def test_notification_consumer_routing(self):
        route = websocket_urlpatterns[0]
        self.assertEqual(route.pattern._regex, r"^ws/notifications/(?P<user_id>\w+)/$")
        self.assertEqual(route.callback.__name__, "NotificationConsumer")

    def test_message_consumer_routing(self):
        route = websocket_urlpatterns[1]
        self.assertEqual(route.pattern._regex, r"^ws/messages/(?P<user_id>\w+)/$")
        self.assertEqual(route.callback.__name__, "MessageConsumer")


# python manage.py test skul_data.tests.notifications_tests.test_notifications_routing
