from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.log_databus.handlers.check_collector.checker.route_checker import RouteChecker


ROUTE = {"name": "test_route", "stream_to": {"stream_to_id": 203, "kafka": {"topic_name": "test_topic"}}}


class RouteCheckerGseShapeTest(SimpleTestCase):
    def setUp(self):
        self.record = Mock()
        self.checker = RouteChecker(12345, check_collector_record=self.record)

    @patch("apps.log_databus.handlers.check_collector.checker.route_checker.GseApi.query_route")
    def test_route_accepts_matching_channel_only(self, query_route):
        query_route.return_value = [
            {"channel_id": 999, "route": [ROUTE]},
            {"metadata": {"channel_id": 12345}, "route": [ROUTE]},
        ]
        self.checker.query_route()
        self.assertEqual(self.checker.route, [ROUTE])

    @patch("apps.log_databus.handlers.check_collector.checker.route_checker.GseApi.query_stream_to")
    def test_stream_to_accepts_flat_and_nested_responses(self, query_stream_to):
        detail = {
            "stream_to_id": 203,
            "name": "test_stream",
            "report_mode": "kafka",
            "kafka": {"storage_address": [{"ip": "kafka.example.test", "port": 9092}]},
        }
        for response in (detail, {"metadata": {"stream_to_id": 203}, "stream_to": detail}):
            with self.subTest(response=response):
                self.checker.kafka = []
                query_stream_to.return_value = [response]
                self.checker.query_stream_to(ROUTE)
                self.assertEqual(self.checker.kafka[0]["ip"], "kafka.example.test")
                self.assertEqual(self.checker.kafka[0]["kafka_topic_name"], "test_topic")

    @patch("apps.log_databus.handlers.check_collector.checker.route_checker.GseApi.query_stream_to")
    def test_mismatched_stream_to_is_not_attributed(self, query_stream_to):
        query_stream_to.return_value = [{"stream_to_id": 999, "name": "other", "report_mode": "kafka"}]
        self.checker.query_stream_to(ROUTE)
        self.assertEqual(self.checker.kafka, [])
