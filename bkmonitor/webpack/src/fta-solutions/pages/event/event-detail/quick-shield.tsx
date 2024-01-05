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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { bulkAddAlertShield } from '../../../../monitor-api/modules/shield';
import VerifyInput from '../../../../monitor-pc/components/verify-input/verify-input.vue';
import MonitorDialog from '../../../../monitor-ui/monitor-dialog/monitor-dialog.vue';

import './quick-shield.scss';

const { i18n } = window;

interface IQuickShieldProps {
  show: boolean;
  details: IDetail[];
  ids?: Array<string>;
  bizIds?: number[];
}
export interface IDetail {
  severity: number;
  dimension?: string;
  trigger?: string;
  strategy?: {
    name?: string;
    id?: number;
  };
}

@Component({
  name: 'QuickShield'
})
export default class MyComponent extends tsc<IQuickShieldProps> {
  /**
   * 由于 event-center 和 event-center-detail 这两个页面都需要 Provide 以下的 authority 和 authorityFromEventDetail
   * 但是都继承了 authorityMixin 的方法，其中 beforeRouteEnter 这个只有页面组件才能执行该回调，
   * 会导致，事件详情侧边栏也会 Provide 一个初始化值到快捷屏蔽告警 dialog 上形成bug，这里将注入两种类型的变量去解决上述问题。
   * 副作用是会产生 Injection "xxx" not found 的警告
   */
  @Inject('authority') authority;
  @Inject('authorityFromEventDetail') authorityFromEventDetail;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('handleShowAuthorityDetailFromEventDetail') handleShowAuthorityDetailFromEventDetail = null;
  @Prop({ type: Boolean, default: false }) show: Boolean;
  @Prop({ type: Array, default: () => [] }) details: IDetail[];
  @Prop({ type: Array, default: () => [] }) ids: Array<string>;
  /* 事件中心暂不允许跨业务操作， 此数组只有一个业务 */
  @Prop({ type: Array, default: () => [] }) bizIds: number[];

