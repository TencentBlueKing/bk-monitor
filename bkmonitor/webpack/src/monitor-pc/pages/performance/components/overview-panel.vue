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
<!--
 * @Author:
 * @Date: 2021-05-25 19:15:01
 * @LastEditTime: 2021-06-18 10:50:19
 * @LastEditors:
 * @Description:
-->
<template>
  <!-- 分类面板 -->
  <div class="performance-overview">
    <div
      v-for="item in panel.list"
      :key="item.key"
      v-bk-tooltips="{
        content: $t('加载中...'),
        disabled: !loading,
        delay: 500,
      }"
      class="performance-overview-panel"
      :class="{ 'panel-active': panel.active === item.key, disabled: loading }"
      @click="!loading && handlePanelClick(item.key)"
    >
      <span
        class="panel-icon icon-monitor"
        :class="item.icon"
      />
      <div class="panel-desc">
        <div class="panel-desc-num">
          {{ item.num || 0 }}
        </div>
        <div class="panel-desc-name">
          {{ item.name }}
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue, Watch } from 'vue-property-decorator';

import type { IPanel, IPanelStatistics } from '../performance-type';

@Component({ name: 'overview-panel' })
export default class OverviewPanel extends Vue {
  @Prop({ default: '' }) private readonly active!: string;
  @Prop({ default: () => ({}) }) private readonly panelStatistics!: IPanelStatistics;
  @Prop({ default: false, type: Boolean }) private readonly loading!: boolean;

  private panel: IPanel = {
    list: [
      {
        icon: 'icon-gaojing',
        name: window.i18n.t('告警中的主机'),
        key: 'unresolveData',
        num: 0,
      },
      {
        icon: 'icon-CPU',
        name: `${window.i18n.t('CPU使用率超80%')}`,
        key: 'cpuData',
        num: 0,
      },
      {
        icon: 'icon-neicun',
        name: `${window.i18n.t('应用内存使用率超80%')}`,
        key: 'menmoryData',
        num: 0,
      },
      {
        icon: 'icon-cipan',
        name: `${window.i18n.t('磁盘空间使用率超80%')}`,
        key: 'diskData',
        num: 0,
      },
    ],
    active: this.active,
  };
  created() {
    this.panel.list.forEach(item => (item.num = this.panelStatistics[item.key]));
  }

  @Watch('active')
  private handleActiveChange(v) {
    this.panel.active = v;
  }

  @Watch('panelStatistics')
  private handlePanelStatisticsChange(statistics: IPanelStatistics) {
    this.panel.list.forEach(item => {
      item.num = statistics[item.key];
    });
  }

  @Emit('click')
  private handlePanelClick(key: string) {
    this.panel.active = this.panel.active === key ? '' : key;
    return this.panel.active;
  }
}
</script>
<style lang="scss" scoped>
@import '../../../theme/index.scss';

.performance-overview {
  display: flex;
  flex-direction: row;
  height: 76px;

  &-panel {
    position: relative;
    display: flex;
    flex: 1 1 315px;
    align-items: center;
    justify-content: flex-start;
    min-width: 200px;
    height: 100%;
    padding-left: 45px;
    background: #fff;
    border: 1px solid #dcdee5;

    @include hover();

    &.disabled {
      cursor: not-allowed;
    }

    &:not(:nth-child(1)) {
      border-left: 0;
    }

    .panel-icon {
      font-size: 32px;
      color: #c4c6cc;
    }

    .panel-desc {
      margin: 0 15px;

      &-num {
        font-size: 16px;
        font-weight: 600;
        line-height: 22px;
        color: #000;
      }

      &-name {
        font-size: 12px;
        line-height: 16px;
        color: #979ba5;
      }
    }

    &.panel-active {
      .panel-icon {
        color: $primaryFontColor;
      }

      &::after {
        position: absolute;
        right: 0;
        bottom: -1px;
        left: 0;
        height: 2px;
        content: '';
        background: $primaryFontColor;
      }
    }
  }
}
</style>
