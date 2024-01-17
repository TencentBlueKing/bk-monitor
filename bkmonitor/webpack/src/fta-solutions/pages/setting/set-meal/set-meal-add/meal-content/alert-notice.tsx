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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone, random } from '../../../../../../monitor-common/utils/utils';
import TemplateInput from '../../../../../../monitor-pc/pages/strategy-config/strategy-config-set/strategy-template-input/strategy-template-input';
import StrategyTemplatePreview from '../../../../../../monitor-pc/pages/strategy-config/strategy-config-set/strategy-template-preview/strategy-template-preview';
import ResizeContainer from '../../../../../components/resize-container/resize-container';
import SetMealAddModule from '../../../../../store/modules/set-meal-add';
import AutoInput from '../../../components/auto-input';
import TipMsg from '../../../components/tip-msg';
import CommonItem from '../components/common-item';
import CustomTab, { IPanels } from '../components/custom-tab';
import NoticeModeNew, { INoticeWayValue, robot } from '../components/notice-mode';

import {
  defaultAddTimeRange,
  executionName,
  executionNotifyConfigChange,
  executionTips,
  IExecution,
  INotice,
  INoticeAlert,
  INoticeTemplate,
  intervalModeTips,
  templateSignalName,
  timeRangeValidate,
  timeTransform
} from './meal-content-data';

import './alert-notice.scss';

const intervalModeList = [
  { id: 'standard', name: window.i18n.t('固定') },
  { id: 'increasing', name: window.i18n.t('递增') }
];

interface IAlertNoticeProps {
  noticeData?: INotice;
}

interface IAlertNoticeEvent {
  onChange?: INotice;
}

@Component({
  name: 'AlertNotice'
})
export default class AlertNotice extends tsc<IAlertNoticeProps, IAlertNoticeEvent> {
  @Prop({ type: Object, default: () => ({}) }) noticeData: INotice;
  @Ref('noticeModeRef') noticeModeRef: NoticeModeNew;

  isShowTemplate = false;

  // 通知告警所有数据
  data: INotice = {};
  // 告警通知配置
  alertActive = '';
  alertData: INoticeAlert = {};
  alertNewkey = '';
  // 通知模板配置
  templateActive = '';
  templateData: INoticeTemplate = {};
  // 执行通知配置
  executionActive = 0;
  executionData: IExecution = {};

  // 时间段列表
  get timePanels(): IPanels[] {
    return (
      this.noticeData.alert
        ?.map(item => ({
          key: item.key,
          timeValue: item.timeRange
        }))
        .sort((a, b) => (timeTransform(a.timeValue[0]) as number) - (timeTransform(b.timeValue[0]) as number)) || []
    );
  }
  // 通知模板类型列表
  get templateTypes() {
    return (
      this.noticeData.template.map(item => ({
        key: item.signal,
        label: templateSignalName[item.signal]
      })) || []
    );
  }
  // 执行通知类型列表
  get executionTypes() {
    return this.noticeData.execution.map(item => ({
      key: `${item.riskLevel}`,
      label: `${executionName[item.riskLevel]}`
    }));
  }
  // 通知方式
  get noticeWayList() {
    return SetMealAddModule.noticeWayList;
  }
  // 模板变量
  get getMessageTemplateList() {
    return SetMealAddModule.getMessageTemplateList;
  }

  @Watch('noticeData', { immediate: true, deep: true })
  handleNoticeData(data: INotice) {
    if (data?.alert) {
      this.data = data;
      if (this.alertActive === '') {
        this.alertActive = data.alert[0].key;
        this.alertData = deepClone(data.alert[0]);
      }
      if (this.templateActive === '') {
        this.templateActive = data.template[0].signal;
        this.templateData = deepClone(data.template[0]);
      }
      if (this.executionActive === 0) {
        this.executionActive = data.execution[0].riskLevel;
        this.executionData = deepClone(data.execution[0]);
      }
    }
  }
  @Emit('change')
  handleChange() {
    this.data.alert = this.data.alert.map(item => {
      if (item.key === this.alertActive) {
        return deepClone(this.alertData);
      }
      return item;
    });
    this.data.template = this.data.template.map(item => {
      if (item.signal === this.templateActive) {
        return deepClone(this.templateData);
      }
      return item;
    });
    this.data.execution = this.data.execution.map(item => {
      if (item.riskLevel === this.executionActive) {
        return deepClone(this.executionData);
      }
      return item;
    });
    return this.data;
  }
  // 通知方式
  noticeConfigChange(noticeConfig: INoticeWayValue[]) {
    this.alertData.notifyConfig = noticeConfig;
    this.handleChange();
  }
  // 执行通知
  executionNoticeConfigChange(noticeConfig: INoticeWayValue[]) {
    this.executionData.notifyConfig = executionNotifyConfigChange(noticeConfig, false);
    this.handleChange();
  }

