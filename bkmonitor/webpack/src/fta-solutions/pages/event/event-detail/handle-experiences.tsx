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
import { Component, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { deleteExperience, getExperience, saveExperience } from '../../../../monitor-api/modules/alert';
import { getMetricListV2 } from '../../../../monitor-api/modules/strategies';
import { random, transformDataKey } from '../../../../monitor-common/utils/utils';
import DeleteSubtitle from '../../../../monitor-pc/pages/strategy-config/strategy-config-common/delete-subtitle';
import ConditionInput, {
  IConditionItem
} from '../../../../monitor-pc/pages/strategy-config/strategy-config-set-new/monitor-data/condition-input';
import Editor from '../../../../monitor-ui/markdown-editor/editor';
import TipMsg from '../../setting/components/tip-msg';

import Viewer from './custom-view';
import { IDetail } from './type';
import WhereDisplay from './where-display';

import './handle-experiences.scss';

enum EType {
  METRIC = 'metric',
  DIMENSION = 'dimension'
}

const bindList = [
  { id: EType.METRIC, name: window.i18n.tc('指标') },
  { id: EType.DIMENSION, name: window.i18n.tc('维度') }
];

interface IHandleExperienceProps {
  show?: boolean;
  detail?: IDetail;
}
interface IExperience {
  type: EType;
  conditions?: IConditionItem[];
  metric?: any[];
  description: string;
  create_user?: string;
  create_time?: string;
  update_user?: string;
  update_time?: string;
  is_match?: boolean; // 是否命中；只作为标识
  id?: string; // 仅用于删除
  alert_name?: string;
}

@Component({
  name: 'HandleExperience'
})
export default class HandleExperience extends tsc<IHandleExperienceProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  isLoading = false;
  // 当前绑定关系
  curBind: EType = EType.METRIC;
  // 条件数据
  conditionList: IConditionItem[] = [];
  // 是否为编辑模式
  mode: 'list' | 'edit' | 'add' = 'list';
  // 当前md文档内容
  curDescription = '';
  // 当前经验列表
  experienceList: IExperience[] = [];
  // 当前指标名
  curMetricName = '';
  // 当前指标标题
  curMetricTitle = window.i18n.tc('指标名');
  // 编辑/新增页时当前更新时间
  curUpdateInfo = '';
  // 获取变量值的参数
  metricMeta = null;
  // 维度列表
  dimensionList = [];
  // 内容校验
  errMsg = '';
  // 所有变量值(避免重复调用接口)
  allWhereValueMap = new Map();
  // 指标翻译
  metricNameMap = {};
  // 条件校验
  errConditions = '';
  selectKey = random(8);
  /* 默认填充维度维度 */
  defalutDimensionValue: { [propName: string]: string[] } = {};

  @Watch('show')
  async handleShow(v) {
    if (v) {
      if (this.experienceList.length) return;
      await this.init();
    }
  }
  /* 获取变量接口参数及维度列表 */
  /* 通过指标id获取维度交集 */
  async init() {
    this.isLoading = true;
    if (!Object.keys(this.defalutDimensionValue).length) {
      this.detail.dimensions.forEach(item => {
        this.defalutDimensionValue[item.key] = Array.isArray(item.value) ? item.value : [item.value];
      });
      const extraInfoDimension = this.detail.extra_info?.origin_alarm?.data?.dimensions || {};
      Object.keys(extraInfoDimension).forEach(key => {
        this.defalutDimensionValue[key] = Array.isArray(extraInfoDimension[key])
          ? extraInfoDimension[key]
          : [extraInfoDimension[key]];
      });
    }
    const [graphQueryConfig = {}] = this.detail.graph_panel?.targets?.[0]?.data?.query_configs || [];
    let dataSourceType = graphQueryConfig?.data_source_label || '';
    let dataTypeLabel = graphQueryConfig?.data_type_label || '';
    let metricField = '';
    let resultTableId = '';
    let metricIds = [];
    if (this.detail.extra_info?.strategy) {
      // 包含策略数据时直接取metric_id
      const [{ query_configs: queryConfigs }] = this.detail.extra_info.strategy.items;
      metricIds = queryConfigs.map(item => item.metric_id);
      metricField = queryConfigs[0].metric_field;
      resultTableId = queryConfigs[0].result_table_id;
      if (!dataSourceType) dataSourceType = queryConfigs[0].data_source_label;
      if (!dataTypeLabel) dataTypeLabel = queryConfigs[0].data_type_label;
    } else {
      metricIds = [`${dataSourceType || 'bk_fta'}.${dataTypeLabel || 'event'}.${this.detail.alert_name}`];
    }
    const { metric_list: metricList = [] } = await getMetricListV2({
      bk_biz_id: this.detail.bk_biz_id,
      page: 1,
      page_size: metricIds.length,
      conditions: [{ key: 'metric_id', value: metricIds }]
    }).catch(() => []);
    metricList.forEach(item => {
      if (!dataSourceType) dataSourceType = item.data_source_label;
      if (!dataTypeLabel) dataTypeLabel = item.data_type_label;
      this.metricNameMap[item.metric_id] = item.name;
    });
    if (!metricField)
      metricField = metricList[0]?.metric_field || graphQueryConfig?.metrics?.[0]?.field || this.detail.alert_name;
    if (!resultTableId)
      resultTableId = metricList[0]?.result_table_id || graphQueryConfig?.table || `${dataSourceType}.${dataTypeLabel}`;
    // 取维度交集
    let mixed = metricList[0]?.dimensions || [];
    metricList?.reduce((pre, cur) => {
      mixed = mixed.filter(n => cur.dimensions.map(dim => dim.id).indexOf(n.id) !== -1);
      return mixed;
    }, []);
    if (mixed.length) {
      this.dimensionList = mixed;
    } else {
      this.dimensionList =
        this.detail.dimensions?.map(item => ({
          id: item.key,
          name: item.display_key,
          is_dimension: true,
          type: 'string'
        })) || [];
    }
    this.metricMeta = {
      data_source_label: dataSourceType,
      data_type_label: dataTypeLabel,
      metric_field: metricField,
      result_table_id: resultTableId
    };
    this.experienceList = await getExperience({
      alert_id: this.detail.id
    }).catch(() => []);
    this.isLoading = false;
  }
  /* 点击添加按钮 */
  handleAdd() {
    const hasMetric = this.experienceList.some(item => item.type === EType.METRIC);
    this.curBind = hasMetric ? EType.DIMENSION : EType.METRIC;
    this.curDescription = '';
    if (hasMetric) {
      this.errConditions = '';
      this.conditionList = [];
      this.curUpdateInfo = '';
      this.dimensionDataChange();
    } else {
      this.metricDataChange();
    }
    this.mode = 'add';
    setTimeout(() => {
      this.errMsg = '';
    }, 50);
  }
  /* 切换绑定关系 */
  handleBindSelect(v: EType) {
    const changeInit = () => {
      this.errConditions = '';
      this.errMsg = '';
      if (v === EType.METRIC) {
        this.metricDataChange();
      } else if (v === EType.DIMENSION) {
        this.conditionList = [];
        this.curDescription = '';
        this.curUpdateInfo = '';
        this.dimensionDataChange();
      }
    };
    // 没有更改过切换后的内容则不弹窗
    const hasMetric = this.experienceList.some(item => item.type === EType.METRIC);
    const metricDescription = hasMetric
      ? this.experienceList.find(item => item.type === EType.METRIC)?.description || ''
      : '';
    const description = this.curBind === EType.DIMENSION ? '' : metricDescription;
    if (this.curDescription !== description && this.curDescription) {
      this.$bkInfo({
        type: 'warning',
        title: this.$t('切换将不保存当前内容'),
        maskClose: true,
        escClose: true,
        confirmFn: () => {
          this.curBind = v;
          changeInit();
        },
        cancelFn: () => {
          this.selectKey = random(8);
        }
      });
      return;
    }
    this.curBind = v;
    changeInit();
  }
  /* 切换至指标类型回填数据 */
  metricDataChange() {
    const hasMetric = this.experienceList.some(item => item.type === EType.METRIC);
    this.curMetricTitle = this.$tc('指标名');
    if (hasMetric) {
      const metricItem = this.experienceList.find(item => item.type === EType.METRIC);
      this.curDescription = metricItem.description;
      if (metricItem.metric.length) {
        this.curMetricName = metricItem.metric.map(id => this.metricNameMap[id] || id).join(',');
      } else {
        this.curMetricName = metricItem.alert_name;
        this.curMetricTitle = this.$tc('告警名称');
      }
      this.curUpdateInfo = this.getUpdataInfo(metricItem) as string;
    } else {
      const queryConfigs = this.detail.extra_info?.strategy.items[0].query_configs || [];
      if (queryConfigs.length) {
        this.curMetricName = queryConfigs.map(item => this.metricNameMap[item.metric_id] || item.metric_id);
      } else {
        this.curMetricName = this.detail.alert_name;
        this.curMetricTitle = this.$tc('告警名称');
      }
      this.curUpdateInfo = '';
    }
  }
  /* 切换至维度类型回填数据 */
  dimensionDataChange() {
    const index = this.experienceList.findIndex(
      item => this.conditionCompare(item.conditions, this.conditionList) && item.type === EType.DIMENSION
    );
    const confirm = () => {
      this.curDescription = this.experienceList[index].description;
      this.curUpdateInfo = this.getUpdataInfo(this.experienceList[index]) as string;
      this.errMsg = '';
    };
    if (index > -1) {
      this.$bkInfo({
        type: 'warning',
        title: window.i18n.tc('已命中一条已有维度，是否填入其经验'),
        maskClose: true,
        escClose: true,
        confirmFn: () => confirm()
      });
    }
  }
  /* 判断条件相等的规则 */
  conditionCompare(left: IConditionItem[], right: IConditionItem[]) {
    const leftCodition = JSON.parse(JSON.stringify(left));
    const rightCondition = JSON.parse(JSON.stringify(right));
    const leftStr = JSON.stringify(leftCodition.map(item => ({ ...item, value: item.value.sort() })));
    const rightStr = JSON.stringify(rightCondition.map(item => ({ ...item, value: item.value.sort() })));
    return leftStr === rightStr;
  }
  /* 取消 */
  handleCancel() {
    this.errConditions = '';
    this.errMsg = '';
    this.mode = 'list';
  }
  /* 编辑 */
  handleEdit(v: IExperience) {
    this.curBind = v.type;
    this.curDescription = v.description;
    this.curUpdateInfo = this.getUpdataInfo(v) as string;
    if (v.type === EType.METRIC) {
      this.curMetricName = v.metric.map(id => this.metricNameMap[id] || id).join(',') || v.alert_name;
      if (v.metric.length) {
        this.curMetricTitle = this.$tc('指标名');
      } else {
        this.curMetricTitle = this.$tc('告警名称');
      }
    } else if (v.type === EType.DIMENSION) {
      this.conditionList = JSON.parse(JSON.stringify(v.conditions));
    }
    this.mode = 'edit';
  }
  /* 删除 */
  handleDelete(v: IExperience, index: number) {
    const titleMap = {
      [EType.METRIC]: v.metric.length ? this.$tc('指标') : this.$tc('告警名称'),
      [EType.DIMENSION]: this.$tc('维度')
    };
    const h = this.$createElement;
    this.$bkInfo({
      type: 'warning',
      title: this.$t('确认删除该经验？'),
      subHeader: h(DeleteSubtitle, { props: { title: titleMap[v.type] } }, [
        h('div', { slot: 'name' }, [
          v.type === EType.METRIC
            ? v.metric?.map(id => this.metricNameMap[id] || id)?.join(',') || v.alert_name
            : h(WhereDisplay, {
                props: {
                  value: v.conditions,
                  groupByList: this.dimensionList,
                  metric: this.metricMeta
                }
              })
        ])
      ]),
      maskClose: true,
      escClose: true,
      confirmFn: () => {
        deleteExperience({ id: v.id })
          .then((res: boolean) => {
            if (res !== false) {
              this.experienceList.splice(index, 1);
              this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
            }
          })
          .catch(() => false);
      }
    });
  }

  /* 保存 */
  async handleSave() {
    if (
      !(!!this.conditionList.length && !!this.conditionList[0]?.key && !!this.conditionList[0]?.value?.length) &&
      this.curBind === EType.DIMENSION
    ) {
      this.errConditions = this.$tc('注意: 必填字段不能为空');
      return;
    }
    if (!this.curDescription) {
      this.handleInputContent('');
      return;
    }
    this.isLoading = true;
    const params = {
      alert_id: this.detail.id,
      description: this.curDescription,
      type: this.curBind,
      conditions: this.curBind === EType.METRIC ? undefined : JSON.parse(JSON.stringify(this.conditionList))
    };
    const item = await saveExperience(params).catch(() => false);
    if (!item) return;
    const hasMetric = this.experienceList.findIndex(item => item.type === EType.METRIC) > -1;
    const index = this.experienceList.findIndex(item =>
      this.curBind === EType.METRIC
        ? item.type === EType.METRIC
        : this.conditionCompare(item.conditions, this.conditionList) && item.type === EType.DIMENSION
    );
    if (index > -1) {
      this.experienceList.splice(index, 1);
    }
    if (item.type === EType.METRIC || !hasMetric) {
      this.experienceList.unshift(item);
    } else {
      this.experienceList.splice(1, 0, item);
    }
    this.init();
    this.mode = 'list';
    this.isLoading = false;
  }

  /* 条件变更 */
  handleCondition(v: IConditionItem[]) {
    this.errConditions = !!v.length && !!v[0]?.key ? '' : this.$tc('注意: 必填字段不能为空');
    this.conditionList = v;
    this.dimensionDataChange();
  }
  /* 输入md文档 */
  handleInputContent(v: string) {
    this.errMsg = !!v ? '' : this.$tc('注意: 必填字段不能为空');
    this.curDescription = v;
  }

  getUpdataInfo(item: IExperience) {
    if (item.update_user) {
      return this.$t('{0} 于 {1} 更新', [item.update_user, dayjs.tz(item.update_time).format('YYYY-MM-DD HH:mm:ss')]);
    }
    return this.$t('{0} 于 {1} 创建', [item.create_user, dayjs.tz(item.create_time).format('YYYY-MM-DD HH:mm:ss')]);
  }

  render() {
    return (
      <div
        v-bkloading={{ isLoading: this.isLoading }}
        class={['event-detail-handleexperiences', { displaynone: !this.show }]}
      >
        <TipMsg msg={this.$tc('处理经验可以与指标和维度进行绑定，可以追加多种处理经验方便经验的共享。')}></TipMsg>
        {/* 添加按钮 */}
        {!this.readonly && this.mode === 'list' && (
          <div
            class='big-add-btn'
            onClick={this.handleAdd}
          >
            <div class='center-text'>
              <span class='icon-monitor icon-mc-add'></span>
              <span class='text'>{this.$t('新增处理建议')}</span>
            </div>
          </div>
        )}
        {/* 空样式 */}
        {!this.experienceList.length && this.mode === 'list' && (
          <div>
            <bk-exception
              type='empty'
              class='empty-bg'
            >
              <span>{this.$t('当前暂无处理经验')}</span>
            </bk-exception>
          </div>
        )}
        {/* 经验列表 */}
        {this.mode === 'list' && (
          <div class='experience-list'>
            {this.experienceList.map((item, index) => (
              <div
                class='experience-item'
                key={index}
              >
                <div class='item-header'>
                  {item.type === EType.METRIC && (
                    <div class='metric-title'>
                      <div class='bookmarks'></div>
                      {item.metric.length
                        ? `${this.$t('指标')} - ${item.metric.map(id => this.metricNameMap[id] || id).join(',')}`
                        : `${this.$t('告警名称')} - ${item.alert_name}`}
                    </div>
                  )}
                  {item.type === EType.DIMENSION && (
                    <div class='dimsion-title'>
                      <span>{`${this.$t('维度')} -`}</span>
                      {Boolean(this.metricMeta) && (
                        <WhereDisplay
                          class='condition-readonly'
                          value={item.conditions as any}
                          groupByList={this.dimensionList}
                          metric={this.metricMeta as any}
                          allWhereValueMap={this.allWhereValueMap}
                          onValueMapChange={v => (this.allWhereValueMap = v)}
                        ></WhereDisplay>
                      )}
                    </div>
                  )}
                  {item.is_match && item.type === EType.DIMENSION && <div class='status'>{this.$t('已命中')}</div>}
                  <div class='update-time'>{this.getUpdataInfo(item)}</div>
                  <div class='operate-options'>
                    <span
                      class='icon-monitor icon-bianji'
                      onClick={() => this.handleEdit(item)}
                    ></span>
                    <span
                      class='icon-monitor icon-mc-delete-line'
                      onClick={() => this.handleDelete(item, index)}
                    ></span>
                  </div>
                </div>
                <div class='item-content'>
                  {item.description ? (
                    <Viewer
                      value={item.description}
                      key={item.description.length}
                    ></Viewer>
                  ) : undefined}
                </div>
              </div>
            ))}
          </div>
        )}
        {/* 编辑/新建内容 */}
        {this.mode !== 'list' && (
          <div class='edit-content'>
            <div class='content-header'>
              <div class='bind-relation'>
                <div class='title'>{this.$t('绑定关系')}</div>
                <div class='red'>*</div>
                <div
                  v-bk-tooltips={{
                    content: this.mode === 'edit' && this.$t('编辑模式不能切换'),
                    placements: ['top'],
                    boundary: 'window',
                    disabled: this.mode !== 'edit',
                    allowHTML: false
                  }}
                >
                  <bk-select
                    class='bind-select'
                    value={this.curBind}
                    clearable={false}
                    readonly={this.mode === 'edit'}
                    key={this.selectKey}
                    onSelected={this.handleBindSelect}
                  >
                    {bindList.map(item => (
                      <bk-option
                        key={item.id}
                        name={item.name}
                        id={item.id}
                      ></bk-option>
                    ))}
                  </bk-select>
                </div>
              </div>
              <div class='bind-condition'>
                {this.curBind === EType.METRIC && (
                  <span class='metric-name'>{`${this.curMetricTitle}：${this.curMetricName}`}</span>
                )}
                {this.curBind === EType.DIMENSION &&
                  (this.mode === 'edit' ? (
                    <WhereDisplay
                      class='condition-readonly'
                      value={this.conditionList as any}
                      groupByList={this.dimensionList}
                      metric={this.metricMeta as any}
                    ></WhereDisplay>
                  ) : (
                    <ConditionInput
                      metricMeta={transformDataKey(this.metricMeta)}
                      dimensionsList={this.dimensionList}
                      conditionList={this.conditionList}
                      defaultValue={this.defalutDimensionValue}
                      on-change={this.handleCondition}
                    ></ConditionInput>
                  ))}
                {!!this.errConditions && this.mode === 'add' ? (
                  <div class='err-red'>{this.errConditions}</div>
                ) : undefined}
              </div>
              <div class='updata-time'>{this.curUpdateInfo}</div>
            </div>
            <div class='content-md'>
              <Editor
                value={this.curDescription}
                on-input={(v: string) => this.handleInputContent(v)}
              ></Editor>
              {this.errMsg ? <div class='err-red'>{this.errMsg}</div> : undefined}
            </div>
            <div class='content-bottom'>
              <bk-button
                theme='primary'
                class='save'
                onClick={this.handleSave}
              >
                {this.$t('保存')}
              </bk-button>
              <bk-button
                class='cancel'
                onClick={this.handleCancel}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        )}
      </div>
    );
  }
}
