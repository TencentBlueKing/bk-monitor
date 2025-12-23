/* eslint-disable @typescript-eslint/naming-convention */
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
import { type PropType, type Ref, computed, defineComponent, inject, ref, watch } from 'vue';

import { Message, OverflowTitle } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { checkIsRoot } from '../../../utils';
import AggregatedEdgesList from '../../components/aggregated-edges-list';
import { NODE_TYPE_ICON } from '../../node-type-svg';
import { canJumpByType, getApmServiceType, handleToLink, truncateText, typeToLinkHandle } from '../../utils';
import MetricView from './metric-view';

import type { ActiveTab, IEdge, IncidentDetailData, ITopoNode } from '../../types';

import './node-info.scss';

export default defineComponent({
  props: {
    model: {
      type: Object as PropType<ITopoNode>,
      required: true,
    },
    showViewResource: {
      type: Boolean,
      required: true,
    },
    linkedEdges: {
      type: Array as PropType<IEdge[]>,
      default: () => [],
    },
    nodeActiveTab: {
      type: String as PropType<ActiveTab>,
      default: 'metric',
    },
  },
  emits: [
    'toDetailSlider',
    'toTracePage',
    'toDetailTab',
    'toDetail',
    'FeedBack',
    'showEdgeDetail',
    'update:nodeActiveTab',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
    const incidentDetailData: Ref<IncidentDetailData> = computed(() => {
      return incidentDetail.value;
    });
    const activeTab = computed({
      get: () => props.nodeActiveTab,
      set: (val: ActiveTab) => {
        emit('update:nodeActiveTab', val);
      },
    });
    const tabPanels = ref([
      { id: 'metric', name: t('指标'), count: 0 },
      { id: 'linkedEdge', name: t('关联边'), count: 0 },
    ]);
    const nodeInfoWrapRef = ref<HTMLElement | null>(null);
    const maxHeight = ref<string>('100%');
    const metricsDataLength = ref<number>(0);
    const hasMetricDataLoaded = ref(false);

    /** 详情侧滑 */
    const goDetailSlider = node => {
      emit('toDetailSlider', node);
    };

    /** 根因上报 */
    const handleFeedBack = node => {
      emit('FeedBack', node);
    };

    /** 跳转trace详情页，高亮对应span */
    const handleViewSpan = node => {
      emit('toTracePage', node.entity, 'traceDetail');
    };

    /** 跳转trace详情页，打开对应span详情 */
    const handleViewSpanDetail = node => {
      emit('toTracePage', node.entity, 'spanDetail');
    };

    /** 告警详情 */
    const goDetailTab = node => {
      emit('toDetailTab', node);
    };

    /** 跳转详情 */
    const handleToDetail = node => {
      emit('toDetail', node);
    };

    /** 拷贝操作 */
    const handleCopy = (text: string) => {
      copyText(text);
      Message({
        theme: 'success',
        message: t('复制成功'),
      });
    };

    const createCommonIconBtn = (
      name: string,
      style?: Record<string, any>,
      needIcon = true,
      node: ITopoNode = {},
      clickFnName = '',
      onClickHandler?: (node: ITopoNode) => void
    ) => {
      const feedbackRootIcon = node.is_feedback_root ? 'icon-mc-cancel-feedback' : 'icon-fankuixingenyin';

      return (
        <span
          style={{ ...style }}
          class='icon-btn'
          onClick={() => onClickHandler?.(node)}
        >
          {needIcon && (
            <i
              class={[
                'icon-monitor',
                'btn-icon',
                clickFnName === 'FeedBack'
                  ? feedbackRootIcon
                  : clickFnName === 'ViewSpan'
                    ? 'icon-fenxiang'
                    : 'icon-ziyuantuopu',
              ]}
            />
          )}
          <span
            class='btn-text'
            v-overflow-tips
            onClick={() => handleToDetail(node)}
          >
            {name}
          </span>
        </span>
      );
    };

    /** 左右组合样式 */
    const createCommonForm = (label: string, value: () => any) => {
      return (
        <div class='content-form'>
          <div class='content-form-label'>{label}</div>
          <div class='content-form-value'>{value?.()}</div>
        </div>
      );
    };

    /** 渲染节点信息 */
    const renderNodeInfo = (node: ITopoNode) => {
      const isRoot = checkIsRoot(node?.entity);
      const isShowRootText = node.is_feedback_root || isRoot;
      const bgColor = isRoot ? '#EA3636' : '#FF9C01';
      return (
        <div class='node-info'>
          <div class='node-info-header'>
            <span class='item-source node-info-header_icon'>
              <i
                class={[
                  'icon-monitor',
                  NODE_TYPE_ICON[getApmServiceType(node?.entity)],
                  (isShowRootText || node?.entity?.is_anomaly) && 'item-anomaly',
                ]}
              />
            </span>
            <div
              key={node?.entity?.entity_id}
              class={['header-name', canJumpByType(node) && 'header-pod-name']}
              v-bk-tooltips={{
                disabled: !canJumpByType(node),
                content: (
                  <div>
                    <div>{node?.entity?.entity_name}</div>
                    <br />
                    {t(`点击前往：${typeToLinkHandle[node?.entity?.entity_type]?.title ?? '主机详情页'}`)}
                  </div>
                ),
              }}
            >
              <span onClick={handleToLink.bind(this, node, bkzIds.value, incidentDetailData.value)}>
                {node?.entity?.entity_name}
              </span>
            </div>
            <span
              class='copy-btn'
              onClick={handleCopy.bind(this, node?.entity?.entity_name)}
            >
              <i class={['icon-monitor', 'copy-icon', 'icon-mc-copy-fill']} />
              {t('复制')}
            </span>
            {isShowRootText && (
              <span
                style={{
                  backgroundColor: isShowRootText ? bgColor : '#00FF00',
                }}
                class='root-mark'
              >
                {truncateText(t('根因'), 28, 11, 'PingFangSC-Medium')}
              </span>
            )}
            <div class='node-info-header-icon-wrap'>
              {isShowRootText &&
                node.entity.rca_trace_info?.abnormal_traces?.length > 0 &&
                createCommonIconBtn(
                  t('查看Span'),
                  {
                    marginLeft: '16px',
                  },
                  true,
                  node,
                  'ViewSpan',
                  handleViewSpan
                )}
              {props.showViewResource &&
                node.is_feedback_root &&
                createCommonIconBtn(
                  t('取消反馈根因'),
                  {
                    marginLeft: '16px',
                  },
                  true,
                  node,
                  'FeedBack',
                  handleFeedBack
                )}
              {props.showViewResource &&
                !node.is_feedback_root &&
                !node?.entity?.is_root &&
                createCommonIconBtn(
                  t('反馈新根因'),
                  {
                    marginLeft: '16px',
                  },
                  true,
                  node,
                  'FeedBack',
                  handleFeedBack
                )}
            </div>
          </div>
          <div class='node-info-content'>
            {node.alert_display.alert_name &&
              createCommonForm(`${t('包含告警')}：`, () => (
                <>
                  <span
                    class='flex-label'
                    onClick={() => goDetailSlider(node)}
                  >
                    {createCommonIconBtn(
                      node.alert_display.alert_name || '',
                      {
                        marginRight: '4px',
                      },
                      false,
                      node
                    )}
                  </span>
                  {node.alert_ids.length > 1 && (
                    <span
                      class='flex-text'
                      onClick={() => goDetailTab(node)}
                    >
                      <i18n-t
                        class='tool-tips-list-title'
                        v-slots={{
                          slot0: () =>
                            createCommonIconBtn(
                              node.alert_ids.length.toString(),
                              {
                                marginLeft: '-5px',
                                color: '#699DF4',
                              },
                              false
                            ),
                        }}
                        keypath='等共 {slot0} 个同类告警'
                        tag='span'
                      />
                    </span>
                  )}
                </>
              ))}
            {isShowRootText &&
              node.entity?.rca_trace_info?.abnormal_message &&
              createCommonForm(`${t('异常信息')}：`, () => (
                <div
                  class='except-info'
                  onClick={handleViewSpanDetail.bind(this, node)}
                >
                  <OverflowTitle
                    class='except-text'
                    popoverOptions={{ maxWidth: 360, placement: 'top', extCls: 'except-text_popover' }}
                    type='tips'
                  >
                    <span>{node.entity.rca_trace_info.abnormal_message}</span>
                  </OverflowTitle>
                  <i class='icon-monitor except-icon icon-fenxiang' />
                </div>
              ))}
            {createCommonForm(`${t('分类')}：`, () => (
              <>{node.entity.rank.rank_category.category_alias}</>
            ))}
            {createCommonForm(`${t('节点类型')}：`, () => (
              <>{node?.entity?.properties?.entity_category || node.entity.rank_name}</>
            ))}
            {createCommonForm(`${t('所属业务')}：`, () => (
              <>
                [#{node.bk_biz_id}] {node.bk_biz_name}
              </>
            ))}
            {node.entity?.tags?.BcsService &&
              createCommonForm(`${t('所属服务')}：`, () => <>{node.entity.tags.BcsService.name}</>)}
          </div>
        </div>
      );
    };

    /** 点击展示边概览 */
    const showEdgeDetail = (node: ITopoNode) => {
      emit('showEdgeDetail', node);
    };

    const getCount = (id: ActiveTab) => {
      if (id === 'metric') {
        return hasMetricDataLoaded.value ? metricsDataLength.value : '';
      }
      return props.linkedEdges.length || 0;
    };

    const handleMetricChange = (val: number) => {
      hasMetricDataLoaded.value = true;
      metricsDataLength.value = val;
    };

    // 由于节点概览的info模块高度是动态的，所以监听model，更新tab高度
    watch(
      () => props.model,
      () => {
        setTimeout(() => {
          if (nodeInfoWrapRef.value) {
            const height = nodeInfoWrapRef.value.offsetHeight;
            maxHeight.value = `calc(100% - ${height + 40}px)`;
          }
        }, 100);
      },
      { immediate: true }
    );

    return {
      activeTab,
      tabPanels,
      maxHeight,
      nodeInfoWrapRef,
      renderNodeInfo,
      showEdgeDetail,
      getCount,
      handleMetricChange,
    };
  },
  render() {
    return [
      <div
        key='nodeInfo'
        ref='nodeInfoWrapRef'
        class='node-info-wrap'
      >
        {this.renderNodeInfo(this.model)}
      </div>,
      <div
        key={`node-info-tab-${this.activeTab}`}
        style={{ maxHeight: this.maxHeight }}
        class='node-info-tab'
      >
        <div class='node-info-tab__head'>
          {this.tabPanels.map(item => (
            <span
              key={item.id}
              class={['head-tab-item', { active: item.id === this.activeTab }]}
              onClick={() => {
                this.activeTab = item.id as ActiveTab;
              }}
            >
              {item.name}
              {this.getCount(item.id as ActiveTab) !== '' && ` (${this.getCount(item.id as ActiveTab)})`}
            </span>
          ))}
        </div>
        <div class='node-info-tab__main'>
          {this.activeTab === 'metric' ? (
            <MetricView
              data={this.model}
              type='node'
              {...this.$attrs}
              getMetricsDataLength={this.handleMetricChange}
            />
          ) : (
            <div class='aggregated-edges-wrap'>
              {this.linkedEdges.map(edge => (
                <AggregatedEdgesList
                  key={edge.id}
                  edge={edge}
                  edgeType={edge.edge_type}
                  onClick={this.showEdgeDetail}
                />
              ))}
            </div>
          )}
        </div>
      </div>,
    ];
  },
});
