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
  <div class="content-retrieval">
    <div
      class="retrieval-title"
      @click="handleChangeStatus"
    >
      <i
        class="icon-monitor icon-arrow-down"
        :class="{ 'retrieval-active': !queryConfig.show }"
      />{{ queryConfig.name }}
    </div>
    <transition
      @after-enter="afterEnter"
      @after-leave="afterLeave"
      @before-enter="beforeEnter"
      @before-leave="beforeLeave"
      @enter="enter"
      @leave="leave"
    >
      <template v-if="metricDetail || queryConfigItem.data_source_label === 'prometheus'">
        <div v-show="queryConfig.show">
          <div v-if="queryConfig.data.query_configs.length === 1">
            <template v-if="queryConfigItem.data_source_label !== 'prometheus'">
              <div class="retrieval-content">
                <div class="retrieval-content-row">
                  <span class="row-label">{{ $t('监控对象') }} : </span>
                  <span class="row-content">{{
                    metricDataList[0] && metricDataList[0]['result_table_label_name']
                  }}</span>
                </div>
                <div class="retrieval-content-row">
                  <span class="row-label">{{ $t('监控指标') }} : </span>
                  <span class="row-content">{{ queryConfigItem.metrics[0].field }}</span>
                </div>
                <div class="retrieval-content-row">
                  <span
                    style="padding-top: 3px"
                    class="row-label"
                    >{{ $t('监控条件') }} :
                  </span>
                  <span class="row-content">
                    <div class="item-agg-condition">
                      <div
                        v-for="(item, index) in getWhereData(queryConfigItem.where)"
                        :style="{ color: aggConditionColorMap[item], 'font-weight': aggConditionFontMap[item] }"
                        class="item-agg-dimension mb-2"
                        :key="index"
                      >
                        {{ Array.isArray(item) ? item.join(' , ') : item }}
                      </div>
                    </div>
                  </span>
                </div>
              </div>
              <div class="retrieval-content-convergence">
                <div class="convergence-label">
                  {{ $t('汇聚方法') }}
                </div>
                <bk-select
                  v-model="queryConfigItem.metrics[0].method"
                  :clearable="false"
                  :popover-options="{ appendTo: 'parent' }"
                  searchable
                  @change="handleMethodChange"
                >
                  <bk-option
                    v-for="option in metricDetail.aggMethodList"
                    :id="option.id"
                    :key="option.id"
                    :name="option.name"
                  />
                </bk-select>
              </div>
              <div class="retrieval-content-convergence">
                <div class="convergence-label">
                  {{ $t('汇聚周期') }}
                </div>
                <cycle-input
                  v-model="queryConfigItem.interval"
                  append-to="parent"
                  @change="handleIntervalChange"
                />
              </div>
            </template>
            <template v-else>
              <div class="promql-content">
                <div class="edit-wrap">
                  <promql-editor
                    :min-height="80"
                    :value="queryConfigItem.promql"
                    @blur="handlePromqlDataCodeBlur"
                    @change="handlePromqlDataCodeChange"
                  />
                </div>
                <div class="step-wrap">
                  <bk-input
                    class="step-input"
                    :value="queryConfigItem.agg_interval"
                    @blur="handleSourceStepBlur"
                    @change="handleSourceStepChange"
                  >
                    <div
                      class="step-input-prepend"
                      slot="prepend"
                    >
                      <span>Step</span>
                      <span
                        class="icon-monitor icon-hint"
                        v-bk-tooltips="{
                          content: $t('数据步长'),
                          placements: ['top'],
                        }"
                      />
                    </div>
                  </bk-input>
                </div>
              </div>
            </template>
          </div>
          <div v-else>
            <div class="retrieval-content">
              <div class="retrieval-content-row">
                <span class="row-label">{{ $t('表达式') }} : </span>
                <span class="row-content">{{ queryConfigdata.expression }}</span>
              </div>
              <div
                v-for="(item, index) in queryConfigdata.query_configs"
                class="query-configs-metric"
                :key="index"
              >
                <div class="retrieval-content-row">
                  <span class="row-label">{{ item.metrics[0].alias }}</span>
                </div>
                <div class="retrieval-content-row">
                  <span class="row-label">{{ $t('监控对象') }} : </span>
                  <span class="row-content">{{
                    metricDataList[index] ? metricDataList[index]['result_table_label_name'] : '--'
                  }}</span>
                </div>
                <div class="retrieval-content-row">
                  <span class="row-label">{{ $t('监控指标') }} : </span>
                  <span class="row-content">{{ item.metrics[0].field }}</span>
                </div>
                <div class="retrieval-content-row">
                  <span class="row-label">{{ $t('监控条件') }} : </span>
                  <span class="row-content">
                    <div class="item-agg-condition">
                      <div
                        v-for="(condition, i) in getWhereData(item.where)"
                        :style="{
                          color: aggConditionColorMap[condition],
                          'font-weight': aggConditionFontMap[condition],
                        }"
                        class="item-agg-dimension mb-2"
                        :key="i"
                      >
                        {{ Array.isArray(condition) ? condition.join(' , ') : condition }}
                      </div>
                    </div>
                  </span>
                </div>
                <div class="retrieval-content-row">
                  <span class="row-label">{{ $t('汇聚方法') }} : </span>
                  <span class="row-content">{{ item.metrics[0].method }}</span>
                </div>
                <div class="retrieval-content-row">
                  <span class="row-label">{{ $t('汇聚周期') }} : </span>
                  <span class="row-content">{{ handleUnitString(+item.interval || 0) }}</span>
                </div>
              </div>
            </div>
          </div>
          <div
            v-for="item in groupList"
            :key="JSON.stringify(item.name)"
          >
            <convergence-options-item
              class="retrieval-convergence"
              v-show="item.checked"
              :default-value="(item && item.defaultValue) || ''"
              :groupby-list="() => getGroupByList(item.id)"
              :has-close-icon="!item.disabled"
              :id="item.id"
              :is-default="item.disabled"
              :title="item.name"
              @checked-change="handleCheckedChange"
              @delete-dimension="handleDeleteDimension(item.id)"
            />
          </div>
          <div
            v-if="queryConfigItem.data_source_label !== 'prometheus'"
            class="add-convergence"
          >
            <custom-select
              :searchable="false"
              :value="groupChecked"
              :z-index="5000"
              multiple
              @change="handleWhereSelected"
              @showChange="handleShowChange"
            >
              <span
                class="add-convergence-trigger"
                slot="target"
              >
                <i class="icon-monitor icon-mc-plus-fill" />
                {{ $t('添加条件') }}
              </span>
              <bk-option
                v-for="item in groupList"
                class="add-con-option"
                :disabled="item.disabled"
                :id="item.id"
                :key="item.id"
                :name="item.name"
              />
            </custom-select>
          </div>
        </div>
      </template>
    </transition>
    <monitor-dialog
      :before-close="handleBackStep"
      :title="$t('添加条件')"
      :value="isdialogShow"
      @on-confirm="handleAddDimension"
    >
      <bk-checkbox-group v-model="groupChecked">
        <bk-checkbox
          v-for="item in groupList"
          class="dialog-checkbox"
          :disabled="item.disabled"
          :key="item.id"
          :value="item.id"
        >
          {{ item.name }}
        </bk-checkbox>
      </bk-checkbox-group>
    </monitor-dialog>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Mixins, Prop, Watch } from 'vue-property-decorator';

