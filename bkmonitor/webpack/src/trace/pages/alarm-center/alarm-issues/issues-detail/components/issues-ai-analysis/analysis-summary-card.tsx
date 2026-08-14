/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { type PropType, computed, defineComponent } from 'vue';

import { Button, Progress } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import type { SourceAnalysisView } from '../../../typing';

import './analysis-summary-card.scss';

export default defineComponent({
  name: 'AnalysisSummaryCard',
  props: {
    sourceAnalysisData: {
      type: Object as PropType<SourceAnalysisView>,
      default: () => ({}),
    },
  },
  emits: {
    reanalyzeAnalysis: () => true,
  },
  setup(props) {
    const { t } = useI18n();

    const isHighConfidence = computed(() => {
      const { result } = props.sourceAnalysisData.latest;
      return result.result_type === 'HIGH_CONFIDENCE';
    });

    return {
      t,
      isHighConfidence,
    };
  },
  render() {
    const { result, triggered_by, triggered_at } = this.sourceAnalysisData.latest;

    return (
      <div class='analysis-summary-card'>
        <div class='analysis-summary-card-left'>
          <Progress
            width={64}
            color={this.isHighConfidence ? '#3A84FF' : '#FFB848'}
            percent={87}
            type='circle'
          >
            <span class={['status-text', { 'is-high-confidence': this.isHighConfidence }]}>
              {this.isHighConfidence ? this.t('高置信度') : this.t('证据不足')}
            </span>
          </Progress>

          <div class='analysis-summary-info'>
            <div class='analysis-summary-desc'>{result.result_card.description}</div>
          </div>
        </div>

        <div class='analysis-summary-card-right'>
          <div class='analysis-users-tag'>
            <span class='person'>
              {this.t('由 {name} 分析 · {time}', {
                name: triggered_by,
                time: dayjs.tz(triggered_at * 1000, window.timezone).format('YYYY-MM-DD HH:mm:ssZZ'),
              })}
            </span>
            <Button
              theme='primary'
              text
              onClick={() => {
                this.$emit('reanalyzeAnalysis');
              }}
            >
              {this.t('重新分析')}
            </Button>
          </div>

          <Button
            size='small'
            theme='primary'
            onClick={() => {}}
          >
            {this.t('重新分派')}
          </Button>
        </div>
      </div>
    );
  },
});
