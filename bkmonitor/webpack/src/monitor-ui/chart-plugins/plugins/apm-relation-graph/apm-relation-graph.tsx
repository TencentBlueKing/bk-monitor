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

import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import StatusTab from '../table-chart/status-tab';
import ApmRelationGraphContent from './components/apm-relation-graph-content';
import BarAlarmChart from './components/bar-alarm-chart';

import type { PanelModel } from '../../typings';

import './apm-relation-graph.scss';

const sideTopoMinWidth = 400;
const sideOverviewMinWidth = 320;

interface IProps {
  panel?: PanelModel;
}
@Component
export default class ApmRelationGraph extends tsc<IProps> {
  @Ref('content-wrap') contentWrap: ApmRelationGraphContent;
  /* 概览图、列表图切换 */
  showTypes = [
    {
      id: 'overview',
      icon: 'icon-mc-overview',
    },
    {
      id: 'table',
      icon: 'icon-mc-list',
    },
  ];
  showType = 'overview';
  /* 数据类型 */
  dataTypes = [
    {
      id: 'error',
      name: '调用错误率',
    },
  ];

  /* 筛选列表 */
  filterList = [
    {
      id: 'all',
      name: '全部',
      icon: 'icon-gailan',
    },
    {
      id: 'http',
      name: '网页',
      icon: 'icon-wangye',
    },
    {
      id: 'rpc',
      name: '远程调用',
      icon: 'icon-yuanchengfuwu',
    },
    {
      id: 'db',
      name: '数据库',
      icon: 'icon-DB',
    },
    {
      id: 'messaging',
      name: '消息队列',
      icon: 'icon-xiaoxizhongjianjian',
    },
    {
      id: 'async_backend',
      name: '后台任务',
      icon: 'icon-renwu',
    },
    {
      id: 'other',
      name: '其他',
      icon: 'icon-zidingyi',
    },
  ];
  /* 展开列表 */
  expandList = [
    {
      id: 'topo',
      icon: 'icon-Component',
    },
    {
      id: 'overview',
      icon: 'icon-mc-overview',
    },
  ];
  expanded = ['topo', 'overview'];

  /**
   * @description 伸缩侧栏
   * @param id
   */
  handleExpand(id: string) {
    const index = this.expanded.findIndex(key => key === id);
    if (index >= 0) {
      let width = 0;
      if (this.expanded.length > 1) {
        if (id === 'topo') {
          const { clientWidth } = this.$el.querySelector('.side-wrap .source-topo');
          width = this.contentWrap.width - clientWidth;
        } else if (id === 'overview') {
          const { clientWidth } = this.$el.querySelector('.side-wrap .service-overview');
          width = this.contentWrap.width - clientWidth;
        }
      } else {
        width = 0;
      }
      this.expanded.splice(index, 1);
      this.contentWrap.setWidth(width);
    } else {
      this.expanded.push(id);
      let width = 0;
      if (id === 'topo') {
        width += sideTopoMinWidth;
      }
      if (id === 'overview') {
        width += sideOverviewMinWidth;
      }
      this.contentWrap.setWidth(this.contentWrap.width + width);
    }
    if (this.expanded.length) {
      let minWidth = 0;
      if (this.expanded.includes('topo')) {
        minWidth += sideTopoMinWidth;
      }
      if (this.expanded.includes('overview')) {
        minWidth += sideOverviewMinWidth;
      }
      this.contentWrap.setMinWidth(minWidth);
    }
  }

  render() {
    return (
      <div class='apm-relation-graph'>
        <div class='apm-relation-graph-header'>
          <div class='header-select-wrap'>
            <div class='data-type-select'>
              {this.showTypes.map(item => (
                <div
                  key={item.id}
                  class={['data-type-item', { active: this.showType === item.id }]}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
            <bk-select class='type-selector'>
              {this.dataTypes.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </div>
          <div class='header-alarm-wrap'>
            <BarAlarmChart
              activeItemHeight={24}
              itemHeight={16}
            />
          </div>
          <div class='header-search-wrap'>
            <StatusTab
              class='ml-24'
              needAll={false}
              statusList={this.filterList}
            />
            <bk-checkbox class='ml-24'>无数据节点</bk-checkbox>
            <bk-input
              class='ml-24'
              behavior='simplicity'
              placeholder={'搜索服务、接口'}
              right-icon='bk-icon icon-search'
              clearable
            />
          </div>
          <div class='header-tool-wrap'>
            <div class='tool-btns'>
              {this.expandList.map(item => (
                <div
                  key={item.id}
                  class={['tool-btn', { active: this.expanded.includes(item.id) }]}
                  onClick={() => this.handleExpand(item.id)}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
          </div>
        </div>
        <ApmRelationGraphContent ref='content-wrap'>
          <div>main</div>
          <div
            class='side-wrap'
            slot='side'
          >
            {this.expanded.includes('topo') && (
              <div
                style={{
                  minWidth: `${sideTopoMinWidth}px`,
                }}
                class='source-topo'
              >
                <div class='header-wrap'>
                  <div class='title'>资源拓扑</div>
                  <div
                    class='expand-btn'
                    onClick={() => this.handleExpand('topo')}
                  >
                    <span class='icon-monitor icon-zhankai' />
                  </div>
                </div>
                <div class='content-wrap' />
              </div>
            )}
            {this.expanded.includes('overview') && (
              <div
                style={{
                  minWidth: `${sideOverviewMinWidth}px`,
                }}
                class={['service-overview', { 'no-border': !this.expanded.includes('topo') }]}
              >
                <div class='header-wrap'>
                  <div class='title'>服务概览</div>
                  <div
                    class='expand-btn'
                    onClick={() => this.handleExpand('overview')}
                  >
                    <span class='icon-monitor icon-zhankai' />
                  </div>
                </div>
                <div class='content-wrap'>
                  <BarAlarmChart
                    activeItemHeight={32}
                    itemHeight={24}
                    showHeader={true}
                    showXAxis={true}
                  >
                    <div slot='title'>告警</div>
                    <div slot='more'>更多</div>
                  </BarAlarmChart>
                </div>
              </div>
            )}
          </div>
        </ApmRelationGraphContent>
      </div>
    );
  }
}
