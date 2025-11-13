/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { defineComponent, onMounted, ref, computed } from 'vue';
import TextHighlight from 'vue-text-highlight';

import { base64Encode } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import $http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'DebugTool',
  components: {
    TextHighlight,
  },
  props: {
    ruleList: {
      type: Array,
      default: () => [],
    },
    maxLogLength: {
      type: Number,
      default: 10_000,
    },
    collectorConfigId: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const { t } = useLocale();
    const store = useStore();

    const logOriginal = ref(''); // 日志源
    const debugRequest = ref(false); // 调试中
    const logOriginalRequest = ref(false); // 原始日志是否正在请求
    const effectOriginal = ref('');

    const cleanConfig = computed(() => store.state.indexSetFieldConfig.clean_config);

    // 获取原始日志内容
    const getLogOriginal = () => {
      const collectorConfigId = cleanConfig.value?.extra?.collector_config_id;
      if (!(collectorConfigId || props.collectorConfigId)) {
        return;
      }

      logOriginalRequest.value = true;
      $http
        .request('source/dataList', {
          params: {
            collector_config_id: collectorConfigId || Number(props.collectorConfigId),
          },
        })
        .then(res => {
          if (res.data?.length) {
            const data = res.data[0];
            logOriginal.value = data.etl.data || '';
          }
        })
        .catch(e => {
          console.error(e);
        })
        .finally(() => {
          logOriginalRequest.value = false;
        });
    };

    const ruleArrToBase64 = (arr = []) => {
      try {
        const ruleNewList = arr.reduce((pre, cur) => {
          const key = Object.keys(cur)[0];
          const val = Object.values(cur)[0];
          const rulesStr = JSON.stringify(`${key}:${val}`);
          pre.push(rulesStr);
          return pre;
        }, []);
        const ruleArrStr = `[${ruleNewList.join(' ,')}]`;
        return base64Encode(ruleArrStr);
      } catch {
        return '';
      }
    };

    const handleClickDebug = () => {
      debugRequest.value = true;
      effectOriginal.value = '';
      const predefinedVariables = ruleArrToBase64(props.ruleList);
      const query = {
        input_data: logOriginal.value,
        predefined_varibles: predefinedVariables,
        max_log_length: props.maxLogLength,
      };
      $http
        .request('/logClustering/debug', { data: { ...query } })
        .then(res => {
          effectOriginal.value = res.data;
        })
        .finally(() => {
          debugRequest.value = false;
        });
    };

    const getHeightLightList = (str: string) => str.match(/#.*?#/g) || [];

    onMounted(() => {
      getLogOriginal();
    });

    return () => (
      <div class='debug-input-box'>
        <div class='debug-title'>{t('原始日志')}</div>
        <div v-bkloading={{ isLoading: logOriginalRequest.value }}>
          <bk-input
            class='log-original-main'
            disabled={logOriginalRequest.value}
            placeholder=' '
            rows={4}
            type='textarea'
            value={logOriginal.value}
            on-change={value => (logOriginal.value = value)}
          />
        </div>

        <bk-button
          class='debug-btn'
          disabled={!(logOriginal.value && props.ruleList.length)}
          loading={debugRequest.value}
          size='small'
          theme='primary'
          on-click={handleClickDebug}
        >
          <log-icon
            class='play-icon'
            type='bofang'
          />
        </bk-button>
        <div class='debug-title'>{t('效果预览')}</div>
        <div
          class='effect-container'
          v-bkloading={{ isLoading: debugRequest.value, size: 'mini' }}
        >
          <text-highlight
            style='word-break: break-all'
            queries={getHeightLightList(effectOriginal.value)}
          >
            {effectOriginal.value}
          </text-highlight>
        </div>
      </div>
    );
  },
});
