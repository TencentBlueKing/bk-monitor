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
import { Component, Emit, Inject, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IDragStatus, filterTaskAlarmColor, isTaskDisable } from '../uptime-check-data';

import './task-card.scss';
import { xssFilter } from 'monitor-common/utils/xss';

export type IOptionTypes = 'clone' | 'delete' | 'edit' | 'enable' | 'stop';
const options: { id: IOptionTypes; name: string }[] = [
  { id: 'edit', name: window.i18n.tc('编辑') },
  { id: 'delete', name: window.i18n.tc('删除') },
  { id: 'clone', name: window.i18n.tc('克隆') },
  { id: 'stop', name: window.i18n.tc('停用') },
  { id: 'enable', name: window.i18n.tc('启用') },
];

const contentItem = [
  { id: 'available', alarmId: 'available_alarm', unit: '%', name: window.i18n.t('可用率') },
  { id: 'task_duration', alarmId: 'task_duration_alarm', unit: 'ms', name: window.i18n.t('平均响应时长') },
];

export interface IData {
  available?: number; // 可用率
  available_alarm?: boolean; // 数字颜色是否变为红色
  bk_biz_id?: number;
  create_user?: string;
  groups?: { id: number; name: string }[];
  id?: number;
  name?: string;
  nodes?: { name?: string }[];
  status?: string; // 状态
  task_duration?: number; // 平均响应时长
  task_duration_alarm?: boolean; // 数字颜色是否变为红色
  url?: string[];
  config: {
    ip_list?: string[]; // 固定ip集合
    node_list?: {bk_host_id?: number}[] | {bk_obj_id?: string}[]; // cmbd查询参数
    url_list?: string[]; // 域名集合
    port?: string; // 端口号，存在此配置时，域名和ip的展示方式为[域名/ip]: 端口号
  }
  protocol: string; // 协议类型
}
interface ITaskCardEvents {
  onCardClick?: number;
  onDragStatus?: IDragStatus;
  onOperate?: IOptionTypes;
}

interface ITaskCardProps {
  data?: IData;
}
@Component({
  name: 'TaskCard',
})
export default class TaskCard extends tsc<ITaskCardProps, ITaskCardEvents> {
  @Inject('authority') authority;
  @Inject('authorityMap') authorityMap;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  @Prop({
    type: Object,
    default: () => ({
      id: 0,
      name: '',
      url: '',
      available: 0,
      available_alarm: false,
      task_duration: 0,
      task_duration_alarm: false,
      status: '',
    }),
  })
  data: IData;

  @Ref('popoverContent') popoverContentRef: HTMLDivElement;

  popoverInstance = null;

