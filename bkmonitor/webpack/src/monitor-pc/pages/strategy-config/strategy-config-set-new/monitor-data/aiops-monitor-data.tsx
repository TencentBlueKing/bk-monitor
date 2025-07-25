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
import { Component, Emit, Mixins, Prop, Ref } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { multivariateAnomalyScenes } from 'monitor-api/modules/strategies';
import { listIntelligentModels } from 'monitor-api/modules/strategies';
import { random, transformDataKey } from 'monitor-common/utils/utils';

import { LETTERS } from '../../../../common/constant';
import { transformValueToMonitor } from '../../../../components/monitor-ip-selector/utils';
import metricTipsContentMixin from '../../../../mixins/metricTipsContentMixin';
import { handleSetTargetDesc as getTargetDesc } from '../../common';
import StrategyTargetTable from '../../strategy-config-detail/strategy-config-detail-table.vue';
import StrategyIpv6 from '../../strategy-ipv6/strategy-ipv6';
import { type IScenarioItem, type ISceneConfig, MetricDetail, MetricType } from '../typings';
import AiopsMonitorMetricSelect from './aiops-monitor-metric-select';

import type { IIpV6Value, INodeType, TargetObjectType } from '../../../../components/monitor-ip-selector/typing';

import './aiops-monitor-data.scss';

interface IProps {
  defaultCheckedTarget?: any;
  defaultScenario?: string;
  isEdit?: boolean;
  metricData?: NewMetricDetail[];
  readonly?: boolean;
  scenarioList?: IScenarioItem[];
  onChange?: (sceneConfig: ISceneConfig) => void;
  onMetricChange?: (value) => void;
  onModelChange?: (value) => void;
  onTargetChange?: (value) => void;
  onTargetTypeChange?: (type: string) => void;
}
interface NewMetricDetail extends MetricDetail {
  sceneConfig: ISceneConfig;
}
@Component({
  components: {
    StrategyTargetTable,
  },
})
class AiopsMonitorData extends Mixins(metricTipsContentMixin) {
  /* 指标数据 */
  @Prop({ default: () => [], type: Array }) metricData: NewMetricDetail[];
  @Prop({ default: () => ({ target_detail: [] }), type: Object }) defaultCheckedTarget: any;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({ type: Boolean, default: false }) isEdit: boolean;
  @Prop({ type: Array, default: () => [] }) scenarioList: IScenarioItem[];
  /* 默认选择的监控对象 */
  @Prop({ type: String, default: '' }) defaultScenario: string;
  @Ref('targetContainer') targetContainerRef: HTMLDivElement;
  @Ref('createForm') createForm: any;
  @Ref('tagListRef') tagListRef: HTMLDivElement;
  /** 表单数据 */
  formModel = {
    level: [],
    scene: '',
    sensitivity: 5,
  };
  target: any = {
    targetType: '',
    desc: {
      message: '',
      subMessage: '',
    },
  };
  /** 表单规则 */
  formRules = {
    scene: [
      {
        required: true,
        message: this.$t('必填项'),
        trigger: 'blur',
      },
    ],
    metrics: [
      {
        validator: this.validateMetrics,
        message: this.$t('至少选择2个指标'),
        trigger: 'change',
      },
    ],
    level: [
      {
        validator(val) {
          return val.length > 0;
        },
        message: this.$t('必填项'),
        trigger: 'blur',
      },
    ],
  };
  // 展开/收起
  tagOpen = false;
  // 是否展示 展开/收起 按钮
  showTagOpen = false;

  /** 场景列表 */
  scenes = [];
  /* 当前场景 */
  scene = null;
  /* 当前场景指标 */
  metrics = [];
  allMetrics = [];
  /** 场景加载 */
  isLoading = false;
  targetContainerHeight = 0;
  showTopoSelector = false;
  ipSelectKey = random(10);
  targetList: any = [];
  /** 告警级别 */
  levelList = [
    { id: 1, name: this.$t('致命'), icon: 'icon-danger' },
    { id: 2, name: this.$t('预警'), icon: 'icon-mind-fill' },
    { id: 3, name: this.$t('提醒'), icon: 'icon-tips' },
  ];

