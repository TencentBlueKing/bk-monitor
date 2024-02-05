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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { actionDetail, searchAlert } from '../../../../monitor-api/modules/alert';
import { isZh } from '../../../../monitor-pc/common/constant';

import { getStatusInfo } from './type';

import './action-detail.scss';

const queryString = (type: 'trigger' | 'defense', id) => {
  if (type === 'trigger') {
    return isZh() ? `处理记录ID: ${id}` : `action_id: ${id}`;
  }
  return isZh() ? `收敛记录ID: ${id}` : `converge_id: ${id}`;
};
export const handleToAlertList = (
  type: 'trigger' | 'defense',
  detailInfo: { create_time: number; end_time: number; id: string; converge_id?: number },
  bizId
) => {
  // const queryStringUrl = `queryString="${encodeURI(queryString(type, detailInfo.id))}"`;
  const curUnix = dayjs.tz().unix() * 1000;
  const oneDay = 60 * 24 * 60 * 1000;
  const startTime = dayjs.tz(detailInfo.create_time * 1000 - oneDay).format('YYYY-MM-DD HH:mm:ss');
  const endTime = detailInfo.end_time
    ? dayjs
        .tz(detailInfo.end_time * 1000 + oneDay > curUnix ? curUnix : detailInfo.end_time * 1000 + oneDay)
        .format('YYYY-MM-DD HH:mm:ss')
    : dayjs.tz().format('YYYY-MM-DD HH:mm:ss');
  window.open(
    `${location.origin}${location.pathname}?bizId=${bizId}/#/event-center?queryString=${queryString(
      type,
      detailInfo.id
    )}&timeRange=${startTime}&timeRange=${endTime}`
  );
};

interface ITableData {
  id: string; // 告警ID
  alert_name: string; // 告警名称
  severity: number; // 级别
  dimensions: {
    display_key?: string;
    display_value?: boolean;
    key?: string;
    value?: boolean;
  }; // 告警内容
  description: string;
}
interface IActiveDetail {
  id?: string;
}
interface IDetailInfo {
  id?: string;
  action_name?: string;
  bk_target_display?: string; // 告警目标
  action_plugin?: { name?: string }; // 套餐类型
  duration?: string; // 耗时
  operator?: string[]; // 负责人
  create_time?: number; // 开始时间
  status?: string; // 状态
  update_time?: number; // 结束时间
  content?: { action_plugin_type?: string; text?: string; url?: string }; // 具体内容
  signal_display?: string; // 触发信号
  converge_id?: number; // 收敛id
  end_time?: number;
  operate_target_string?: string; // 执行对象
  bk_biz_id?: string;
  failure_type?: string;
  action_config_id?: string;
  action_plugin_type?: string;
}

@Component({
  name: 'ActiveDetail'
})
export default class ActiveDetail extends tsc<IActiveDetail> {
  @Prop({ type: String, default: '' }) id: string;

  detailInfo: IDetailInfo = {};
  tableData: { trigger: ITableData[]; defense: ITableData[] } = {
    trigger: [],
    defense: []
  };
  loading = false;
  popoperInstance: any = null;

  // 是否为单页
  get getIsPage() {
    return this.$route.name === 'event-center-action-detail';
  }

