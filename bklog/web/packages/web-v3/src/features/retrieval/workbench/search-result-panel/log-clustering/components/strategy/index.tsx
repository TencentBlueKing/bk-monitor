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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { MessagePlugin as TDesignMessage, Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
import { asDictionary } from '@/shared/utils/typed-record';

import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { From } from '@/platform/compat/tdesign/magic-controls';

import './index.scss';


type FormType = 'alarm' | 'increase';
type StrategyType = 'new_cls_strategy' | 'normal_strategy';

const { $i18n } = window.mainComponent;

interface StrategyProps {
  "strategySubmitStatus"?: (v: boolean) => boolean;
  "clusterSwitch"?: boolean;
  "isClusterActive"?: boolean;
}

@Component
export default class Strategy extends tsc<StrategyProps> {
  @Ref('strategyFrom') strategyFromRef!: From;
  /** 策略状态更新函数 */
  @Prop({ type: Function }) strategySubmitStatus!: (v: boolean) => boolean;
  /** 日志聚类总开关 */
  @Prop({ type: Boolean, default: false }) clusterSwitch!: boolean;
  @Prop({ type: Boolean, default: false }) isClusterActive!: boolean;

  isShowDialog = false;
  formLoading = false;
  /** 当前编辑的类型 */
  activeType: FormType = 'alarm';
  /** 聚类接口类型映射 */
  typeMapping = {
    new_cls_strategy: 'alarm',
    normal_strategy: 'increase',
  };
  strategyMapping = {
    alarm: 'new_cls_strategy',
    increase: 'normal_strategy',
  };
  isEdit = false;
  baseAlarmFormData = null;
  baseIncreaseFormData = null;
  labelName = [];
  /** 聚类消息初始化对应的key */
  infoKeyData = asDictionary({
    alarm: {
      submit: 'alarmIsSubmit',
      data: 'alarmFormData',
    },
    increase: {
      submit: 'increaseIsSubmit',
      data: 'increaseFormData',
    },
  });
  /** 新类提交数据 */
  alarmFormData = {
    interval: '30',
    threshold: '1',
    level: 2,
    user_groups: [],
    label_name: [],
  };
  /** 数据提交表单数据 */
  increaseFormData = {
    level: 2,
    sensitivity: 5,
    user_groups: [],
    label_name: [],
  };
  /** 告警级别下拉框 */
  levelSelectList = [
    { id: 1, name: $i18n.t('致命') },
    { id: 2, name: $i18n.t('预警') },
    { id: 3, name: $i18n.t('提醒') },
  ];
  /** 告警组下拉框 */
  groupSelectList = [];
  /** 新类告警策略是否保存过 */
  alarmIsSubmit = false;
  /** 数量突增告警告警是否保存过 */
  increaseIsSubmit = false;
  rules = {
    interval: [
      {
        required: true,
        message: $i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
    threshold: [
      {
        required: true,
        message: $i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
    level: [
      {
        required: true,
        message: $i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
    user_groups: [
      {
        required: true,
        message: $i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
  };

  get isAlarmType(): boolean {
    return this.activeType === 'alarm';
  }
  get bkBizId() {
    return useApplicationStore().bkBizId;
  }
  get formData(): any {
    return this.isAlarmType ? this.alarmFormData : this.increaseFormData;
  }
  /** 新增按钮是否禁用 */
  get addBtnIsDisabled(): boolean {
    return this.alarmIsSubmit && this.increaseIsSubmit;
  }

  get isExternal() {
    return useApplicationStore().isExternal;
  }

  @Watch('alarmIsSubmit')
  watchStrategyStatus(v: boolean) {
    this.strategySubmitStatus(v);
  }

  mounted() {
    if (!(this.clusterSwitch && this.isClusterActive)) {
      return;
    }
    this.baseAlarmFormData = structuredClone(this.alarmFormData);
    this.baseIncreaseFormData = structuredClone(this.increaseFormData);
    this.initStrategyInfo();
  }

  /** 给索引集添加标签 */
  requestGetUserGroup() {
    this.formLoading = true;
    ServicesInstance.retrieve.userGroup({
        data: {
          bk_biz_id: this.bkBizId,
        },
      })
      .then(res => {
        this.groupSelectList = res.data.map((item: { id: any; name: any; }) => ({
          id: item.id,
          name: item.name,
        }));
      })
      .finally(() => {
        this.formLoading = false;
      });
  }
  /** 获取信息 */
  async requestStrategyInfo(strategyType: StrategyType = 'new_cls_strategy') {
    try {
      const res = await ServicesInstance.retrieve.getClusteringInfo({
        params: {
          index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
          strategy_type: strategyType,
        },
      });
      return { data: res.data, type: this.typeMapping[strategyType] ?? strategyType };
    } catch {
      return { type: strategyType };
    }
  }
  handleSelectFromType(shotType: FormType) {
    this.strategyFromRef.clearError();
    this.activeType = shotType;
  }
  handleConfirmSubmit() {
    this.strategyFromRef.validate().then(() => {
      const submitPostStr = (this.isAlarmType ? ServicesInstance.retrieve.newClsStrategy : ServicesInstance.retrieve.normalStrategy);
      const data = this.isAlarmType ? this.alarmFormData : this.increaseFormData;
      const { label_name: _labelName, ...otherData } = data;
      submitPostStr({
          params: {
            index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
          },
          data: otherData,
        })
        .then(res => {
          if (res.code === 0) {
            TDesignMessage("success", { content: this.$t('操作成功') });
            this.isShowDialog = false;
          }
        });
    });
  }
  handleOpenDialog(v: boolean) {
    if (v) {
      this.requestGetUserGroup();
    } else {
      this.isEdit = false;
      this.strategyFromRef.clearError();
      this.initStrategyInfo();
    }
  }
  editStrategy(type: FormType) {
    this.initStrategyInfo();
    this.activeType = type;
    this.isEdit = true;
    this.isShowDialog = true;
  }
  deleteStrategy(type: FormType) {
    const strategyType = this.strategyMapping[type] ?? type;
    const h = this.$createElement;
    this.$bkInfo({
      title: this.$t('是否删除该策略？'),
      confirmLoading: true,
      theme: 'danger',
      okText: this.$t('删除'),
      subHeader: h(
        'div',
        {
          style: {
            display: 'flex',
            justifyContent: 'center',
          },
        },
        [
          h(
            'span',
            {
              style: {
                color: '#63656E',
              },
            },
            [this.$t('策略：') as string],
          ),
          h('span', this.$t(type === 'alarm' ? '新类告警策略' : '数量突增告警策略') as string),
        ],
      ),
      confirmFn: async () => {
        try {
          const res = await ServicesInstance.retrieve.deleteClusteringInfo({
            params: {
              index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
            },
            data: { strategy_type: strategyType },
          });
          if (res.code === 0) {
            this.isShowDialog = false;
            TDesignMessage("success", { content: this.$t('操作成功') });
            this.initStrategyInfo();
          }
          return true;
        } catch (e) {
          console.warn(e);
          return false;
        }
      },
    });
  }
  initStrategyInfo() {
    Promise.all([this.requestStrategyInfo('new_cls_strategy'), this.requestStrategyInfo('normal_strategy')])
      .then(values => {
        for (const vItem of values) {
          const isSubmit = JSON.stringify(vItem.data) !== '{}';
          this[this.infoKeyData[vItem.type].submit] = isSubmit;
          if (isSubmit) {
            Object.assign(this[this.infoKeyData[vItem.type].data], vItem.data);
          } else {
            this.resetFormData(vItem.type as FormType);
          }
        }
      })
      .catch(error => {
        this.resetFormData(error.type);
        this.labelName = [
          ...new Set([...(this.alarmFormData?.label_name ?? []), ...(this.increaseFormData?.label_name ?? [])]),
        ];
      })
      .finally(() => {
        this.labelName = [
          ...new Set([...(this.alarmFormData?.label_name ?? []), ...(this.increaseFormData?.label_name ?? [])]),
        ];
      });
  }
  /** 重置表单参数 */
  resetFormData(type: FormType = 'alarm') {
    type === 'alarm'
      ? Object.assign(this.alarmFormData, this.baseAlarmFormData)
      : Object.assign(this.increaseFormData, this.baseIncreaseFormData);
  }
  /** 点击新增告警 */
  handleAddNewStrategy() {
    this.activeType = this.alarmIsSubmit ? 'increase' : 'alarm';
    this.resetFormData(this.activeType);
    this.isShowDialog = true;
  }
  /** 跳转告警策略列表 */
  handleJumpStrategyList() {
    const bizid = useApplicationStore().indexItem.items[0].bk_biz_id;
    window.open(
      `${window.MONITOR_URL}/?bizId=${bizid}#/strategy-config?strategyLabels=${JSON.stringify(this.labelName)}`,
      '_blank',
    );
  }
  handleCreateUserGroups() {
    const bizid = useApplicationStore().indexItem.items[0].bk_biz_id;
    window.open(`${window.MONITOR_URL}/?bizId=${bizid}#/alarm-group/add`, '_blank');
  }
  render() {
    if (this.isExternal) {
      return <div />;
    }

    const strategyDialog = () => (
      <bk-dialog
        width='480'
        ext-cls='strategy-dialog'
        v-model={this.isShowDialog}
        confirm-fn={this.handleConfirmSubmit}
        header-position='left'
        mask-close={false}
        theme='primary'
        title={$i18n.t(this.isEdit ? '编辑策略' : '新建策略')}
        onValueChange={this.handleOpenDialog}
      >
        {/* <bk-alert type='info'>
        <div slot='title'>
          <i18n path='当前页面提供快速配置，如需完整配置，请前往{0}'>
            <span class='info-btn'>
              {$i18n.t('新建完整策略')} <i class='bklog-icon bklog-jump'></i>
            </span>
          </i18n>
        </div>
      </bk-alert> */}
        <div class={['select-group bk-button-group', { 'increase-group': !this.isAlarmType }]}>
          <TButton
            class={{ 'is-selected': this.isAlarmType }}
            disabled={this.alarmIsSubmit && !this.isEdit}
            onClick={() => this.handleSelectFromType('alarm')}
          >
            {$i18n.t('新类告警策略')}
          </TButton>
          <TButton
            class={{ 'is-selected': !this.isAlarmType }}
            disabled={this.increaseIsSubmit && !this.isEdit}
            onClick={() => this.handleSelectFromType('increase')}
          >
            {$i18n.t('数量突增告警')}
          </TButton>
        </div>
        <bk-form
          ref='strategyFrom'
          v-loading={{ loading: this.formLoading }}
          form-type='vertical'
          {...{
            ...{
              model: this.formData,
              rules: this.rules,
            },
          }}
        >
          <bk-form-item
            v-show={this.isAlarmType}
            desc={$i18n.t('表示近一段时间内新增日志模式。可自定义新类判定的时间区间。如：近30天内新增')}
            desc-type={'icon'}
            label={$i18n.t('新类告警间隔（天）')}
            property='interval'
            required
          >
            <bk-input
              v-model={this.formData.interval}
              placeholder={$i18n.t('每隔 n（整数）天数，再次产生的日志模式将视为新类')}
              show-controls={false}
              type='number'
            />
          </bk-form-item>
          <bk-form-item
            v-show={this.isAlarmType}
            desc={$i18n.t('表示某日志模式数量突然异常增长，可能某些模块突发风险')}
            desc-type={'icon'}
            label={$i18n.t('新类告警阈值')}
            property='threshold'
            required
          >
            <bk-input
              v-model={this.formData.threshold}
              placeholder={$i18n.t('新类对应日志触发告警的条数')}
              show-controls={false}
              type='number'
            />
          </bk-form-item>
          <bk-form-item
            label={$i18n.t('告警级别')}
            property='level'
            required
          >
            <bk-select
              v-model={this.formData.level}
              searchable
            >
              {this.levelSelectList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            v-show={!this.isAlarmType}
            label={$i18n.t('变化敏感度')}
            property='sensitivity'
            required
          >
            <div class='level-box'>
              <bk-slider
                v-slots={{
                  start: () => <span style='margin-right: 10px;'>{$i18n.t('低')}</span>,
                  end: () => <span style='margin-left: 10px;'>{$i18n.t('高')}</span>,
                }}
                v-model={this.formData.sensitivity}
                max-value={10}
                min-value={0}
              ></bk-slider>
            </div>
          </bk-form-item>
          <bk-form-item
            label={$i18n.t('告警组')}
            property='user_groups'
            required
          >
            <bk-select
              v-slots={{
                extension: () => (
                  <div
                    class='groups-btn'
                    onClick={() => this.handleCreateUserGroups()}
                  >
                    <i class='bk-icon icon-plus-circle' />
                    {$i18n.t('新增告警组')}
                  </div>
                ),
              }}
              v-model={this.formData.user_groups}
              ext-popover-cls='strategy-create-groups'
              display-tag
              multiple
              searchable
            >
              {this.groupSelectList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
    const popoverSlot = (type: FormType = 'alarm') => (
      <bk-popover
        v-slots={{
          content: () => (
            <div>
              <span>{$i18n.t(type === 'alarm' ? '新类告警策略' : '数量突增告警策略')}</span>
              <span
                class='operator'
                onClick={() => this.editStrategy(type)}
              >
                {$i18n.t('编辑')}
              </span>
              <span
                class='operator'
                onClick={() => this.deleteStrategy(type)}
              >
                {$i18n.t('删除')}
              </span>
            </div>
          ),
        }}
        ext-cls='strategy-popover'
        disabled={!this.clusterSwitch}
        placement='top'
        theme='light'
      >
        <div
          class={['edit-strategy-box', type]}
          onClick={() => this.editStrategy(type)}
        >
          <i class={['bklog-icon log-icon', type === 'alarm' ? 'bklog-new-alarm' : 'bklog-sudden-increase']} />
          {/* <span class='num'>1</span> */}
        </div>
      </bk-popover>
    );
    return (
      <div class='strategy-container'>
        {strategyDialog()}
        <div class='new-built-container'>
          <div
            v-log-tooltip={{
              content: this.$t('聚类告警已开启，请点击右侧入口编辑策略'),
              disabled: !this.addBtnIsDisabled,
            }}
          >
            <TButton
              disabled={this.addBtnIsDisabled || !this.clusterSwitch}
              icon={() => <span class={`bk-icon icon-${'plus'}`} />}
              size='small'
              onClick={this.handleAddNewStrategy}
            >
              {$i18n.t('新建策略')}
            </TButton>
          </div>
          {this.alarmIsSubmit && popoverSlot('alarm')}
          {this.increaseIsSubmit && popoverSlot('increase')}
        </div>
        {!!this.labelName.length && (
          <TButton
            size='small'

            onClick={this.handleJumpStrategyList} variant={(true) ? 'text' : ('base')}
          >
            <span>{$i18n.t('查看策略')}</span>
            <i
              style={{ 'margin-left': '4px' }}
              class='bklog-icon bklog-jump'
            />
          </TButton>
        )}
      </div>
    );
  }
}
