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
/* eslint-disable camelcase */
import { Component, Emit, Inject, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getPlugins, getPluginTemplates, getTemplateDetail } from '../../../../monitor-api/modules/action';
import { retrieveActionConfig } from '../../../../monitor-api/modules/model';
import { getNoticeWay } from '../../../../monitor-api/modules/notice_group';
import { getStrategyListV2 } from '../../../../monitor-api/modules/strategies';
import { Debounce, deepClone, transformDataKey } from '../../../../monitor-common/utils/utils';
import HistoryDialog from '../../../../monitor-pc/components/history-dialog/history-dialog';
import { strategyType } from '../../strategy-config/typings/strategy';
import * as ruleAuth from '../set-meal/authority-map';
import Container from '../set-meal/set-meal-add/components/container';
import NoticeModeNew from '../set-meal/set-meal-add/components/notice-mode';
import HttpCallBack from '../set-meal/set-meal-add/meal-content/http-callback';
import {
  executionName,
  executionNotifyConfigChange,
  executionTips,
  IExecution,
  IMealData,
  INoticeAlert,
  INoticeTemplate,
  intervalModeName,
  mealContentDataBackfill,
  mealDataInit,
  templateSignalName
} from '../set-meal/set-meal-add/meal-content/meal-content-data';

import './set-meal-detail.scss';

export interface ISetMealDetail {
  isShow?: boolean;
  id: number;
  width?: number;
  strategyType?: strategyType;
  strategyId?: number | string;
}

interface IEvent {
  onShowChange?: boolean;
}

@Component({
  name: 'set-meal-detail',
  components: {
    HistoryDialog
  }
})
export default class SetMealDeail extends tsc<ISetMealDetail, IEvent> {
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Model('showChange', { default: false, type: Boolean }) isShow: boolean;
  @Prop({ default: 0, type: Number }) id: number;
  @Prop({ default: 540, type: Number }) width: number;
  @Prop({ default: 'fta', type: String }) strategyType: strategyType;
  @Prop({ default: false, type: Boolean }) needEditTips: boolean;
  @Prop({ default: '', type: [Number, String] }) strategyId: number;
  @Ref('strategyListWrap') strategyListWrapRef: any;

  isLoading = false;
  detailInfo: any = {};

  // 套餐内容
  mealData: IMealData = mealDataInit();
  noticeAlertActive = '';
  noticeAlertData: INoticeAlert = {};
  noticeExecutionActive = 0;
  noticeExecutionData: IExecution = {};
  noticeTemplateActive = '';
  noticeTemplateData: INoticeTemplate = {};
  noticeWayList = [];

  // 周边系统数据
  peripheralData: any = {
    label: '',
    templates: [],
    formName: '',
    formData: []
  };

  // 关联策略
  strategyList = [];

  isShowMoreStrategy = false;

  mealTypeList = [];

  tableScrollEl: HTMLBaseElement;
  tableScrollDebounce: any = null;
  strategyListInTheEnd = false;
  customName = {
    title: `${window.i18n.t('执行阶段')}`,
    1: `${window.i18n.t('失败时')}`,
    2: `${window.i18n.t('成功时')}`,
    3: `${window.i18n.t('执行前')}`
  };

  // 监控
  get isMonitor(): boolean {
    return this.strategyType === 'monitor';
  }

  // 套餐类型名字
  get getMealTypeName() {
    const id = this.detailInfo.plugin_id;
    const res = this.mealTypeList.find(item => item.id === id);
    return res?.name || id;
  }
  // 周边系统下拉名字
  get getPeripheralDataInfo() {
    const id = this.detailInfo?.execute_config?.template_id;
    const res = this.peripheralData.templates.find(item => String(item.id) === String(id));
    return {
      name: res?.name || '',
      id,
      url: res?.url || ''
    };
  }
  // 业务列表
  get bizList() {
    return this.$store.getters.bizList;
  }

  // 业务名
  get getBizName() {
    return this.bizList.find(item => item.id === +this.detailInfo.bk_biz_id)?.name;
  }

