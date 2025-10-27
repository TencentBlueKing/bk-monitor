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

import { defineComponent, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import DimensionSplit from './dimension-split';
import TemporaryGroup from './temporary-group';
import TimeCompare from './time-compare';

import './index.scss';

export default defineComponent({
  name: 'QuickFilter',
  components: {
    DimensionSplit,
    TemporaryGroup,
    TimeCompare,
  },
  props: {
    fingerOperateData: {
      type: Object,
      require: true,
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    requestData: {
      type: Object,
      require: true,
    },
    totalFields: {
      type: Array,
      require: true,
    },
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    strategyHaveSubmit: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const dimensionSplitRef = ref(null);
    const temporaryGroupRef = ref(null);
    const timeCompareRef = ref(null);
    const isNear24 = ref(false);

    const handleFingerOperate = (operateType: string, val: any, isQuery: boolean) => {
      if (operateType === 'requestData') {
        const dimensionValue = dimensionSplitRef.value?.getValue();
        const groupValue = temporaryGroupRef.value?.getValue();
        const yoyValue = timeCompareRef.value?.getValue();
        const sortedValue = {
          group_by: [...dimensionValue, ...groupValue],
          ...yoyValue,
        };
        emit('handle-finger-operate', operateType, sortedValue, isQuery);
        return;
      }
      emit('handle-finger-operate', operateType, val, isQuery);
    };

    const handleShowNearPattern = (isShow: boolean) => {
      isNear24.value = isShow;
      emit('handle-finger-operate', 'requestData', { show_new_pattern: isShow }, true);
    };

    const handleClickTrigger = (type: string, auto = false) => {
      const triggerRefsMap = {
        'dimension-split': dimensionSplitRef,
        'temporary-group': temporaryGroupRef,
        'time-compare': timeCompareRef,
      };
      Object.keys(triggerRefsMap).forEach(key => {
        if (key !== type) {
          triggerRefsMap[key].value.hide();
        }
      });

      if (auto) {
        triggerRefsMap[type].value?.show();
      }
    };

    return () => (
      <div class='fingerprint-setting'>
        <div
          v-bk-tooltips={{
            content: t('请先新建新类告警策略'),
            disabled: props.strategyHaveSubmit,
          }}
        >
          <bk-checkbox
            class='new-class-checkbox'
            value={isNear24.value}
            disabled={!props.clusterSwitch || !props.strategyHaveSubmit}
            false-value={false}
            true-value={true}
            data-test-id='fingerTable_checkBox_selectCustomSize'
            on-change={handleShowNearPattern}
          >
            <span>{t('仅查看新类 Pattern')}</span>
          </bk-checkbox>
        </div>
        <div class='split-line'></div>
        <dimension-split
          ref={dimensionSplitRef}
          indexId={props.indexId}
          clusterSwitch={props.clusterSwitch}
          fingerOperateData={props.fingerOperateData}
          on-handle-finger-operate={handleFingerOperate}
          on-click-trigger={() => handleClickTrigger('dimension-split')}
          on-open-temp-group={() => handleClickTrigger('temporary-group', true)}
        />
        <temporary-group
          ref={temporaryGroupRef}
          indexId={props.indexId}
          clusterSwitch={props.clusterSwitch}
          fingerOperateData={props.fingerOperateData}
          on-handle-finger-operate={handleFingerOperate}
          on-click-trigger={() => handleClickTrigger('temporary-group')}
          on-open-dimension-split={() => handleClickTrigger('dimension-split', true)}
        />
        <time-compare
          ref={timeCompareRef}
          indexId={props.indexId}
          clusterSwitch={props.clusterSwitch}
          requestData={props.requestData}
          fingerOperateData={props.fingerOperateData}
          on-handle-finger-operate={handleFingerOperate}
          on-click-trigger={() => handleClickTrigger('time-compare')}
        />
      </div>
    );
  },
});
