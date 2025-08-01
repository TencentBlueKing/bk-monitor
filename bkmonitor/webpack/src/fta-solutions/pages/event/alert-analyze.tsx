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

import { copyText } from 'monitor-common/utils/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';

import type { ActionAnlyzeField, AnlyzeField, ICommonItem, SearchType } from './typings/event';
import type { EmptyStatusOperationType } from 'monitor-pc/components/empty-status/types';
import type VueI18n from 'vue-i18n';
import type { TranslateResult } from 'vue-i18n';

import './alert-analyze.scss';

interface IAlertAnalyzeEvent {
  onAppendQuery: { queryString: string; type: 'add' | 'del' };
  onDetailFieldChange: string;
  onFieldChange: string[];
}
interface IAlertAnalyzeProps {
  analyzeData: any;
  analyzeFields: string[];
  analyzeTagList: ICommonItem[];
  bizIds: number[];
  detailField: string;
  detailFieldData: any;
  detailLoading: boolean;
  hasSearchParams?: boolean;
  loading: boolean;
  searchType?: SearchType;
  clearSearch?: (type: EmptyStatusOperationType) => void;
}
interface ITabPanelItem {
  id: tableType;
  name: string | TranslateResult;
}

type tableType = 'field' | 'tag';
@Component
export default class AlertAnalyze extends tsc<IAlertAnalyzeProps, IAlertAnalyzeEvent> {
  @Prop({ default: () => [], type: Array }) analyzeData: any;
  @Prop({ default: () => [], type: Array }) analyzeFields: any;
  @Prop({ default: () => [], type: Array }) analyzeTagList: ICommonItem[];
  @Prop({ default: '', type: String }) detailField: string;
  @Prop({ default: () => ({}), type: Object }) detailFieldData: any;
  @Prop({ default: false, type: Boolean }) loading: boolean;
  @Prop({ default: false, type: Boolean }) detailLoading: boolean;
  @Prop({ default: () => [] }) bizIds: number[];
  @Prop({ default: 'alert', type: String }) searchType: SearchType;
  @Prop({ default: false, type: Boolean }) hasSearchParams: boolean;
  @Prop({ default: () => {}, type: Function }) clearSearch: (type: EmptyStatusOperationType) => void;

  dialogShow = false;
  sideslideShow = false;
  activePanel: tableType = 'field';
  panelList: ITabPanelItem[] = [];
  mockFieldList: string[] = [];
  mockTagList: string[] = [];

  get alertFieldMap(): Record<AnlyzeField, VueI18n.TranslateResult> {
    return {
      alert_name: this.$t('告警名称'),
      metric: this.$t('指标ID'),
      duration: this.$t('持续时间'),
      ip: this.$t('目标IP'),
      ipv6: this.$t('目标IPv6'),
      bk_cloud_id: this.$t('管控区域ID'),
      strategy_id: this.$t('策略ID'),
      assignee: this.$t('通知人'),
      bk_service_instance_id: this.$t('服务实例ID'),
      plugin_id: this.$t('告警来源'),
    };
  }
  get actionFieldMap(): Record<ActionAnlyzeField, VueI18n.TranslateResult> {
    return {
      action_name: this.$t('套餐名称'),
      strategy_name: this.$t('策略名称'),
      operator: this.$t('负责人'),
      duration: this.$t('处理时长'),
      action_plugin_type: this.$t('套餐类型'),
      operate_target_string: this.$t('执行对象'),
    };
  }

  get curFieldMap() {
    return this.searchType === 'alert' ? this.alertFieldMap : this.actionFieldMap;
  }

  @Watch('searchType')
  handleSearchType(v) {
    if (v === 'action') {
      this.handleAlertTabChange('field');
    }
  }

  created() {
    this.panelList = [
      {
        id: 'field',
        name: this.$t('button-字段'),
      },
      {
        id: 'tag',
        name: this.$t('维度'),
      },
    ];
    this.mockFieldList = this.analyzeFields;
    this.mockTagList = this.analyzeFields;
  }

  /**
   * @description: 添加字段tab切换触发
   * @param {tableType} v tab类型
   * @return {*}
   */
  handleAlertTabChange(v: tableType) {
    this.activePanel = v;
  }

