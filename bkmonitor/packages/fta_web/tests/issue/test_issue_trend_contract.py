from pathlib import Path


ISSUE_PACKAGE = Path(__file__).resolve().parents[2] / "issue"
BKMONITOR_ROOT = Path(__file__).resolve().parents[4]


def test_issue_trend_endpoint_contract_is_registered():
    resources = (ISSUE_PACKAGE / "resources.py").read_text()
    views = (ISSUE_PACKAGE / "views.py").read_text()

    assert "class IssueTrendResource(Resource):" in resources
    assert 'endpoint="issue/trend"' in views
    assert '"issue/trend"' in views


def test_search_can_skip_legacy_trend_query():
    resources = (ISSUE_PACKAGE / "resources.py").read_text()
    handler = (ISSUE_PACKAGE / "handlers" / "issue.py").read_text()

    assert 'show_trend = serializers.BooleanField(label="展示趋势", default=True)' in resources
    assert "if show_trend:" in handler
    assert "self.add_alert_summary(issues)" in handler


def test_trend_query_sets_bucket_size_from_expanded_ids():
    handler = (ISSUE_PACKAGE / "handlers" / "issue.py").read_text()

    assert "TREND_QUERY_BATCH_SIZE = 100" in handler
    assert "for index in range(0, len(alert_query_issue_ids), TREND_QUERY_BATCH_SIZE)" in handler
    assert "bucket_size=len(batch_issue_ids)" in handler


def test_issue_list_renders_before_trend_is_loaded():
    issues_service = (
        BKMONITOR_ROOT / "webpack" / "src" / "trace" / "pages" / "alarm-center" / "services" / "issues-services.ts"
    ).read_text()
    alarm_table = (
        BKMONITOR_ROOT / "webpack" / "src" / "trace" / "pages" / "alarm-center" / "composables" / "use-alarm-table.ts"
    ).read_text()
    issues_table = (
        BKMONITOR_ROOT
        / "webpack"
        / "src"
        / "trace"
        / "pages"
        / "alarm-center"
        / "alarm-issues"
        / "hooks"
        / "use-issues-table.ts"
    ).read_text()

    list_method = issues_service.split("async getFilterTableList", 1)[1].split("async getIssueTrend", 1)[0]
    assert "issueTrend" not in list_method
    assert alarm_table.index("data.value = res.data") < alarm_table.index("getIssueTrend")
    assert alarm_table.index("loading.value = false") < alarm_table.index("getIssueTrend")
    assert issues_table.index("data.value = res.data") < issues_table.index("getIssueTrend")
    assert issues_table.index("loading.value = false") < issues_table.index("getIssueTrend")