  metricpopoerInstance = null;

  get readonlyMetrics() {
    return this.scene?.metrics?.filter(item => this.metrics.includes(item.metric_id)) || [];
  }
  get targetDesc() {
    return this.handleSetTargetDesc(this.targetList, this.metricData?.[0]?.targetType);
  }
  @Emit('change')
  handleChange(value?) {
    if (value) {
      return value;
    }
    const metricsSet = new Set(this.metrics);
    const metrics = [];
    this.scene?.metrics?.forEach(item => {
      if (metricsSet.has(item.metric_id)) {
        metrics.push({
          ...item,
          metric: undefined,
        });
      }
    });
    const algorithm = {
      // type: MetricType.MultivariateAnomalyDetection,
      type: MetricType.HostAnomalyDetection,
      config: {
        scene_id: this.formModel.scene,
        metrics,
        sensitivity: this.formModel.sensitivity,
        levels: this.formModel.level,
      },
      level: this.formModel.level[0],
      unit_prefix: '',
    };
    return {
      ...this.scene,
      metrics,
      query_configs: this.scene?.query_config ? [{ ...this.scene.query_config }] : [],
      algorithms: [algorithm],
    };
  }
  @Emit('targetChange')
  handleTargetSave() {
    this.showTopoSelector = false;
    this.handleTargetTypeChange(this.target.targetType);
    return this.targetList;
  }
  @Emit('targetTypeChange')
  handleTargetTypeChange(type: string) {
    return type;
  }
  @Emit('metricChange')
  handleMetricEmitChange() {
    const metrics = [];
    const metricsSet = new Set(this.metrics);
    this.allMetrics.forEach(item => {
      if (metricsSet.has(item.metric_id)) {
        item.alias = LETTERS[metrics.length];
        metrics.push(item);
      }
    });
    return metrics;
  }

  created() {
    this.getSchemeList();
    this.multivariateAnomalyScenes();
    this.targetList = this.defaultCheckedTarget?.target_detail || [];
    // 初始化时监控目标显示
    this.handleSetTargetDesc(
      this.targetList,
      this.metricData?.[0]?.targetType,
      this.defaultCheckedTarget?.node_count || 0,
      this.defaultCheckedTarget?.instance_count || 0
    );
  }

  destroyed() {
    this.handleModelChange([]);
  }

  async getSchemeList() {
    const list = await listIntelligentModels({
      algorithm: MetricType.HostAnomalyDetection,
    });
    const modelList = list.map(item => ({
      name: item.name,
      instruction: item.instruction,
      document: item.document,
    }));
    this.handleModelChange(modelList);
  }

  @Emit('modelChange')
  handleModelChange(value) {
    return value;
  }