  // 关联的策略列表
  get filterStrategyList() {
    return this.strategyList.filter((item, index) => (this.isShowMoreStrategy ? true : index <= 2));
  }
  // 策略展示更多按钮
  get tplShowMore() {
    const leng = this.detailInfo.strategy_count;
    if (!leng) return leng;
    if (leng <= 3) return undefined;
    if (!this.isShowMoreStrategy)
      return (
        <div
          class='show-more-btn'
          onClick={() => (this.isShowMoreStrategy = true)}
        >
          {this.$t('展开更多 ({num})', { num: leng })}
        </div>
      );
    return (
      <div
        class='show-more-btn'
        onClick={() => (this.isShowMoreStrategy = false)}
      >
        {this.$t('收起更多 ({num})', { num: leng })}
      </div>
    );
  }

  // 流程服务类型
  get isCommon() {
    return !this.isHttp && !this.isNotice;
  }
  // http回调
  get isHttp() {
    return this.detailInfo.plugin_type === 'webhook';
  }
  // 通知套餐
  get isNotice() {
    return this.detailInfo.plugin_type === 'notice';
  }

  get formData() {
    const valueMap = this.detailInfo?.execute_config?.template_detail;
    const res = this.peripheralData.formData.map(item => ({
      label: item.formItemProps.label,
      value: valueMap[item.key] || ''
    }));
    return res;
  }

  get historyList() {
    if (!this.detailInfo || !Object.keys(this.detailInfo).length) return [];
    return [
      { label: this.$t('创建人'), value: this.detailInfo.create_user || '--' },
      { label: this.$t('创建时间'), value: this.detailInfo.create_time || '--' },
      { label: this.$t('最近更新人'), value: this.detailInfo.update_user || '--' },
      { label: this.$t('修改时间'), value: this.detailInfo.update_time || '--' }
    ];
  }

  beforeDestroy() {
    this.tableScrollEl?.removeEventListener('scroll', this.handleTableScroll);
  }

  /**
   * @description: 监听表格滚动
   * @param {*}
   * @return {*}
   */
  addListenerTableScroll() {
    this.tableScrollEl = this.strategyListWrapRef.$el.querySelector('.bk-table-body-wrapper');
    this.tableScrollEl.addEventListener('scroll', this.handleTableScroll);
  }

  /**
   * @description: 处理表格滚动
   * @param {*} e
   * @return {*}
   */
  @Debounce(300)
  handleTableScroll(e) {
    const { scrollHeight } = e.target;
    const { scrollTop } = e.target;
    const { clientHeight } = e.target;
    const isEnd = !!(scrollHeight - Math.ceil(scrollTop) === clientHeight && scrollTop);
    if (isEnd) this.getStategyList();
  }

  @Emit('showChange')
  showChange(v) {
    this.strategyListInTheEnd = false;
    this.isShowMoreStrategy = false;
    this.strategyList = [];
    return v;
  }

  @Watch('isShow')
  isShowChange(v) {
    if (v) {
      this.getDetailInfo();
    }
  }
  @Watch('strategyList')
  strategyListChange(list) {
    if (list?.length) {
      // 表格增加滚动的监听
      this.isShow && this.$nextTick(this.addListenerTableScroll);
    }
  }

  /**
   * 获取下拉数据
   */
  async getSelectListData() {
    const promiseList = [];
    // 获取关联的策略
    promiseList.push(this.getStategyList());
    // 套餐类型列表
    promiseList.push(this.getMealTypeList());
    // 通知类型列表
    promiseList.push(this.getNoticeWay());
    // 流程服务
    if (this.isCommon) {
      promiseList.push(this.getPluginTemplates(this.detailInfo.plugin_id));
      // form表单数据
      const templateId = this.detailInfo?.execute_config?.template_id;
      promiseList.push(this.getTemplateDetail(this.detailInfo.plugin_id, templateId));
    }
    Promise.all(promiseList).finally(() => (this.isLoading = false));
  }

