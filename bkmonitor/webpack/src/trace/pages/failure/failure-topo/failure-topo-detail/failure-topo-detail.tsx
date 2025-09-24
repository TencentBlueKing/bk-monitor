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
import { type PropType, computed, defineComponent, ref, watch } from 'vue';

import { Exception } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import NoDataImg from '../../../../static/img/no-data.svg';
import EdgeInfo from './components/edge-info';
import NodeInfo from './components/node-info';

import type { IEdge, ActiveTab } from '../types';

import './failure-topo-detail.scss';

export default defineComponent({
  props: {
    showViewResource: {
      type: Boolean,
      default: true,
    },
    isClickEdgeItem: {
      type: Boolean,
      default: false,
    },
    type: {
      type: String,
      default: 'node',
    },
    edge: {
      type: Object as PropType<IEdge>,
      default: () => {},
    },
    model: {
      type: Object as PropType<any>,
      required: true,
    },
    linkedEdges: {
      type: Array as PropType<IEdge[]>,
      default: () => [],
    },
  },
  emits: [
    'FeedBack',
    'toDetail',
    'toDetailSlider',
    'toDetailTab',
    'toTracePage',
    'collapseService',
    'highlightEdge',
    'clearHighlightEdge',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 当前点击的边 */
    const activeEdge = ref(null);
    const showException = computed(
      () => (props.type === 'node' && !props.model) || (props.type === 'edge' && !activeEdge.value)
    );
    const forcedView = ref<'edge' | null>(null);
    const currentType = computed(() => forcedView.value || props.type);
    const nodeActiveTab = ref<ActiveTab>('metric');

    /** 线存在变化或者type变化为edge时或点击聚合边选项需要更新边信息时，更新当前边信息 */
    watch(
      () => ({ edge: props.edge, isUpdate: props.isClickEdgeItem }),
      ({ edge, isUpdate }) => {
        if (!edge?.aggregated || isUpdate) {
          activeEdge.value = edge || {};
          if (forcedView.value === 'edge') {
            handleBack('metric');
          } else {
            nodeActiveTab.value = 'metric';
          }
        }
      },
      { immediate: true }
    );

    watch(
      () => props.model,
      () => {
        // 节点信息更新时，若还在查看关联边信息，则需要返回到节点概览页
        if (forcedView.value === 'edge') {
          handleBack('metric');
        } else {
          nodeActiveTab.value = 'metric';
        }
      },
      { immediate: true }
    );

    /** 根因上报 */
    const handleFeedBack = node => {
      emit('FeedBack', node);
    };

    /** 跳转详情 */
    const handleToDetail = node => {
      emit('toDetail', node);
    };

    /** 详情侧滑 */
    const goDetailSlider = node => {
      emit('toDetailSlider', node);
    };

    /** 跳转trace页面 */
    const handleToTracePage = (entity, type) => {
      emit('toTracePage', entity, type);
    };

    /** 告警详情 */
    const goDetailTab = node => {
      emit('toDetailTab', node);
    };

    const handleException = () => {
      return (
        <Exception
          class='exception-wrap'
          v-slots={{
            type: () => (
              <img
                class='custom-icon'
                alt=''
                src={NoDataImg}
              />
            ),
          }}
        >
          <div style={{ color: '#979BA5' }}>
            <div class='exception-title'>{t('暂无数据')}</div>
          </div>
        </Exception>
      );
    };

    /** 返回到节点概览页 */
    const handleBack = (type: ActiveTab) => {
      forcedView.value = null;
      // 清除高亮边
      emit('clearHighlightEdge', false, props.model.id);

      nodeActiveTab.value = type;
    };

    const handleCollapseService = () => {
      emit('collapseService');
    };

    const handleShowEdgeDetail = linkedEdgeData => {
      forcedView.value = 'edge';
      activeEdge.value = linkedEdgeData;
      emit('highlightEdge', linkedEdgeData);
    };

    return {
      activeEdge,
      showException,
      currentType,
      forcedView,
      nodeActiveTab,
      goDetailTab,
      handleException,
      handleCollapseService,
      handleBack,
      handleShowEdgeDetail,
      handleFeedBack,
      handleToDetail,
      goDetailSlider,
      handleToTracePage,
      t,
    };
  },
  render() {
    return (
      <div class='failure-topo-detail'>
        <div class='detail-title'>
          {this.forcedView && (
            <span onClick={() => this.handleBack('linkedEdge')}>
              <i class='icon-monitor icon-back-left detail-title_back' />
            </span>
          )}
          <span class='detail-title_label'>{this.currentType === 'edge' ? this.t('边概览') : this.t('节点概览')}</span>
          <span onClick={this.handleCollapseService}>
            <i class='icon-monitor icon-gongneng-shouqi detail-title_icon' />
          </span>
        </div>

        {this.showException ? (
          this.handleException()
        ) : (
          // biome-ignore lint/complexity/noUselessFragments: <explanation>
          <>
            {this.currentType === 'edge' ? (
              <EdgeInfo
                activeEdge={this.activeEdge}
                {...this.$attrs}
              />
            ) : (
              <NodeInfo
                linkedEdges={this.linkedEdges}
                model={this.model}
                showViewResource={this.showViewResource}
                {...this.$attrs}
                v-model:nodeActiveTab={this.nodeActiveTab}
                onFeedBack={this.handleFeedBack}
                onShowEdgeDetail={this.handleShowEdgeDetail}
                onToDetail={this.handleToDetail}
                onToDetailSlider={this.goDetailSlider}
                onToDetailTab={this.goDetailTab}
                onToTracePage={this.handleToTracePage}
              />
            )}
          </>
        )}
      </div>
    );
  },
});
