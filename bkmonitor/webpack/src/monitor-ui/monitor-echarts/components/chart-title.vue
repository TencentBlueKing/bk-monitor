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
  <div class="title-wrapper">
    <div
      ref="chartTitle"
      class="chart-title"
      tabindex="0"
      @click="handleShowMenu"
      @blur="showMenu = false"
    >
      <div class="main-title">
        <i
          v-if="hasMetric"
          v-bk-tooltips="alarmTips"
          class="icon-monitor icon-inform alarm-icon"
          :class="`status-${alarmStatus.status + 1}`"
          @click.self.stop="handleAlarmClick"
        />
        <div class="title-name">
          {{ title }}
        </div>
        <span
          v-if="hasMetric && extendMetricData.collect_interval"
          class="title-interval"
          >{{ extendMetricData.collect_interval }}m</span
        >
        <i
          v-show="showMore"
          v-if="hasMetric"
          class="icon-monitor icon-tishi tips-icon"
          @mouseenter.self.stop="handleShowTips"
          @mouseleave.self.stop="handleHideTips"
        />
        <i
          v-show="showMore"
          :style="{ marginLeft: hasMetric ? '0px' : 'auto' }"
          class="icon-monitor icon-mc-more more-icon"
        />
      </div>
      <div
        v-if="subtitle"
        :style="{ marginLeft: hasMetric ? '20px' : '0px' }"
        class="sub-title"
      >
        {{ subtitle }}
      </div>
    </div>
    <chart-menu
      v-show="showMenu"
      :list="menuList"
      :style="{ left: menuLeft + 'px' }"
      @menu-click="handleMenuClick"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue } from 'vue-property-decorator';

import ChartMenu from './chart-menu.vue';

interface IExtendMetricData {
  collect_config?: string;
  collect_interval?: number;
  data_source_label?: string;
  data_type_label?: string;
  description?: string;
  metric_field?: string;
  metric_field_name?: string;
  metric_id?: string;
  related_id?: string;
  related_name?: string;
  result_table_id?: string;
  result_table_label?: string;
  result_table_name?: string;
  extend_fields?: {
    bk_data_id?: string;
    scenario_name?: string;
    storage_cluster_name?: string;
  };
}
@Component({
  name: 'chart-title',
  components: {
    ChartMenu,
  },
})
export default class ChartTitle extends Vue {
  @Prop({ default: '' }) title: string;
  @Prop({ default: '' }) subtitle: string;
  @Prop({ default: () => ({ status: 0, number: 0 }) })
  alarmStatus: { alert_number: number; status: number; strategy_number: number };
  @Prop({
    default() {
      return {};
    },
  })
  extendMetricData: IExtendMetricData;
  @Prop({ default: '3' }) collectInterval: string;
  @Prop({ default: false }) showMore: boolean;
  @Prop({ default: () => [] }) menuList: string[];
  @Ref('chartTitle') chartTitleRef: HTMLDivElement;
  private showMenu = false;
  private menuLeft = 0;
  private popoverInstance = null;
  get alarmTips() {
    const { status, alert_number, strategy_number } = this.alarmStatus;
    let content = '';
    switch (status) {
      case 1:
        content = this.$t('已设置 {0} 个策略', [strategy_number]);
        break;
      case 2:
        content = this.$t('告警中，告警数量：{0}', [alert_number]);
        break;
      default:
      case 0:
        content = this.$t('未配置策略');
        break;
    }
    return {
      content,
      showOnInit: false,
      trigger: 'mouseenter',
      placements: ['top'],
      allowHTML: false,
    };
  }
  get hasMetric() {
    return !!this.extendMetricData?.metric_field;
  }
  handleShowMenu(e: MouseEvent) {
    this.showMenu = !this.showMenu;
    const rect = this.chartTitleRef.getBoundingClientRect();
    this.menuLeft = rect.width - 185 < e.layerX ? rect.width - 185 : e.layerX;
  }
  handleMenuClick(item) {
    this.showMenu = false;
    this.$emit('menu-click', item);
  }
  @Emit('alarm-click')
  handleAlarmClick() {
    return this.alarmStatus;
  }
  handleShowTips(e: MouseEvent) {
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.handleTips(),
      trigger: 'manual',
      theme: 'tippy-metric',
      arrow: true,
      placement: 'auto',
      boundary: 'window',
    });
    this.popoverInstance?.show(100);
  }
  handleHideTips() {
    this.popoverInstance?.hide(0);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }
  // 卡片内容展示设置 根据不同的数据来源展示不同的数据
  handleTips() {
    const data = this.extendMetricData;
    const curActive = `${data.data_source_label}_${data.data_type_label}`;
    const options = [
      // 公共展示项
      { val: data.metric_field, label: this.$t('指标名') },
      { val: data.metric_field_name, label: this.$t('指标别名') },
    ];
    const elList = {
      bk_monitor_time_series: [
        // 监控采集
        ...options,
        { val: data.related_id, label: this.$t('插件ID') },
        { val: data.related_name, label: this.$t('插件名') },
        { val: data.result_table_id, label: this.$t('分类ID') },
        { val: data.result_table_name, label: this.$t('分类名') },
        { val: data.description, label: this.$t('含义') },
      ],
      bk_log_search_time_series: [
        // 日志采集
        ...options,
        { val: data.related_name, label: this.$t('索引集') },
        { val: data.result_table_id, label: this.$t('索引') },
        { val: data.extend_fields.scenario_name, label: this.$t('数据源类别') },
        { val: data.extend_fields.storage_cluster_name, label: this.$t('数据源名') },
      ],
      bk_data_time_series: [
        // 数据平台
        ...options,
        { val: data.result_table_id, label: this.$t('表名') },
      ],
      custom_time_series: [
        // 自定义指标
        ...options,
        { val: data.extend_fields.bk_data_id, label: this.$t('数据ID') },
        { val: data.result_table_name, label: this.$t('数据名') },
      ],
      bk_monitor_log: [...options],
    };
    // 拨测指标融合后不需要显示插件id插件名
    const resultTableLabel = data.result_table_label;
    const relatedId = data.related_id;
    if (resultTableLabel === 'uptimecheck' && !relatedId) {
      const list = elList.bk_monitor_time_series;
      elList.bk_monitor_time_series = list.filter(
        item => item.label !== this.$t('插件ID') && item.label !== this.$t('插件名')
      );
    }
    const curElList = elList[curActive] || [...options];
    let content =
      curActive === 'bk_log_search_time_series'
        ? `<div class="item">${data.related_name}.${data.metric_field}</div>\n`
        : `<div class="item">${data.result_table_id}.${data.metric_field}</div>\n`;
    if (data.collect_config) {
      const collectorConfig = data.collect_config
        .split(';')
        .map(item => `<div>${item}</div>`)
        .join('');
      curElList.splice(0, 0, { label: this.$t('采集配置'), val: collectorConfig });
    }

    if (data.metric_field === data.metric_field_name) {
      const index = curElList.indexOf(item => item.label === this.$t('指标别名'));
      curElList.splice(index, 1);
    }
    curElList.forEach(item => {
      content += `<div class="item"><div>${item.label}：${item.val || '--'}</div></div>\n`;
    });
    return content;
  }
}
</script>
<style lang="scss" scoped>
$alarmColor: #dcdee5 #63656e #ea3636;

