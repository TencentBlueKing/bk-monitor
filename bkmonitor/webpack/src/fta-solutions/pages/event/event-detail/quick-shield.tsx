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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { bulkAddAlertShield } from 'monitor-api/modules/shield';
import VerifyInput from 'monitor-pc/components/verify-input/verify-input.vue';
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';

import DimensionTransfer from './dimension-transfer';

import type { IDimensionItem } from '../typings/event';

import './quick-shield.scss';

const { i18n } = window;

interface IQuickShieldProps {
  show: boolean;
  details: IDetail[];
  ids?: Array<string>;
  bizIds?: number[];
  authority?: Record<string, boolean>;
  handleShowAuthorityDetail?: (action: any) => void;
}
export interface IDetail {
  severity: number;
  dimension?: IDimensionItem[];
  trigger?: string;
  isModified?: boolean;
  alertId: string;
  strategy?: {
    name?: string;
    id?: number;
  };
}

interface DimensionConfig {
  alert_ids: string[];
  dimensions?: { [key: string]: string[] };
}

@Component({
  name: 'QuickShield',
})
export default class EventQuickShield extends tsc<IQuickShieldProps> {
  @Prop({ type: Object, default: () => ({}) }) authority: IQuickShieldProps['authority'];
  @Prop({ type: Function, default: null }) handleShowAuthorityDetail: IQuickShieldProps['handleShowAuthorityDetail'];
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Array, default: () => [] }) details: IDetail[];
  @Prop({ type: Array, default: () => [] }) ids: Array<string>;
  /* 事件中心暂不允许跨业务操作， 此数组只有一个业务 */
  @Prop({ type: Array, default: () => [] }) bizIds: number[];

  loading = false;
  rule = { customTime: false };
  timeList = [
    { name: `0.5${i18n.t('小时')}`, id: 18 },
    { name: `1${i18n.t('小时')}`, id: 36 },
    { name: `12${i18n.t('小时')}`, id: 432 },
    { name: `1${i18n.t('天')}`, id: 864 },
    { name: `7${i18n.t('天')}`, id: 6048 },
  ];
  timeValue = 18;
  customTime: any = ['', ''];
  options = {
    disabledDate(date) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      // 用户手动修改的时间不在可选时间内，回撤修改操作
      if (Array.isArray(date)) {
        return date.some(item => item.getTime() < today.getTime() || item.getTime() > today.getTime() + 8.64e7 * 181);
      }
      return date.getTime() < today.getTime() || date.getTime() > today.getTime() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
    },
  };
  levelMap = ['', i18n.t('致命'), i18n.t('提醒'), i18n.t('预警')];
  desc = '';

  backupDetails: IDetail[] = [];

  dimensionSelectShow = false;
  transferDimensionList: IDimensionItem[] = [];
  transferTargetList: string[] = [];
  transferEditIndex = -1;

  @Watch('ids', { immediate: true, deep: true })
  handleShow(newIds, oldIds) {
    if (`${JSON.stringify(newIds)}` !== `${JSON.stringify(oldIds)}`) {
      this.handleDialogShow();
    }
  }

  @Watch('details', { immediate: true })
  handleDetailsChange() {
    const data = structuredClone(this.details || []);
    this.backupDetails = data.map(detail => {
      return {
        ...detail,
        modified: false,
      };
    });
  }

  handleDialogShow() {
    // this.loading = true
    this.timeValue = 18;
    this.desc = '';
    this.customTime = '';
  }

  handleformat(time, fmte) {
    let fmt = fmte;
    const obj = {
      'M+': time.getMonth() + 1, // 月份
      'd+': time.getDate(), // 日
      'h+': time.getHours(), // 小时
      'm+': time.getMinutes(), // 分
      's+': time.getSeconds(), // 秒
      'q+': Math.floor((time.getMonth() + 3) / 3), // 季度
      S: time.getMilliseconds(), // 毫秒
    };
    if (/(y+)/.test(fmt)) fmt = fmt.replace(RegExp.$1, `${time.getFullYear()}`.substr(4 - RegExp.$1.length));

    for (const key in obj) {
      if (new RegExp(`(${key})`).test(fmt)) {
        fmt = fmt.replace(RegExp.$1, RegExp.$1.length === 1 ? obj[key] : `00${obj[key]}`.substr(`${obj[key]}`.length));
      }
    }
    return fmt;
  }
  getTime() {
    let begin: Date = null;
    let end: Date = null;
    if (this.timeValue === 0) {
      const [beginTime, endTime] = this.customTime;
      if (beginTime === '' || endTime === '') {
        this.rule.customTime = true;
        return false;
      }
      begin = this.handleformat(beginTime, 'yyyy-MM-dd hh:mm:ss');
      end = this.handleformat(endTime, 'yyyy-MM-dd hh:mm:ss');
    } else {
      begin = new Date();
      const nowS = begin.getTime();
      end = new Date(nowS + this.timeValue * 100000);
      begin = this.handleformat(begin, 'yyyy-MM-dd hh:mm:ss');
      end = this.handleformat(end, 'yyyy-MM-dd hh:mm:ss');
    }
    return { begin, end };
  }
  handleSubmit() {
    const time = this.getTime();
    if (time) {
      this.loading = true;
      const params = {
        bk_biz_id: this.bizIds?.[0] || this.$store.getters.bizId,
        category: 'alert',
        begin_time: time.begin,
        end_time: time.end,
        dimension_config: { alert_ids: this.ids?.map(id => id.toString()) },
        shield_notice: false,
        description: this.desc,
        cycle_config: {
          begin_time: '',
          type: 1,
          day_list: [],
          week_list: [],
          end_time: '',
        },
      };
      dayjs.locale('en');
      let toTime = `${dayjs(time.begin).to(dayjs(time.end), true)}`;
      const tims = [
        ['day', 'd'],
        ['days', 'd'],
        ['hours', 'h'],
        ['hour', 'h'],
        ['minutes', 'm'],
        ['minute', 'm'],
        ['years', 'y'],
        ['year', 'y'],
      ];
      tims.forEach(item => {
        toTime = toTime.replace(item[0], item[1]);
      });
      // 当修改维度信息时，调整入参
      const changedDetails = this.backupDetails.filter(item => item.isModified);
      if (changedDetails.length) {
        (params.dimension_config as DimensionConfig).dimensions = changedDetails.reduce((pre, item) => {
          if (item.isModified) {
            pre[item.alertId.toString()] = item.dimension
              .filter(dim => dim.key && (dim.display_value || dim.value))
              .map(dim => dim.key);
          }
          return pre;
        }, {});
      }
      bulkAddAlertShield(params)
        .then(() => {
          this.handleSucces(true);
          this.handleTimeChange(toTime);
          this.handleShowChange(false);
          this.$bkMessage({ theme: 'success', message: this.$t('创建告警屏蔽成功') });
        })
        .finally(() => {
          this.loading = false;
        });
    }
  }

  @Emit('succes')
  handleSucces(v) {
    return v;
  }

  @Emit('change')
  handleShowChange(v) {
    return v;
  }
  @Emit('time-change')
  handleTimeChange(val: string) {
    return val;
  }

  handleScopeChange(e, type) {
    e.stopPropagation();
    this.timeValue = type;
    if (type === 0) {
      this.$nextTick(() => {
        const refTime: any = this.$refs.time;
        refTime.visible = true;
      });
    } else {
      this.customTime = '';
    }
  }

  handleToStrategy(id: number) {
    const url = location.href.replace(location.hash, `#/strategy-config/detail/${id}`);
    window.open(url);
  }

  // 删除维度信息
  // handleTagClose(detail: IDetail, index: number) {
  //   detail.dimension.splice(index, 1);
  //   detail.isModified = true;
  // }

  // 点击重置icon
  // handleReset(detailIndex: number) {
  //   const resetDetail = structuredClone(this.details[detailIndex]);
  //   this.backupDetails.splice(detailIndex, 1, {
  //     ...resetDetail,
  //     isModified: false,
  //   });
  // }

  // 编辑维度信息
  handleDimensionSelect(detail, idx) {
    // 初始化穿梭框数据
    this.transferDimensionList = this.details[idx].dimension;
    // 选中的数据
    this.transferTargetList = detail.dimension.map(dimension => dimension.key);
    this.transferEditIndex = idx;
    this.dimensionSelectShow = true;
  }

  handleTransferConfirm(selectedDimensionArr: IDimensionItem[]) {
    const { backupDetails, transferEditIndex: idx } = this;
    // 增删维度信息
    backupDetails[idx].dimension = this.details[idx].dimension.filter(dimensionItem =>
      selectedDimensionArr.some(targetItem => targetItem.key === dimensionItem.key)
    );
    // 设置编辑状态
    backupDetails[idx].isModified = false;
    // 穿梭框抛出的维度信息与最初不一致时，设置为已修改
    if (this.details[idx].dimension.length !== selectedDimensionArr.length) {
      backupDetails[idx].isModified = true;
    }
    this.dimensionSelectShow = false;
    this.handleResetTransferData();
  }

  handleTransferCancel() {
    this.dimensionSelectShow = false;
    this.handleResetTransferData();
  }

  handleResetTransferData() {
    this.transferDimensionList = [];
    this.transferTargetList = [];
    this.transferEditIndex = -1;
  }

  getInfoCompnent() {
    return this.backupDetails.map((detail, idx) => (
      <div
        key={idx}
        class='item-content'
      >
        {!!detail.strategy?.id && (
          <div class='column-item'>
            <div class='column-label'> {`${this.$t('策略名称')}：`} </div>
            <div class='column-content'>
              {detail.strategy.name}
              <i
                class='icon-monitor icon-mc-wailian'
                onClick={() => this.handleToStrategy(detail.strategy.id)}
              />
            </div>
          </div>
        )}
        {/* <div class='column-item'>
          <div class='column-label'> {`${this.$t('告警级别')}：`} </div>
          <div class='column-content'>{this.levelMap[detail.severity]}</div>
        </div> */}
        <div class='column-item'>
          <div class='column-label is-special'> {`${this.$t('维度信息')}：`} </div>
          <div class='column-content'>
            {detail.dimension?.map((dem, dimensionIndex) => (
              <bk-tag
                key={dem.key + dimensionIndex}
                ext-cls='tag-theme'
                type='stroke'
                // closable
                // on-close={() => this.handleTagClose(detail, dimensionIndex)}
              >
                {`${dem.display_key || dem.key}(${dem.display_value || dem.value})`}
              </bk-tag>
            )) || '--'}
            {this.details[idx].dimension.length > 0 && (
              <span
                class='dimension-edit'
                v-bk-tooltips={{ content: `${this.$t('编辑')}` }}
                onClick={() => this.handleDimensionSelect(detail, idx)}
              >
                <i class='icon-monitor icon-bianji' />
              </span>
            )}
            {/* {detail.isModified && (
              <span
                class='reset'
                v-bk-tooltips={{ content: `${this.$t('重置')}` }}
                onClick={() => this.handleReset(idx)}
              >
                <i class='icon-monitor icon-zhongzhi1' />
              </span>
            )} */}
          </div>
        </div>
        <div
          style='margin-bottom: 18px'
          class='column-item'
        >
          <div class='column-label'> {`${this.$t('触发条件')}：`} </div>
          <div class='column-content'>{detail.trigger}</div>
        </div>
      </div>
    ));
  }

  getContentComponent() {
    return (
      <div
        class='quick-alarm-shield-event'
        v-bkloading={{ isLoading: this.loading }}
      >
        {!this.loading ? (
          <div class='stratrgy-item'>
            <div class='item-label item-before'> {this.$t('屏蔽时间')} </div>
            <VerifyInput
              show-validate={this.rule.customTime}
              {...{ on: { 'update: show-validate': val => (this.rule.customTime = val) } }}
              validator={{ content: this.$t('至少选择一种时间') }}
            >
              <div class='item-time'>
                {this.timeList.map((item, index) => (
                  <bk-button
                    key={index}
                    class={['width-item', { 'is-selected': this.timeValue === item.id }]}
                    on-click={e => this.handleScopeChange(e, item.id)}
                  >
                    {item.name}
                  </bk-button>
                ))}
                {this.timeValue !== 0 ? (
                  <bk-button
                    class={['custom-width', { 'is-selected': this.timeValue === 0 }]}
                    on-click={e => this.handleScopeChange(e, 0)}
                  >
                    {this.$t('button-自定义')}
                  </bk-button>
                ) : (
                  <bk-date-picker
                    ref='time'
                    v-model={this.customTime}
                    options={this.options}
                    placeholder={this.$t('选择日期时间范围')}
                    type={'datetimerange'}
                  />
                )}
              </div>
            </VerifyInput>
          </div>
        ) : undefined}
        <div class='stratrgy-item m0'>
          <div class='item-label'> {this.$t('屏蔽内容')} </div>
          <div class='item-tips'>
            <i class='icon-monitor icon-hint' />{' '}
            {this.$t('屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。')}{' '}
          </div>
          {this.getInfoCompnent()}
        </div>
        <div class='stratrgy-item'>
          <div class='item-label'> {this.$t('屏蔽原因')} </div>
          <div class='item-desc'>
            <bk-input
              width={625}
              v-model={this.desc}
              maxlength={100}
              rows={3}
              type='textarea'
            />
          </div>
        </div>
      </div>
    );
  }

  render() {
    return (
      <MonitorDialog
        width={'804'}
        class='quick-shield-dialog'
        header-position={'left'}
        title={this.$t('快捷屏蔽告警')}
        value={this.show}
        on-change={this.handleShowChange}
      >
        {this.getContentComponent()}
        <template slot='footer'>
          <bk-button
            style='margin-right: 10px'
            v-authority={{ active: !this.authority?.ALARM_SHIELD_MANAGE_AUTH }}
            disabled={this.loading}
            theme='primary'
            on-click={() =>
              this.authority?.ALARM_SHIELD_MANAGE_AUTH
                ? this.handleSubmit()
                : this.handleShowAuthorityDetail?.(this.authority?.ALARM_SHIELD_MANAGE_AUTH)
            }
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button on-click={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
        </template>
        {/* 穿梭框 */}
        <bk-dialog
          width={640}
          ext-cls='dimension-select-dialog-wrap'
          v-model={this.dimensionSelectShow}
          header-position='left'
          mask-close={false}
          show-footer={false}
          title={this.$t('选择维度信息')}
        >
          <DimensionTransfer
            fields={this.transferDimensionList}
            show={this.dimensionSelectShow}
            value={this.transferTargetList}
            onCancel={this.handleTransferCancel}
            onConfirm={this.handleTransferConfirm}
          />
        </bk-dialog>
      </MonitorDialog>
    );
  }
}
