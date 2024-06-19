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
import { PropType, defineComponent, ref } from 'vue';

import RelationTopo from '../../../components/relation-topo/relation-topo';
import ServiceTopo from '../../../components/relation-topo/service-topo';

import './node-topo.scss';

enum EType {
  service = 'service',
  time = 'time',
}
const typeList = [
  {
    id: EType.time,
    name: window.i18n.t('时间'),
  },
  {
    id: EType.service,
    name: window.i18n.t('服务'),
  },
];

const NodeTopoProps = {
  compareTraceID: {
    type: String,
    default: '',
  },
  updateMatchedSpanIds: Function as PropType<(count: number) => void>,
};

export default defineComponent({
  name: 'NodeTopo',
  props: NodeTopoProps,
  emits: ['showSpanDetail', 'spanListChange', 'compareSpanListChange', 'update:loading'],
  setup() {
    const relationTopo = ref();

    const type = ref<EType>(EType.time);

    function handleTypeChange(value: EType) {
      if (type.value !== value) {
        type.value = value;
      }
    }

    function handleKeywordFliter(value: string[]) {
      relationTopo.value?.handleKeywordFliter?.(value);
    }
    function clearSearch() {
      relationTopo.value?.clearSearch?.();
    }
    function handleClassifyFilter(matchedSpanIds: Set<string>) {
      relationTopo.value?.handleClassifyFilter(matchedSpanIds);
    }
    function viewCompare(traceID) {
      relationTopo.value?.viewCompare(traceID);
    }

    return {
      type,
      relationTopo,
      handleTypeChange,
      handleKeywordFliter,
      clearSearch,
      handleClassifyFilter,
      viewCompare,
    };
  },
  render() {
    return (
      <div class='trace-detail-node-topo'>
        <div class='header-type-list'>
          {typeList.map(item => (
            <div
              class={['header-type-list-item', { active: this.type === item.id }]}
              onClick={() => this.handleTypeChange(item.id)}
            >
              {item.name}
            </div>
          ))}
        </div>
        {this.type === EType.time && (
          <RelationTopo
            ref='relationTopo'
            {...this.$props}
            onCompareSpanListChange={(...arg) => this.$emit('compareSpanListChange', ...arg)}
            onShowSpanDetail={(...arg) => this.$emit('showSpanDetail', ...arg)}
            onSpanListChange={(...arg) => this.$emit('spanListChange', ...arg)}
            onUpdate:loading={(...arg) => this.$emit('update:loading', ...arg)}
          ></RelationTopo>
        )}
        {this.type === EType.service && <ServiceTopo></ServiceTopo>}
      </div>
    );
  },
});
