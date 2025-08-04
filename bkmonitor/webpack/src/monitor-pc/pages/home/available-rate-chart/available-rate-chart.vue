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
  <panel-card
    class="available-rate-chart"
    :title="$t('拨测站点可用率趋势对比')"
  >
    <bk-dropdown-menu
      ref="dropdown"
      slot="title"
      :class="['title-setting', { 'title-disable': !series.length && !setList.length }]"
      :disabled="!setList.length"
      trigger="click"
    >
      <div
        slot="dropdown-trigger"
        class="chart-dropdown"
      >
        <svg-icon
          :style="{ color: !series.length && !setList.length ? '#979BA5' : '#3A84FF' }"
          class="icon-setting"
          icon-name="setting"
        />
        <span class="tag-setting"> {{ $t('展示设置') }} </span>
      </div>
      <div
        v-if="setList.length"
        slot="dropdown-content"
        style="margin: -6px 0"
      >
        <ul
          class="bk-dropdown-list title-setting-dropdown"
          @click.stop="triggerCheckedHandle"
        >
          <li
            v-for="item in setList"
            :key="item.id"
            @click.stop="triggerCheckedHandle"
          >
            <label class="bk-form-checkbox bk-checkbox-small check-label-item char-checkbox">
              <input
                v-model="checkedSets"
                class="bk-checkbox"
                :value="item.id"
                type="checkbox"
              />
              <i class="bk-checkbox-text">{{ item.name }}</i>
            </label>
          </li>
        </ul>
        <div
          slot="dropdown-content"
          class="title-setting-footer"
        >
          <span @click="submitHandle"> {{ $t('确定') }} </span>
          <span @click="cancelHandle"> {{ $t('取消') }} </span>
        </div>
      </div>
    </bk-dropdown-menu>
    <monitor-echart
      height="300"
      :colors="[
        '#27C24C',
        '#058DC7',
        '#ED561B',
        '#DDDF00',
        '#24CBE5',
        '#64E572',
        '#FF9655',
        '#FFF263',
        '#6AF9C4',
        '#CAE1FF',
        '#CDCDB4',
        '#FE0000',
        '#C3017C',
      ]"
      :options="newOptions"
      :series="newSeries"
      :set-no-data="false"
      unit="%"
    />
  </panel-card>
</template>

<script>
import MonitorEchart from 'monitor-ui/monitor-echarts/monitor-echarts';

import PanelCard from '../components/panel-card/panel-card';

export default {
  name: 'AvailableRateChart',
  components: {
    MonitorEchart,
    PanelCard,
  },
  props: {
    setList: {
      type: Array,
      required: true,
    },
    checkedList: {
      type: Array,
      default() {
        return [];
      },
    },
    series: {
      type: Array,
      required: true,
    },
    utcoffset: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      checkedSets: [],
    };
  },
  computed: {
    newOptions() {
      return {
        yAxis: {
          axisLine: {
            show: true,
          },
          z: 6,
        },
        xAxis: {
          splitLine: {
            show: true,
            lineStyle: {
              color: '#DCDEE5',
              type: 'dashed',
            },
          },
          axisLine: {
            show: true,
          },
          z: 6,
        },
      };
    },
    newSeries() {
      const markArea = {
        silent: true,
        show: true,
        itemStyle: {
          color: 'rgba(255,246,242,.5)',
          borderWidth: 1,
          borderColor: 'rgba(255,246,242,.5)',
          shadowColor: 'rgba(255,246,242,.5)',
          shadowBlur: 0,
        },
        data: [
          [
            {
              xAxis: 'min',
              yAxis: 0,
            },
            {
              xAxis: 'max',
              yAxis: 80, // this.delegateGet('getModel').getComponent('yAxis').axis.scale._extent[1]
            },
          ],
        ],
        opacity: 0.1,
      };
      return this.series?.length
        ? this.series.map(item => ({
            ...item,
            markArea,
          }))
        : [
            {
              data: [
                [null, 0],
                [null, 100],
              ],
              markArea,
            },
          ];
    },
  },
  watch: {
    checkedList: {
      handler(val) {
        this.checkedSets = val;
      },
    },
  },
  created() {
    this.checkedSets = this.checkedList;
  },
  methods: {
    cancelHandle() {
      this.$refs.dropdown.hide();
      this.checkedSets = this.checkedList;
    },
    submitHandle() {
      this.$emit('update', this.checkedSets);
      this.$refs.dropdown.hide();
    },
    triggerCheckedHandle() {
      // e.stopPropagation()
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

.available-rate-chart {
  .title {
    &-setting {
      float: right;
      width: 250px;
      font-size: $fontSmSize;
      color: #3a84ff;
      text-align: right;

      .chart-dropdown {
        display: flex;
        align-items: center;
        justify-content: flex-end;
      }

      .icon-setting {
        width: 16px;
        height: 16px;
        margin-right: 5px;
        vertical-align: middle;
        color: #3a84ff;
      }

      .tag-setting {
        @include hover();
      }

      &-dropdown {
        max-width: 250px;
        max-height: 250px;
        overflow: auto;
        text-align: left;

        li {
          padding: 0px 10px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;

          .check-label-item {
            min-width: 100%;
            margin: 5px;

            @include hover();

            .bk-checkbox-text {
              font-style: normal;
            }
          }

          .bk-checkbox {
            cursor: pointer;
          }

          &:hover {
            cursor: pointer;
            background: #eaf3ff;
          }
        }
      }

      &-footer {
        display: flex;
        align-items: center;
        justify-content: space-around;
        border-top: 1px solid $defaultBorderColor;

        :nth-child(2) {
          background: #fafbfd;
          border-left: 1px solid $defaultBorderColor;
        }

        span {
          flex: 1;
          height: 30px;
          line-height: 30px;
          text-align: center;

          @include hover();
        }
      }
    }

    &-disable {
      color: #979ba5;

      @include hover(not-allowed);

      .tag-setting {
        @include hover(not-allowed);
      }
    }
  }
}
</style>
