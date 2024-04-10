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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { addShield } from 'monitor-api/modules/shield';
import { getStrategyV2 } from 'monitor-api/modules/strategies';
import { formatDatetime } from 'monitor-common/utils/utils';

import VerifyInput from '../../../components/verify-input/verify-input.vue';
import StrategyDetail from '../alarm-shield-components/strategy-detail-new';

import './quick-alarm-shield-strategy.scss';

interface QuickAlarmShieldStrategyProps {
  isShowStrategy: boolean;
  strategyId: number;
}

interface QuickAlarmShieldStrategyEvents {
  onSuccess: () => void;
}

@Component({
  components: {
    VerifyInput,
    StrategyDetail
  }
})
export default class QuickAlarmShieldStrategy extends tsc<
  QuickAlarmShieldStrategyProps,
  QuickAlarmShieldStrategyEvents
> {
  @Prop({ type: Boolean, default: false }) isShowStrategy: boolean;
  @Prop({ type: Number }) strategyId: number;

  @Ref('time') time: any;

  timeValue = 18;
  customTime = ['', ''];
  desc = '';
  typeLabel = '';
  rule = {
    customTime: false
  };
  loading = false;
  strategyData: any = {};
  options = {
    disabledDate(date) {
      return date.getTime() < Date.now() - 8.64e7 || date.getTime() > Date.now() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
    }
  };
  timeList = [
    { name: `0.5${window.i18n.t('小时')}`, id: 18 },
    { name: `1${window.i18n.t('小时')}`, id: 36 },
    { name: `12${window.i18n.t('小时')}`, id: 432 },
    { name: `1${window.i18n.t('天')}`, id: 864 },
    { name: `7${window.i18n.t('天')}`, id: 6048 }
  ];

  @Watch('strategyId', { immediate: true })
  handlerStrategyIdChange(newId, oldId) {
    if (`${newId}` !== `${oldId}`) {
      this.handleDialogShow();
    }
  }

  handleSubmit(v) {
    const time = this.getTime();
    if (time) {
      this.loading = true;
      const params = {
        category: 'strategy',
        begin_time: time.begin,
        end_time: time.end,
        dimension_config: {
          id: [this.strategyId],
          level: [this.strategyData?.detects[0].level]
        },
        cycle_config: {
          begin_time: '',
          type: 1,
          day_list: [],
          week_list: [],
          end_time: ''
        },
        shield_notice: false,
        description: this.desc,
        is_quick: true
      };
      addShield(params)
        .then(() => {
          v.close();
          this.$bkMessage({ theme: 'success', message: this.$t('恭喜，创建告警屏蔽成功') });
          this.$emit('success');
        })
        .finally(() => {
          this.loading = false;
        });
    }
  }
  handleDialogShow() {
    this.loading = true;
    this.timeValue = 18;
    this.desc = '';
    this.customTime = ['', ''];
    this.getDetailStrategy();
  }
  getDetailStrategy() {
    if (this.strategyId) {
      getStrategyV2({ id: this.strategyId })
        .then(res => {
          this.strategyData = res;
        })
        .finally(() => {
          this.loading = false;
        });
    }
  }
  handleAfterLeave() {
    this.rule.customTime = false;
    this.$emit('update:isShowStrategy', false);
  }
  handleToStrategy() {
    const params = {
      strategyId: String(this.strategyId)
    };
    this.$emit('update:isShowStrategy', false);
    this.$router.push({ name: 'alarm-shield-add', params });
  }

  handleformat(time, fmte) {
    return formatDatetime(time, fmte);
  }
  getTime() {
    let begin = '';
    let end = '';
    if (this.timeValue === 0) {
      const [beginTime, endTime] = this.customTime;
      if (beginTime === '' || endTime === '') {
        this.rule.customTime = true;
        return false;
      }
      begin = this.handleformat(beginTime, 'yyyy-MM-dd hh:mm:ss');
      end = this.handleformat(endTime, 'yyyy-MM-dd hh:mm:ss');
    } else {
      const beginDate = new Date();
      const nowS = beginDate.getTime();
      const endDate = new Date(nowS + this.timeValue * 100000);
      begin = this.handleformat(beginDate, 'yyyy-MM-dd hh:mm:ss');
      end = this.handleformat(endDate, 'yyyy-MM-dd hh:mm:ss');
    }
    return { begin, end };
  }
  handleScopeChange(type) {
    this.timeValue = type;
    if (type === 0) {
      this.$nextTick(() => {
        this.time.visible = true;
      });
    } else {
      this.customTime = ['', ''];
    }
  }

  render() {
    return (
      <bk-dialog
        ext-cls='quick-alarm-shield-strategy-dialog'
        value={this.isShowStrategy}
        theme='primary'
        header-position='left'
        on-after-leave={this.handleAfterLeave}
        confirm-fn={this.handleSubmit}
        title={this.$t('快捷屏蔽策略')}
        width='773px'
      >
        <div
          class='quick-alarm-shield-strategy'
          v-bkloading={{ isLoading: this.loading }}
        >
          {!this.loading && (
            <div class='strategy-item'>
              <div
                class='item-label item-before'
                style='width: 66px'
              >
                {this.$t('屏蔽时间')}
              </div>
              <verify-input
                show-validate={this.rule.customTime}
                {...{ on: { 'update: show-validate': val => (this.rule.customTime = val) } }}
                validator={{ content: this.$t('至少选择一种时间') }}
              >
                <div class='item-time'>
                  {this.timeList.map((item, index) => (
                    <bk-button
                      key={index}
                      class={{ 'is-selected': this.timeValue === item.id, 'width-item': true }}
                      onClick={() => this.handleScopeChange(item.id)}
                    >
                      {item.name}
                    </bk-button>
                  ))}
                  {this.timeValue !== 0 ? (
                    <bk-button
                      class={{ 'is-selected': this.timeValue === 0, 'custom-width': true }}
                      onClick={() => this.handleScopeChange(0)}
                    >
                      {this.$t('button-自定义')}
                    </bk-button>
                  ) : (
                    <bk-date-picker
                      v-model={this.customTime}
                      options={this.options}
                      placeholder={this.$t('选择时间范围')}
                      type='datetimerange'
                      ref='time'
                    />
                  )}
                </div>
              </verify-input>
            </div>
          )}

          <div class='strategy-item'>
            <div class='item-label'>{this.$t('策略内容')}</div>
            <strategy-detail strategy-data={this.strategyData} />
          </div>
          <div
            class='strategy-item'
            style='margin-bottom: 11px'
          >
            <div class='item-label'>{this.$t('屏蔽原因')}</div>
            <div>
              <bk-input
                type='textarea'
                v-model={this.desc}
                width='625'
                rows={3}
                maxlength={100}
              />
            </div>
          </div>
        </div>
      </bk-dialog>
    );
  }
}
