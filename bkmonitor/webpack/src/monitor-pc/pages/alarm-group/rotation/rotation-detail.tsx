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

import { retrieveDutyRule } from '../../../../monitor-api/modules/model';
import { previewDutyRulePlan } from '../../../../monitor-api/modules/user_groups';
import {
  getAutoOrderList,
  getPreviewParams,
  noOrderDutyData,
  setPreviewDataOfServer
} from '../../../../trace/pages/rotation/components/calendar-preview';
import { RotationTabTypeEnum } from '../../../../trace/pages/rotation/typings/common';
import { randomColor, RuleDetailModel, transformRulesDetail } from '../../../../trace/pages/rotation/utils';
import HistoryDialog from '../../../components/history-dialog/history-dialog';

import RotationCalendarPreview from './rotation-calendar-preview';

import './rotation-detail.scss';

interface IProps {
  show: boolean;
  id: number | string;
  onShowChange?: (v: boolean) => void;
}

@Component
export default class RotationDetail extends tsc<IProps> {
  @Prop({ type: [Number, String], default: '' }) id: number | string;
  @Prop({ type: Boolean, default: false }) show: boolean;

  detailData = null;
  type: RotationTabTypeEnum = RotationTabTypeEnum.REGULAR;

  previewData = [];

  loading = false;
  rules: RuleDetailModel[] = [];

  get historyList() {
    return [
      { label: this.$t('创建人'), value: this.detailData?.create_user || '--' },
      { label: this.$t('创建时间'), value: this.detailData?.create_time || '--' },
      { label: this.$t('最近更新人'), value: this.detailData?.update_user || '--' },
      { label: this.$t('修改时间'), value: this.detailData?.update_time || '--' }
    ];
  }

  @Watch('show')
  handleShow(v: boolean) {
    if (v) {
      this.getData();
    }
  }

  @Emit('showChange')
  emitIsShow(val: boolean) {
    return val;
  }

  getData() {
    this.loading = true;
    retrieveDutyRule(this.id)
      .then((res: any) => {
        this.detailData = res;
        this.type = res.category;
        this.rules = transformRulesDetail(res.duty_arranges, res.category);
        this.getPreviewData();
      })
      .finally(() => {
        this.loading = false;
      });
  }

  async getPreviewData() {
    const params = {
      ...getPreviewParams(this.detailData.effective_time),
      source_type: 'DB',
      id: this.id
    };
    const data = await previewDutyRulePlan(params).catch(() => []);
    const autoOrders = getAutoOrderList(this.detailData);
    this.previewData = setPreviewDataOfServer(
      this.detailData.category === 'regular' ? noOrderDutyData(data) : data,
      autoOrders
    );
  }

  handleToEdit() {
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/trace/rotation/edit/${this.detailData.id}`;
    window.open(url);
  }

  renderUserLogo(user) {
    if (user.logo)
      return (
        <img
          src={user.logo}
          alt=''
        ></img>
      );
    if (user.type === 'group') return <span class='icon-monitor icon-mc-user-group no-img'></span>;
    return <span class='icon-monitor icon-mc-user-one no-img'></span>;
  }

  render() {
    function formItem(label, content) {
      return (
        <div class='form-item'>
          <div class='form-item-label'>{label} : </div>
          <div class='form-item-content'>{content}</div>
        </div>
      );
    }
    return (
      <bk-sideslider
        ext-cls='alarm-group-rotation-detail-side'
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        width={960}
        quick-close={true}
        is-show={this.show}
      >
        <div
          class='rotation-detail-side-header'
          slot='header'
        >
          <span class='header-left'>{this.$t('轮值详情')}</span>
          <span class='header-right'>
            <bk-button
              class='mr-8'
              theme='primary'
              outline
              onClick={() => this.handleToEdit()}
            >
              {this.$t('编辑')}
            </bk-button>
            <HistoryDialog
              style='margin: 0 0 0 8px'
              list={this.historyList}
            ></HistoryDialog>
          </span>
        </div>
        <div
          slot='content'
          class='rotation-detail-side-content'
        >
          {formItem(this.$t('规则名称'), <span class='detail-text text-wrap'>{this.detailData?.name || '--'}</span>)}
          {formItem(this.$t('标签'), <span class='detail-text'>{this.detailData?.labels?.join(', ') || '--'}</span>)}
          {formItem(
            this.$t('轮值类型'),
            <span class='detail-text'>
              {this.type === RotationTabTypeEnum.REGULAR ? this.$t('日常轮班') : this.$t('交替轮值')}
            </span>
          )}
          {formItem(
            this.type === RotationTabTypeEnum.REGULAR ? this.$t('值班规则') : this.$t('轮值规则'),
            this.rules.map(rule => (
              <div class='rule-item-wrap'>
                {rule.ruleTime.map((time, ind) => (
                  <div class='rule-item'>
                    {rule.ruleTime.length > 1 && [
                      <span class='rule-item-index'>{this.$t('第 {num} 班', { num: ind + 1 })}</span>,
                      <div class='col-separate'></div>
                    ]}
                    <span class='rule-item-title'>{time.day}</span>
                    {time.timer.map(item => (
                      <div class='rule-item-time-tag'>{item}</div>
                    ))}
                    {time.periodSettings && <span class='rule-item-period'>{time.periodSettings}</span>}
                  </div>
                ))}
                {rule.isAuto && (
                  <div class='auto-group'>
                    <span>{this.$t('单次值班')}</span>
                    {rule.groupNumber}
                    <span>{this.$t('人')}</span>
                  </div>
                )}
                <div class='notice-user-list'>
                  {rule.ruleUser.map(item => (
                    <div class={['notice-user-item', rule.isAuto && 'no-pl']}>
                      {!rule.isAuto && (
                        <div
                          class='has-color'
                          style={{ background: randomColor(item.orderIndex) }}
                        ></div>
                      )}
                      {item.users.map((user, ind) => (
                        <div class='personnel-choice'>
                          {rule.isAuto && (
                            <span
                              class='user-color'
                              style={{ 'background-color': randomColor(item.orderIndex + ind) }}
                            ></span>
                          )}
                          {this.renderUserLogo(user)}
                          <span>{user.display_name}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
          {formItem(
            this.$t('生效时间'),
            <span class='detail-text'>{`${this.detailData?.effective_time} - ${
              this.detailData?.end_time || this.$t('永久')
            }`}</span>
          )}
          {formItem(this.$t('轮值预览'), <RotationCalendarPreview value={this.previewData}></RotationCalendarPreview>)}
        </div>
      </bk-sideslider>
    );
  }
}
