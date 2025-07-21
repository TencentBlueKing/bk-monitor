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
  <table
    v-if="legendType === 'table'"
    class="chart-legend"
  >
    <colgroup>
      <col style="width: 100%" />
    </colgroup>
    <thead>
      <tr>
        <th
          v-for="title in headList"
          style="text-align: right"
          :key="title"
          @click="handleSortChange(title)"
        >
          {{ title }}
          <span class="caret-wrapper">
            <i
              class="sort-caret is-asc"
              :class="{ active: sortTitle === title && sort === 1 }"
              @click.self.stop="handleSortChange(title, 1)"
            >
            </i>
            <i
              class="sort-caret is-desc"
              :class="{ active: sortTitle === title && sort === 2 }"
              @click.self.stop="handleSortChange(title, 2)"
            >
            </i>
          </span>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="(item, index) in list"
        :key="index"
      >
        <td
          v-for="title in headList"
          :key="title"
        >
          <div
            :style="{ width: title === 'Min' ? '228px' : '68px' }"
            class="content-wrapper"
          >
            <div
              v-if="title === 'Min'"
              class="legend-metric"
              @click="e => handleLegendEvent(e, 'click', item)"
              @mouseenter="e => handleLegendEvent(e, 'highlight', item)"
              @mouseleave="e => handleLegendEvent(e, 'downplay', item)"
            >
              <span
                :style="{ backgroundColor: item.show ? item.color : '#ccc' }"
                class="metric-label"
              ></span>
              <span
                :style="{ color: item.show ? '#63656e' : '#ccc' }"
                class="metric-name"
                v-bk-overflow-tips="{ placement: 'top', offset: '100, 0' }"
              >
                {{ item.name }}
              </span>
            </div>
            <div class="legend-value">
              {{ item[title.toLocaleLowerCase()] }}
            </div>
          </div>
        </td>
      </tr>
    </tbody>
  </table>
  <div
    v-else
    class="common-legend"
  >
    <div
      v-for="(legend, index) in legendData"
      class="common-legend-item"
      :key="index"
      @click="e => handleLegendEvent(e, 'click', legend)"
      @mouseenter="e => handleLegendEvent(e, 'highlight', legend)"
      @mouseleave="e => handleLegendEvent(e, 'downplay', legend)"
    >
      <span
        :style="{ backgroundColor: legend.show ? legend.color : '#ccc' }"
        class="legend-icon"
      ></span>
      <div
        :style="{ color: legend.show ? '#63656e' : '#ccc' }"
        class="legend-name"
      >
        {{ legend.name }}
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Vue, Prop, Emit, Watch } from 'vue-property-decorator';

import { ILegendItem } from '../options/type-interface';

@Component({
  name: 'chart-legend',
})
export default class ChartLegend extends Vue {
  @Prop({ required: true }) readonly legendData: ILegendItem[];
  @Prop({ default: 'common' }) readonly legendType: 'common' | 'table';
  headList: string[] = ['Min', 'Max', 'Avg'];
  list: ILegendItem[] = [];
  sort = 0;
  sortTitle = '';
  @Watch('legendData', { immediate: true })
  handleLegendDataChange() {
    this.handleSortChange();
  }

  @Emit('legend-event')
  handleLegendEvent(e, actionType: string, item: ILegendItem) {
    let eventType = actionType;
    if (e.shiftKey && actionType === 'click') {
      eventType = 'shift-click';
    }
    return { actionType: eventType, item };
  }
  handleSortChange(title?: 'Avg' | 'Max' | 'Min', sort?) {
    this.sortTitle = title || '';
    if (title) {
      if (typeof sort === 'number') {
        this.sort = sort;
      } else {
        this.sort = (this.sort + 1) % 3;
      }
    }
    if (this.sort === 0 || !title) {
      this.list = this.legendData;
      return;
    }
    const sortId = title.toLocaleLowerCase();
    this.list = this.legendData.slice().sort((a, b) => {
      const [aVal] = a[sortId].match(/\d+\.?\d+/) || [0];
      const [bVal] = b[sortId].match(/\d+\.?\d+/) || [0];
      if (this.sort === 1) {
        return +aVal - +bVal;
      }
      return +bVal - +aVal;
    });
  }
}
</script>

<style lang="scss" scoped>
  .chart-legend {
    min-width: 400px;
    overflow: auto;
    font-size: 12px;
    line-height: 26px;
    color: #63656e;
    border-collapse: collapse;
    user-select: none;

    tr {
      height: 26px;
    }

    thead tr,
    tr:nth-child(even) {
      background: #f5f6fa;
    }

    th {
      padding: 0 12px;
      font-weight: bold;
      white-space: nowrap;

      &:hover {
        cursor: pointer;
        background-color: #f0f1f5;
      }

      .caret-wrapper {
        position: relative;
        top: -1px;
        display: inline-flex;
        flex: 20px 0 0;
        flex-direction: column;
        align-items: center;
        height: 20px;
        margin-left: 4px;
        vertical-align: middle;
        cursor: pointer;

        .sort-caret {
          position: absolute;
          width: 0;
          height: 0;
          margin-left: 4px;
          border: 5px solid transparent;

          &:hover {
            cursor: pointer;
          }

          &.is-asc {
            top: -1px;
            border-bottom-color: #c0c4cc;

            &.active {
              border-bottom-color: #63656e;
            }
          }

          &.is-desc {
            bottom: -1px;
            border-top-color: #c0c4cc;

            &.active {
              border-top-color: #63656e;
            }
          }
        }
      }
    }

    td {
      display: table-cell;
      padding: 0 6px;
      text-align: right;
      white-space: nowrap;

      .content-wrapper {
        display: flex;
        align-items: center;
        text-align: right;

        .legend-metric {
          display: inline-flex;
          align-items: center;
          margin-right: 9px;
          overflow: hidden;
          text-align: left;
          text-overflow: ellipsis;
          white-space: nowrap;

          .metric-label {
            display: inline-block;
            width: 12px;
            min-width: 12px;
            height: 4px;
            margin-right: 6px;
            background-color: violet;
          }

          .metric-name {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          &:hover {
            color: #999;
            cursor: pointer;
          }
        }

        .legend-value {
          margin-left: auto;
          text-align: right;
        }
      }
    }
  }

  .common-legend {
    &-item {
      display: flex;
      align-items: center;
      float: left;
      margin-left: 10px;
      font-size: 12px;
      line-height: 16px;
      white-space: nowrap;

      .legend-icon {
        width: 12px;
        height: 4px;
        margin-right: 6px;
        background-color: violet;
      }

      &:hover {
        color: #999;
        cursor: pointer;
      }
    }
  }
</style>
