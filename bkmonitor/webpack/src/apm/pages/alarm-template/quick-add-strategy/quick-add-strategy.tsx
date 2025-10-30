/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Component, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';
import { applyStrategyTemplate, listUserGroup, searchStrategyTemplate } from 'monitor-api/modules/model';
import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';
import authorityMixinCreate from 'monitor-pc/mixins/authorityMixin';
import { MANAGE_AUTH as MANAGE } from 'monitor-pc/pages/alarm-group/authority-map';

import TemplateForm from '../components/template-form/template-form';
import { getCheckStrategyTemplate, getTemplatePreview } from '../service';
import JudgmentConditions from './judgment-conditions';
import TemplateList from './template-list';

import type {
  AlgorithmItem,
  DetectConfig,
  EditTemplateFormData,
  TemplateDetail,
  UserGroupItem,
} from '../components/template-form/typing';
import type { IAlarmGroupList, ITempLateItem } from './typing';
import type { VariableModelType } from 'monitor-pc/pages/query-template/variables';

import './quick-add-strategy.scss';

interface IProps {
  params?: Record<string, any>;
  show?: boolean;
  onShowChange?: (v: boolean) => void;
}

@Component
class QuickAddStrategy extends Mixins(
  authorityMixinCreate({
    ALARM_GROUP_MANAGE_AUTH: MANAGE,
  })
) {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) params: Record<string, any>;
  @Ref('templateForm') templateFormRef: TemplateForm;

  loading = false;
  templateList: ITempLateItem[] = [];
  alarmGroupList: IAlarmGroupList[] = [];
  alarmGroupLoading = false;
  cursorId: number = null;
  cursorItem: ITempLateItem = null;
  /** 模板详情数据 */
  templateDetail: Record<number, TemplateDetail> = {};
  /** 模板详情表单值 */
  templateFormData: Record<number, EditTemplateFormData> = {};
  /** 记录哪些模板修改了哪些值 */
  editTemplateFormData: Record<number, Partial<EditTemplateFormData & { context: Record<string, any> }>> = {};
  /** 模板变量列表 */
  variablesList: Record<number, VariableModelType[]> = {};
  /** 模板详情loading */
  templateDetailLoading = false;
  /** 函数列表 */
  metricFunctions = [];

  checkedList = [];

  globalParams = null;

  templateListLoading = false;

  @Watch('show')
  handleWatchShowChange(v: boolean) {
    if (v) {
      this.getAlarmGroupList();
      this.getFunctions();
      this.getTemplateList();
    } else {
      this.templateDetail = {};
      this.templateFormData = {};
      this.editTemplateFormData = {};
      this.variablesList = {};
      this.templateList = [];
      this.checkedList = [];
      this.cursorId = null;
      this.cursorItem = null;
    }
  }

  handleShowTemplateDetails() {
    // todo
    const { app_name: appName } = this.params;
    const { from, to } = this.$route.query;
    let urlStr = `${window.__BK_WEWEB_DATA__?.baseroute || ''}application/?filter-app_name=${appName}&dashboardId=alarm_template&strategy_template_details_id=${this.cursorId}`;
    urlStr += `&from=${from || DEFAULT_TIME_RANGE[0]}&to=${to || DEFAULT_TIME_RANGE[1]}`;
    const { href } = this.$router.resolve({
      path: urlStr,
    });
    const url = location.href.replace(location.pathname, '/').replace(location.hash, '') + href;
    window.open(url);
  }

  handleShowChange(v: boolean) {
    this.$emit('showChange', v);
  }

  getAlarmGroupList() {
    if (this.alarmGroupList.length) {
      return;
    }
    this.alarmGroupLoading = true;
    return listUserGroup({ exclude_detail_info: 1 })
      .then(data => {
        this.alarmGroupList = data.map(item => ({
          id: item.id,
          name: item.name,
          needDuty: item.need_duty,
          receiver:
            item?.users?.map(rec => rec.display_name).filter((item, index, arr) => arr.indexOf(item) === index) || [],
        }));
      })
      .finally(() => {
        this.alarmGroupLoading = false;
      });
  }

  getFunctions() {
    if (this.metricFunctions.length) {
      return;
    }
    getFunctions().then(data => {
      this.metricFunctions = data;
    });
  }

  /**
   * 处理光标选择变化
   * 根据传入的模板ID更新当前选中的模板项
   * @param {number} id - 选中的模板ID
   */
  handleCursorChange(id: number) {
    this.cursorId = id;
    this.cursorItem = this.templateList.find(item => item.id === id);
    this.getTemplatePreview(id);
  }

  async getTemplatePreview(id: number) {
    if (!this.templateFormData[id]) {
      this.templateDetailLoading = true;
      const data = await getTemplatePreview({
        strategy_template_id: id,
        app_name: this.params?.app_name,
        service_name: this.params?.service_name,
      });
      if (data.isCancel) return;
      this.templateDetailLoading = false;
      if (data.success) {
        /** 不需要响应式 */
        this.templateDetail[id] = JSON.parse(JSON.stringify(data.detailData));
        this.editTemplateFormData[id] = {};
        this.$set(this.templateFormData, id, {
          name: data.detailData.name,
          algorithms: data.detailData.algorithms,
          detect: data.detailData.detect,
          is_auto_apply: data.detailData.is_auto_apply,
          query_template: data.detailData.query_template,
          system: data.detailData.system,
          user_group_list: data.detailData.user_group_list,
        });
        this.$set(this.variablesList, id, data.variablesList);
      }
    }
  }

  handleCheckedChange(checked) {
    this.checkedList = checked;
  }

  /** 检测规则修改 */
  handleAlgorithmsChange(val: AlgorithmItem[]) {
    const currentTemplateData = this.templateFormData[this.cursorId];
    const detailData = this.templateDetail[this.cursorId];
    currentTemplateData.algorithms = val;
    /** 判断当前编辑的检测规则是否和详情的检测规则一致 */
    if (
      val.length === detailData.algorithms.length &&
      val.every(item => {
        const detail = detailData.algorithms.find(detail => detail.level === item.level);
        return detail && JSON.stringify(item.config) === JSON.stringify(detail.config);
      })
    ) {
      delete this.editTemplateFormData[this.cursorId].algorithms;
    } else {
      this.editTemplateFormData[this.cursorId].algorithms = val;
    }
  }

  /** 判断条件修改 */
  handleDetectChange(val: DetectConfig) {
    const currentTemplateData = this.templateFormData[this.cursorId];
    const detailData = this.templateDetail[this.cursorId];
    currentTemplateData.detect = val;
    if (
      val.type === detailData.detect.type &&
      Object.keys(val.config).every(key => val.config[key] === detailData.detect.config[key])
    ) {
      delete this.editTemplateFormData[this.cursorId].detect;
    } else {
      this.editTemplateFormData[this.cursorId].detect = val;
    }
  }

  /** 修改告警组  */
  handleAlarmGroupChange(val: UserGroupItem[]) {
    const currentTemplateData = this.templateFormData[this.cursorId];
    const detailData = this.templateDetail[this.cursorId];
    currentTemplateData.user_group_list = val;
    if (
      val.every(item => detailData.user_group_list.find(detail => detail.id === item.id)) &&
      val.length === detailData.user_group_list.length
    ) {
      delete this.editTemplateFormData[this.cursorId].user_group_list;
    } else {
      this.editTemplateFormData[this.cursorId].user_group_list = val;
    }
  }

  /** 修改变量 */
  handleVariableValueChange(value: any, index: number) {
    const currentVariable: VariableModelType = this.variablesList[this.cursorId][index];
    const detailData = this.templateDetail[this.cursorId];
    currentVariable.value = value;
    if (JSON.stringify(value) === JSON.stringify(detailData.context[currentVariable.variableName])) {
      delete this.editTemplateFormData[this.cursorId].context?.[currentVariable.variableName];
    } else {
      this.editTemplateFormData[this.cursorId].context = {
        ...(this.editTemplateFormData[this.cursorId].context || {}),
        [currentVariable.variableName]: value,
      };
    }
  }

  /**
   * 应用策略模板
   * 异步方法，用于批量应用选中的策略模板
   * 构建请求参数并调用后端接口，处理成功和失败情况
   * @returns {Promise<boolean>} 返回Promise，true表示应用成功，false表示失败
   */
  async applyStrategyTemplate() {
    const params = {
      app_name: this.params?.app_name,
      service_names: [this.params?.service_name],
      strategy_template_ids: this.checkedList,
      extra_configs: Object.keys(this.editTemplateFormData).reduce((pre, cur) => {
        if (Object.keys(this.editTemplateFormData[cur]).length > 0) {
          pre.push({
            ...this.editTemplateFormData[cur],
            strategy_template_id: cur,
            service_name: this.params?.service_name,
          });
        }
        return pre;
      }, []),
      global_config: this.globalParams || undefined,
      is_reuse_instance_config: true,
    };
    const res = await applyStrategyTemplate(params)
      .then(() => {
        return true;
      })
      .catch(() => {
        return false;
      });
    if (res) {
      this.$bkMessage({
        message: this.$t('生成成功'),
        theme: 'success',
      });
      return true;
    }
    return false;
  }

  /**
   * 处理表单提交
   * 异步方法，用于处理一键生成策略的提交操作
   * 1. 首先调用应用策略模板方法
   * 2. 检查是否有已应用的模板需要警告用户
   * 3. 显示成功信息弹窗，提供用户操作选项
   * @returns {Promise<void>} 无返回值
   */
  async handleSubmit() {
    const valid = await this.templateFormRef.formRef?.validate?.().catch(() => false);
    if (!valid) return;

    const h = this.$createElement;
    this.loading = true;
    const isSuccess = await this.applyStrategyTemplate();
    this.loading = false;
    if (!isSuccess) {
      return;
    }

    const hasBeenApplied = this.checkedList.some(id => {
      const templateItem = this.templateList.find(item => item.id === id);
      return !!templateItem?.has_been_applied;
    });

    this.$bkInfo({
      type: 'success',
      title: this.$t('批量创建策略成功'),
      okText: this.$t('留在当前页'),
      width: 480,
      closeFn: () => {
        return true;
      },
      cancelFn: () => {
        const filtersStr = JSON.stringify([
          {
            key: 'label_name',
            value: [`/APM-APP(${this.params?.app_name})/`],
          },
        ]);
        window.open(
          location.href.replace(location.hash, `#/strategy-config?page=1&pageSize=100&filters=${filtersStr}`)
        );
        return true;
      },
      subHeader: hasBeenApplied
        ? h(
            'div',
            {
              style: {
                height: '46px',
                background: '#F5F7FA',
                display: 'flex',
                alignItems: 'center',
                color: '#4D4F56',
                justifyContent: 'center',
              },
            },
            this.$t('已配置策略重新下发会被覆盖') as string
          )
        : undefined,
      cancelText: this.$t('前往策略列表'),
    });
  }

  /**
   * 获取模板列表
   * 异步方法，用于查询并加载策略模板列表
   * 1. 设置加载状态为 true
   * 2. 调用接口搜索策略模板
   * 3. 检查模板应用状态并更新列表
   * 4. 如果有模板，默认选中第一个
   * 5. 设置加载状态为 false
   * @returns {Promise<void>} 无返回值
   */
  async getTemplateList() {
    this.templateListLoading = true;
    const data = await searchStrategyTemplate({
      app_name: this.params?.app_name,
      conditions: [
        {
          key: 'is_enabled',
          value: [true],
        },
      ],
      simple: true,
    }).catch(() => ({ list: [] }));
    const templateList = await this.checkTemplateList(
      (data?.list || []).map(item => {
        const system = item.system;
        const category = item.category;
        const obj: Partial<ITempLateItem> = {};
        if (typeof system === 'object') {
          obj.system = system.value || '';
          obj.system_alias = system.alias || '';
        }
        if (typeof category === 'object') {
          obj.category = category.value || '';
          obj.category_alias = category.alias || '';
        }
        return {
          ...item,
          ...obj,
        };
      })
    );
    // 检查是否有system为'RPC'的项，如果有则移动到首位
    const rpcIndex = templateList.findIndex(item => item.system === 'RPC');
    if (rpcIndex > 0) {
      const rpcItem = templateList.splice(rpcIndex, 1)[0];
      templateList.unshift(rpcItem);
    }
    this.templateList = templateList;
    if (this.templateList.length) {
      // strategy_template_codes 包含 code 时，默认选中这一个 优先选中 type=builtin
      let id = null;
      const checkIds = new Set();
      let needCheck = true;
      for (const temp of this.templateList) {
        if (temp?.type === 'builtin' && this.params?.strategy_template_codes?.includes(temp?.code)) {
          if (!id) {
            id = temp.id;
          }
          checkIds.add(temp.id);
        }
      }
      if (!id) {
        for (const temp of this.templateList) {
          if (this.params?.strategy_template_codes?.includes(temp?.code)) {
            if (!id) {
              id = temp.id;
            }
            checkIds.add(temp.id);
          }
        }
        if (!id) {
          id = this.templateList[0].id;
          needCheck = false;
        }
      }
      this.handleCursorChange(id);
      if (needCheck) {
        this.handleCheckedChange(Array.from(checkIds));
      }
    }
    this.templateListLoading = false;
  }

  /**
   * 检查模板列表中的应用状态
   * 异步方法，用于批量检查策略模板是否已被应用
   * 1. 调用接口查询模板的应用状态
   * 2. 将查询结果映射到模板列表中
   * 3. 更新模板的 has_been_applied 和 strategy 属性
   * @param {ITempLateItem[]} list - 需要检查的模板列表
   * @returns {Promise<ITempLateItem[]>} 返回更新后的模板列表
   */
  async checkTemplateList(list: ITempLateItem[]) {
    const data = await getCheckStrategyTemplate({
      strategy_template_ids: list.map(item => item.id),
      app_name: this.params?.app_name,
      service_names: [this.params?.service_name],
    }).catch(() => ({ list: [] }));
    const temp = new Map();
    for (const item of data?.list || []) {
      temp.set(item.strategy_template_id, item);
    }
    for (const item of list) {
      const checkItem = temp.get(item.id);
      if (checkItem) {
        item.has_been_applied = !!checkItem?.has_been_applied;
        item.strategy = checkItem?.strategy;
      }
    }
    return list;
  }

  handleJudgmentConditionsChange(params) {
    this.globalParams = params;
  }

  handleGoStrategy(id) {
    if (id) {
      window.open(location.href.replace(location.hash, `#/strategy-config/detail/${id}`));
    }
  }

  render() {
    return (
      <bk-sideslider
        width={1200}
        ext-cls={'quick-add-strategy-side-component'}
        before-close={() => {
          this.handleShowChange(false);
        }}
        isShow={this.show}
        zIndex={977}
        quick-close
      >
        <div slot='header'>{this.$t('一键添加策略')}</div>
        <div
          class='quick-add-strategy-content'
          slot='content'
        >
          <div class='template-list'>
            {this.templateListLoading ? (
              <div class='template-list-loading'>
                {new Array(10).fill(0).map((_, index) => (
                  <div
                    key={index}
                    class='template-list-loading-item skeleton-element'
                  />
                ))}
              </div>
            ) : (
              <TemplateList
                checked={this.checkedList}
                cursorId={this.cursorId}
                templateList={this.templateList}
                onCheckedChange={this.handleCheckedChange}
                onCursorChange={this.handleCursorChange}
                onGoStrategy={this.handleGoStrategy}
              />
            )}
            <JudgmentConditions
              userList={this.alarmGroupList}
              onChange={this.handleJudgmentConditionsChange}
            />
          </div>

          <div class='template-preview'>
            {!!this.cursorId && [
              <div
                key='template-preview-header'
                class='template-preview-header'
              >
                <span class='header-title'>{this.$t('预览')}</span>
                <span class='split-line' />
                <span
                  class='header-desc'
                  v-bk-overflow-tips
                >
                  {this.cursorItem?.name || '--'}
                </span>
                <span
                  class='header-right-link'
                  onClick={this.handleShowTemplateDetails}
                >
                  <span>{this.$t('模板详情')}</span>
                  <span class='icon-monitor icon-fenxiang' />
                </span>
              </div>,
              <div
                key='template-preview-content'
                class='template-preview-content'
              >
                <TemplateForm
                  ref='templateForm'
                  data={this.templateFormData[this.cursorId]}
                  labelWidth={120}
                  loading={this.templateDetailLoading}
                  metricFunctions={this.metricFunctions}
                  scene='view'
                  variablesList={this.variablesList[this.cursorId]}
                  onAlarmGroupChange={this.handleAlarmGroupChange}
                  onAlgorithmsChange={this.handleAlgorithmsChange}
                  onDetectChange={this.handleDetectChange}
                  onVariableValueChange={this.handleVariableValueChange}
                />
              </div>,
            ]}
          </div>
        </div>
        <div
          class='quick-add-strategy-footer'
          slot='footer'
        >
          <bk-button
            class='mr-8 ml-24'
            disabled={!this.checkedList.length}
            loading={this.loading}
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.$t('一键生成')}
          </bk-button>
          <bk-button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
        </div>
      </bk-sideslider>
    );
  }
}

export default ofType<IProps>().convert(QuickAddStrategy);
