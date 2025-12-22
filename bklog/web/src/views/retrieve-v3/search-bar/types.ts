export type ParseResult = 'SUCCESS' | 'PARTIAL_SUCCESS' | 'FAILED';

export interface AiQueryResult {
  startTime?: string;
  endTime?: string;
  queryString?: string;
  parseResult?: ParseResult;
  explain?: string;
}

export interface AiQueryContent {
  end_time?: string;
  start_time?: string;
  query_string?: string;
  parse_result?: ParseResult;
  explain?: string;
}
