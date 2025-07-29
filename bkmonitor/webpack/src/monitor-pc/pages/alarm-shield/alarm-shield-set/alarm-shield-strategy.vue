-
<!--
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
-->
<template>
  <div class="alarm-shield-strategy">
    <!-- 所属 -->
    <div class="strategy-item">
      <div class="item-label">
        {{ $t('所属') }}
      </div>
      <div class="strategy-item-content">
        <bk-select
          v-model="bizId"
          style="width: 413px"
          readonly
        >
          <bk-option
            v-for="(option, index) in bizList"
            :id="option.id"
            :key="index"
            :name="option.text"
          />
        </bk-select>
      </div>
    </div>
    <!-- 屏蔽策略 -->
    <div
      class="strategy-item"
      :class="{ 'verify-show': rule.strategyId }"
    >
      <div class="item-label">
        {{ $t('屏蔽策略') }}
      </div>
      <verify-input
        :show-validate.sync="rule.strategyId"
        :validator="{ content: $t('选择屏蔽策略') }"
      >
        <div class="strategy-item-content">
          <bk-select
            v-model="strategyId"
            style="width: 836px"
            searchable
            multiple
            :disabled="isEdit"
            @change="handleStrategyInfo"
          >
            <bk-option
              v-for="option in strategyList"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
              <span style="margin-right: 9px">{{ option.name }}</span>
              <span style="color: #c4c6cc">
                {{ option.firstLabelName }}-{{ option.secondLabelName }}（#{{ option.id }}）
              </span>
            </bk-option>
          </bk-select>
        </div>
      </verify-input>
    </div>
    <!-- 选择策略后展示 -->
    <template v-if="isShowDetail">
      <!-- 策略内容 -->
      <div
        v-if="isOneStrategy && strategyData"
        class="strategy-detail"
      >
        <div class="item-label">
          {{ $t('策略内容') }}
        </div>
        <!-- 策略详情展示组件 -->
        <strategy-detail-new :strategy-data="strategyData" />
      </div>
      <div
        v-if="strategyId.length > 0"
        class="strategy-detail"
      >
        <div class="item-label">
          {{ $t('维度选择') }}
        </div>
        <div
          v-if="isEdit"
          class="condition-table"
        >
          <bk-table
            :data="[{}]"
            :max-height="450"
            size="large"
          >
            <bk-table-column :label="$t('维度条件')">
              <template slot-scope>
                <where-display
                  v-if="dimensionCondition.conditionList.length"
                  :key="dimensionCondition.conditionKey"
                  :value="dimensionCondition.conditionList"
                  :readonly="true"
                  :all-names="dimensionCondition.allNames"
                />
                <span v-else>--</span>
              </template>
            </bk-table-column>
          </bk-table>
        </div>
        <simple-condition-input
          v-else
          :key="dimensionCondition.conditionKey"
          :condition-list="dimensionCondition.conditionList"
          :dimensions-list="dimensionCondition.dimensionList"
          :metric-meta="dimensionCondition.metricMeta"
          @change="
            v => {
              dimensionCondition.conditionList = v;
            }
          "
        />
      </div>
      <!-- 选择实例 IP 节点 -->
      <div
        v-if="isShowShieldScope && !(dataTarget.length === 1 && dataTarget[0] === '')"
        class="strategy-detail"
      >
        <div class="item-label">
          {{ $t('屏蔽范围') }}
        </div>
        <!-- 选择器组件 -->
        <div class="strategy-item-content shield-target">
          <shield-target
            ref="shieldTarget"
            :is-edit="isEdit"
            :is-clone="isClone"
            :shield-data="shieldData"
            :target-data="targetData"
            :type="targetType"
            :data-target="dataTarget"
            :need-verify="false"
          />
        </div>
      </div>
      <div class="strategy-item">
        <div class="item-label">
          {{ $t('告警等级') }}
        </div>
        <verify-input
          :show-validate="rule.noticeLever"
          :validator="{ content: $t('至少选择一种告警等级') }"
        >
          <div class="strategy-item-content">
            <bk-checkbox-group
              v-model="noticeLever"
              @change="handleAlarmLevel"
            >
              <bk-checkbox
                v-for="(item, index) in levelMap"
                :key="index"
                :value="index + 1"
                :disabled="!levelOptional.includes(index + 1)"
                class="checkbox-group"
              >
                {{ item }}
              </bk-checkbox>
            </bk-checkbox-group>
          </div>
        </verify-input>
      </div>
    </template>
    <!-- 屏蔽时间 -->
    <shield-date-config
      ref="noticeDate"
      v-model="commonDateData"
      :is-clone="isClone"
    />
    <!-- 屏蔽时间 -->
    <div class="strategy-desc">
      <div class="item-label">
        {{ $t('屏蔽原因') }}
      </div>
      <div class="strategy-desc-content">
        <bk-input
          v-model="desc"
          class="content-desc"
          type="textarea"
          :row="3"
          :maxlength="100"
        />
      </div>
    </div>
    <!-- 通知组 -->
    <alarm-shield-notice
      ref="notice"
      @change-show="handleChangeShow"
    />
    <div class="strategy-form">
      <div class="strategy-btn">
        <bk-button
          class="button"
          :theme="'primary'"
          @click="handleSubmit"
        >
          {{ $t('提交') }}
        </bk-button>
        <bk-button
          class="button ml10"
          :theme="'default'"
          @click="$router.push({ name: 'alarm-shield' })"
        >
          {{ $t('取消') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Mixins, Model, Prop, Ref, Watch } from 'vue-property-decorator';

import WhereDisplay from 'fta-solutions/pages/event/event-detail/where-display';
import { addShield, editShield } from 'monitor-api/modules/shield';
import { getMetricListV2, getStrategyListV2, getStrategyV2, plainStrategyList } from 'monitor-api/modules/strategies';
import { random, transformDataKey } from 'monitor-common/utils/utils';

import VerifyInput from '../../../components/verify-input/verify-input.vue';
import alarmShieldMixin from '../../../mixins/alarmShieldMixin';
import strategyMapMixin from '../../../mixins/strategyMapMixin';
import ShieldDateConfig from '../alarm-shield-components/alarm-shield-date.vue';
import AlarmShieldNotice from '../alarm-shield-components/alarm-shield-notice.vue';
import ShieldTarget from '../alarm-shield-components/alarm-shield-target.vue';
import StrategyDetailNew from '../alarm-shield-components/strategy-detail-new.tsx';
import StrategyDetail from '../alarm-shield-components/strategy-detail.vue';
import SimpleConditionInput from '../components/simple-condition-input';

import type MonitorVue from '../../../types/index';
import type { TranslateResult } from 'vue-i18n/types/index';
import type { Location } from 'vue-router/types/router';

interface IDimensionConfig {
  dimension_conditions?: any; // 参考基于维度进行屏蔽
  id: number[];
  level: string[];
  scope_type?: string;
  target?: [];
}
interface IParams {
  begin_time: string;
  bk_biz_id: string;
  category: string;
  cycle_config: {};
  description: string;
  dimension_config: IDimensionConfig;
  end_time: string;
  id?: string;
  level?: string[];
  notice_config?: {};
  shield_notice: boolean;
}
interface IStrategyList {
  firstLabelName: string;
  id: number | string;
  name: string;
  scenario: string;
  secondLabelName: string;
}
@Component({
  components: {
    ShieldDateConfig,
    AlarmShieldNotice,
    VerifyInput,
    StrategyDetail,
    ShieldTarget,
    StrategyDetailNew,
    SimpleConditionInput,
    WhereDisplay,
  },
})
export default class AlarmShieldStrategy extends Mixins(alarmShieldMixin, strategyMapMixin)<MonitorVue> {
  isEdit = false; // 是否编辑
  isClone = false; // 是否克隆
  bizList: { id: string; name: string }[] = []; // 业务列表
  bizId = ''; // 当前业务
  strategyList: IStrategyList[] = []; // 蔽策略的列表
  strategyData: any = {}; //   被屏蔽策略的数据
  strategyId: number[] = []; // 被屏蔽策略的id
  isShowDetail = false; // 是否展示策略详情
  // isOneStrategy: boolean = false // 是否只选择一个策略
  noticeLever: string[] = []; // 告警等级
  desc = ''; // 屏蔽原因
  noticeShow = false; // 是否展示通知设置
  levelMap: TranslateResult[] = []; // 告警等级Map
  targetData: any[] = []; // 勾选的屏蔽范围
  targetType = ''; // 屏蔽范围类型
  dataTarget: string[] = [];
  //  校验提示
  rule: { noticeLever: boolean; strategyId: boolean } = {
    strategyId: false,
    noticeLever: false,
  };
  /* 告警等级可选项 */
  levelOptional = [];
  /* 维度选择 */
  dimensionCondition = {
    conditionKey: random(8),
    dimensionList: [], // 维度列表
    metricMeta: null, // 获取条件候选值得参数
    conditionList: [], // 维度条件数据
    allNames: {}, // 维度名合集
  };
  //  屏蔽范围组件
  @Ref() readonly shieldTarget!: ShieldTarget;

  @Model('changeCommonDateData', {
    type: Object,
  })
  commonDateData!: object;

  //  编辑时回填的屏蔽详情数据
  @Prop({ default: () => ({}) })
  shieldData: any;

  //  是否来自策略列表页
  @Prop({ default: () => ({}) })
  fromStrategy: { id: number; is: boolean };

  @Prop({ default: false })
  edit: boolean;

  @Watch('shieldData', { deep: true })
  onShieldDataChange(v: any = {}): void {
    let data: any;
    switch (this.$route.name) {
      case 'alarm-shield-edit':
        this.isEdit = true;
        data = transformDataKey(v);
        this.handleSetEditOrCloneData(data);
        break;
      case 'alarm-shield-clone':
        data = transformDataKey(v);
        this.handleSetEditOrCloneData(data);
        this.isClone = true;
        break;
      default:
        break;
    }

    if (v.id && v.dimension_config?.dimension_conditions) {
      /* 回填维度条件 */
      this.dimensionCondition.conditionList = v.dimension_config.dimension_conditions.map(item => ({
        ...item,
        dimensionName: item.name || item.key,
      }));
      this.dimensionCondition.conditionList.forEach(item => {
        this.dimensionCondition.allNames[item.key] = item.name || item.key;
      });
      this.dimensionCondition.conditionKey = random(8);
    }
  }

  // 监听strategyId，必填校验
  @Watch('strategyId')
  onStrategyId(newVal): void {
    this.rule.strategyId = !newVal.length;
  }

  //  是否展示屏蔽范围
  get isShowShieldScope(): boolean {
    if (this.isEdit || this.isClone) {
      return !!this.targetData.length;
    }
    return this.strategyId.length !== 0;
  }

  get isOneStrategy(): boolean {
    return this.strategyId.length === 1;
  }

  created() {
    this.levelMap = [this.$t('致命'), this.$t('预警'), this.$t('提醒')];
    this.isClone = this.$route.name === 'alarm-shield-clone';
  }

  async activated() {
    this.bizId = this.$store.getters.bizId;
    this.bizList = this.$store.getters.bizList;
    this.getStrategyData();
  }

  //  告警勾选时校验
  handleAlarmLevel(arr: string[]): void {
    this.rule.noticeLever = !arr.length;
  }

  //  编辑和克隆时 处理屏蔽详情数据
  handleSetEditOrCloneData(data: any = {}): void {
    //  回填基本数据
    this.bizId = data.bkBizId;
    this.strategyId = data.dimensionConfig.strategies.map(item => item.id);
    // this.strategyData = data.dimensionConfig.itemList[0]
    this.noticeLever = data.dimensionConfig.level;
    this.desc = data.description;
    //  回填通知时间 每天 每周 每月
    const { cycleConfig } = data;
    const cycleMap: { 1: string; 2: string; 3: string; 4: string } = { 1: 'single', 2: 'day', 3: 'week', 4: 'month' };
    const type = cycleMap[cycleConfig.type];
    const shieldDate: any = {};
    shieldDate.typeEn = type;
    shieldDate[type] = {
      list: [...cycleConfig.dayList, ...cycleConfig.weekList],
      range: [cycleConfig.beginTime, cycleConfig.endTime],
    };
    shieldDate.dateRange = [data.beginTime, data.endTime];
    //  单次
    if (cycleConfig.type === 1) {
      shieldDate[type].range = [data.beginTime, data.endTime];
      shieldDate.dateRange = [];
    }
    const RNoticeDate: any = this.$refs.noticeDate;
    RNoticeDate.setDate(shieldDate);
    //  回填通知设置部分数据
    this.noticeShow = data.shieldNotice;
    if (this.noticeShow) {
      const shieldNoticeData = {
        notificationMethod: data.noticeConfig.noticeWay,
        noticeNumber: data.noticeConfig.noticeTime,
        member: {
          value: data.noticeConfig.noticeReceiver.map(item => item.id),
        },
      };
      const RNotice: any = this.$refs.notice;
      RNotice.setNoticeData(shieldNoticeData);
    }

    //  回填屏蔽范围部分数据
    if (data.dimensionConfig.target?.length) {
      this.targetData = data.dimensionConfig.target.map(item => ({ name: item }));
      this.targetType = data.dimensionConfig.scopeType;
    }
  }

  //  获取策略轻量列表
  async getStrategyData(): Promise<any> {
    this.$emit('update:loading', true);
    const data = await plainStrategyList().catch(() => {
      this.$emit('update:loading', false);
    });
    this.strategyList = transformDataKey(data);

    if (!this.edit && !this.isClone) {
      this.$emit('update:loading', false);
    }
  }

  //  获取被屏蔽的策略详情
  async handleStrategyInfo(id: number[]): void {
    if (!this.edit && !this.isClone) {
      this.noticeLever = [];
      this.dimensionCondtionInit();
    }
    if (id.length === 0) {
      this.levelOptional = [];
      this.isShowDetail = true;
      this.dimensionCondtionInit();
      return;
    }
    if (id.length === 1) {
      this.$emit('update:loading', true);
      this.isShowDetail = false;
      if (!this.isEdit && !this.isClone) {
        this.noticeLever = [];
      }
      getStrategyV2({ id: id[0] })
        .then(data => {
          this.strategyData = data;
          this.levelOptional = data.detects.map(item => item.level);
          this.isShowDetail = true;
          this.setDimensionConditionParams([data]);
        })
        .catch(() => {
          this.isShowDetail = false;
        })
        .finally(() => {
          this.$emit('update:loading', false);
        });

      await this.getStrategyData();
    } else {
      this.strategyLevelFilter(id);
      this.isShowDetail = true;
    }
    const res = this.strategyList.filter(item => id.indexOf(item.id) > -1).map(item => item.dataTarget);
    this.dataTarget = Array.from(new Set(res));
  }

  /* 只能选择策略存在的级别 */
  async strategyLevelFilter(ids: number[]) {
    this.$emit('update:loading', true);
    const list = await getStrategyListV2({
      conditions: [
        {
          key: 'strategy_id',
          value: ids,
        },
      ],
    })
      .then(res => res.strategy_config_list)
      .catch(() => []);
    const allLevel = list.reduce((pre, cur) => {
      const curLevel = cur.detects.map(item => item.level);
      const res = Array.from(new Set(curLevel.concat(pre)));
      return res;
    }, []);
    this.levelOptional = allLevel;
    this.setDimensionConditionParams(list);
    this.$emit('update:loading', false);
  }

  /* 获取可选维度条件 */
  dimensionCondtionInit() {
    this.dimensionCondition.dimensionList = [];
    this.dimensionCondition.metricMeta = null;
    this.dimensionCondition.conditionList = [];
  }
  async setDimensionConditionParams(strategys: any[]) {
    if (strategys.length) {
      const metricIds = [];
      strategys.forEach(item => {
        item.items?.[0].query_configs.forEach(queryConfig => {
          if (!metricIds.includes(queryConfig.metric_id)) {
            metricIds.push(queryConfig.metric_id);
          }
        });
      });
      const { metric_list: metricList = [] } = await getMetricListV2({
        page: 1,
        page_size: metricIds.length,
        conditions: [{ key: 'metric_id', value: metricIds }],
      }).catch(() => ({}));
      const [metricItem] = metricList;
      if (metricItem) {
        this.dimensionCondition.metricMeta = {
          dataSourceLabel: metricItem.data_source_label,
          dataTypeLabel: metricItem.data_type_label,
          metricField: metricItem.metric_field,
          resultTableId: metricItem.result_table_id,
          indexSetId: metricItem.index_set_id,
        };
      } else {
        this.dimensionCondition.metricMeta = null;
      }
      this.dimensionCondition.dimensionList = (
        metricList.length
          ? metricList.reduce((pre, cur) => {
              const dimensionList = pre
                .concat(cur.dimensions.filter(item => typeof item.is_dimension === 'undefined' || item.is_dimension))
                .filter((item, index, arr) => arr.map(item => item.id).indexOf(item.id, 0) === index);
              return dimensionList;
            }, [])
          : []
      ).filter(item => !['bk_target_ip', 'bk_target_cloud_id', 'bk_topo_node'].includes(item.id));
      this.dimensionCondition.conditionKey = random(8);
    }
  }

  //  提交
  handleSubmit(): void {
    const RNotice: any = this.$refs.notice;
    const RNoticeDate: any = this.$refs.noticeDate;

    // 拿到通知组的数据
    const notice = RNotice.getNoticeConfig();
    const date = RNoticeDate.getDateData();
    if (!this.strategyId || !this.noticeLever.length || !notice || !date) {
      this.rule.strategyId = !this.strategyId.length;
      this.rule.noticeLever = !this.noticeLever.length;
      return;
    }

    const cycle = this.getDateConfig(date);

    const params: IParams = {
      bk_biz_id: this.bizId,
      category: 'strategy',
      dimension_config: {
        id: this.strategyId,
        level: this.noticeLever,
        dimension_conditions: this.dimensionCondition.conditionList
          .map(item => ({
            condition: item.condition,
            key: item.key,
            method: item.method,
            value: item.value,
            name: item.dimensionName,
          }))
          .filter(item => !!item.key),
      },
      description: this.desc,
      shield_notice: this.noticeShow,
      cycle_config: cycle.cycle_config,
      begin_time: cycle.begin_time,
      end_time: cycle.end_time,
    };
    if (this.shieldTarget && !this.isEdit && this.isShowShieldScope) {
      const targetData: { scope_type: string; target: [] } = this.shieldTarget.getTargetData();
      if (targetData?.target?.length) {
        params.dimension_config.scope_type = targetData.scope_type;
        params.dimension_config.target = targetData.target;
      }
    }
    if (this.noticeShow) {
      params.notice_config = notice;
    }
    this.$emit('update:loading', true);
    const routerParams: Location = { name: 'alarm-shield', params: { refresh: 'true' } };
    let text = this.$t('创建屏蔽成功');
    if (this.isEdit) {
      text = this.isEdit && this.$t('编辑屏蔽成功');
    } else if (this.isClone) {
      text = this.isClone && this.$t('克隆屏蔽成功');
    }
    if (this.isEdit) {
      params.id = this.shieldData.id;
      params.level = this.noticeLever;
      editShield(params)
        .then(() => {
          this.$bkMessage({ theme: 'success', message: text });
          this.$router.push(routerParams);
        })
        .finally(() => {
          this.$emit('update:loading', false);
        });
    } else {
      addShield(params)
        .then(() => {
          this.$bkMessage({ theme: 'success', message: text });
          this.$router.push(routerParams);
        })
        .finally(() => {
          this.$emit('update:loading', false);
        });
    }
  }

  //  是否展示通知设置
  handleChangeShow(v): void {
    this.noticeShow = v;
  }
}
</script>

<style lang="scss" scoped>
.alarm-shield-strategy {
  min-height: calc(100vh - 145px);
  padding: 40px 0 36px 30px;
  font-size: 14px;
  color: #63656e;

  .strategy-btn {
    margin-left: 134px;

    .button {
      margin-right: 8px;
    }
  }

  .verify-show {
    /* stylelint-disable-next-line declaration-no-important */
    margin-bottom: 32px !important;
  }

  .strategy-item {
    display: flex;
    align-items: center;
    height: 32px;
    margin-bottom: 20px;

    .item-label {
      position: relative;
      flex: 0 0;
      min-width: 110px;
      margin-right: 24px;
      text-align: right;

      &::before {
        position: absolute;
        top: 2px;
        right: -9px;
        color: #ea3636;
        content: '*';
      }
    }

    &-content {
      flex-grow: 1;

      .checkbox-group {
        margin-right: 32px;
      }

      &.shield-target {
        :deep(.ip-select-right) {
          max-width: 600px;
        }
      }
    }
  }

  .strategy-detail {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;

    .item-label {
      position: relative;
      flex: 0 0;
      min-width: 110px;
      padding-top: 6px;
      margin-right: 24px;
      text-align: right;
    }

    &-content {
      display: flex;
      flex-direction: column;
      width: calc(100vw - 306px);
      min-width: 836px;
      padding: 18px 21px 11px 21px;
      background: #fafbfd;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .column-item {
        display: flex;
        align-items: flex-start;
        min-height: 32px;
        margin-bottom: 10px;
      }

      .item-label {
        min-width: 70px;
        margin-right: 6px;
        text-align: right;
      }

      .item-content {
        word-break: break-all;
        word-wrap: break-word;
      }

      .item-aggDimension {
        height: 32px;
        padding: 7px 12px 9px 12px;
        margin: 0 2px 2px 0;
        font-size: 12px;
        line-height: 16px;
        text-align: center;
        background: #fff;
        border: 1px solid #dcdee5;
        border-radius: 2px;
      }

      .item-aggCondition {
        display: flex;
        flex-wrap: wrap;
        max-width: calc(100vw - 322px);

        .item-blue {
          color: #3a84ff;
        }

        .item-yellow {
          color: #ff9c01;
        }
      }

      &-aggCondition {
        align-items: flex-start;
      }
    }

    .condition-table {
      width: 100%;
      max-width: 836px;
    }
  }

  .strategy-desc,
  .strategy-form {
    display: flex;
    align-items: flex-start;
    height: 62px;
    margin-bottom: 17px;

    .item-label {
      flex: 0 0;
      min-width: 110px;
      padding-top: 6px;
      margin-right: 24px;
      text-align: right;
    }

    &-content {
      .content-desc {
        width: 836px;
      }
    }

    .strategy-btn {
      display: flex;
    }

    :deep(.bk-textarea-wrapper .bk-form-textarea.textarea-maxlength) {
      margin-bottom: 0;
    }

    :deep(.bk-form-textarea) {
      min-height: 60px;
    }
  }

  :deep(.notice-component .set-shield-config-item .item-label) {
    text-align: left;
  }
}
</style>