  async getNoticeWay() {
    const data = await getNoticeWay().catch(() => []);
    this.noticeWayList = data.map(item => ({
      type: item.type,
      label: item.label,
      icon: item.icon,
      tip: item.type === 'wxwork-bot' ? window.i18n.t('获取群ID方法', { name: item.name }) : undefined
    }));
  }

  /**
   * @description: 获取套餐关联的测录列表
   * @param {*}
   * @return {*}
   */
  async getStategyList() {
    if (this.detailInfo.strategy_count <= this.strategyList.length || this.strategyListInTheEnd) return;
    const limit = 10;
    const page =
      (this.strategyList.length % limit
        ? Math.ceil(this.strategyList.length / limit)
        : this.strategyList.length / limit + 1) || 1;
    const params = {
      page,
      page_size: limit,
      conditions: [{ key: 'action_name', value: [this.detailInfo.name] }],
      order_by: '-update_time',
      with_user_group: true
    };
    const res = await getStrategyListV2(params).catch(() => []);
    const list = res.strategy_config_list;
    if (list.length < limit) this.strategyListInTheEnd = true;
    if (page > 1) {
      this.strategyList.push(...list);
    } else {
      this.strategyList = list;
    }
  }

  /**
   * 获取插件列表
   */
  async getMealTypeList() {
    const result = await getPlugins().catch(() => []);
    this.mealTypeList = result.reduce((total: any, cur) => (total = [...total, ...cur.children]), []);
  }

  // 获取作业平台下拉数据
  async getPluginTemplates(id: number) {
    const data: any = await getPluginTemplates({ plugin_id: id }).finally(() => (this.isLoading = false));
    this.peripheralData.label = data.name;
    this.peripheralData.templates = data.templates;
  }

  // 获取动态form表单数据
  async getTemplateDetail(pluginId: number, templateId: number) {
    if (templateId) {
      const data: any = await getTemplateDetail({ plugin_id: pluginId, template_id: templateId });
      this.peripheralData.formName = data.name;
      this.peripheralData.formData = data.params;
    } else {
      this.peripheralData.formName = '';
      this.peripheralData.formData = [];
    }
  }

  // 获取详情信息
  getDetailInfo() {
    this.isLoading = true;
    retrieveActionConfig(this.id).then(res => {
      this.detailInfo = res;
      this.mealData = mealContentDataBackfill(transformDataKey(res));
      const { notice } = this.mealData;
      this.noticeAlertActive = notice.alert[0].key;
      this.noticeAlertData = deepClone(notice.alert[0]);
      this.noticeTemplateActive = notice.template[0].signal;
      this.noticeTemplateData = deepClone(notice.template[0]);
      this.noticeExecutionActive = notice.execution[0].riskLevel;
      this.noticeExecutionData = deepClone(notice.execution[0]);
      this.getSelectListData();
    });
  }

  /**
   * @description: 编辑套餐
   * @param {*}
   * @return {*}
   */
  toEditMeal() {
    this.showChange(false);
    const { id } = this.detailInfo;
    this.$router.push({
      path: `/set-meal-edit/${id}`,
      params: {
        strategyId: `${this.strategyId}`
      }
    });
  }
  /**
   * @description: 跳转策略列表
   * @return {*}
   */
  handleToStrategyList() {
    if (!this.detailInfo.strategy_count) return;
    this.$router.push({
      name: 'strategy-config',
      params: {
        actionName: this.detailInfo.name
      }
    });
  }

  /**
   * @description: 策略详情
   * @param {number} id 策略id
   * @return {*}
   */
  toStrategy(id: number) {
    window.open(location.href.replace(location.hash, `#/strategy-config/detail/${id}`));
  }

  isAuth(bkBizId: number): {
    authority: boolean;
    authorityType: string;
  } {
    return {
      authority: bkBizId === 0 ? this.authority.MANAGE_PUBLIC_ACTION_CONFIG : this.authority.MANAGE_ACTION_CONFIG,
      authorityType: bkBizId === 0 ? ruleAuth.MANAGE_PUBLIC_ACTION_CONFIG : ruleAuth.MANAGE_ACTION_CONFIG
    };
  }

