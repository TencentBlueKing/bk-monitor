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
  <div class="main-component-content">
    <p>{{ $t('后台服务器性能指标') }}</p>
    <div
      id="panelBody"
      style="margin-bottom: 10px"
    >
      <template>
        <el-table
          :data="filteredHostDataList"
          @selection-change="selectionChange"
          ref="multipleTable"
          tooltip-effect="dark"
          style="width: 70%"
        >
          <el-table-column
            type="selection"
            width="55"
          />
          <el-table-column
            label="IP"
            align="center"
          >
            <template slot-scope="scope">
              <span class="name-style">
                {{ scope.row.ip }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            :label="$t('CPU使用率')"
            align="center"
          >
            <template
              slot-scope="scope"
              v-if="scope.row['system.cpu.percent']"
            >
              <el-tooltip
                effect="dark"
                placement="right"
              >
                <div slot="content">
                  <div style="min-width: 200px">
                    <p style="color: #fff">
                      {{ $t('单核CPU使用率') }}
                    </p>
                    <div v-if="scope.row['system.cpu.percent.all'].value.length > 0">
                      <div
                        v-for="(item, index) in scope.row['system.cpu.percent.all'].value"
                        :key="index"
                        style="margin: 4px"
                      >
                        <span style="float: left; margin-left: 2px">{{ index + 1 }}</span>
                        <div style="margin-left: 26px">
                          <el-progress
                            :percentage="item"
                            :color="getColor(item)"
                          />
                        </div>
                      </div>
                    </div>
                    <div v-else>
                      <div>{{ $t('无数据') }}</div>
                    </div>
                  </div>
                </div>
                <div style="display: inline-block; cursor: pointer">
                  <el-progress
                    type="circle"
                    :percentage="floatFix(scope.row['system.cpu.percent'].value)"
                    :color="scope.row['system.cpu.percent'].value > 80 ? '#ff6678' : '#75cba8'"
                    :width="40"
                    :stroke-width="3"
                    v-if="scope.row['system.cpu.percent'] && scope.row['system.cpu.percent'].value"
                  />
                  <span v-else> {{ $t('无数据') }} </span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            v-for="(item, index) in displayedMetricsExclude"
            :key="index"
            :render-header="renderHeader"
            align="center"
          >
            <template slot-scope="scope">
              <el-progress
                type="circle"
                :percentage="floatFix(scope.row[item].value)"
                :color="scope.row[item].value > 80 ? '#ff6666' : '#46c37b'"
                :width="40"
                :stroke-width="3"
                v-if="scope.row[item] && scope.row[item].hasOwnProperty('value')"
              />
              <span v-else> {{ $t('无数据') }} </span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </div>
</template>
<script>
// import { mapState } from 'vuex'
import { Progress, Table, TableColumn, Tooltip } from 'element-ui';

import store from '../store/healthz/store';

export default {
  name: 'MoHealthzBackendMetricsView',
  components: {
    ElTable: Table,
    ElTableColumn: TableColumn,
    ElTooltip: Tooltip,
    ElProgress: Progress
  },
  data() {
    return {
      contentCPU: ''
    };
  },
  computed: {
    globalData() {
      return store.state.globalData;
    },
    selectedIPs() {
      return store.state.selectedIPs;
    },
    allIPs() {
      return store.state.allIPs;
    },
    displayedMetrics() {
      return store.state.displayedMetrics;
    },
    displayedMetricsDescription() {
      return store.state.displayedMetricsDescription;
    },
    // ...mapState([
    //     'globalData',
    //     'selectedIPs',
    //     'allIPs',
    //     'displayedMetrics',
    //     'displayedMetricsDescription'
    // ]),
    // 不包括CPU使用率的显示指标，CPU使用率需要特殊指标
    displayedMetricsExclude() {
      const returnData = [];
      for (let i = 0; i < this.displayedMetrics.length; i++) {
        const tmp = this.displayedMetrics[i];
        if (tmp !== 'system.cpu.percent') returnData.push(tmp);
      }
      return returnData;
    },
    // 获取到目前所有的system指标，根据ip去重
    hostDataList() {
      const tmpHostData = {};
      for (let i = 0; i < this.globalData.length; i++) {
        const tmpData = this.globalData[i];
        if (
          tmpData.node_name === 'system'
          && Object.prototype.hasOwnProperty.call(tmpData, 'server_ip')
          && tmpData.server_ip !== ''
        ) {
          if (Object.prototype.hasOwnProperty.call(tmpHostData, tmpData.server_ip)) {
            tmpHostData[tmpData.server_ip][tmpData.metric_alias] = {
              value: tmpData.result.value,
              description: tmpData.description,
              status: tmpData.result.status
            };
          } else {
            tmpHostData[tmpData.server_ip] = {};
          }
        }
      }
      return tmpHostData;
    },
    // 经过allIPs和displayedMetrics过滤的主机列表
    filteredHostDataList() {
      const returnData = [];
      for (let i = 0; i < this.allIPs.length; i++) {
        const tmpIP = this.allIPs[i];
        const tmp = { ip: tmpIP };
        // 循环需要的指标
        for (let j = 0; j < this.displayedMetrics.length; j++) {
          const tmpMetrics = this.displayedMetrics[j];
          tmp[tmpMetrics] = this.hostDataList[tmpIP][tmpMetrics];
          // 如果 CPU使用率在选中的指标里，则需要把各核使用率放进去，以显示细节
          if (tmpMetrics === 'system.cpu.percent') {
            tmp['system.cpu.percent.all'] = this.hostDataList[tmpIP]['system.cpu.percent.all'];
          }
        }
        returnData.push(tmp);
      }
      return returnData;
    }
  },
  watch: {
    filteredHostDataList(newValue) {
      // 数据更新时，更改选中状态
      this.$nextTick(function () {
        this.toggleSelection(newValue);
      });
    }
  },
  methods: {
    // 根据数值大小确定显示颜色
    getColor(value) {
      if (value < 50) return '#75cba8';
      if (value < 80) return '#f7c566';
      if (value <= 100) return '#ff6678';
    },
    // 数字保留一位小数
    floatFix(value) {
      return parseFloat(value.toFixed(1));
    },
    // 用户选择checkbox
    selectionChange(rows) {
      const returnData = [];
      for (let i = 0; i < rows.length; i++) {
        returnData.push(rows[i].ip);
      }
      store.commit('changeSelectedIPs', returnData);
    },
    // 根据对应的数据，选中对应的行
    toggleSelection(rows) {
      if (rows) {
        rows.forEach((row) => {
          this.$refs.multipleTable.toggleRowSelection(row);
        });
      } else {
        this.$refs.multipleTable.clearSelection();
      }
    },
    // 自定义表头
    renderHeader(h, { $index }) {
      const index = $index - 3;
      const metrics = this.displayedMetricsExclude[index];
      // 获取到对应的description作为表头
      return this.displayedMetricsDescription[metrics];
    },
    // 显示当前主机监控窗口
    showHostDialog(ip) {
      store.commit('changeHostPopupVisible', true);
      store.commit('changeServerIP', ip);
    }
  }
};
</script>
<style lang="scss">
@import '../style/healthz';

.el-progress-bar + .el-progress__text {
  color: #fff;
}
</style>