.title-wrapper {
  flex: 1;
  width: 100%;

  .chart-title {
    padding: 5px 10px;
    margin-left: -10px;
    font-size: 12px;
    // background-color: white;
    color: #63656e;
    border-radius: 2px;

    .main-title {
      display: flex;
      flex-wrap: nowrap;
      align-items: center;
      font-weight: 700;

      .alarm-icon {
        z-index: 9;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 14px;
        height: 14px;
        margin-right: 6px;
        font-size: 14px;
        color: #dcdee5;

        @for $i from 1 through 3 {
          &.status-#{$i} {
            /* stylelint-disable-next-line function-no-unknown */
            color: nth($alarmColor, $i);
          }
        }

        &::before {
          height: 14px;
        }
      }

      .title-name {
        display: flex;
        align-items: center;
        height: 20px;
        overflow: hidden;
        line-height: 20px;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .title-interval {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 16px;
        padding: 0 2px;
        margin-left: 6px;
        font-size: 12px;
        font-weight: normal;
        color: #63656e;
        border: 1px solid rgba(151, 155, 165, 0.3);
        border-radius: 2px;
      }

      .tips-icon,
      %tips-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 14px;
        height: 14px;
        margin-right: 10px;
        margin-left: auto;
        font-size: 14px;
        color: #979ba5;

        &::before {
          height: 14px;
        }
      }

      .more-icon {
        margin-right: 0;
        margin-left: 0;

        @extend %tips-icon;
      }
    }

    &:hover {
      cursor: pointer;
      background-color: #f4f6fa;

      .main-title {
        color: black;

        .more-icon {
          color: #3a84ff;
          // display: flex;
        }
      }
    }

    .sub-title {
      height: 16px;
      margin-left: 20px;
      overflow: hidden;
      line-height: 16px;
      color: #979ba5;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}
</style>