  /* 跳转到具体的执行方案 */
  handleToPeripheral() {
    const id = this.detailInfo?.execute_config?.template_id;
    const res = this.peripheralData.templates.find(item => String(item.id) === String(id));
    if (res?.url) {
      window.open(res.url);
    }
  }

  protected render() {
    const formatter = row => (
      <span class='strategy-table-cell'>
        <span
          class='name'
          onClick={() => this.toStrategy(row.id)}
        >
          {row.name}
        </span>
        <span class='id'>&nbsp;(#{row.id})</span>
      </span>
    );
    return (
      <div class='set-meal-detail-wrap'>
        <bk-sideslider
          isShow={this.isShow}
          width={this.width}
          quickClose
          {...{
            on: {
              'update:isShow': this.showChange
            }
          }}
        >
          <div
            slot='header'
            class='title-wrap'
          >
            <span class='title'>{this.$t('套餐详情')}</span>
            {this.detailInfo?.edit_allowed && (
              <div class='title-btn'>
                {/* <i class="icon-monitor icon-mc-link"></i> */}
                <bk-button
                  v-authority={{ active: !this.isAuth(Number(this.detailInfo.bk_biz_id)).authority }}
                  onClick={() =>
                    this.isAuth(Number(this.detailInfo.bk_biz_id)).authority
                      ? this.toEditMeal()
                      : this.handleShowAuthorityDetail(this.isAuth(Number(this.detailInfo.bk_biz_id)).authorityType)
                  }
                  theme='primary'
                  outline={true}
                  style='width: 88px; margin-right: 8px'
                  v-bk-tooltips={{
                    content: this.$t('进入编辑页，编辑完可直接返回不会丢失数据'),
                    disabled: !this.needEditTips
                  }}
                >
                  {this.$t('编辑')}
                </bk-button>
                <HistoryDialog list={this.historyList} />
              </div>
            )}
          </div>
          <div
            slot='content'
            class='set-meal-detail-content'
            v-bkloading={{ isLoading: this.isLoading }}
          >
            <div class='detail-content-h1'>{this.$t('基本信息')}</div>
            <div class='detail-conent-form'>
              <div class='content-form-item'>
                <div
                  class='form-item-label'
                  v-en-class='en-lang'
                >
                  {this.$t('所属')}
                </div>
                <div class='form-item-content'>{this.getBizName}</div>
              </div>
              <div class='content-form-item'>
                <div
                  class='form-item-label'
                  v-en-class='en-lang'
                >
                  {this.$t('套餐名称')}
                </div>
                <div class='form-item-content'>
                  <div
                    class='form-item-content-desc'
                    v-bk-overflow-tips
                  >
                    {this.detailInfo.name}
                  </div>
                </div>
              </div>
              <div class='content-form-item'>
                <div
                  class='form-item-label'
                  v-en-class='en-lang'
                >
                  {this.$t('关联策略')}
                </div>
                <div
                  class='form-item-content'
                  key={this.id}
                >
                  {this.tplShowMore}
                  {this.strategyList.length ? (
                    <bk-table
                      max-height={400}
                      ref='strategyListWrap'
                      data={this.filterStrategyList}
                    >
                      <bk-table-column
                        label={this.$t('策略名')}
                        formatter={formatter}
                      ></bk-table-column>
                    </bk-table>
                  ) : undefined}
                </div>
              </div>
              <div class='content-form-item'>
                <div
                  class='form-item-label'
                  v-en-class='en-lang'
                >
                  {this.$t('是否启用')}
                </div>
                <div class='form-item-content'>
                  {this.detailInfo.is_enabled ? <span class='status-label-enabled'>{this.$t('已启用')}</span> : '--'}
                </div>
              </div>
              <div class='content-form-item'>
                <div
                  class='form-item-label'
                  v-en-class='en-lang'
                >
                  {this.$t('说明')}
                </div>
                <div class='form-item-content'>
                  <div
                    class='form-item-content-desc'
                    v-bk-overflow-tips
                  >
                    {this.detailInfo.desc || '--'}
                  </div>
                </div>
              </div>
            </div>
            <div class='detail-content-h1 mt32'>{this.$t('套餐内容')}</div>
            <div class='detail-conent-form'>
              {!this.isCommon ? (
                <div class='content-form-item'>
                  <div
                    class='form-item-label'
                    v-en-class='en-lang'
                  >
                    {this.$t('套餐类型')}
                  </div>
                  <div class='form-item-content'>{this.getMealTypeName}</div>
                </div>
              ) : undefined}
              {
                // 流程服务
                this.isCommon ? (
                  <div>
                    <div class='content-form-item'>
                      <div
                        class='form-item-label'
                        v-en-class='en-lang'
                      >
                        {this.$t('套餐类型')}
                      </div>
                      <div class='form-item-content'>{this.getMealTypeName}</div>
                    </div>
                    <div class='content-form-item'>
                      <div
                        class='form-item-label'
                        v-en-class='en-lang'
                      >
                        {this.peripheralData.label}
                      </div>
                      <div class='form-item-content'>
                        {this.getPeripheralDataInfo?.name || (
                          <span>
                            {this.getPeripheralDataInfo?.id || ''}
                            <span style={{ color: '#ff9c01' }}>（{window.i18n.t('已删除')}）</span>
                          </span>
                        )}
                        {this.getPeripheralDataInfo?.url ? (
                          <i
                            class='icon-monitor icon-mc-link link'
                            onClick={this.handleToPeripheral}
                          ></i>
                        ) : undefined}
                      </div>
                    </div>
                  </div>
                ) : undefined
              }
              {this.isCommon ? (
                <Container
                  title={this.peripheralData.formName}
                  class='form-container'
                >
                  {this.formData.map(item => (
                    <div class='content-form-item'>
                      <div
                        class='form-item-label'
                        v-en-class='en-lang'
                        v-bk-overflow-tips
                      >
                        {item.label}
                      </div>
                      <div class='form-item-content'>
                        {item.value ? (
                          item.value
                        ) : (
                          <span class='form-value-placeholder'>
                            <i class='icon-monitor icon-remind'></i>
                            <span class='value-placeholder-text'>{this.$t('变量不存在，请前往编辑套餐')}</span>
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                  {!this.formData.length ? this.$t('当前{n}无需填写参数', { n: this.peripheralData.label }) : undefined}
                </Container>
              ) : undefined}
              {this.isCommon ? (
                <div
                  class='content-form-item'
                  style={{ marginTop: '16px' }}
                >
                  <div
                    class='form-item-label'
                    v-en-class='en-lang'
                  >
                    {this.$t('失败处理')}
                  </div>
                  <div class='form-item-content'>
                    <i18n
                      path='当执行{0}分钟未结束按失败处理。'
                      class='failure-text'
                    >
                      {this.mealData.peripheral.timeout}
                    </i18n>
                  </div>
                </div>
              ) : undefined}
              {
                // http回调
                this.isHttp ? (
                  <HttpCallBack
                    value={this.mealData.webhook}
                    label='URL'
                    isEdit={false}
                  ></HttpCallBack>
                ) : undefined
              }
              {
                // 通知
                this.isNotice ? (
                  <div class='notice-form-container'>
                    <div class='notice-title'>{this.$t('告警阶段')}</div>
                    <div class='notice-item-wrap alert'>
                      <bk-tab
                        active={this.noticeAlertActive}
                        labelHeight={42}
                        on-tab-change={(v: string) => {
                          this.noticeAlertActive = v;
                          this.noticeAlertData = this.mealData.notice.alert.find(item => item.key === v);
                        }}
                      >
                        {this.mealData.notice.alert
                          .map(item => ({ key: item.key, label: item.timeRange.join('-') }))
                          .map(item => (
                            <bk-tab-panel
                              key={item.key}
                              name={item.key}
                              label={item.label}
                            ></bk-tab-panel>
                          ))}
                      </bk-tab>
                      <div class='notice-tab-wrap'>
                        <div
                          class='content-form-item'
                          style={{ marginTop: '16px' }}
                        >
                          <div
                            class='form-item-label'
                            v-en-class='en-lang'
                          >
                            {this.$tc('通知间隔')}
                          </div>
                          <div class='form-item-content'>
                            <i18n
                              path='若产生相同的告警未确认或者未屏蔽,则{0}间隔{1}分钟再进行告警。'
                              class='content-interval'
                            >
                              <span>{intervalModeName[this.noticeAlertData.intervalNotifyMode]}</span>
                              <span>{this.noticeAlertData.notifyInterval}</span>
                            </i18n>
                          </div>
                        </div>
                        <div class='content-form-item-column'>
                          <div
                            class='form-item-label'
                            v-en-class='en-lang'
                          >
                            {this.$t('通知方式')}
                          </div>
                          <div class='form-item-content pb12'>
                            <NoticeModeNew
                              noticeWay={this.noticeWayList}
                              notifyConfig={this.noticeAlertData.notifyConfig}
                              readonly={true}
                            ></NoticeModeNew>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div class='notice-item-wrap template'>
                      <bk-tab
                        active={this.noticeTemplateActive}
                        labelHeight={42}
                        on-tab-change={(v: string) => {
                          this.noticeTemplateActive = v;
                          this.noticeTemplateData = this.mealData.notice.template.find(item => item.signal === v);
                        }}
                      >
                        {this.mealData.notice.template
                          .map(item => ({ key: item.signal, label: templateSignalName[item.signal] }))
                          .map(item => (
                            <bk-tab-panel
                              key={item.key}
                              name={item.key}
                              label={item.label}
                            ></bk-tab-panel>
                          ))}
                      </bk-tab>
                      <div class='notice-tab-wrap'>
                        <div
                          class='content-form-item'
                          style={{ marginTop: '16px' }}
                        >
                          <div
                            class='form-item-label'
                            v-en-class='en-lang'
                          >
                            {this.$tc('告警标题')}
                          </div>
                          <div class='form-item-content'>{this.noticeTemplateData.titleTmpl}</div>
                        </div>
                        <div class='content-form-item-column'>
                          <div
                            class='form-item-label'
                            v-en-class='en-lang'
                          >
                            {this.$t('告警通知模板')}
                          </div>
                          <div class='form-item-content pb12'>
                            <pre class='text-area-display'>{this.noticeTemplateData.messageTmpl}</pre>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div class='notice-title execution'>{this.$t('执行通知')}</div>
                    <div class='notice-item-wrap execution'>
                      <bk-tab
                        active={this.noticeExecutionActive}
                        labelHeight={42}
                        on-tab-change={(v: number) => {
                          this.noticeExecutionActive = v;
                          this.noticeExecutionData = this.mealData.notice.execution.find(item => item.riskLevel === v);
                        }}
                      >
                        {this.mealData.notice.execution
                          .map(item => ({ key: item.riskLevel, label: executionName[item.riskLevel] }))
                          .map(item => (
                            <bk-tab-panel
                              key={item.key}
                              name={item.key}
                              label={item.label}
                            ></bk-tab-panel>
                          ))}
                      </bk-tab>
                      <div class='notice-tab-wrap'>
                        <div
                          class='content-form-item-column'
                          style={{ marginTop: '16px' }}
                        >
                          <div
                            class='form-item-label'
                            v-en-class='en-lang'
                          >
                            <span class='icon-monitor icon-hint'></span>
                            {executionTips[this.noticeExecutionActive]}
                          </div>
                          <div class='form-item-content pb12'>
                            <NoticeModeNew
                              noticeWay={this.noticeWayList}
                              notifyConfig={executionNotifyConfigChange(this.noticeExecutionData.notifyConfig)}
                              readonly={true}
                              type={1}
                            ></NoticeModeNew>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : undefined
              }
            </div>
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