  async created() {
    this.loading = true;
    this.detailInfo = await actionDetail({ id: this.id }).catch(() => ({}));
    const oneDay = 60 * 24 * 60;
    const params = {
      conditions: [],
      end_time: this.detailInfo.end_time || dayjs.tz().unix(),
      ordering: [],
      page: 1,
      page_size: 10,
      record_history: false,
      show_aggs: false,
      show_overview: false,
      start_time: this.detailInfo.create_time - oneDay
    };
    const triggerData = await searchAlert({
      ...params,
      query_string: this.queryString('trigger')
    }).catch(() => []);
    const defense = await searchAlert({
      ...params,
      query_string: this.queryString('defense')
    }).catch(() => []);
    this.tableData.trigger = triggerData.alerts;
    this.tableData.defense = defense.alerts;
    this.loading = false;
  }
  queryString(type: 'trigger' | 'defense') {
    const { id } = this.detailInfo;
    return `${queryString(type, id)}`;
  }
  /**
   * @description: 跳转到告警列表
   * @param {*} type
   * @return {*}
   */
  handleToAlertList(type: 'trigger' | 'defense') {
    const { create_time: createTime, end_time: endTime, id, converge_id: convergeId } = this.detailInfo;
    handleToAlertList(
      type,
      { create_time: createTime, end_time: endTime, id, converge_id: convergeId },
      this.detailInfo.bk_biz_id || this.$store.getters.bizId
    );
  }
  handlePopoverShow(e: MouseEvent, content: string) {
    this.popoperInstance = this.$bkPopover(e.target, {
      content,
      maxWidth: 320,
      arrow: true
    });
    this.popoperInstance?.show?.(100);
  }
  handlePopoverHide() {
    this.popoperInstance?.hide?.(0);
    this.popoperInstance?.destroy?.();
    this.popoperInstance = null;
  }

  handleToActionDetail() {
    window.open(
      `${location.origin}${location.pathname}?bizId=${this.detailInfo.bk_biz_id}/#/set-meal-edit/${this.detailInfo.action_config_id}`
    );
  }

  handleDescEnter(e: MouseEvent, dimensions, description) {
    this.handlePopoverShow(
      e,
      [
        `<div class="dimension-desc">${this.$t('维度信息')}：${
          dimensions?.map?.(item => `${item.display_key || item.key}(${item.display_value || item.value})`).join('-') ||
          '--'
        }</div>`,
        `<div class="description-desc">${this.$t('告警内容')}：${description || '--'}</div>`
      ]
        .filter(Boolean)
        .join('')
    );
  }

