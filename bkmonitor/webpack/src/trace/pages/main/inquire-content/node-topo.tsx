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
import { type PropType, computed, defineComponent, ref } from 'vue';

import RelationTopo from '../../../components/relation-topo/relation-topo';
import ServiceTopo from '../../../components/relation-topo/service-topo';
import { useTraceStore } from '../../../store/modules/trace';
import { ETopoType as EType } from '../../../typings/trace';

import './node-topo.scss';

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
  type: {
    type: String as PropType<EType>,
    default: EType.time,
  },
  updateMatchedSpanIds: Function as PropType<(count: number) => void>,
};

export default defineComponent({
  name: 'NodeTopo',
  props: NodeTopoProps,
  emits: [
    'showSpanDetail',
    'spanListChange',
    'compareSpanListChange',
    'update:loading',
    'typeChange',
    'serviceTopoClickItem',
  ],
  setup(props, { emit }) {
    const store = useTraceStore();
    const relationTopo = ref();

    const type = ref<EType>(EType.time);

    // 服务topo数据
    const serviceTopoData = computed(() => store.traceData.streamline_service_topo);
    /** 是否显示耗时 */
    const isShowDuration = computed(() => store.traceViewFilters.includes('duration'));

    // 当前classify 用于服务topo搜索
    const currentClassify = ref(null);

    init();

    function init() {
      type.value = props.type;
    }

    /* 以下函数皆为RelationTopo组件的emit  */
    function handleTypeChange(value: EType) {
      if (type.value !== value) {
        type.value = value;
        emit('typeChange', value);
      }
    }
    function handleKeywordFliter(value: string[]) {
      relationTopo.value?.handleKeywordFliter?.(value);
    }
    function clearSearch() {
      relationTopo.value?.clearSearch?.();
      currentClassify.value = null;
    }
    function handleClassifyFilter(matchedSpanIds: Set<string>, classify) {
      currentClassify.value = classify;
      relationTopo.value?.handleClassifyFilter(matchedSpanIds);
    }
    function viewCompare(traceID) {
      relationTopo.value?.viewCompare(traceID);
    }
    function prevResult() {
      relationTopo.value?.prevResult();
    }
    function nextResult() {
      relationTopo.value?.nextResult();
    }
    function handleClickItem(keys) {
      emit('serviceTopoClickItem', keys);
    }

    return {
      type,
      relationTopo,
      serviceTopoData,
      isShowDuration,
      currentClassify,
      handleTypeChange,
      handleKeywordFliter,
      clearSearch,
      handleClassifyFilter,
      viewCompare,
      prevResult,
      nextResult,
      handleClickItem,
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
          />
        )}
        {this.type === EType.service && (
          <ServiceTopo
            classify={this.currentClassify}
            isShowDuration={this.isShowDuration}
            serviceTopoData={this.serviceTopoData}
            onClickItem={keys => this.handleClickItem(keys)}
          />
        )}
      </div>
    );
  },
});
