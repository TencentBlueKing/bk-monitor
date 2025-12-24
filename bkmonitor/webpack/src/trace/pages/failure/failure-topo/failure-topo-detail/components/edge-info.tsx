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
import { type PropType, type Ref, computed, defineComponent, inject } from 'vue';

import { OverflowTitle } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { checkIsRoot } from '../../../utils';
import { NODE_TYPE_ICON } from '../../node-type-svg';
import { canJumpByType, getApmServiceType, handleToLink } from '../../utils';
import MetricView from './metric-view';

import type { IncidentDetailData, ITopoNode } from '../../types';

import './edge-info.scss';

export default defineComponent({
  props: {
    activeEdge: {
      type: Object as PropType<any>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
    const incidentDetailData: Ref<IncidentDetailData> = computed(() => {
      return incidentDetail.value;
    });

    /** 边的node展示  */
    const createEdgeNodeItem = (node: ITopoNode) => {
      return [
        <div
          key={`${node?.entity?.entity_id}-${node?.entity?.entity_name}`}
          class='node-source-wrap'
        >
          <div
            class={[
              'node-source',
              node?.entity?.is_anomaly && 'node-source-anomaly',
              node?.entity?.is_on_alert && 'node-source-alert',
              node?.alert_all_recorved && 'node-source-alert-recorved',
            ]}
          >
            <span class='node-item'>
              <span>
                {(node?.entity?.is_on_alert || node?.alert_all_recorved) && (
                  <span class='alert-wrap'>
                    <i class='icon-monitor icon-menu-event' />
                  </span>
                )}

                <i
                  style={{ color: '#eaebf0' }}
                  class={[
                    'item-source mr0',
                    'icon-monitor',
                    'edge-item-source',
                    NODE_TYPE_ICON[getApmServiceType(node?.entity)],
                    node?.entity?.is_anomaly && 'item-anomaly',
                  ]}
                />
              </span>
            </span>
            <span class='node-name-start'>
              {node?.entity?.properties?.entity_category || node?.entity?.entity_type}
              {' ('}
            </span>
            <OverflowTitle
              key={node?.entity?.entity_id}
              class={['node-name', canJumpByType(node) && 'node-link-name']}
              type='tips'
            >
              <span onClick={handleToLink.bind(this, node, bkzIds.value, incidentDetailData.value)}>
                {node?.entity?.entity_name || '--'}
              </span>
            </OverflowTitle>
            <span style={{ color: '#eaebf0' }}>{')'}</span>
            {(checkIsRoot(node?.entity) || node.is_feedback_root) && (
              <span class={['node-root-icon', node.is_feedback_root ? 'node-root-feedback-icon' : false]}>
                {t('根因')}
              </span>
            )}
          </div>
        </div>,
      ];
    };

    /**
     * 为调用关系则创建流动线
     * 线根据direction 渲染不同的流动方向
     * ebpfCall为true表示调用关系，反之为从属关系
     */
    const createEdgeLink = () => {
      const { is_anomaly, edge_type, events } = props.activeEdge;
      const ebpfCall = edge_type === 'ebpf_call';
      const directionReverse = events[0]?.direction === 'reverse';
      /** 流动线创建 */
      const renderSvg = () => {
        return (
          <div class='link-svg'>
            <svg
              width='2'
              height='22'
              xmlns='http://www.w3.org/2000/svg'
            >
              <line
                class={{ 'flowing-dash': ebpfCall }}
                stroke='#f55555'
                stroke-dasharray='5,5'
                stroke-width='2'
                x1='1'
                x2='1'
                y1='0'
                y2='22'
              />
            </svg>
          </div>
        );
      };
      const nodeLinkStyle = {
        '--arrowColor': is_anomaly ? '#f55555' : '#63656e',
        '--arrowRight': is_anomaly ? '-5px' : '-6px',
      };
      return (
        <div
          style={nodeLinkStyle}
          class={[
            'node-link',
            !is_anomaly && 'node-link-normal',
            directionReverse && 'reverse-node-link',
            ebpfCall && 'edpf-link-arrow',
          ]}
        >
          {ebpfCall && is_anomaly && renderSvg()}
        </div>
      );
    };

    /** 渲染边的信息 */
    const renderEdgeInfo = () => {
      const nodes: ITopoNode[] = props.activeEdge.nodes;
      return [
        <div
          key={`edge-info-${props.activeEdge.id}`}
          class={'edge-info-content'}
        >
          {createEdgeNodeItem(nodes[0])}
          {createEdgeLink()}
          {createEdgeNodeItem(nodes[1])}
        </div>,
      ];
    };
    return {
      renderEdgeInfo,
      t,
    };
  },
  render() {
    return (
      <div class='edge-wrap'>
        <div class='edge-info'>{this.renderEdgeInfo()}</div>
        <div class='edge-metrics'>
          <div class='edge-metrics_title'>{this.t('指标')}</div>
          <div class='edge-metrics_main'>
            <MetricView
              data={this.activeEdge}
              type='edge'
              {...this.$attrs}
            />
          </div>
        </div>
      </div>
    );
  },
});