  handleAddTarget() {
    this.showTopoSelector = true;
    this.ipSelectKey = random(10);
    this.$nextTick(() => {
      this.targetContainerHeight = this.targetContainerRef?.clientHeight;
    });
  }
  /** 告警变化 */
  handleLevelChange(value) {
    this.formModel.level = value;
    if (this.scene) {
      this.handleChange();
    }
  }
  /** 场景切换 */
  handleScenSelected(value, isInitMetrics = true) {
    this.formModel.scene = value;
    this.scene = this.scenes.find(item => item.scene_id === this.formModel.scene);
    this.allMetrics =
      this.scene?.metrics?.map(
        item =>
          new MetricDetail({
            ...item.metric,
            ...item,
            metric: undefined,
          })
      ) || [];
    if (isInitMetrics) {
      this.metrics = this.scene?.metrics?.map(item => item.metric_id) || [];
    }
    this.$nextTick(() => {
      this.handleCalcShowOpenTag();
    });
    this.handleChange();
    this.handleMetricEmitChange();
  }
  /** 计算指标是否存在多行情况 */
  handleCalcShowOpenTag() {
    if (!this.scene?.metrics?.length || !this.tagListRef) {
      return;
    }
    const { height, top: parentTop } = this.tagListRef.getBoundingClientRect();
    // 单行不展示 展开/收起 按钮
    this.showTagOpen = Array.from(this.tagListRef.querySelectorAll('.bk-tag')).some(ele => {
      const { top } = ele.getBoundingClientRect();
      return top >= height + parentTop;
    });
  }
  /** 或去场景 */
  multivariateAnomalyScenes() {
    this.isLoading = true;
    const sceneId = this.metricData?.[0]?.sceneConfig?.algorithms?.[0]?.config?.scene_id;
    if (sceneId) {
      const level = this.metricData[0].sceneConfig.algorithms[0]?.config?.levels || [];
      if (level.length) {
        this.formModel.level = level;
      } else {
        this.formModel.level = [];
      }
      this.formModel.sensitivity = this.metricData[0].sceneConfig.algorithms[0]?.config?.sensitivity || 5;
      this.metrics = this.metricData[0].sceneConfig.algorithms[0]?.config?.metrics?.map(item => item.metric_id) || [];
    }
    multivariateAnomalyScenes()
      .then(res => {
        this.scenes = res;
        if (sceneId) {
          this.handleScenSelected(sceneId, false);
        } else if (this.$route.query?.scene_id) {
          this.handleScenSelected(this.$route.query.scene_id);
        } else if (this.scenes.length && !this.formModel.scene) {
          this.handleScenSelected(this.scenes[0].scene_id);
        }
        this.isLoading = false;
      })
      .catch(err => {
        console.log(err);
      })
      .finally(() => {
        this.isLoading = false;
      });
  }
  // 编辑时设置监控目标描述
  handleSetTargetDesc(
    targetList: { all_host: any[]; bk_obj_id: string; count: number; instances_count?: number; nodes_count?: number }[],
    bkTargetType: string,
    nodeCount = 0,
    instance_count = 0
  ) {
    const [{ objectType }] = this.metricData;
    const result = getTargetDesc(targetList, bkTargetType, objectType, nodeCount, instance_count);
    this.target.desc.message = result.message;
    this.target.desc.subMessage = result.subMessage;
    return {
      message: result.message,
      subMessage: result.subMessage,
    };
  }
  handleTargetCancel() {
    this.showTopoSelector = false;
    this.ipSelectKey = random(10);
    this.targetList = this.defaultCheckedTarget?.target_detail?.slice?.() || [];
    this.handleSetTargetDesc(this.targetList, this.metricData[0].targetType);
  }
  handleTopoCheckedChange(data: { nodeType: INodeType; objectType: TargetObjectType; value: IIpV6Value }) {
    this.targetList = transformValueToMonitor(data.value, data.nodeType);
    this.target.targetType = data.nodeType;
    this.handleSetTargetDesc(this.targetList, this.target.targetType);
    this.handleTargetSave();
  }
  /** 表单验证 */
  validate() {
    return this.createForm.validate();
  }

  /**
   * @description 展示指标tip
   * @param e
   * @param item
   */
  handleMetricMouseenter(e: MouseEvent, item: MetricDetail) {
    let content = '';
    try {
      content = this.handleGetMetricTipsContent(item);
    } catch (error) {
      // content = `${this.$t('指标不存在')}`;
    }
    if (content) {
      this.metricpopoerInstance = this.$bkPopover(e.target, {
        content,
        placement: 'top',
        theme: 'monitor-metric-input',
        arrow: true,
        flip: false,
        interactive: true,
        interactiveBorder: 6,
        onHidden: () => {
          this.metricpopoerInstance?.destroy?.();
          this.metricpopoerInstance = null;
        },
      });
      this.metricpopoerInstance?.show?.(100);
    }
  }

  /**
   * @description 指标选择变化
   * @param v
   */
  handleMetricChange(v) {
    this.metrics = v;
    this.handleChange();
    this.handleMetricEmitChange();
  }

