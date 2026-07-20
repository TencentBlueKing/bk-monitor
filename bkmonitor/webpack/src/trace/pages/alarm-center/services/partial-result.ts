export type PartialReason = {
  candidate_limit?: number;
  code: string;
  failed_shards?: number;
  scanned_candidate_count?: number;
  scopes: string[];
};

export type PartialResultState = {
  isPartial: boolean;
  partialReasons: PartialReason[];
  totalRelation: 'eq' | 'gte';
};

export function getPartialResultState(response: {
  is_partial?: boolean;
  partial_reasons?: PartialReason[];
  total_relation?: string;
}): PartialResultState {
  return {
    isPartial: response.is_partial === true,
    partialReasons: Array.isArray(response.partial_reasons) ? response.partial_reasons : [],
    totalRelation: response.total_relation === 'gte' ? 'gte' : 'eq',
  };
}
