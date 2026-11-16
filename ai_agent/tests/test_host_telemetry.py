"""升级 OTel 时，监控现有延迟导出器必须仍能启动、导出和退出。"""

import ast
import threading
from pathlib import Path

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_existing_monitor_lazy_processor_with_selected_otel():
    # 只装载原有类，避免初始化整套 Django/数据库；不复制其实现。
    source = Path(__file__).resolve().parents[2] / "bkmonitor/bkmonitor/trace/log_trace.py"
    tree = ast.parse(source.read_text())
    definition = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LazyBatchSpanProcessor"
    )
    namespace = {"BatchSpanProcessor": BatchSpanProcessor, "ReadableSpan": ReadableSpan, "threading": threading}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(source), "exec"), namespace)
    exporter = InMemorySpanExporter()
    processor = namespace["LazyBatchSpanProcessor"](exporter)
    provider = TracerProvider()
    provider.add_span_processor(processor)
    assert processor.worker_thread is None
    try:
        with provider.get_tracer(__name__).start_as_current_span("host-compatibility"):
            pass
        assert provider.force_flush(timeout_millis=2000)
        assert [span.name for span in exporter.get_finished_spans()] == ["host-compatibility"]
    finally:
        provider.shutdown()
