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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { multivariateAnomalyScenes } from '../../../../../monitor-api/modules/strategies';
import { random, transformDataKey } from '../../../../../monitor-common/utils/utils';
import { IIpV6Value, INodeType, TargetObjectType } from '../../../../components/monitor-ip-selector/typing';
import { transformValueToMonitor } from '../../../../components/monitor-ip-selector/utils';
import { handleSetTargetDesc } from '../../common';
import StrategyTargetTable from '../../strategy-config-detail/strategy-config-detail-table.vue';
import StrategyIpv6 from '../../strategy-ipv6/strategy-ipv6';
import { ISceneConfig, MetricDetail, MetricType } from '../typings';

import './aiops-monitor-data.scss';

interface NewMetricDetail extends MetricDetail {
  sceneConfig: ISceneConfig;
}
interface IProps {
  metricData?: NewMetricDetail[];
  defaultCheckedTarget?: any;
  readonly?: boolean;
  onChange?: (sceneConfig: ISceneConfig) => void;
  onTargetTypeChange?: (type: string) => void;
  onTargetChange?: (value) => void;
}
@Component({
  components: {
    StrategyTargetTable
  }
})
export default class AiopsMonitorData extends tsc<IProps> {
  /* 指标数据 */
  @Prop({ default: () => [], type: Array }) metricData: NewMetricDetail[];
  @Prop({ default: () => ({ target_detail: [] }), type: Object }) defaultCheckedTarget: any;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Ref('targetContainer') targetContainerRef: HTMLDivElement;
  @Ref('createForm') createForm: any;
  @Ref('tagListRef') tagListRef: HTMLDivElement;
  /** 表单数据 */
  formModel = {
    level: 0,
    scene: ''
  };
  target: any = {
    targetType: '',
    desc: {
      message: '',
      subMessage: ''
    }
  };
  /** 表单规则 */
  formRules = {
    scene: [
      {
        required: true,
        message: this.$t('必填项'),
        trigger: 'blur'
      }
    ],
    level: [
      {
        validator(val) {
          return val > 0;
        },
        message: this.$t('必填项'),
        trigger: 'blur'
      }
    ]
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
    { id: 3, name: this.$t('提醒'), icon: 'icon-tips' }
  ];