  public loading = false;
  public rule = { customTime: false };
  public timeList = [
    { name: `0.5${i18n.t('小时')}`, id: 18 },
    { name: `1${i18n.t('小时')}`, id: 36 },
    { name: `12${i18n.t('小时')}`, id: 432 },
    { name: `1${i18n.t('天')}`, id: 864 },
    { name: `7${i18n.t('天')}`, id: 6048 }
  ];
  public timeValue = 18;
  public customTime: any = ['', ''];
  public options = {
    disabledDate(date) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      // 用户手动修改的时间不在可选时间内，回撤修改操作
      if (Array.isArray(date)) {
        return date.some(item => item.getTime() < today.getTime() || item.getTime() > today.getTime() + 8.64e7 * 181);
      }
      return date.getTime() < today.getTime() || date.getTime() > today.getTime() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
    }
  };
  public levelMap = ['', i18n.t('致命'), i18n.t('提醒'), i18n.t('预警')];
  public desc = '';

  @Watch('ids', { immediate: true })
  handleShow(newIds, oldIds) {
    if (`${JSON.stringify(newIds)}` !== `${JSON.stringify(oldIds)}`) {
      this.handleDialogShow();
    }
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
      S: time.getMilliseconds() // 毫秒
    };
    if (/(y+)/.test(fmt)) fmt = fmt.replace(RegExp.$1, `${time.getFullYear()}`.substr(4 - RegExp.$1.length));
    // eslint-disable-next-line no-restricted-syntax
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
        dimension_config: { alert_ids: this.ids },
        shield_notice: false,
        description: this.desc,
        cycle_config: {
          begin_time: '',
          type: 1,
          day_list: [],
          week_list: [],
          end_time: ''
        }
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
        ['year', 'y']
      ];
      tims.forEach(item => {
        toTime = toTime.replace(item[0], item[1]);
      });
      bulkAddAlertShield(params)
        .then(() => {
          this.handleSucces(true);
          this.handleTimeChange(toTime);
          this.handleShowChange(false);
          this.$bkMessage({ theme: 'success', message: this.$t('恭喜，创建告警屏蔽成功') });
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

  getAuthority(): any {
    const routeName = this.$route.name;
    if (routeName === 'event-center') return this.authority;
    if (routeName === 'event-center-detail') return this.authorityFromEventDetail;
    return {};
  }

  getHandleShowAuthorityDetail(action: any) {
    const routeName = this.$route.name;
    if (routeName === 'event-center') this.handleShowAuthorityDetail(action);
    if (routeName === 'event-center-detail') this.handleShowAuthorityDetailFromEventDetail?.(action);
  }

  getInfoCompnent() {
    return this.details.map(detail => (
      <div class='item-content'>
        {!!detail.strategy?.id && (
          <div class='column-item'>
            <div class='column-label'> {`${this.$t('策略名称')}：`} </div>
            <div class='column-content'>
              {detail.strategy.name}
              <i
                class='icon-monitor icon-mc-wailian'
                onClick={() => this.handleToStrategy(detail.strategy.id)}
              ></i>
            </div>
          </div>
        )}
        <div class='column-item'>
          <div class='column-label'> {`${this.$t('告警级别')}：`} </div>
          <div class='column-content'>{this.levelMap[detail.severity]}</div>
        </div>
        <div class='column-item'>
          <div class='column-label'> {`${this.$t('维度信息')}：`} </div>
          <div class='column-content'>{detail.dimension}</div>
        </div>
        <div
          class='column-item'
          style='margin-bottom: 18px'
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
                    on-click={e => this.handleScopeChange(e, item.id)}
                    class={['width-item', { 'is-selected': this.timeValue === item.id }]}
                  >
                    {item.name}
                  </bk-button>
                ))}
                {this.timeValue !== 0 ? (
                  <bk-button
                    on-click={e => this.handleScopeChange(e, 0)}
                    class={['custom-width', { 'is-selected': this.timeValue === 0 }]}
                  >
                    {this.$t('button-自定义')}
                  </bk-button>
                ) : (
                  <bk-date-picker
                    ref='time'
                    type={'datetimerange'}
                    placeholder={this.$t('选择日期时间范围')}
                    options={this.options}
                    v-model={this.customTime}
                  ></bk-date-picker>
                )}
              </div>
            </VerifyInput>
          </div>
        ) : undefined}
        <div class='stratrgy-item m0'>
          <div class='item-label'> {this.$t('告警内容')} </div>
          <div class='item-tips'>
            <i class='icon-monitor icon-hint'></i>{' '}
            {this.$t('屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。')}{' '}
          </div>
          {this.getInfoCompnent()}
        </div>
        <div class='stratrgy-item'>
          <div class='item-label'> {this.$t('屏蔽原因')} </div>
          <div class='item-desc'>
            <bk-input
              type='textarea'
              v-model={this.desc}
              width={625}
              rows={3}
              maxlength={100}
            ></bk-input>
          </div>
        </div>
      </div>
    );
  }

  render() {
    return (
      <MonitorDialog
        class='quick-shield-dialog'
        value={this.show}
        on-change={this.handleShowChange}
        title={this.$t('快捷屏蔽告警')}
        header-position={'left'}
        width={'804'}
      >
        {this.getContentComponent()}
        <template slot='footer'>
          <bk-button
            on-click={() =>
              this.getAuthority()?.ALARM_SHIELD_MANAGE_AUTH
                ? this.handleSubmit()
                : this.getHandleShowAuthorityDetail(this.getAuthority()?.ALARM_SHIELD_MANAGE_AUTH)
            }
            theme='primary'
            style='margin-right: 10px'
            disabled={this.loading}
            v-authority={{ active: !this.getAuthority()?.ALARM_SHIELD_MANAGE_AUTH }}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button on-click={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
        </template>
      </MonitorDialog>
    );
  }
}
