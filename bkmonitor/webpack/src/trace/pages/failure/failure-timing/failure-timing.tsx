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
import { type PropType, type Ref, defineComponent, inject } from 'vue';

import { Alert, Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import TimelineDiagram from './timeline-diagram';

import type { IAlert, IAlertObj, IIncidentOperation } from '../types';

import './failure-timing.scss';

export default defineComponent({
  name: 'FailureTiming',
  props: {
    alertAggregateData: {
      type: Array as PropType<IAlert[]>,
      default: () => [],
    },
    scrollTop: {
      type: Number,
      default: 0,
    },
    chooseOperation: {
      type: Object as () => IIncidentOperation,
      default: () => ({}),
    },
  },
  emits: ['goAlertDetail', 'refresh', 'changeTab'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const operationsLoading = inject<Ref>('operationsLoading');
    const goAlertDetail = (alertObj: IAlertObj) => {
      emit('goAlertDetail', alertObj);
    };
    const refresh = () => {
      emit('refresh');
    };
    const changeTab = () => {
      emit('changeTab');
    };
    return {
      t,
      operationsLoading,
      goAlertDetail,
      refresh,
      changeTab,
    };
  },
  render() {
    return (
      <div class='failure-timing'>
        <Alert
          class='timing-alert'
          title={this.t(
            '在“故障处理”展开折叠告警拓扑，会对应展开收起时序图块；在“故障流转”点击事件，会高亮对应的时间节点。'
          )}
          theme='info'
        />
        <Loading loading={this.operationsLoading}>
          <TimelineDiagram
            alertAggregateData={this.$props.alertAggregateData}
            chooseOperation={this.$props.chooseOperation}
            scrollTop={this.$props.scrollTop}
            onChangeTab={this.changeTab}
            onGoAlertDetail={this.goAlertDetail}
            onRefresh={this.refresh}
          />
        </Loading>
      </div>
    );
  },
});