  /**
   * @description: 添加分析字段触发
   * @param {string} v 添加之后的字段
   * @return {*}
   */
  handleFieldChange(v: string[]) {
    this.mockFieldList = v;
  }
  @Emit('fieldChange')
  /**
   * @description: 保存添加后的字段
   * @param {*}
   * @return {*}
   */
  handleSaveFieldChange() {
    this.dialogShow = false;
    return this.searchType === 'alert'
      ? [
          ...this.mockFieldList.filter(id => this.alertFieldMap[id]),
          ...this.mockTagList.filter(id => !this.alertFieldMap[id]),
        ]
      : [...this.mockFieldList.filter(id => this.actionFieldMap[id])];
  }
  @Emit('fieldChange')
  /**
   * @description: 点击删除chart触发
   * @param {string} field
   * @return {*}
   */
  handleDeleteFieldAnalyze(field: string) {
    return this.analyzeFields.filter(id => id !== field);
  }

  handleTagChange(v: string[]) {
    this.mockTagList = v;
  }

  @Emit('detailFieldChange')
  /**
   * @description: 点击查看全部触发
   * @param {string} v
   * @return {*}
   */
  handleDetailFieldChange(v: string) {
    this.sideslideShow = true;
    return v;
  }

  @Emit('appendQuery')
  handleAddQueryString(item: any, chartItem: any, type: 'add' | 'del') {
    this.sideslideShow = false;
    const fieldName = ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale)
      ? this.curFieldMap?.[item.field] || item.field
      : item.field;