import { dimensionUnifyQuery } from 'monitor-api/modules/grafana';
import { getMetricListV2 } from 'monitor-api/modules/strategies';
import { deepClone } from 'monitor-common/utils/utils';
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';

import { strategyMapMixin } from '../../common/mixins';
import CustomSelect from '../../components/custom-select/custom-select';
import CycleInput from '../../components/cycle-input/cycle-input';
import { secToString } from '../../components/cycle-input/utils';
import PromqlEditor from '../../components/promql-editor/promql-editor';
// import { handleTimeRange } from '../../utils/index';
import { handleTransformToTimestamp } from '../../components/time-range/utils';
import { CONDITION_METHOD_LIST } from '../../constant/constant';
import collapseMixin from '../../mixins/collapseMixin';
import { MetricDetail } from '../strategy-config/strategy-config-set-new/typings';
import ConvergenceOptionsItem from './convergence-options-item.vue';

@Component({
  name: 'query-criteria-item',
  components: {
    ConvergenceOptionsItem,
    MonitorDialog,
    CycleInput,
    CustomSelect,
    PromqlEditor,
  },
})
export default class QueryCriteriaItem extends Mixins(collapseMixin, strategyMapMixin) {
  @Prop({ required: true, type: Object, default: () => ({}) }) readonly queryConfig: any;
  @Prop(Number) readonly groupIndex: number;
  @Prop({ type: Object }) compareValue: any;

  isdialogShow = false;
  beforeChangeCheckedDimensions = [];
  checkedDimensions = [];
  metricDataList: any[] = [];
  groupBySelectList = [];
  aggCondition = [];
  intervalList = [
    { id: 60, name: '1min' },
    { id: 120, name: '2min' },
    { id: 300, name: '5min' },
  ];
  groupList = [];
  groupChecked = [];

  queryConfigItem: any = {};
  queryConfigdata: any = null;
  metricDetail = null;
  secToString: Function = secToString;