  // 模板预览
  handleShowTemplate() {
    if (!this.templateData.messageTmpl) return;
    this.isShowTemplate = true;
  }
  // 修改告警模板
  noticeTemplateChange(tplStr: string) {
    this.templateData.messageTmpl = tplStr;
    this.handleChange();
  }

  // 增加时间段
  handleAddTimeRang() {
    const defaultTimeRange = defaultAddTimeRange(this.data.alert.map(item => item.timeRange));
    if (!defaultTimeRange.length) {
      this.$bkMessage({
        theme: 'warning',
        message: window.i18n.tc('时间段重叠了')
      });
      return;
    }
    const copyData: INoticeAlert = deepClone(this.alertData);
    copyData.key = random(10);
    copyData.timeRange = defaultTimeRange[defaultTimeRange.length - 1] as string[];
    this.data.alert.push(copyData);
    this.$nextTick(() => {
      this.alertNewkey = copyData.key;
    });
    this.handleChange();
  }
  // 切换时间段
  handleChangeTimeRang(v: string) {
    this.alertActive = v;
    this.alertData = this.data.alert.find(item => item.key === v);
  }
  // 编辑时间段
  handleEditTimeRang(v: { value: string[]; key: string }) {
    const curTimeRange = deepClone(this.alertData.timeRange);
    // 时间段校验
    if (
      !timeRangeValidate(
        this.data.alert.filter(item => item.key !== v.key).map(item => item.timeRange),
        v.value
      )
    ) {
      this.$bkMessage({
        theme: 'warning',
        message: window.i18n.tc('时间段重叠了')
      });
      this.alertData.timeRange = curTimeRange;
      this.handleChange();
      return;
    }
    this.data.alert = this.data.alert.map(item => {
      if (item.key === v.key) {
        return {
          ...item,
          timeRange: v.value
        };
      }
      return { ...item };
    });
    if (this.alertActive === v.key) {
      this.alertData.timeRange = v.value;
    }
    this.handleChange();
  }
  // 删除时间段
  handleDelTimeRang(v: string) {
    const index = this.data.alert.findIndex(item => item.key === v);
    this.data.alert.splice(index, 1);
  }
  // 切换模板类型
  handleChangeTemplate(v: string) {
    this.templateActive = v;
    this.templateData = this.data.template.find(item => item.signal === v);
  }
  // 切换执行通知
  handleChangeExecution(v: number) {
    this.executionActive = v;
    this.executionData = this.data.execution.find(item => `${item.riskLevel}` === `${v}`);
  }

  // 校验
  async validator() {
    const allNoticeModeValidator = this.data.alert.some(alertItem => {
      const isPass = alertItem.notifyConfig.every(item => {
        const hasRobot = item.type.includes(robot.wxworkBot);
        if (hasRobot && !item.chatid) return false;
        if (!item.type?.length) return false;
        return true;
      });
      if (!isPass) {
        this.handleChangeTimeRang(alertItem.key);
      }
      return !isPass;
    });
    await this.$nextTick();
    this.noticeModeRef.validator();
    return !allNoticeModeValidator;
  }