  get titleUrl() {
    const { config, url, protocol } = this.data;
    const titleData = [];
    // 固定IP
    if (config.ip_list?.length) {
      // 有端口号则显示方式变为[ip]: 端口号
      const ipList = config.ip_list.map(ip => config.port ? `[${ip}]:${config.port}` : ip);
      const displayIps = ipList;
      titleData.push({
        name: this.$t('固定IP'),
        value: displayIps,
        total: config.ip_list.length,
      });
    }

    // 域名
    if (config.url_list?.length) {
      // 有端口号则显示方式变为[ip]: 端口号
      const urlList = config.url_list.map(ip => config.port ? `[${ip}]:${config.port}` : ip);
      const displayUrls = urlList;
      titleData.push({
        name: protocol === 'HTTP' ? 'URL' : this.$t('域名'),
        value: displayUrls,
        total: config.url_list.length,
      });
    }

    // CMBD
    if (config.node_list?.length) {
      let name = '';
      // ip-静态拓扑 
      if ('bk_host_id' in config.node_list[0]) {
        name = this.$t('IP-静态拓扑') as string;
      } else if ('bk_obj_id' in config.node_list[0]) {
        switch (config.node_list[0].bk_obj_id.toUpperCase()) {
          case 'SET':
            name = this.$t('动态拓扑') as string;
            break;
          case 'SERVICE_TEMPLATE':
            name = this.$t('服务模板') as string;
            break;
          case 'SET_TEMPLATE':
            name = this.$t('集群模板') as string;
            break;
          default:
            break;
        }
      }
      // 处理CMBD数据
      const displayCMBDData = [];

      // 统计ipList重复项目和次数
      const ipListMap = new Map();
      for (const item of config.ip_list) {
        ipListMap.set(item, (ipListMap.get(item) || 0) + 1);
      }

      // 统计url数据重复项目和次数
      const urlDataMap = new Map();
      for (const item of url) {
        urlDataMap.set(item, (urlDataMap.get(item) || 0) + 1);
      }
      // 通过在url字段里排除固定ip列表(ip_list)和域名列表(url_list)数据，来推算出CMBD数据（固定ip列表数据可能有重复，且有可能与CMBD数据重复）
      /**
       * @param item // 后端返回总数据的item
       * @param countInArrTotal // 后端返回总数据的重复的次数
       * @param ipListMap  // 固定ip列表数据的重复项目和次数
       * @param config // 是否包含端口，后端返回url的数据仅显示方式不同
       * @returns 
       */
      const shouldDisplayItem = (item, countInArrTotal, ipListMap, config) => {
        let address = item;
        // 如果配置有端口，将带有端口的显示改为普通ip/域名显示([1.1.1.1]:8080 → 1.1.1.1)，然后进行匹配
        if (config.port) {
          const match = item.match(/\[([^\]]+)\]:\d+/); // 去除中括号和端口号的正则
          if (match) {
            address = match[1];
          } else {
            return false; // 没有匹配到，跳过
          }
        }
        const countInIpList = ipListMap.get(address) || 0;
        // 当前项在固定ip列表和总数据都有出现，且总数据内重复的次数大于固定ip列表内重复的次数，表明当前项是CMBD内的数据
        // 或者 当前项没在固定ip列表内出现过，也不在域名列表内出现过，也表明是CMBD内的数据
        return (countInArrTotal > countInIpList && countInIpList !== 0) || (countInIpList === 0 && !config.url_list.includes(address));
      };
      // 放入符合条件的数据
      for (const [item, countInArrTotal] of urlDataMap) {
        if (shouldDisplayItem(item, countInArrTotal, ipListMap, config)) {
          displayCMBDData.push(item);
        }
      }
      titleData.push({
        name,
        // value: displayCMBDData.length > 3 ? `${displayCMBDData.slice(0, 3).join('<br />  ●')}...` : displayCMBDData.join('<br />  ●'),
        value: displayCMBDData,
        total: displayCMBDData.length,
      });
    }
    return titleData;
  }

  handleDragStart() {
    const status = {
      taskId: this.data.id,
      dragging: true,
    };
    this.handleDragStatus(status);
  }
  handleDragEnd() {
    this.handleDragStatus({
      taskId: 0,
      dragging: false,
    });
  }
  handleMouseleave() {
    this.handlePopoverHide();
  }
  @Emit('operate')
  handleOptionsClick(e: Event, item) {
    e.stopPropagation();
    return item.id;
  }
  handlePopoverShow(e: Event) {
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.popoverContentRef,
      arrow: false,
      trigger: 'click',
      placement: 'bottom',
      theme: 'light task-card',
      maxWidth: 520,
      duration: [200, 0],
      appendTo: () => this.$el,
    });
    this.popoverInstance?.show(100);
  }
  handlePopoverHide() {
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }

  // 返回拖拽状态
  @Emit('dragStatus')
  handleDragStatus(v: IDragStatus) {
    return v;
  }
  // 点击卡片时
  @Emit('cardClick')
  handleCardClick() {
    return this.data.id;
  }

  renderCardTooltips() {
    return (
      `<div class='card-info-tooltips'>
        ${this.titleUrl.map(item => (
          `<div>
            <div>【${xssFilter(item.name)}】共${xssFilter(item.total)}个</div>
            ${item.total > 3
              ? item.value.slice(0, 3).map((v, index) => `<div class='card-info-tooltips__value'>&nbsp;●&nbsp;${xssFilter(v)}${index === 2 ? '...' : ''}</div>`).join('')
              : item.value.map(v => `<div class='card-info-tooltips__value'>&nbsp;●&nbsp;${xssFilter(v)}</div>`).join('')}
          </div>`
        )).join('<br />')}
      </div>`
    );
  }

  render() {
    return (
      <div
        class='uptime-check-task-card'
        draggable
        on-click={this.handleCardClick}
        on-dragend={this.handleDragEnd}
        on-dragstart={this.handleDragStart}
        on-mouseleave={this.handleMouseleave}
      >
        <div class='card-title'>
          <div class={['title-name', { disabled: isTaskDisable(this.data.status) }]}>
            <span
              class='name-text'
              v-bk-overflow-tips
            >
              {this.data.name}
            </span>
            {isTaskDisable(this.data.status) && <span class='title-status'>{this.$t('已停用')}</span>}
            {/* <span class="title-tip icon-monitor icon-hint"></span> */}
          </div>
          <div
            class='title-url'
            v-bk-tooltips={{
              content: this.renderCardTooltips(),
              allowHTML: true,
            }}
          >
            {
              // this.data.url.join(',')
              this.titleUrl.map(item => (
                `${item.name}（${item.total}）`
              )).join('、')
            }
          </div>
          <span
            class='title-icon'
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            onClick={(e: Event) => {
              e.stopPropagation();
              if (this.authority.MANAGE_AUTH) {
                this.handlePopoverShow(e);
              } else {
                this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH);
              }
            }}
          >
            <i class='icon-monitor icon-mc-more' />
          </span>
        </div>
        <div class='card-content'>
          {contentItem.map(item => (
            <div class='label-item'>
              {isTaskDisable(this.data.status) ? (
                <div class='top-nodata'>--</div>
              ) : !(item.id === 'task_duration' && this.data.task_duration === null) ? (
                <div class='top'>
                  <span
                    style={{ color: filterTaskAlarmColor(this.data[item.id], this.data[item.alarmId]) }}
                    class='num'
                  >
                    {this.data[item.id]}
                  </span>
                  <span class='unit'>{item.unit}</span>
                </div>
              ) : (
                <span class='icon-monitor icon-remind' />
              )}
              <div class='bottom'>{item.name}</div>
            </div>
          ))}
        </div>
        <div style={{ display: 'none' }}>
          <div
            ref='popoverContent'
            class='popover-desc'
          >
            {options
              .filter(item => (isTaskDisable(this.data.status) ? item.id !== 'stop' : item.id !== 'enable'))
              .map(item => (
                <div
                  class='popover-desc-btn'
                  onClick={(e: Event) => this.handleOptionsClick(e, item)}
                >
                  {item.name}
                </div>
              ))}
          </div>
        </div>
      </div>
    );
  }
}