  /* queryConfigs内的where条件 */
  whereChecked = [];

  get dimensionsFilterList() {
    return this.metricDataList.reduce((total, cur) => {
      for (const set of cur.dimensions) {
        const isExit = total.find(re => re.id === set.id);
        if (isExit) continue;
        if ('is_dimension' in set) {
          set.is_dimension && total.push(set);
        } else {
          total.push(set);
        }
      }
      return total;
    }, []);
  }

  @Watch('queryConfig', { immediate: true, deep: true })
  queryConfigChange() {
    this.queryConfigItem = deepClone(this.queryConfig.data.query_configs[0]);
    this.queryConfigdata = deepClone(this.queryConfig.data);
  }

  created() {
    this.checkedDimensions = this.queryConfigItem.group_by || [];
    this.groupChecked = this.queryConfigItem.group_by || [];
    this.whereChecked = this.queryConfigItem.where || [];
    this.beforeChangeCheckedDimensions = this.queryConfigItem.group_by || [];
    if (this.queryConfigItem.data_source_label !== 'prometheus') {
      this.getMetricData();
    }
  }

  handleMethodChange(v) {
    this.$emit('query-change', v, 'method', this.groupIndex);
  }

  handleIntervalChange(v) {
    this.$emit('query-change', v, 'interval', this.groupIndex);
  }

  /**
   * @description: 获取指标信息
   */
  async getMetricData() {
    const promiseList = this.queryConfigdata.query_configs.map(item => {
      const isLogSearch = !!item?.index_set_id;
      const dataSourceType = item?.data_source_label || '';
      return getMetricListV2({
        data_source_label: Array.isArray(dataSourceType) ? dataSourceType : [dataSourceType],
        data_type_label: item?.data_type_label,
        page: 1,
        page_size: 10,
        result_table_label: item?.result_table_label,
        conditions: isLogSearch
          ? [{ key: 'index_set_id', value: item?.index_set_id }]
          : [
              { key: 'metric_field', value: [item?.metrics[0].field] },
              { key: 'result_table_id', value: [item?.table] },
            ],
        search_value: '',
        tag: '',
      })
        .then(data => data?.metric_list?.[0] || {})
        .catch(err => {
          console.log(err);
          return null;
        });
    });
    const res = await Promise.all(promiseList);
    this.metricDetail = new MetricDetail(res[0] as any);
    this.metricDataList = res;
    if (this.metricDataList[0]?.dimensions) {
      this.groupList = this.dimensionsFilterList
        .map(item => {
          const isDefault = this.groupChecked.some(set => item.id === set);
          let defaultValue = '';
          for (const w of this.whereChecked) {
            if (w.key === item.id) {
              defaultValue = w.value?.[0] || '';
              if (!isDefault) {
                this.groupChecked.push(item.id);
              }
              break;
            }
          }
          return {
            ...item,
            disabled: isDefault,
            order: isDefault ? 0 : 1,
            checked: isDefault || !!defaultValue || false,
            defaultValue,
          };
        })
        .sort((a, b) => a.order - b.order);
    } else {
      this.groupList = [];
    }
    return res;
  }

  handlePromqlDataCodeChange(val) {
    this.queryConfigItem.promql = val;
  }
  handlePromqlDataCodeBlur() {
    this.$emit('query-change', this.queryConfigItem.promql, 'promql', this.groupIndex);
  }

  /**
   * @description: 处理条件展示
   * @return {*}
   */
  getWhereData(where = []) {
    const result = [];
    where.forEach(item => {
      if (item.condition) {
        result.push(item.condition.toLocaleUpperCase());
      }
      const method = CONDITION_METHOD_LIST.find(set => set.id === item.method);
      result.push(item.key);
      result.push(method?.name || item.method);
      result.push(item.value.map(v => v || `-${window.i18n.t('空')}-`));
    });
    return result;
  }

  handleAddDimension() {
    this.groupList.forEach(item => {
      item.checked = item.disable || this.groupChecked.some(id => id === item.id);
    });
    this.handleBackStep();
  }

  handleDeleteDimension(key) {
    this.groupChecked = this.groupChecked.filter(id => id !== key);
    this.groupList.forEach(item => {
      item.checked = item.disabled || this.groupChecked.some(id => id === item.id);
    });
    const res = {};
    res[key] = 'all';
    this.$emit('checked-change', this.groupIndex, res);
  }