  @Emit('change')
  handleChange(value?) {
    if (value) {
      return value;
    }
    const algorithm = {
      level: this.formModel.level,
      type: MetricType.MultivariateAnomalyDetection,
      config: {
        scene_id: this.formModel.scene,
        metrics: this.scene.metrics
      },
      unit_prefix: ''
    };
    return {
      ...this.scene,
      query_configs: [{ ...this.scene.query_config }],
      algorithms: [algorithm]
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

  created() {
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
    if (!!this.scene) {
      this.handleChange();
    }
  }
  /** 场景切换 */
  handleScenSelected(value) {
    this.formModel.scene = value;
    this.scene = this.scenes.find(item => item.scene_id === this.formModel.scene);
    this.$nextTick(() => {
      this.handleCalcShowOpenTag();
    });
    this.handleChange();
  }
  /** 计算指标是否存在多行情况 */
  handleCalcShowOpenTag() {
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
      this.formModel.level = this.metricData[0].sceneConfig.algorithms[0].level;
    }
    multivariateAnomalyScenes()
      .then(res => {
        this.scenes = res;
        if (sceneId) {
          this.handleScenSelected(sceneId);
        } else if (this.$route.query?.scene_id) {
          this.handleScenSelected(this.$route.query.scene_id);
        }
        this.isLoading = false;
      })
      .catch(() => (this.isLoading = false));
  }
  // 编辑时设置监控目标描述
  handleSetTargetDesc(
    targetList: { count: number; bk_obj_id: string; nodes_count?: number; instances_count?: number; all_host: any[] }[],
    bkTargetType: string,
    nodeCount = 0,
    instance_count = 0
  ) {
    const [{ objectType }] = this.metricData;
    const result = handleSetTargetDesc(targetList, bkTargetType, objectType, nodeCount, instance_count);
    this.target.desc.message = result.message;
    this.target.desc.subMessage = result.subMessage;
  }
  handleTargetCancel() {
    this.showTopoSelector = false;
    this.ipSelectKey = random(10);
    this.targetList = this.defaultCheckedTarget?.target_detail?.slice?.() || [];
    this.handleSetTargetDesc(this.targetList, this.metricData[0].targetType);
  }
  handleTopoCheckedChange(data: { value: IIpV6Value; nodeType: INodeType; objectType: TargetObjectType }) {
    this.targetList = transformValueToMonitor(data.value, data.nodeType);
    this.target.targetType = data.nodeType;
    this.handleSetTargetDesc(this.targetList, this.target.targetType);
    this.handleTargetSave();
  }
  /** 表单验证 */
  validate() {
    return this.createForm.validate();
  }

  render() {
    return (
      <div
        class='aiops-monitor-data'
        v-bkloading={{ isLoading: this.isLoading && this.readonly, zIndex: 10 }}
      >
        <bk-form
          class='form-wrap'
          ref='createForm'
          labelWidth={110}
          {...{
            props: {
              model: this.formModel,
              rules: this.formRules
            }
          }}
        >
          <bk-form-item label={`${this.$t('监控项')}：`}>
            <span class='aiops-monitor-data-text'>{this.$t('场景智能检测')}</span>
          </bk-form-item>
          <bk-form-item
            label={`${this.$t('观测场景')}：`}
            class='scene-select'
            error-display-type='normal'
            property={'scene'}
          >
            {this.readonly ? (
              <span>{this.scene?.scene_name}</span>
            ) : (
              <bk-select
                loading={this.isLoading}
                value={this.formModel.scene}
                clearable={false}
                behavior='simplicity'
                onSelected={this.handleScenSelected}
              >
                {this.scenes.map(scene => (
                  <bk-option
                    id={scene.scene_id}
                    name={scene.scene_name}
                    key={scene.scene_id}
                  >
                    {scene.scene_name}
                  </bk-option>
                ))}
              </bk-select>
            )}
          </bk-form-item>
          <div class='aiops-tag-wrap'>
            {this.scene?.metrics?.length > 0 && (
              <div class={['aiops-tag-content', this.tagOpen && 'aiops-tag-content-open']}>
                <i18n
                  path='共{count}个指标'
                  tag='span'
                  class='nowrap'
                >
                  <span
                    slot='count'
                    class='aiops-tag-count'
                  >
                    {this.scene.metrics.length}
                  </span>
                </i18n>
                ：
                <div
                  class='aiops-tag-list'
                  ref='tagListRef'
                >
                  {this.scene.metrics.map(metric => (
                    <bk-tag>{metric.name}</bk-tag>
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
          <bk-form-item
            label={`${this.$t('监控目标')}：`}
            error-display-type='normal'
          >
            <div class='ip-wrapper'>
              {!this.targetList.length && !this.target.desc.message.length
                ? [
                    !this.readonly ? (
                      <div
                        class='ip-wrapper-title'
                        on-click={this.handleAddTarget}
                      >
                        <i class='icon-monitor icon-mc-plus-fill'></i>
                        {this.$t('添加监控目标')}
                      </div>
                    ) : (
                      <span>{this.$t('未添加监控目标')}</span>
                    ),
                    <span class='subtitle ml5'>{`(${this.$t('默认为本业务')})`}</span>
                  ]
                : [
                    <i class='icon-monitor icon-mc-tv'></i>,
                    <span
                      class='subtitle'
                      style='color: #63656e;'
                    >
                      {this.target.desc.message}
                      {this.target.desc.subMessage}
                    </span>,

                    this.readonly ? (
                      <span
                        class='ip-wrapper-title'
                        onClick={this.handleAddTarget}
                      >
                        {this.$t('查看监控目标')}
                      </span>
                    ) : (
                      <span
                        class='icon-monitor icon-bianji'
                        onClick={this.handleAddTarget}
                      ></span>
                    )
                  ]}
            </div>
          </bk-form-item>
          <bk-form-item
            label={`${this.$t('过滤告警级别')}：`}
            property={'level'}
            error-display-type='normal'
          >
            <div class='aiops-level-list'>
              {this.readonly
                ? this.levelList
                    .filter(
                      item => (this.formModel.level === item.id || this.formModel.level > item.id ? item.id : 0) !== 0
                    )
                    .map(item => (
                      <span class='level-check'>
                        <i class={['icon-monitor', item.icon, `status-${item.id}`]}></i>
                        <span>{item.name}</span>
                      </span>
                    ))
                : this.levelList.map(item => (
                    <bk-checkbox
                      class='level-check'
                      value={this.formModel.level === item.id || this.formModel.level > item.id ? item.id : 0}
                      disabled={this.formModel.level > item.id}
                      true-value={item.id}
                      false-value={0}
                      v-bk-tooltips={{
                        disabled: !(this.formModel.level > item.id),
                        content: this.$t('已选择更低级告警级别')
                      }}
                      onChange={this.handleLevelChange}
                    >
                      <i class={['icon-monitor', item.icon, `status-${item.id}`]}></i>
                      <span>{item.name}</span>
                    </bk-checkbox>
                  ))}
            </div>
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
          showDialog={this.showTopoSelector}
          nodeType={targetType as INodeType}
          objectType={objectType as TargetObjectType}
          checkedNodes={this.targetList || []}
          onChange={this.handleTopoCheckedChange}
          onCloseDialog={v => (this.showTopoSelector = v)}
        />
      );
    }
    const tableData = this.readonly ? transformDataKey(this.defaultCheckedTarget?.detail || []) : [];
    return (
      <bk-dialog
        v-model={this.showTopoSelector}
        on-change={v => (this.showTopoSelector = v)}
        on-on-cancel={this.handleTargetCancel}
        need-footer={false}
        header-position='left'
        width='1100'
        title={this.$t('监控目标')}
        zIndex={1002}
      >
        <strategy-target-table
          tableData={tableData}
          targetType={targetType}
          objType={objectType}
        />
      </bk-dialog>
    );
  }
}
