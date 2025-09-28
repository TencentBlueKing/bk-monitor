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
import { type PropType, type Ref, computed, defineComponent, getCurrentInstance, inject, ref } from 'vue';

import { Message, Popover } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import AggregatedEdgesList from './components/aggregated-edges-list';
import { NODE_TYPE_ICON } from './node-type-svg';
import { canJumpByType, handleToLink, typeToLinkHandle } from './utils';
import { getApmServiceType, getNodeAttrs } from './utils';

import type { IEdge, IncidentDetailData, ITopoNode } from './types';

import './failure-topo-tooltips.scss';
type PopoverInstance = {
  [key: string]: any;
  close?: () => void;
  hide?: () => void;
  show?: () => void;
};

export default defineComponent({
  props: {
    /** 是否展示从属关系相关内容 */
    showViewResource: {
      type: Boolean,
      default: true,
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
      type: [Object, Array] as PropType<any>,
      required: true,
    },
  },
  emits: ['viewResource', 'viewService', 'hide'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    /** 当前点击的节点 */
    const activeNode = ref(null);
    const popover = ref<HTMLDivElement>();
    const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
    const incidentDetailData: Ref<IncidentDetailData> = computed(() => {
      return incidentDetail.value;
    });
    const { proxy } = getCurrentInstance();

    /** 展示右侧资源图 */
    const handleViewResource = node => {
      if (node.entity.entity_id.indexOf('Unknown') !== -1) return;
      emit('hide');
      emit('viewResource', { sourceNode: props.model, node });
    };

    /** tooltips消失销毁图表 */
    const handleAfterHidden = () => {
      activeNode.value = null;
    };

    const handleActiveNode = (node: ITopoNode) => {
      // 存储当前聚合item的id
      activeNode.value = node;
    };

    /** 展示右侧节点/边概览 */
    const handleViewService = (node: ITopoNode) => {
      emit('hide');
      emit('viewService', { type: props.type, data: node, sourceNode: props.model, isAggregatedEdge: true });
    };

    /** 拷贝操作 */
    const handleCopy = (text: string) => {
      copyText(text);
      emit('hide');
      Message({
        theme: 'success',
        message: t('复制成功'),
      });
    };

    /** 跳转详情页 */
    const handleLink = (node: ITopoNode) => {
      handleToLink(node, bkzIds.value, incidentDetailData.value);
      emit('hide');
    };

    /** popover隐藏 */
    const hide = () => {
      if (!activeNode?.value?.id) {
        return;
      }
      (proxy.$refs?.[`popover_${activeNode.value.id}`] as PopoverInstance)?.hide?.();
      activeNode.value = null;
    };

    /** 聚合节点的Tooltips */
    const createNodeToolTipList = (node: ITopoNode) => {
      const { aggregated_nodes: aggregatedList, total_count, anomaly_count, entity } = node;
      const { groupAttrs } = getNodeAttrs(props.model);
      const createNodeItem = node => {
        const isShowRootText = node?.entity?.is_anomaly;
        return (
          <Popover
            ref={`popover_${node.id}`}
            extCls='failure-topo-tooltips-popover'
            v-slots={{
              content: <div class='failure-topo-tooltips'>{createNodeToolTip(node)}</div>,
              default: (
                <li
                  class={['node-list-item']}
                  onClick={handleActiveNode.bind(this, node)}
                >
                  <span class='tool-tips-list-item'>
                    <span
                      key={`${node.id}-edge-icon-source`}
                      style={{ backgroundColor: groupAttrs.fill, border: `1px solid ${groupAttrs.stroke}` }}
                      class='item-source'
                    >
                      <i
                        class={[
                          'icon-monitor',
                          NODE_TYPE_ICON[getApmServiceType(node?.entity)],
                          isShowRootText && 'item-anomaly',
                          node?.entity?.is_on_alert && 'item-alert',
                        ]}
                      />
                    </span>
                    <span
                      key={`${node.id}-edge-name`}
                      class='tool-tips-list-item__name'
                    >
                      {node?.entity?.entity_name}
                    </span>
                  </span>
                </li>
              ),
            }}
            arrow={false}
            placement='right-start'
            popoverDelay={[100, 200]}
            renderType='shown'
            trigger='click'
            onAfterHidden={handleAfterHidden}
          />
        );
      };
      return (
        <div class='node-tooltips-list-wrap'>
          <span class='title-wrap'>
            <i18n-t
              class='tool-tips-list-title'
              v-slots={{
                slot0: () => <span class='weight'>{total_count}</span>,
                type: () => entity.entity_type,
                slot1: () => <span class='weight error-color'>{anomaly_count}</span>,
              }}
              keypath={
                (anomaly_count as number) > 0
                  ? '共 {slot0} 个 {type}节点，其中 {slot1} 个异常'
                  : '共 {slot0} 个 {type}节点'
              }
              tag='span'
            />
          </span>
          <ul class='tool-tips-list'>{[createNodeItem(node), ...aggregatedList.map(createNodeItem)]}</ul>
        </div>
      );
    };

    /** 节点的Tooltips */
    const createNodeToolTip = (node: ITopoNode) => {
      return (
        <div class='node-tooltip-list'>
          <div
            class='list-item'
            onClick={handleViewService.bind(this, node)}
          >
            <i
              style='font-size: 13px;'
              class='icon-monitor icon-mc-overview list-item-icon'
            />
            {t('节点概览')}
          </div>
          {props.showViewResource && (
            <div
              class={['list-item', node.entity.entity_id.indexOf('Unknown') !== -1 ? 'is-disabled' : '']}
              v-bk-tooltips={{
                disabled: node.entity.entity_id.indexOf('Unknown') === -1,
                content: t('第三方节点不支持查看从属'),
                placement: 'bottom',
              }}
              onClick={handleViewResource.bind(this, node)}
            >
              <i
                style='font-size: 15px; margin-left: -1px;'
                class='icon-monitor icon-ziyuan list-item-icon'
              />
              {t('从属关系')}
            </div>
          )}
          {canJumpByType(node) && (
            <div
              class='list-item'
              onClick={handleLink.bind(this, node)}
            >
              <i class='icon-monitor icon-fenxiang list-item-icon' />
              <i18n-t keypath={'跳转至 {0} 查看'}>
                <span style={{ padding: '0 2px' }}>
                  {typeToLinkHandle[node?.entity?.entity_type]?.title ?? '主机详情页'}
                </span>
              </i18n-t>
            </div>
          )}
          <div
            class='list-item'
            onClick={handleCopy.bind(this, node?.entity?.entity_name)}
          >
            <i class='icon-monitor icon-mc-copy list-item-icon' />
            {t('复制节点名')}
          </div>
        </div>
      );
    };

    /** 聚合边的Tooltips */
    const createEdgeToolTipList = (edge: IEdge) => {
      const { aggregated_edges: aggregatedList, edge_type } = edge;
      return (
        <div class='edge-tooltips-list-wrap'>
          <span class='title-wrap'>
            <i18n-t
              class='tool-tips-list-title'
              v-slots={{
                slot0: () => <span class='weight'>{aggregatedList.length + 1}</span>,
              }}
              keypath='共 {slot0} 条边'
              tag='span'
            />
          </span>
          <ul class='tool-tips-list'>
            <AggregatedEdgesList
              edge={edge}
              edgeType={edge_type as string}
              onClick={handleViewService}
            />
            {aggregatedList.map(aggEdge => (
              <AggregatedEdgesList
                key={aggEdge.id}
                edge={aggEdge}
                edgeType={edge_type as string}
                onClick={handleViewService}
              />
            ))}
          </ul>
        </div>
      );
    };

    /** 渲染节点的tips */
    const renderNodeTips = () => {
      const { aggregated_nodes } = props.model;
      return props.showViewResource && aggregated_nodes.length > 0
        ? createNodeToolTipList(props.model)
        : createNodeToolTip(props.model);
    };

    /** 渲染边的tips */
    const renderEdgeTips = () => {
      if (props.edge?.aggregated) {
        return createEdgeToolTipList(props.edge);
      }
      return null;
    };

    return {
      popover,
      activeNode,
      hide,
      renderNodeTips,
      renderEdgeTips,
    };
  },
  render() {
    if (!this.model) return undefined;
    return (
      <div class='failure-topo-tooltips'>{this.type === 'edge' ? this.renderEdgeTips() : this.renderNodeTips()}</div>
    );
  },
});
