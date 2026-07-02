from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.log_clustering.handlers.pipline_service.base_pipline_service import BasePipeLineService


class PipelineServiceForTest(BasePipeLineService):
    def build_data_context(self, params, *args, **kwargs):
        return params

    def build_pipeline(self, data_context, *args, **kwargs):
        return data_context


class TestPipelineStart(SimpleTestCase):
    @patch("retrying.time.sleep", return_value=None)
    @patch("apps.log_clustering.handlers.pipline_service.base_pipline_service.task_service.run_pipeline")
    def test_start_pipeline_does_not_retry_failed_result(self, mock_run_pipeline, mock_sleep):
        service = PipelineServiceForTest()
        failed_result = Mock(result=False)
        mock_run_pipeline.side_effect = [failed_result, Mock(result=True)]

        result = service.start_pipeline(pipeline=Mock())

        self.assertIs(result, failed_result)
        mock_run_pipeline.assert_called_once()
        mock_sleep.assert_not_called()
