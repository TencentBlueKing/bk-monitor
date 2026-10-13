const assert = require('node:assert/strict');
const test = require('node:test');
const {
  extractRequestId,
  isInternalApiDump,
  parseCollectorApiError,
} = require('./collector-api-error.parser.js');

const TAPD_MESSAGE =
  '7fcce575d86c218cd939b429957c0660：[log_search元数据-API][Metadata元数据-API]Failed to get partitions path => /api/bk-monitor/prod/app/metadata/kafka_tail/（3600500）path => /api/c/compapi/v2/bk_log/databus_collectors/collector_config_id/tail/（3600500）';

test('extracts request id from backend message prefix', () => {
  assert.equal(extractRequestId(TAPD_MESSAGE), '7fcce575d86c218cd939b429957c0660');
});

test('extracts request id from traceparent when message has none', () => {
  assert.equal(
    extractRequestId('plain error', '00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01'),
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  );
});

test('maps kafka_tail / partitions dump to kafka_tail kind', () => {
  const parsed = parseCollectorApiError(TAPD_MESSAGE);
  assert.equal(parsed.kind, 'kafka_tail');
  assert.equal(parsed.requestId, '7fcce575d86c218cd939b429957c0660');
  assert.equal(parsed.original.includes('kafka_tail'), true);
});

test('does not rewrite ordinary user-facing chinese errors', () => {
  const parsed = parseCollectorApiError('请选择集群');
  assert.equal(parsed.kind, null);
  assert.equal(isInternalApiDump('请选择集群'), false);
});

test('maps generic path dump without kafka_tail', () => {
  const parsed = parseCollectorApiError('[log_search元数据-API] boom path => /api/c/compapi/v2/bk_log/foo/');
  assert.equal(parsed.kind, 'internal_dump');
});
