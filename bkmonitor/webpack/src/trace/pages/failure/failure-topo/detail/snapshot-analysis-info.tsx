import { defineComponent, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import type { SnapshotAnalysis, SnapshotScore } from '../snapshot-analysis';

export default defineComponent({
  props: {
    analysis: { type: Object as PropType<SnapshotAnalysis | null>, default: null },
    scores: { type: Array as PropType<SnapshotScore[]>, default: () => [] },
  },
  setup(props) {
    const { t } = useI18n();
    const methodName = (method?: string | null) => {
      if (method === 'graph_walk') return t('图谱游走');
      if (method === 'graph_causal_rca') return t('小模型图谱RCA');
      return method;
    };
    const scoreName = (kind: string) =>
      ({
        legacy_anomaly_score: t('原始异常评分'),
        self_anomaly: t('自身异常程度'),
        propagated_impact: t('传播影响'),
        explained_errors: t('解释错误数'),
        entrance_error_explanation_ratio: t('入口错误解释比例'),
        propagation_path_membership: t('传播路径标记'),
      })[kind] || kind;
    const renderScores = (scores: SnapshotScore[]) =>
      scores.map(score => (
        <div key={`${score.kind}:${score.method || ''}`}>
          {scoreName(score.kind)}：{score.value ?? t('未提供')}
          {score.method ? ` (${methodName(score.method)})` : ''}
        </div>
      ));
    return () => {
      if (!props.analysis) return null;
      const producer = props.analysis.producer;
      const engineName =
        producer?.engine === 'graph_walk'
          ? t('大模型图谱游走')
          : producer?.engine === 'graph_causal_rca'
            ? t('小模型图谱RCA')
            : t('未知');
      return (
        <div class='snapshot-analysis-info'>
          <div>
            {t('分析来源')}：{engineName}
            {producer?.algorithm_version ? ` (${producer.algorithm_version})` : ''}
          </div>
          {!props.analysis.root_causes?.length && renderScores(props.scores)}
          {(props.analysis.root_causes || []).map(candidate => (
            <div key={candidate.entity_ref}>
              <div>
                {t('候选排名')}：{candidate.rank ?? t('未提供')}
              </div>
              {renderScores(candidate.scores)}
              {(Array.isArray(candidate.reason) ? candidate.reason : [candidate.reason])
                .filter(reason => typeof reason === 'string' && reason.length)
                .map(reason => (
                  <div key={reason}>
                    {t('分析依据')}：{reason}
                  </div>
                ))}
            </div>
          ))}
        </div>
      );
    };
  },
});
