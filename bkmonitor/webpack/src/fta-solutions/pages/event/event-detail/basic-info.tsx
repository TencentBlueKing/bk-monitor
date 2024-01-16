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
import { Component, Emit, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { TabEnum as CollectorTabEnum } from '../../../../monitor-pc/pages/collector-config/collector-detail/typings/detail';
import { toPerformanceDetail } from '../../../common/go-link';
import { getOperatorDisabled } from '../utils';

import { IDetail } from './type';

import './basic-info.scss';
/* eslint-disable camelcase */
interface IBasicInfoProps {
  basicInfo: IDetail;
}
interface IEvents {
  onAlarmDispatch?: () => void;
}
@Component({
  name: 'BasicInfo'
})
export default class MyComponent extends tsc<IBasicInfoProps, IEvents> {
  @Prop({ type: Object, default: () => ({}) }) basicInfo: IDetail;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  cloudIdMap = ['bk_target_cloud_id', 'bk_cloud_id'];
  ipMap = ['bk_target_ip', 'ip', 'bk_host_id'];

  get bizList() {
    return this.$store.getters.bizList;
  }

  get handleStatusString() {
    const total = this.basicInfo?.overview?.count;
    if (!total) return '--';
    let successCount = 0;
    let failCount = 0;
    let partialFailureCount = 0;
    successCount = this.basicInfo.overview?.children?.find?.(item => item.id === 'success')?.count || 0;
    failCount = this.basicInfo.overview?.children?.find?.(item => item.id === 'failure')?.count || 0;
    partialFailureCount = this.basicInfo.overview?.children?.find?.(item => item.id === 'partial_failure')?.count || 0;
    return `${this.$t(' {0} 次', [total])}(${successCount ? this.$t('{0}次成功', [successCount]) : ''}${
      failCount ? `${successCount ? ', ' : ''}${this.$t('{0}次失败', [failCount])}` : ''
    }${
      partialFailureCount
        ? `${successCount || failCount ? ', ' : ''}${this.$t('{0}次部分失败', [partialFailureCount])}`
        : ''
    })`;
  }

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

  @Emit('strategy-detail')
  toStrategyDetail() {
    return true;
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

  handleToPerformance(item) {
    if (this.ipMap.includes(item.key)) {
      if (item.key === 'bk_host_id') {
        toPerformanceDetail(this.basicInfo.bk_biz_id, item.value);
      } else {
        const cloudId = this.basicInfo.dimensions.find(item => this.cloudIdMap.includes(item.key)).value;
        toPerformanceDetail(this.basicInfo.bk_biz_id, `${item.value}-${cloudId}`);
      }
    }
  }
  // 头部彩色条形
  getHeaderBarComponent(eventStatus: string, isShielded: boolean) {
    const classList = {
      RECOVERED: 'bar-recovered',
      ABNORMAL: 'bar-abnormal',
      CLOSED: 'bar-closed'
    };
    const className = eventStatus ? classList[eventStatus] : '';
    return <div class={[className, { 'bar-small': isShielded }]}></div>;
  }
  // 告警级别标签
  getTagComponent(severity) {
    const level = {
      1: { label: this.$t('致命'), className: 'level-tag-fatal' },
      2: { label: this.$t('预警'), className: 'level-tag-warning' },
      3: { label: this.$t('提醒'), className: 'level-tag-info' }
    };
    const className = severity ? level[severity].className : '';
    const label = severity ? level[severity].label : '';
    return <div class={['level-tag', className]}>{label}</div>;
  }
  getDimensionsInfo() {
    return this.filterDimensions?.length
      ? this.filterDimensions?.map((item, index) => [
          index !== 0 && <span>&nbsp;,&nbsp;</span>,
          <span
            onClick={() => !this.readonly && this.handleToPerformance(item)}
            style={{
              cursor: this.ipMap.includes(item.key) ? 'pointer' : 'auto'
            }}
          >
            <span>{item.display_key}</span>
            <span>=</span>
            <span
              class={{ 'info-check': this.ipMap.includes(item.key) }}
              style='margin-left: 0;'
            >
              {item.display_value}
            </span>
          </span>
        ])
      : '--';
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
        <span>{this.basicInfo?.follower?.join(',') || '--'}</span>
        {!!this.basicInfo?.follower?.length && !!this.bkCollectConfigId && (
          <span
            class='fenxiang-btn'
            onClick={this.handleToCollectDetail}
          >
            <span>{this.$t('变更')}</span>
            <span class='icon-monitor icon-fenxiang'></span>
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
      appointee
    } = this.basicInfo;
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
            class='icon-monitor icon-chuli'
            v-bk-tooltips={{ content: this.$t('手动处理') }}
            onClick={() => this.$emit('manual-process')}
          ></span>,
          <span
            class='alarm-dispatch'
            onClick={this.handleAlarmDispatch}
            v-bk-tooltips={{ content: this.$t('告警分派') }}
          >
            <span class='icon-monitor icon-fenpai'></span>
          </span>
        ]}
      </span>
    );
    let alertInfoList: any = [];
    Object.keys(alert_info || {}).forEach(key => {
      const count = alert_info[key];
      if (count > 0) {
        if (key === 'failed_count') {
          alertInfoList.push(this.$t('{count}次失败', { count }));
        } else if (key === 'partial_count') {
          alertInfoList.push(this.$t('{count}次部分失败', { count }));
        } else if (key === 'success_count') {
          alertInfoList.push(this.$t('{count}次成功', { count }));
        } else if (key === 'shielded_count') {
          alertInfoList.push(this.$t('{count}次被屏蔽', { count }));
        } else if (key === 'empty_receiver_count') {
          alertInfoList.push(this.$t('{count}次通知状态为空', { count }));
        }
      }
    });
    alertInfoList = this.handleStatusString;
    const topItems = [
      {
        children: [
          { title: this.$t('所属空间'), content: this.bizList?.find(item => item.id === bk_biz_id)?.text },
          {
            title: this.$t('处理状态'),
            content: alertInfoList,
            icon: alertInfoList === '--' ? '' : 'icon-tishi',
            iconTip: this.$t('处理详情'),
            click: this.processingStatus
          }
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
        ]
      },
      {
        children: [
          {
            title: this.$t('首次异常时间'),
            content: dayjs.tz(first_anomaly_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
            timeZone: dayjs.tz(first_anomaly_time * 1000).format('Z')
          },
          { title: this.$t('处理阶段'), content: handleStatus() }
        ]
      },
      {
        children: [
          {
            title: this.$t('告警产生时间'),
            content: dayjs.tz(create_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
            timeZone: dayjs.tz(create_time * 1000).format('Z')
          },
          {
            title: this.$t('负责人'),
            content: appointee?.join(',') || '--'
          }
        ]
      },
      {
        children: [
          { title: this.$t('持续时间'), content: duration },
          { title: this.$t('关注人'), content: this.getFollowerInfo() }
        ]
      }
    ];
    const bottomItems = [
      {
        title: this.$t('维度信息'),
        content: this.getDimensionsInfo() || '--',
        extCls: 'flex-wrap'
      },
      { title: this.$t('告警内容'), content: description, extCls: 'flex-wrap' },
      {
        title: this.$t('关联信息'),
        content: relation_info || '--',
        extCls: 'no-flex'
      }
    ] as any;
    return (
      <div class='detail-form'>
        <div class='detail-form-top'>
          {topItems.map(child => (
            <div class='top-form-item'>
              {child.children.map(item => (
                <div class='item-col'>
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
                        on-click={item.click ? item.click : false}
                        class={['icon-monitor', item.icon]}
                        v-bk-tooltips={{ content: item.iconTip, allowHTML: false }}
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
          {bottomItems.map(item => (
            <div class={['item-col', item.extCls]}>
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
                    on-click={item.click ? item.click : false}
                    class={['icon-monitor', item.icon]}
                    v-bk-tooltips={{ content: item.iconTip, allowHTML: false }}
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
  // 右侧状态操作区域
  getRightStatusComponent(eventStatus: string, isAck: boolean, isShielded: boolean) {
    const { shield_left_time } = this.basicInfo;
    // eventStatus 已/未恢复/关闭 isAck 已确认 isShielded 已屏蔽
    const status = ['RECOVERED', 'ABNORMAL', 'CLOSED'];
    let iconName = '';
    let iconColor = '';
    let iconText = '';
    let operateDom = null;
    const shieldedDom = () =>
      this.readonly ? undefined : (
        <bk-button
          class='mr10'
          theme='primary'
          size='small'
          outline={true}
          on-click={this.handleQuickShield}
        >
          {this.$t('快捷屏蔽')}
        </bk-button>
      );
    const confirmDom = () =>
      this.readonly ? undefined : (
        <bk-button
          theme='primary'
          size='small'
          outline={true}
          on-click={this.handleAlarmConfirm}
        >
          {this.$t('告警确认')}
        </bk-button>
      );
    if (eventStatus === status[0]) {
      /* 已恢复 */
      iconName = 'icon-mc-check-fill';
      iconColor = '#2dcb56';
      if (!isShielded) {
        /* 已恢复未屏蔽 */
        iconText = `${this.$t('已恢复')}`;
        operateDom = <div class='status-operate'>{shieldedDom()}</div>;
      } else {
        /* 已恢复已屏蔽 */
        iconText = `${this.$t('已恢复')}（${this.$t('已屏蔽')}）`;
        operateDom = null;
      }
    } else if (eventStatus === status[1]) {
      /* 未恢复 */
      if (!isAck && !isShielded) {
        /* 未恢复未屏蔽未确认 */
        iconName = 'icon-mind-fill';
        iconColor = '#ff5656';
        iconText = `${this.$t('未恢复')}`;
        operateDom = (
          <div class='status-operate'>
            {shieldedDom()}
            {confirmDom()}
          </div>
        );
      } else if (isShielded) {
        /* 未恢复已屏蔽 */
        iconName = 'icon-menu-shield';
        iconColor = '#979ba5';
        iconText = `${this.$t('未恢复')}（${this.$t('已屏蔽')}）`;
        operateDom = this.basicInfo.shield_id && [
          <div class='status-operate'>
            <span class='shielded-text'>{this.$t('屏蔽时间剩余')}</span>
            <span class='shielded-time'>{shield_left_time}</span>
          </div>,
          !this.readonly ? (
            <div
              class='shielded-link'
              onClick={this.handleToShield}
            >
              {this.$t('屏蔽策略')}
              <span class='icon-monitor icon-fenxiang'></span>
            </div>
          ) : undefined
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
      iconColor = '#dcdee5';
      if (!isShielded) {
        /* 已关闭未屏蔽 */
        iconText = `${this.$t('已关闭')}`;
        operateDom = !this.readonly ? (
          <div class='status-operate'>
            <bk-button
              theme='primary'
              size='small'
              outline={true}
              on-click={this.handleQuickShield}
            >
              {this.$t('快捷屏蔽')}
            </bk-button>
          </div>
        ) : undefined;
      } else {
        /* 已关闭已屏蔽 */
        iconText = `${this.$t('已关闭')}（${this.$t('已屏蔽')}）`;
        operateDom = null;
      }
    }
    return (
      <div class='right-status'>
        <div class='status-icon'>
          <span
            class={['icon-monitor', iconName]}
            style={{ color: iconColor }}
          ></span>
          <div class='status-text'>{iconText}</div>
        </div>
        {!this.followerDisabled ? operateDom || undefined : undefined}
      </div>
    );
  }

  render() {
    const { severity, is_shielded, is_ack, status, alert_name } = this.basicInfo;
    return (
      <div class='event-detail-basic'>
        {this.getHeaderBarComponent(status, is_shielded)}
        <div class='basic-detail'>
          <div class='basic-left'>
            <div class='basic-title'>
              {this.getTagComponent(severity)}
              <span
                class='basic-title-name'
                v-bk-tooltips={{ content: alert_name, allowHTML: false }}
              >
                {alert_name}
              </span>
              {!this.readonly && this.basicInfo.plugin_id ? (
                <span
                  class='btn-strategy-detail'
                  onClick={this.toStrategyDetail}
                >
                  <span>{this.$t('来源：{0}', [this.basicInfo.plugin_display_name])}</span>
                  <i class='icon-monitor icon-fenxiang icon-float'></i>
                </span>
              ) : undefined}
            </div>
            {this.getDetailFormComponent()}
          </div>
          <div
            class='basic-right'
            v-en-class='en-lang'
          >
            {this.getRightStatusComponent(status, is_ack, is_shielded)}
          </div>
        </div>
      </div>
    );
  }
}