  /**
   * @description 敏感度变化
   * @param v
   */
  handleSensitivity(v) {
    this.formModel.sensitivity = v;
    this.handleChange();
  }

  validateMetrics() {
    return this.metrics?.length >= 2;
  }

  renderIpWrapper() {
    if (this.targetList.length || this.targetDesc.message.length) {
      return [
        <i
          key={1}
          class='icon-monitor icon-mc-tv'
        />,
        <span
          key={2}
          style='color: #63656e;'
          class='subtitle'
        >
          {this.targetDesc.message}
          {this.targetDesc.subMessage}
        </span>,
        this.readonly ? (
          <span
            key={3}
            class='ip-wrapper-title'
            onClick={this.handleAddTarget}
          >
            {this.$t('查看监控目标')}
          </span>
        ) : (
          <span
            key={4}
            class='icon-monitor icon-bianji'
            onClick={this.handleAddTarget}
          />
        ),
      ];
    }

    if (this.readonly) {
      return <span>{this.$t('本业务')}</span>;
    }

    return [
      <div
        key={1}
        class='ip-wrapper-title'
        on-click={this.handleAddTarget}
      >
        <i class='icon-monitor icon-mc-plus-fill' />
        {this.$t('添加监控目标')}
      </div>,
      <span
        key={2}
        class='subtitle ml5'
      >{`(${this.$t('默认为本业务')})`}</span>,
    ];
  }

