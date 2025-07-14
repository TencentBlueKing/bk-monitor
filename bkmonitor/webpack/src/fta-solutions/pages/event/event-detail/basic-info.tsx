/* eslint-disable @typescript-eslint/naming-convention */
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
import VueJsonPretty from 'vue-json-pretty';
import { Component, Emit, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { copyText } from 'monitor-common/utils';
import { ETagsType } from 'monitor-pc/components/biz-select/list';
import { TabEnum as CollectorTabEnum } from 'monitor-pc/pages/collector-config/collector-detail/typings/detail';

import { toPerformanceDetail, toBcsDetail } from '../../../common/go-link';
import EventDetail from '../../../store/modules/event-detail';
import { getOperatorDisabled } from '../utils';

import type { IDetail } from './type';

import './basic-info.scss';
import 'vue-json-pretty/lib/styles.css';

interface IBasicInfoProps {
  basicInfo: IDetail;
}
interface IEvents {
  onAlarmDispatch?: () => void;
}
@Component({
  name: 'BasicInfo',
})
export default class MyComponent extends tsc<IBasicInfoProps, IEvents> {
  @Prop({ type: Object, default: () => ({}) }) basicInfo: IDetail;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  cloudIdMap = ['bk_target_cloud_id', 'bk_cloud_id'];
  ipMap = ['bk_target_ip', 'ip', 'bk_host_id', 'tags.bcs_cluster_id'];
  operateDesc = null;
  showReason = false;
  get bizList() {
    return this.$store.getters.bizList;
  }
  get handleStatusString() {
    // 从 this.basicInfo 中获取总计数，如果不存在则返回 '--'
    const total = this.basicInfo?.overview?.count;
    if (!total) return '--';

    // 定义需要统计的状态及其初始计数
    const statusKeys = ['success', 'failure', 'partial_failure'];
    const statusCounts = Object.fromEntries(statusKeys.map(key => [key, 0]));

    // 遍历 children 数组，更新对应状态的计数
    const children = this.basicInfo.overview?.children || [];
    children.map(item => {
      if (statusKeys.includes(item.id)) {
        statusCounts[item.id] = item.count;
      }
    });

    // 生成每种状态的描述字符串数组
    const statusDescriptions = statusKeys
      .map(key => {
        const count = statusCounts[key];
        if (count) {
          const statusText = {
            success: '次成功',
            failure: '次失败',
            partial_failure: '次部分失败',
          }[key];
          return this.$t(`{0}${statusText}`, [count]);
        }
        return null;
      })
      .filter(description => description !== null);
    // 拼接所有状态描述字符串
    const details = statusDescriptions.join(', ');

    // 生成最终的状态字符串
    return `${this.$t(' {0} 次', [total])}(${details})`;
  }

  // get handleStatusString() {
  //   const total = this.basicInfo?.overview?.count;
  //   if (!total) return '--';
  //   let successCount = 0;
  //   let failCount = 0;
  //   let partialFailureCount = 0;
  //   successCount = this.basicInfo.overview?.children?.find?.(item => item.id === 'success')?.count || 0;
  //   failCount = this.basicInfo.overview?.children?.find?.(item => item.id === 'failure')?.count || 0;
  //   partialFailureCount =
  //     this.basicInfo.overview?.children?.find?.(item => item.id === 'partial_failure')?.count || 0;
  //   return `${this.$t(' {0} 次', [total])}(${successCount ? this.$t('{0}次成功', [successCount]) : ''}${
  //     failCount ? `${successCount ? ', ' : ''}${this.$t('{0}次失败', [failCount])}` : ''
  //   }${
  //     partialFailureCount
  //       ? `${successCount || failCount ? ', ' : ''}${this.$t('{0}次部分失败', [partialFailureCount])}`
  //       : ''
  //   })`;
  // }

  get filterDimensions() {
    return this.basicInfo.dimensions?.filter(item => !(this.cloudIdMap.includes(item.key) && item.value === 0));
  }

  /* bk_collect_config_id */
  get bkCollectConfigId() {
    const labels = this.basicInfo?.extra_info?.strategy?.labels || [];
    const need = labels.some(item => ['集成内置', 'Datalink BuiltIn'].includes(item));
    return need
      ? this.basicInfo.dimensions?.find(
          item => item.key === 'bk_collect_config_id' || item.key === 'tags.bk_collect_config_id'
        )?.value
      : '';
  }

  get followerDisabled() {
    return getOperatorDisabled(this.basicInfo.follower, this.basicInfo.assignee);
  }

  @Emit('processing-status')
  processingStatus() {
    return true;
  }
  @Emit('quick-shield')
  handleQuickShield() {
    return true;
  }
  @Emit('alarm-confirm')
  handleAlarmConfirm() {
    return true;
  }
  @Emit('alarmDispatch')
  handleAlarmDispatch() {}

  // 跳转到屏蔽页
  handleToShield() {
    if (!this.basicInfo.shield_id?.[0]) return;
    window.open(
      `${location.origin}${location.pathname}?bizId=${this.basicInfo.bk_biz_id}/#/trace/alarm-shield/edit/${this.basicInfo.shield_id[0]}`
    );
  }
  /** 不同情况下的跳转逻辑 */
  handleToPerformance(item) {
    const { ipMap, cloudIdMap, basicInfo } = this;
    const isKeyInIpMap = ipMap.includes(item.key);

    if (!isKeyInIpMap) {
      return;
    }

    switch (item.key) {
      /** 增加集群跳转到BCS */
      case 'tags.bcs_cluster_id':
        toBcsDetail(item.project_name, item.value);
        break;

      /** 跳转到主机监控 */
      case 'bk_host_id':
        toPerformanceDetail(basicInfo.bk_biz_id, item.value);
        break;

      default: {
        const cloudIdItem = basicInfo.dimensions.find(dim => cloudIdMap.includes(dim.key));
        if (!cloudIdItem) {
          return;
        }
        const cloudId = cloudIdItem.value;
        toPerformanceDetail(basicInfo.bk_biz_id, `${item.value}-${cloudId}`);
        break;
      }
    }
  }

  // 头部彩色条形
  getHeaderBarComponent(eventStatus: string, isShielded: boolean, isAck: boolean) {
    const classList = {
      RECOVERED: 'bar-recovered',
      ABNORMAL: 'bar-abnormal',
      CLOSED: 'bar-closed',
    };
    const className = eventStatus ? classList[eventStatus] : '';
    return (
      <div
        class={[className, { 'bar-small': isShielded }, { 'bar-shielded': eventStatus === 'ABNORMAL' && isShielded }]}
      >
        {this.getRightStatusComponent(eventStatus, isAck, isShielded)}
      </div>
    );
  }
  // 告警级别标签
  getTagComponent(severity) {
    const level = {
      1: { label: this.$t('致命'), className: 'level-tag-fatal' },
      2: { label: this.$t('预警'), className: 'level-tag-warning' },
      3: { label: this.$t('提醒'), className: 'level-tag-info' },
    };
    const className = severity ? level[severity].className : '';
    const label = severity ? level[severity].label : '';
    return <div class={['level-tag', className]}>{label}</div>;
  }
  getDimensionsInfo() {
    return this.filterDimensions?.length
      ? this.filterDimensions?.map(item => [
          <span
            key={item.display_key}
            style={{
              cursor: this.ipMap.includes(item.key) ? 'pointer' : 'auto',
            }}
            class='dimensions-item'
            onClick={() => !this.readonly && this.handleToPerformance(item)}
          >
            <span class='name'>{item.display_key}</span>
            <span class='eq'>=</span>
            <span
              style='margin-left: 0; display: block'
              class={['content', { 'info-check': this.ipMap.includes(item.key) }]}
            >
              {item.display_value}
            </span>
          </span>,
        ])
      : '--';
  }

  // 关联信息渲染方式
  getRelationInfo(relationInfo: string) {
    try {
      const parsedInfo = JSON.parse(relationInfo);
      return (
        <span
          class='relation-log-btn'
          onClick={() => this.handleRelationInfoDialog(parsedInfo)}
        >
          <span class='icon-monitor icon-guanlian' /> {this.$t('关联日志')}
        </span>
      );
    } catch {
      return relationInfo;
    }
  }

  // 关联日志的渲染方式
  handleRelationInfoDialog(relationInfo) {
    const h = this.$createElement;
    this.$bkInfo({
      width: 960,
      cancelText: this.$t('关闭'),
      extCls: 'event-relation-dialog',
      title: this.$t('关联日志'),
      subHeader: h(
        'div', // 使用 div 元素包装整个内容
        { class: 'json-view-content' },
        [
          h('i', {
            class: 'icon-monitor icon-mc-copy',
            directives: [
              {
                name: 'bk-tooltips',
                value: this.$t('复制'),
                arg: 'distance',
                modifiers: { '5': true },
              },
            ],
            on: {
              click: () => this.handleCopy(relationInfo),
            },
          }),
          h(VueJsonPretty, {
            props: {
              collapsedOnClickBrackets: false,
              data: relationInfo,
              deep: 5,
              showIcon: true,
              // showLine: false
            },
          }),
        ]
      ),
    });
  }

  handleCopy(str) {
    copyText(JSON.stringify(str, null, 4), msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  handleToCollectDetail() {
    window.open(
      `${location.origin}${location.pathname}?bizId=${this.basicInfo.bk_biz_id}#/collect-config/detail/${this.bkCollectConfigId}?tab=${CollectorTabEnum.TargetDetail}`
    );
  }
  /* 关注人 */
  getFollowerInfo() {
    return (
      <span class='follower-info'>
        {this.basicInfo?.follower?.length
          ? this.basicInfo?.follower.map((v, index, arr) => [
              <bk-user-display-name
                key={v}
                user-id={v}
              />,
              index !== arr.length - 1 ? <span key={`${v}-${index}`}>{','}</span> : null,
            ])
          : '--'}
        {!!this.basicInfo?.follower?.length && !!this.bkCollectConfigId && (
          <span
            class='fenxiang-btn'
            onClick={this.handleToCollectDetail}
          >
            <span>{this.$t('变更')}</span>
            <span class='icon-monitor icon-fenxiang' />
          </span>
        )}
      </span>
    );
  }
  // 基本信息表单
  getDetailFormComponent() {
    const {
      bk_biz_id,
      first_anomaly_time,
      create_time,
      alert_info,
      description,
      duration,
      relation_info,
      // plugin_display_name, // 告警来源
      // plugin_id, // 告警来源ID
      // is_ack, // 是否确认
      // is_shielded, // 是否屏蔽
      // is_handled // 是否已处理
      stage_display, // 处理阶段
      appointee,
    } = this.basicInfo;
    const bizItem = this.bizList?.find(item => item.id === bk_biz_id);
    const bizIdName =
      bizItem?.space_type_id === ETagsType.BKCC ? `#${bizItem?.id}` : bizItem?.space_id || bizItem?.space_code || '';
    // 处理阶段 优先级: is_shielded > is_ack > is_handled
    // const handleStatus = () => (is_shielded ? this.$t('已屏蔽') : false)
    //   || (is_ack ? this.$t('已确认') : false)
    //   || (is_handled ? this.$t('已处理') : false)
    //   || '--';
    const handleStatus = () => (
      <span>
        {stage_display || '--'}
        {!this.readonly && [
          <span
            key='manual-process'
            onClick={() => this.$emit('manual-process')}
          >
            <span class='icon-monitor icon-chuli' />
            <span class='blue-txt'>{this.$t('手动处理')}</span>
          </span>,
          <span
            key='manual-dispatch'
            onClick={this.handleAlarmDispatch}
          >
            <span class='alarm-dispatch'>
              <span class='icon-monitor icon-fenpai' />
            </span>
            <span class='blue-txt'>{this.$t('告警分派')}</span>
          </span>,
        ]}
      </span>
    );
    let alertInfoList: any = [];
    const messageMap = {
      failed_count: '{count}次失败',
      partial_count: '{count}次部分失败',
      success_count: '{count}次成功',
      shielded_count: '{count}次被屏蔽',
      empty_receiver_count: '{count}次通知状态为空',
    };
    // biome-ignore lint/complexity/noForEach: <explanation>
    Object.keys(alert_info || {}).forEach(key => {
      const count = alert_info[key];
      if (count > 0) {
        const message = messageMap[key];
        if (message) {
          alertInfoList.push(this.$t(message, { count }));
        }
        // if (key === 'failed_count') {
        //   alertInfoList.push(this.$t('{count}次失败', { count }));
        // } else if (key === 'partial_count') {
        //   alertInfoList.push(this.$t('{count}次部分失败', { count }));
        // } else if (key === 'success_count') {
        //   alertInfoList.push(this.$t('{count}次成功', { count }));
        // } else if (key === 'shielded_count') {
        //   alertInfoList.push(this.$t('{count}次被屏蔽', { count }));
        // } else if (key === 'empty_receiver_count') {
        //   alertInfoList.push(this.$t('{count}次通知状态为空', { count }));
        // }
      }
    });
    alertInfoList = this.handleStatusString;
    const topItems = [
      {
        children: [
          { title: this.$t('所属空间'), content: bizItem ? `${bizItem?.text} (${bizIdName})` : '--' },
          {
            title: this.$t('处理状态'),
            content: alertInfoList,
            icon: alertInfoList === '--' ? '' : 'icon-xiangqing1',
            iconTip: this.$t('处理详情'),
            iconText: this.$t('处理详情'),
            click: this.processingStatus,
          },
          // {
          //   title: this.$t('告警名称'),
          //   content: [
          //     <span
          //       class='alert-name'
          //       v-bk-tooltips={{ content: alert_name }}
          //     >
          //       {alert_name}
          //     </span>,
          //     plugin_display_name && plugin_id !== 'bkmonitor' && (
          //       <bk-tag
          //         class='alert-origin'
          //         v-bk-tooltips={{ content: plugin_display_name }}
          //       >
          //         {this.$t('来源:')}
          //         {plugin_display_name}
          //       </bk-tag>
          //     )
          //   ],
          //   icon: !this.readonly && this.basicInfo.extra_info?.strategy ? 'icon-fenxiang' : false,
          //   iconText: this.$t('策略详情'),
          //   click: this.toStrategyDetail
          // }
        ],
      },
      {
        children: [
          {
            title: this.$t('异常时间'),
            content: dayjs.tz(first_anomaly_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
            timeZone: dayjs.tz(first_anomaly_time * 1000).format('Z'),
          },
          { title: this.$t('处理阶段'), content: handleStatus() },
        ],
      },
      {
        children: [
          {
            title: this.$t('告警产生'),
            content: dayjs.tz(create_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
            timeZone: dayjs.tz(create_time * 1000).format('Z'),
          },
          {
            title: this.$t('负责人'),
            extCls: 'flex-wrap',
            content: appointee?.length
              ? appointee.map((v, index, arr) => [
                  <bk-user-display-name
                    key={v}
                    user-id={v}
                  />,
                  index !== arr.length - 1 ? <span key={`${v}-${index}`}>{','}</span> : null,
                ])
              : '--',
          },
        ],
      },
      {
        children: [
          { title: this.$t('持续时间'), content: duration },
          { title: this.$t('关注人'), content: this.getFollowerInfo() },
        ],
      },
    ];
    const bottomItems = [
      {
        title: this.$t('维度信息'),
        content: this.getDimensionsInfo() || '--',
        extCls: this.getDimensionsInfo() === '--' ? 'flex-wrap' : 'flex-wrap dimensions-wrap',
      },
      { title: this.$t('告警内容'), content: description, extCls: 'flex-wrap content-break-spaces' },
      {
        title: this.$t('关联信息'),
        content: relation_info?.trim() ? this.getRelationInfo(relation_info) : '--',
        extCls: 'no-flex',
      },
    ] as any;
    return (
      <div class='detail-form'>
        <div class='detail-form-top'>
          {topItems.map((child, index) => (
            <div
              key={index}
              class='top-form-item'
            >
              {child.children.map((item, ind) => (
                <div
                  key={ind}
                  class={['item-col', item.extCls]}
                >
                  <div
                    class='item-label'
                    v-en-class='fb-146'
                  >
                    {item.title}：
                  </div>
                  <div class='item-content'>
                    {item.content}
                    {item.timeZone ? <span class='item-time-zone'>{item.timeZone}</span> : undefined}
                    {item.icon ? (
                      <span
                        class={['icon-monitor', item.icon]}
                        v-bk-tooltips={{ content: item.iconTip, allowHTML: false }}
                        on-click={item.click ? item.click : false}
                      >
                        <span class='icon-title'>{item?.iconText || ''}</span>
                      </span>
                    ) : undefined}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div class='detail-form-bottom'>
          {bottomItems.map((item, ind) => (
            <div
              key={`item${ind}`}
              class={['item-col', item.extCls]}
            >
              <div
                class='item-label'
                v-en-class='fb-146'
              >
                {item.title}：
              </div>
              <div class='item-content'>
                {item.content}
                {item.icon ? (
                  <span
                    class={['icon-monitor', item.icon]}
                    v-bk-tooltips={{ content: item.iconTip, allowHTML: false }}
                    on-click={item.click ? item.click : false}
                  >
                    <span class='icon-title'>{item.iconText || ''}</span>
                  </span>
                ) : undefined}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  getEventLog() {
    return EventDetail.getListEventLog({
      bk_biz_id: this.basicInfo.bk_biz_id,
      id: this.basicInfo.id,
      offset: 0,
      limit: 20,
      operate: ['CLOSE'],
    });
  }
  // 右侧状态操作区域
  getRightStatusComponent(eventStatus: string, isAck: boolean, isShielded: boolean) {
    const { shield_left_time, duration } = this.basicInfo;
    // eventStatus 已/未恢复/关闭 isAck 已确认 isShielded 已屏蔽
    const status = ['RECOVERED', 'ABNORMAL', 'CLOSED'];
    let iconName = '';
    let iconColor = '';
    let iconText = '';
    let operateDom = null;
    const shieldedDom = () =>
      this.readonly ? undefined : (
        <span
          class='shielded-link mr10'
          on-click={this.handleQuickShield}
        >
          <i class='icon-monitor icon-mc-notice-shield' />
          {this.$t('快捷屏蔽')}
        </span>
      );
    const confirmDom = () =>
      this.readonly ? undefined : (
        <bk-button
          size='small'
          theme='primary'
          on-click={this.handleAlarmConfirm}
        >
          {this.$t('告警确认')}
        </bk-button>
      );
    if (eventStatus === status[0]) {
      /* 已恢复 */
      iconName = 'icon-mc-check-fill';
      iconColor = '#2dcb56';
      iconText = `${this.$t('已恢复')}`;
      operateDom = null;
    } else if (eventStatus === status[1]) {
      /* 未恢复 */
      if (!isAck && !isShielded) {
        /* 未恢复未屏蔽未确认 */
        iconName = 'icon-mind-fill';
        iconColor = '#ff5656';
        iconText = `${this.$t('未恢复')}`;
        operateDom = (
          <div class='status-operate-btn'>
            {shieldedDom()}
            {confirmDom()}
          </div>
        );
      } else if (isShielded) {
        /* 未恢复已屏蔽 */
        iconName = 'icon-menu-shield';
        iconColor = '#979ba5';
        iconText = `${this.$t('未恢复')}(${this.$t('已屏蔽')})`;
        operateDom = this.basicInfo.shield_id && [
          <div
            key={'status-operate'}
            class='status-operate'
          >
            <span class='status-operate-line' />
            <span class='shielded-text'>{this.$t('屏蔽时间剩余')}：</span>
            <span class='shielded-time'>{shield_left_time}</span>
          </div>,
          !this.readonly ? (
            <div
              key={'status-operate-btn'}
              class='status-operate-btn'
            >
              <div
                class='shielded-link'
                onClick={this.handleToShield}
              >
                <span class='icon-monitor icon-fenxiang' />
                {this.$t('屏蔽策略')}
              </div>
            </div>
          ) : undefined,
        ];
      } else if (isAck) {
        /* 未恢复已确认 */
        iconName = 'icon-mc-check-fill';
        iconColor = '#699df4';
        iconText = `${this.$t('未恢复')}（${this.$t('已确认')}）`;
        operateDom = <div class='status-operate'>{shieldedDom()}</div>;
      }
    } else if (eventStatus === status[2]) {
      /* 已关闭 */
      iconName = 'icon-mc-close-fill';
      iconColor = '#979BA5';
      iconText = `${this.$t('已失效')}`;
      operateDom = null;
      this.getEventLog().then(res => {
        this.operateDesc = res[0]?.contents?.[0] ? res[0].contents[0] : this.$t('告警已失效');
        this.showReason = true;
      });
    }
    return (
      <div class='right-status'>
        <div class='status-icon'>
          <span
            style={{ color: iconColor }}
            class={['icon-monitor', iconName]}
          />
          <div class='status-text'>
            <span>{iconText}</span>
          </div>
          {this.showReason ? (
            <div class='status-operate'>
              <span class='status-operate-line' />
              <span class='close-tips'>{this.operateDesc}</span>
            </div>
          ) : undefined}
          {eventStatus !== status[2] && this.basicInfo?.duration && !isShielded && (
            <div class='status-operate'>
              <span class='status-operate-line' />
              <span class='shielded-text'>{this.$t('持续时间')}：</span>
              <span>{duration}</span>
            </div>
          )}
        </div>
        {!this.followerDisabled ? operateDom || undefined : undefined}
      </div>
    );
  }

  render() {
    const { is_shielded, is_ack, status } = this.basicInfo;
    return (
      <div class='event-detail-basic'>
        {this.getHeaderBarComponent(status, is_shielded, is_ack)}
        <div class='basic-detail'>
          <div class='basic-left'>{this.getDetailFormComponent()}</div>
        </div>
      </div>
    );
  }
}