    return { type, queryString: `${fieldName} : ${chartItem.id}` };
    // if (item.field === 'duration') {
    //   return { type, queryString: `${fieldName} : ${chartItem.id}` };
    // }
    // return { type, queryString: `${fieldName} : "${chartItem.id}"` };
  }

  handleCopyNames(names: { name: string }[]) {
    const value = names.map(item => item.name).join('\n');
    copyText(value, msg => {
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

  /**
   * @description: 查看全部组件
   * @param {*}
   * @return {*}
   */
  detailSideslider() {
    return (
      <bk-sideslider
        width={420}
        is-show={this.sideslideShow}
        quick-close={true}
        quickClose
        {...{ on: { 'update:isShow': (v: boolean) => (this.sideslideShow = v) } }}
      >
        <div
          class='analyze-field-detail-slider-header'
          slot='header'
        >
          {`${
            this.curFieldMap[this.detailField] ||
            this.analyzeTagList.find(set => set.id === this.detailField)?.name ||
            this.detailField
          } ( ${this.detailFieldData?.bucket_count || 0} )`}
          {!!this.detailFieldData?.buckets?.length && (
            <span
              class='icon-monitor icon-mc-copy'
              v-bk-tooltips={{ placement: 'right', content: this.$t('批量复制') }}
              onClick={() => this.handleCopyNames(this.detailFieldData.buckets || [])}
            />
          )}
        </div>
        <div
          class='analyze-field-detail'
          slot='content'
          v-bkloading={{ isLoading: this.detailLoading }}
        >
          {this.chartItemComponent(this.detailFieldData)}
        </div>
      </bk-sideslider>
    );
  }
  /**
   * @description: 添加字段组件
   * @param {*}
   * @return {*}
   */
  fieldDialog() {
    return (
      <bk-dialog
        width={480}
        v-model={this.dialogShow}
        confirm-fn={this.handleSaveFieldChange}
        header-position='left'
        title={this.$t('添加字段')}
      >
        <div class='dialog-content'>
          {this.searchType === 'alert' && (
            <div class='bk-button-group'>
              {this.panelList.map(item => (
                <bk-button
                  key={item.id}
                  class={{ 'tab-btn': true, 'is-selected': this.activePanel === item.id }}
                  onClick={() => this.handleAlertTabChange(item.id)}
                >
                  {item.name}
                </bk-button>
              ))}
            </div>
          )}
          {this.activePanel === 'field' ? (
            <bk-checkbox-group
              key='filed'
              class='check-group'
              value={this.analyzeFields.slice()}
              on-change={this.handleFieldChange}
            >
              {Object.keys(this.curFieldMap).map(key => (
                <bk-checkbox
                  key={key}
                  class='check-group-item'
                  value={key}
                >
                  <span
                    class='check-group-item-name'
                    v-bk-overflow-tips
                  >
                    {this.curFieldMap[key]}
                  </span>
                </bk-checkbox>
              ))}
            </bk-checkbox-group>
          ) : (
            this.searchType === 'alert' && (
              <bk-checkbox-group
                key='tag'
                class='check-group'
                value={this.analyzeFields.slice()}
                on-change={this.handleTagChange}
              >
                {this.analyzeTagList.map(item => (
                  <bk-checkbox
                    key={item.id}
                    class='check-group-item'
                    value={item.id}
                  >
                    <span
                      class='check-group-item-name'
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </span>
                  </bk-checkbox>
                ))}
              </bk-checkbox-group>
            )
          )}
        </div>
      </bk-dialog>
    );
  }
  getBizeName(bizId) {
    return this.$store.getters.bizIdMap.get(+bizId)?.name || bizId;
  }
  /**
   * @description: 获取名称
   * @param {string} field
   * @param {any} item
   * @return {*}
   */
  getNameByFiled(field, item) {
    const renderUserName = item => <bk-user-display-name user-id={item.name} />;
    const fieldMap = {
      bk_cloud_id: this.getBizeName,
      // 多租户改造
      operator: renderUserName,
      assignee: renderUserName,
    };
    return fieldMap[field] ? fieldMap[field](item) : item.name;
  }
  /**
   * @description: 列表组件
   * @param {any} item
   * @return {*}
   */
  chartItemComponent(item: any, count = 10000) {
    return (
      <ul class='item-chart'>
        {item?.buckets?.length ? (
          item.buckets.slice(0, count).map((chart, index) => (
            <li
              key={index}
              class='chart-item'
            >
              <div class='chart-process'>
                <div class='process-title'>
                  <span
                    class='process-title-text'
                    title={chart.name}
                  >
                    {this.getNameByFiled(item.field, chart)}
                  </span>
                  <span class='title-percent'>
                    <span class='count'>{chart.count}</span>
                    <span>{(chart.percent * 100).toFixed(2)}%</span>
                  </span>
                </div>
                <bk-progress
                  key={index}
                  class='process-item'
                  color='#8DD3B5'
                  percent={chart.percent}
                  show-text={false}
                  strokeWidth={6}
                  theme='success'
                />
              </div>
              <i
                class='bk-icon icon-enlarge-line search-icon'
                onClick={() => this.handleAddQueryString(item, chart, 'add')}
              />
              <i
                class='bk-icon icon-narrow-line search-icon'
                onClick={() => this.handleAddQueryString(item, chart, 'del')}
              />
            </li>
          ))
        ) : (
          <EmptyStatus
            type={this.hasSearchParams ? 'search-empty' : 'empty'}
            onOperation={(type: EmptyStatusOperationType) => {
              this.clearSearch(type);
            }}
          />
        )}
      </ul>
    );
  }
  render() {
    return (
      <div
        class='analyze-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        <bk-button
          class='add-btn'
          icon='plus'
          theme='primary'
          onClick={() => (this.dialogShow = true)}
        >
          {this.$t('新增')}
        </bk-button>
        {this.analyzeData?.length ? (
          <ul class='alert-analyze'>
            {this.analyzeData.map(item =>
              this.curFieldMap?.[item.field] || item.buckets.length ? (
                <li
                  key={item.field}
                  class='alert-analyze-item'
                >
                  <div class='item-title'>
                    {/* <i class="icon-drag"/> */}
                    <span class='title-name'>
                      {item.field === 'bk_biz_id'
                        ? this.$t('项目空间')
                        : this.curFieldMap[item.field] || this.analyzeTagList.find(set => set.id === item.field)?.name}
                      {item.bucket_count ? ` ( ${item.bucket_count} )` : ''}
                      {!!item.buckets?.length && (
                        <span
                          class='icon-monitor icon-mc-copy'
                          v-bk-tooltips={{ placement: 'top', content: this.$t('批量复制') }}
                          onClick={() => this.handleCopyNames(item.buckets || [])}
                        />
                      )}
                    </span>
                    {item.bucket_count > 5 ? (
                      <bk-button
                        class='check-btn'
                        disabled={!item.bucket_count}
                        text
                        onClick={() => item.bucket_count && this.handleDetailFieldChange(item.field)}
                      >
                        {this.$t('查看全部')}
                      </bk-button>
                    ) : undefined}
                  </div>
                  {this.chartItemComponent(item, 5)}
                  <i
                    class='icon-monitor icon-mc-close-fill delete-icon'
                    onClick={() => this.handleDeleteFieldAnalyze(item.field)}
                  />
                </li>
              ) : undefined
            )}
          </ul>
        ) : (
          <EmptyStatus
            class='analyze-empty-warp'
            type={this.hasSearchParams ? 'search-empty' : 'empty'}
            onOperation={(type: EmptyStatusOperationType) => {
              this.clearSearch(type);
            }}
          />
        )}
        {this.fieldDialog()}
        {this.detailSideslider()}
      </div>
    );
  }
}
