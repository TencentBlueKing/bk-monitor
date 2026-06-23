from django.test import SimpleTestCase

from apps.api.base import DataApiRetryClass


class TestDataApiRetryClass(SimpleTestCase):
    def test_default_does_not_retry_exceptions(self):
        retry = DataApiRetryClass.create_retry_obj()

        self.assertFalse(retry.retry_on_exception(RuntimeError("failed")))

    def test_result_retry_does_not_retry_exceptions_by_default(self):
        retry = DataApiRetryClass.create_retry_obj(fail_check_functions=[lambda result: False])

        self.assertFalse(retry.retry_on_exception(RuntimeError("failed")))

    def test_explicit_exception_exclusion_keeps_existing_behavior(self):
        retry = DataApiRetryClass.create_retry_obj(exceptions=[ValueError])

        self.assertFalse(retry.retry_on_exception(ValueError("do not retry")))
        self.assertTrue(retry.retry_on_exception(RuntimeError("retry")))