  render() {
    return (
      <div
        class='aiops-monitor-data'
        v-bkloading={{ isLoading: this.isLoading && this.readonly, zIndex: 10 }}
      >
        <bk-form
          ref='createForm'
          class='form-wrap'
          labelWidth={110}
          {...{
            props: {
              model: this.formModel,
              rules: this.formRules,
            },
          }}
        >
          <bk-form-item label={this.$t('监控项')}>
            <span class='aiops-monitor-data-text'>{this.$t('场景智能检测')}</span>
          </bk-form-item>
          <bk-form-item
            class='scene-select'
            error-display-type='normal'
            label={this.$t('观测场景')}
            property={'scene'}
          >
            {this.readonly ? (
              <span>{this.scene?.scene_name}</span>
            ) : (
              <bk-popover
                content={this.$t('主机场景检测数据源正在接入中，请稍后重试')}
                disabled={this.scenes.length !== 0}
              >
                <bk-select
                  class='scene-selector'
                  behavior='simplicity'
                  clearable={false}
                  disabled={this.scenes.length === 0}
                  loading={this.isLoading}
                  value={this.formModel.scene}
                  onSelected={v => this.handleScenSelected(v)}
                >
                  {this.scenes.map(scene => (
                    <bk-option
                      id={scene.scene_id}
                      key={scene.scene_id}
                      name={scene.scene_name}
                    >
                      {scene.scene_name}
                    </bk-option>
                  ))}
                </bk-select>
              </bk-popover>
            )}
          </bk-form-item>
          <bk-form-item
            class='metric-select'
            error-display-type='normal'
            label={this.$t('指标')}
            property={'metrics'}
          >
            {this.readonly ? (
              <div class='aiops-tag-wrap'>
                {this.readonlyMetrics.length > 0 && (
                  <div class={['aiops-tag-content', this.tagOpen && 'aiops-tag-content-open']}>
                    <i18n
                      class='nowrap'
                      path='共{count}个指标'
                      tag='span'
                    >
                      <span
                        class='aiops-tag-count'
                        slot='count'
                      >
                        {this.readonlyMetrics.length}
                      </span>
                    </i18n>
                    ：
                    <div
                      ref='tagListRef'
                      class='aiops-tag-list'
                    >
                      {this.readonlyMetrics.map(metric => (
                        <span
                          key={metric.metric_id}
                          onMouseenter={e => this.handleMetricMouseenter(e, metric.metric)}
                        >
                          <bk-tag>{metric.name}</bk-tag>
                        </span>
                      ))}
                    </div>
                    {this.showTagOpen && (
                      <span
                        class='aiops-tag-toggle nowrap'
                        onClick={() => (this.tagOpen = !this.tagOpen)}
                      >
                        <bk-icon
                          style='font-size: 18px;'
                          type={!this.tagOpen ? 'angle-double-down' : 'angle-double-up'}
                        />
                        {this.$t(this.tagOpen ? '收起' : '展开')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div
                class='aiops-metric-select'
                tabindex={0}
              >
                <AiopsMonitorMetricSelect
                  defaultScenario={this.defaultScenario}
                  metrics={this.allMetrics}
                  scenarioList={this.scenarioList}
                  value={this.metrics}
                  onChange={this.handleMetricChange}
                />
              </div>
            )}
          </bk-form-item>

          <bk-form-item
            error-display-type='normal'
            label={this.$t('监控目标')}
          >
            <div class='ip-wrapper'>{this.renderIpWrapper()}</div>
          </bk-form-item>
          <bk-form-item
            desc={{
              width: 188,
              theme: 'pd10',
              content: this.$t('告警生成后，将根据指标的异常程度、发生异常的指标数，为告警自动评级'),
            }}
            error-display-type='normal'
            label={this.$t('生成告警级别')}
            property={'level'}
          >
            <div class='aiops-level-list'>
              {this.readonly ? (
                this.levelList
                  .filter(item => this.formModel.level.includes(item.id))
                  .map((item, index) => (
                    <span
                      key={index}
                      class='level-check'
                    >
                      <i class={['icon-monitor', item.icon, `status-${item.id}`]} />
                      <span>{item.name}</span>
                    </span>
                  ))
              ) : (
                <bk-checkbox-group
                  value={this.formModel.level}
                  onChange={this.handleLevelChange}
                >
                  {this.levelList.map((item, index) => (
                    <bk-checkbox
                      key={index}
                      class='level-check'
                      value={item.id}
                    >
                      <i class={['icon-monitor', item.icon, `status-${item.id}`]} />
                      <span>{item.name}</span>
                    </bk-checkbox>
                  ))}
                </bk-checkbox-group>
              )}
            </div>
          </bk-form-item>
          <bk-form-item label={this.$t('敏感度')}>
            <bk-slider
              class={`process-item ${this.readonly ? 'process-item-readonly' : ''}`}
              custom-content={{ 1: { label: this.$t('较少告警') }, 10: { label: this.$t('较多告警') } }}
              disable={this.readonly}
              max-value={10}
              min-value={1}
              show-custom-label={true}
              value={this.formModel.sensitivity}
              onInput={this.handleSensitivity}
            />
            {this.readonly && <span class='item-readonly-value'>{this.formModel.sensitivity}</span>}
          </bk-form-item>
        </bk-form>
        {this.metricData.some(item => item.canSetTarget) && this.ipSelect()}
      </div>
    );
  }

  ipSelect() {
    const [{ targetType, objectType }] = this.metricData;
    if (!this.readonly) {
      return (
        <StrategyIpv6
          checkedNodes={this.targetList || []}
          nodeType={targetType as INodeType}
          objectType={objectType as TargetObjectType}
          showDialog={this.showTopoSelector}
          onChange={this.handleTopoCheckedChange}
          onCloseDialog={v => (this.showTopoSelector = v)}
        />
      );
    }
    const tableData = this.readonly ? transformDataKey(this.defaultCheckedTarget?.detail || []) : [];
    return (
      <bk-dialog
        width='1100'
        v-model={this.showTopoSelector}
        header-position='left'
        need-footer={false}
        title={this.$t('监控目标')}
        zIndex={1002}
        on-change={v => (this.showTopoSelector = v)}
        on-on-cancel={this.handleTargetCancel}
      >
        <strategy-target-table
          objType={objectType}
          tableData={tableData}
          targetType={targetType}
        />
      </bk-dialog>
    );
  }
}

export default tsx.ofType<IProps>().convert(AiopsMonitorData);