  render() {
    return (
      <div class='alert-notice-new'>
        <div class='header-title'>{this.$t('告警阶段')}</div>
        <div class='content-wrap-key1'>
          <div class='wrap-top'></div>
          <CustomTab
            panels={this.timePanels}
            active={this.alertActive}
            type={'period'}
            newKey={this.alertNewkey}
            onAdd={this.handleAddTimeRang}
            onChange={this.handleChangeTimeRang}
            onDel={this.handleDelTimeRang}
            onTimeChange={this.handleEditTimeRang}
          ></CustomTab>
          <div class='wrap-bottom'>
            <div class='label-wrap'>
              <span class='label'>{this.$t('通知间隔')}：</span>
              <span class='content'>
                <i18n
                  path='若产生相同的告警未确认或者未屏蔽,则{0}间隔{1}分钟再进行告警。'
                  class='content-interval'
                >
                  <bk-select
                    style='margin-top: -1px; min-width: 74px;'
                    class='select select-inline'
                    clearable={false}
                    behavior='simplicity'
                    v-model={this.alertData.intervalNotifyMode}
                    onChange={this.handleChange}
                  >
                    {intervalModeList.map(item => (
                      <bk-option
                        key={item.id}
                        id={item.id}
                        name={item.name}
                      ></bk-option>
                    ))}
                  </bk-select>
                  <bk-input
                    class='input-inline input-center'
                    style='width: 56px;'
                    behavior='simplicity'
                    v-model={this.alertData.notifyInterval}
                    type='number'
                    onInput={this.handleChange}
                  ></bk-input>
                </i18n>
                <span
                  class='icon-monitor icon-hint'
                  v-bk-tooltips={{ content: intervalModeTips[this.alertData.intervalNotifyMode], allowHTML: false }}
                  style={{ color: '#979ba5', marginTop: '-3px' }}
                ></span>
              </span>
            </div>
            <NoticeModeNew
              class='notice-mode'
              ref='noticeModeRef'
              noticeWay={this.noticeWayList}
              notifyConfig={this.alertData.notifyConfig}
              showlevelMark={true}
              onChange={this.noticeConfigChange}
            ></NoticeModeNew>
          </div>
        </div>
        <div class='content-wrap-key1'>
          <div class='wrap-top'>
            <CustomTab
              panels={this.templateTypes}
              active={this.templateActive}
              type={'text'}
              onChange={this.handleChangeTemplate}
            ></CustomTab>
          </div>
          <div class='wrap-bottom'>
            <CommonItem
              title={this.$tc('告警标题')}
              required
            >
              <AutoInput
                class='template-title'
                tipsData={this.getMessageTemplateList}
                v-model={this.templateData.titleTmpl}
                onChange={this.handleChange}
              ></AutoInput>
              {/* <bk-input
                behavior='simplicity'
                ext-cls="template-title"
                v-model={this.templateData.titleTmpl}
                onInput={this.handleChange}></bk-input> */}
            </CommonItem>
            <div
              class='label-wrap'
              style='margin-top: 24px;'
            >
              <span class='label'>{this.$t('告警通知模板')}</span>
              <span class='content desc'>{this.$t('(变量列表及模板说明详见右侧栏)')}</span>
              <div
                class={['template-btn-wrap', { 'template-btn-disabled': !this.templateData.messageTmpl }]}
                onClick={this.handleShowTemplate}
              >
                <i class='icon-monitor icon-audit'></i>
                <span class='template-btn-text'>{this.$t('模板预览')}</span>
              </div>
            </div>
            <ResizeContainer
              style='margin-top: 8px'
              height={215}
              minHeight={80}
              minWidth={200}
            >
              <TemplateInput
                default-value={this.templateData.messageTmpl}
                trigger-list={this.getMessageTemplateList}
                onChange={this.noticeTemplateChange}
                style='width: 100%; height: 100%;'
              ></TemplateInput>
            </ResizeContainer>
          </div>
          {/* <bk-button class="debug-btn" theme="primary" outline={true} onClick={() => (this.showTestDialog = true)}>
          {this.$t('调试')}
        </bk-button> */}
          <StrategyTemplatePreview
            dialogShow={this.isShowTemplate}
            template={this.templateData.messageTmpl}
            {...{ on: { 'update:dialogShow': v => (this.isShowTemplate = v) } }}
          ></StrategyTemplatePreview>
        </div>
        <div class='header-title execution'>{this.$t('执行通知')}</div>
        <TipMsg
          class='storm-item-msg'
          msg={`${this.$t(
            '除了通知套餐外其他都是可以设置套餐的敏感度，通知套餐基于不同的敏感度可以配置不同的通知方式。'
          )}`}
          style={{ marginTop: '10px' }}
        ></TipMsg>
        <div
          class='content-wrap-key1'
          style={{ marginTop: '10px' }}
        >
          <div class='wrap-top'>
            <CustomTab
              panels={this.executionTypes}
              active={this.executionActive}
              type={'text'}
              onChange={this.handleChangeExecution}
            ></CustomTab>
          </div>
          <div class='wrap-bottom execution'>
            <TipMsg
              class='storm-item-msg'
              msg={executionTips[this.executionActive]}
            ></TipMsg>
            <NoticeModeNew
              noticeWay={this.noticeWayList}
              notifyConfig={executionNotifyConfigChange(this.executionData?.notifyConfig)}
              type={1}
              onChange={this.executionNoticeConfigChange}
            ></NoticeModeNew>
          </div>
        </div>
      </div>
    );
  }
}