  getTableComponent(tableData) {
    const level = {
      1: { color: '#eb3635', label: this.$t('致命') },
      2: { color: '#ff9c00', label: this.$t('预警') },
      3: { color: '#3a84ff', label: this.$t('提醒') }
    };
    const severity = severity => (
      <span
        class='severity'
        style={{
          borderLeft: `4px solid ${level[severity].color}`,
          color: level[severity].color
        }}
      >
        {level[severity].label}
      </span>
    );
    const alertContent = (dimensions, description) => (
      <div
        onMouseenter={e => this.handleDescEnter(e, dimensions, description)}
        onMouseleave={this.handlePopoverHide}
      >
        <div class='dimension-desc'>
          {this.$t('维度信息')}：
          {dimensions?.length
            ? dimensions.map(item => `${item.display_key || item.key}(${item.display_value || item.value})`).join('-')
            : '--'}
        </div>
        <div class='description-desc'>
          {this.$t('告警内容')}：{description || '--'}
        </div>
      </div>
    );
    return (
      <bk-table data={tableData}>
        <bk-table-column
          label={this.$t('告警ID')}
          width='150'
          scopedSlots={{ default: props => props.row.id }}
        ></bk-table-column>
        <bk-table-column
          label={this.$t('告警名称')}
          width='200'
          scopedSlots={{ default: props => props.row.alert_name }}
        ></bk-table-column>
        <bk-table-column
          label={this.$t('告警级别')}
          width='100'
          scopedSlots={{ default: props => severity(props.row.severity) }}
        ></bk-table-column>
        <bk-table-column
          label={this.$t('告警内容')}
          scopedSlots={{ default: props => alertContent(props.row.dimensions, props.row.description) }}
        ></bk-table-column>
      </bk-table>
    );
  }
  render() {
    const {
      action_name: actionName,
      bk_target_display: bkTargetDisplay,
      action_plugin: actionPlugin,
      duration,
      operator,
      create_time: createTime,
      update_time: updateTime,
      status,
      content,
      signal_display: signalDisplay,
      operate_target_string: operateTargetString,
      failure_type: failureType,
      action_plugin_type: actionPluginType
    } = this.detailInfo;
    const statusInfo = getStatusInfo(status, failureType);
    const arrContent = content?.text?.split('$');
    const link = arrContent?.[1] || '';
    const info = [
      [
        {
          title: this.$t('套餐名称'),
          content: (
            <span>
              {actionName}
              {actionPluginType !== 'notice' && (
                <span
                  class='fenxiang-link'
                  onClick={this.handleToActionDetail}
                >
                  <span class='icon-monitor icon-fenxiang'></span>
                </span>
              )}
            </span>
          ),
          extCls: true
        },
        { title: this.$t('告警目标'), content: bkTargetDisplay }
      ],
      [
        { title: this.$t('套餐类型'), content: actionPlugin?.name, extCls: true },
        { title: this.$t('处理时长'), content: duration }
      ],
      [
        { title: this.$t('负责人'), content: operator?.join(';') || '--' },
        { title: this.$t('执行对象'), content: operateTargetString || '--' }
      ],
      [
        { title: this.$t('开始时间'), content: dayjs.tz(createTime * 1000).format('YYYY-MM-DD HH:mm:ss') },
        { title: this.$t('执行状态'), content: <div class={statusInfo.status}>{statusInfo.text}</div>, extCls: true }
      ],
      [
        { title: this.$t('结束时间'), content: dayjs.tz(updateTime * 1000).format('YYYY-MM-DD HH:mm:ss') },
        { title: this.$t('触发信号'), content: signalDisplay, extCls: true }
      ],
      [
        {
          title: this.$t('具体内容'),
          content: (
            <div class='info-jtnr'>
              {arrContent?.[0] || ''}
              {link ? (
                <span
                  class='info-jtnr-link'
                  onClick={() => content?.url && window.open(content.url)}
                >
                  <span class='icon-monitor icon-copy-link'></span>
                  {link}
                </span>
              ) : undefined}
              {arrContent?.[2] || ''}
            </div>
          ),
          extCls: true
        }
      ]
    ];
    return (
      <div
        class={['active-detail-record', { 'active-detail-record-page': this.getIsPage }]}
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='detail-top'>
          <div class='detail-title'>{this.$t('处理详情')}</div>
          <div class='detail-info'>
            {info.map(child => (
              <div class={['form-item', { 'form-item-1': child.length === 1 }]}>
                {child.map((item, index) => (
                  <div class={['item-col', `item-col-${index}`]}>
                    <div class='item-label'>{item.title}&nbsp;:&nbsp;</div>
                    <div class='item-content'>
                      {item?.extCls ? item.content : <span class='item-content-text'>{item.content}</span>}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
        <div class='detail-table'>
          {this.tableData.trigger.length
            ? [
                <div class='table-title first'>
                  {this.$t('触发的告警')}
                  <i18n
                    path='仅展示最近10条，更多详情请{0}'
                    class='msg'
                  >
                    <span
                      class='table-title-link'
                      onClick={() => this.handleToAlertList('trigger')}
                    >
                      {/* <span class="icon-monitor icon-copy-link"></span> */}
                      <span class='link-text'>{this.$t('前往告警列表')}</span>
                    </span>
                  </i18n>
                </div>,
                <div class='table-content'>{this.getTableComponent(this.tableData.trigger)}</div>
              ]
            : undefined}
          {this.tableData.defense?.length
            ? [
                <div class='table-title'>
                  {this.$t('防御的告警')}
                  <i18n
                    path='仅展示最近10条，更多详情请{0}'
                    class='msg'
                  >
                    <span
                      class='table-title-link'
                      onClick={() => this.handleToAlertList('defense')}
                    >
                      {/* <span class="icon-monitor icon-copy-link"></span> */}
                      <span class='link-text'>{this.$t('前往告警列表')}</span>
                    </span>
                  </i18n>
                </div>,
                <div class='table-content'>{this.getTableComponent(this.tableData.defense)}</div>
              ]
            : undefined}
        </div>
      </div>
    );
  }
}