  async getGroupByList(field) {
    const { query_configs: queryConfig, ...otherParams } = this.queryConfig.data;
    const params = {
      query_configs: queryConfig.map(item => {
        if (!item.index_set_id) delete item.index_set_id;
        return item;
      }),
      ...otherParams,
    };
    const timerange = this.getTimerange();
    const resList = await dimensionUnifyQuery({
      dimension_field: field,
      ...params,
      ...timerange,
    })
      .then(varList => {
        const result = Array.isArray(varList) ? varList.map(item => ({ name: item.label, id: item.value })) : [];
        return result;
      })
      .catch(err => {
        console.log(err);
        return [];
      });
    return resList;
  }

  //  获取图表时间范围
  getTimerange() {
    const { tools } = this.compareValue;
    // const res = handleTimeRange(tools.timeRange);
    const [startTime, endTime] = handleTransformToTimestamp(tools.timeRange);
    return {
      start_time: startTime,
      end_time: endTime,
    };
  }

  handleOpenDialog() {
    this.isdialogShow = true;
  }

  handleBackStep() {
    this.isdialogShow = false;
  }

  handleCheckedChange(value) {
    this.$emit('checked-change', this.groupIndex, value, this.metricDataList);
  }

  @Emit('change-status')
  handleChangeStatus() {
    return this.queryConfig.name;
  }

  /**
   * @description: 处理周期的展示
   * @param {number} value 秒
   * @return {string}
   */
  handleUnitString(value) {
    const data = secToString({ value, unit: '' });
    return `${data.value} ${data.unitEn || 'm'}`;
  }

  /** 选中的条件 */
  handleWhereSelected(val) {
    this.groupChecked = val;
  }
  /** 弹层收起添加条件 */
  handleShowChange(show) {
    if (!show) {
      this.handleAddDimension();
    }
  }

  handleSourceStepChange(value: string) {
    this.queryConfigItem.agg_interval = value;
  }

  handleSourceStepBlur() {
    this.$emit('query-change', this.queryConfigItem.agg_interval, 'step', this.groupIndex);
  }
}
</script>

<style lang="scss" scoped>
.content-retrieval {
  border-bottom: 1px solid #f0f1f5;

  .retrieval-title {
    display: flex;
    align-items: center;
    height: 40px;
    padding: 0 14px;
    color: #313238;
    cursor: pointer;

    .icon-arrow-down {
      margin-right: 6px;
      font-size: 24px;
      color: #63656e;
      transition: 0.3s;
    }

    .retrieval-active {
      transform: rotate(-90deg);
      transition: 0.3s;
    }
  }

  .retrieval-content {
    padding: 0 30px 8px 30px;

    &-row {
      display: flex;
      min-height: 20px;
      margin-bottom: 10px;
      line-height: 20px;

      .row-label {
        min-width: 60px;
        margin-right: 12px;
        color: #979ba5;
      }

      .row-content {
        line-height: 20px;
        word-break: break-all;

        .item-agg-dimension {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 24px;
          margin: 0 4px 2px 0;
          line-height: 16px;
          text-align: left;
          border-radius: 2px;
        }

        .item-agg-condition {
          display: flex;
          flex-wrap: wrap;
          text-align: left;
          background: #fff;
        }
      }
    }

    .query-configs-metric {
      padding: 10px;
      background-color: #f0f1f5;
      border-radius: 3px;

      &:not(:last-child) {
        margin-bottom: 8px;
      }

      .retrieval-content-row {
        margin-bottom: 5px;

        .row-content {
          .item-agg-condition {
            background-color: initial;

            .retrieval-content {
              min-height: 18px;
            }
          }
        }
      }
    }
  }

  .promql-content {
    .edit-wrap {
      position: relative;
      margin: 0 24px;
    }

    .step-wrap {
      display: block;
      margin: 10px 0 10px 24px;

      .step-input {
        width: 205px;

        .step-input-prepend {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 96px;
          height: 100%;
          font-size: 12px;

          .icon-hint {
            margin-left: 8px;
          }
        }
      }
    }
  }

  .retrieval-content-convergence {
    width: 320px;
    height: 73px;
    padding: 5px 10px 10px 10px;
    margin: 0 auto;

    .convergence-label {
      margin-bottom: 6px;
    }
  }

  .retrieval-convergence {
    margin: 0 auto;
  }

  .add-convergence {
    padding: 0 28px;
    margin-bottom: 9px;

    .add-convergence-trigger {
      display: flex;
      align-items: center;
      color: #3a84ff;
      cursor: pointer;
    }

    .icon-mc-plus-fill {
      margin-right: 5px;
      font-size: 14px;
    }
  }

  .dialog-checkbox {
    padding-right: 16px;
    margin-top: 8px;
  }
}
</style>
<style lang="scss">
.bk-options {
  .add-con-option {
    &.is-selected {
      &.is-disabled {
        color: #63656e;
        background-color: #f5f7fa;
      }
    }
  }
}
</style>
