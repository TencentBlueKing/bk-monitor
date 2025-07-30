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
  <div
    v-bkloading="{ isLoading: strategyTarget.loading }"
    class="strategy-detail-table detail-content"
  >
    <div v-if="tableData.length">
      <!-- 表格 -->
      <bk-table
        v-if="targetType === 'INSTANCE'"
        :data="tableData"
        :empty-text="$t('无数据')"
        :header-border="false"
        :outer-border="false"
      >
        <bk-table-column
          label="IP"
          min-width="120"
          prop="ip"
        />
        <bk-table-column
          :label="$t('Agent状态')"
          min-width="100"
        >
          <template slot-scope="scope">
            <span
              v-if="scope.row.agentStatus"
              :style="{ color: statusColorMap[scope.row.agentStatus] }"
              >{{ statusMap[scope.row.agentStatus] }}</span
            >
            <span v-else>--</span>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('管控区域')"
          min-width="250"
          prop="bkCloudName"
        >
          <template slot-scope="scope">
            <span>{{ scope.row.bkCloudName || '--' }}</span>
          </template>
        </bk-table-column>
      </bk-table>
      <bk-table
        v-else-if="['DYNAMIC_GROUP'].includes(targetType)"
        :data="tableData"
        :empty-text="$t('无数据')"
      >
        <bk-table-column
          :label="$t('节点名称')"
          min-width="120"
          prop="name"
        />
        <bk-table-column
          :label="$t('主机数')"
          min-width="100"
        >
          <template slot-scope="scope">
            <div class="target-count">
              {{ scope.row.count }}
            </div>
          </template>
        </bk-table-column>
      </bk-table>
      <bk-table
        v-else-if="['TOPO', 'SERVICE_TEMPLATE', 'SET_TEMPLATE'].includes(targetType) || objType === 'SERVICE'"
        :data="tableData"
        :empty-text="$t('无数据')"
      >
        <bk-table-column
          :label="$t('节点名称')"
          min-width="120"
          prop="nodePath"
        />
        <bk-table-column
          v-if="objType === 'SERVICE'"
          :label="$t('实例数')"
          min-width="100"
        >
          <template slot-scope="scope">
            <div class="target-count">
              {{ scope.row.count }}
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          v-else-if="targetType === 'TOPO' || objType === 'HOST'"
          :label="$t('主机数')"
          min-width="100"
        >
          <template slot-scope="scope">
            <div class="target-count">
              {{ scope.row.count }}
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('分类')"
          min-width="250"
        >
          <template slot-scope="scope">
            <div class="monitoring-target">
              <div
                v-for="(item, index) in scope.row.labels"
                :key="index"
                class="target-labels"
              >
                <div class="label-first">
                  {{ item.first }}
                </div>
                <div class="label-second">
                  {{ item.second }}
                </div>
              </div>
            </div>
          </template>
        </bk-table-column>
      </bk-table>
      <div class="table-mask" />
      <!-- 分页 -->
      <!-- <bk-pagination
                key="sdfsdfsdf"
                class="table-pagination"
                align="right"
                size="small"
                pagination-able
                show-total-count
                :current="tableInstance.page"
                :limit="tableInstance.pageSize"
                :count="tableInstance.total"
                :limit-list="tableInstance.pageList"
                @change="handlePageChange"
                @limit-change="handleLimitChange">
            </bk-pagination> -->
    </div>
    <!-- 无数据 -->
    <div
      v-else
      class="table-no-data"
    >
      <i class="icon-monitor icon-tishi" />
      <span class="table-no-data-explain"> {{ $t('暂无任何监控目标') }} </span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'StrategyConfigDetailTable',
  props: {
    // 表格数据
    tableData: {
      type: Array,
      default: () => [],
    },
    targetType: String,
    objType: String,
  },
  data() {
    return {
      statusColorMap: {
        normal: '#2DCB56',
        abnormal: '#EA3636',
        not_exist: '#C4C6CC',
      },
      statusMap: {
        normal: `Agent ${this.$t('正常')}`,
        abnormal: `Agent ${this.$t('异常')}`,
        not_exist: `Agent ${this.$t('未安装')}`,
      },
      strategyTarget: {
        type: '',
        data: [],
        tableData: [],
        loading: false,
      },
      tableInstance: {
        page: 1,
        pageSize: 10,
        pageList: [10, 20, 50, 100],
        total: 0,
      },
    };
  },
  watch: {
    tableData: {
      handler() {
        this.tableData && this.handleTableData(false);
      },
      immediate: true,
    },
  },
  methods: {
    // table数据变更事件
    // biome-ignore lint/style/useDefaultParameterLast: <explanation>
    handleTableData(needLoading = true, time) {
      this.strategyTarget.loading = needLoading;
      const { tableInstance } = this;
      const ret = this.tableData;
      this.tableInstance.total = ret.length;
      this.strategyTarget.tableData = ret.slice(
        tableInstance.pageSize * (tableInstance.page - 1),
        tableInstance.pageSize * tableInstance.page
      );
      if (needLoading) {
        setTimeout(() => {
          this.strategyTarget.loading = false;
        }, time);
      }
    },
    // 分页切换事件
    handlePageChange(page) {
      this.tableInstance.page = page;
      this.handleTableData(false, 50);
    },
    // 每页条数切换事件
    handleLimitChange(limit) {
      this.tableInstance.page = 1;
      this.tableInstance.pageSize = limit;
      this.handleTableData(false, 50);
    },
  },
};
</script>

<style lang="scss" scoped>
.strategy-detail-table {
  position: relative;
  height: 478px;
  margin-top: 18px;

  :deep(.bk-table-body-wrapper) {
    max-height: 433px;
    overflow-x: hidden;
    overflow-y: auto;
  }

  .table-mask {
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 9;
    height: 5px;
    background-color: #fff;
  }

  .target-count {
    width: 59px;
    text-align: right;
  }

  .monitoring-target {
    display: flex;
    flex-wrap: wrap;
    padding: 6px 0 4px 0;
  }

  .target-labels {
    display: flex;
    margin: 0 6px 2px 0;
  }

  .label-first {
    padding: 3px 10px 5px;
    background: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 2px 0 0 2px;
  }

  .label-second {
    padding: 3px 10px 5px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-left: 0;
    border-radius: 0 2px 2px 0;
  }

  .table-pagination {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    height: 60px;
    padding: 0 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-top: 0;

    :deep(.bk-page-count) {
      margin-right: auto;
    }
  }

  .table-no-data {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;

    i {
      margin: 208px 0 13px 0;
      font-size: 28px;
      color: #dcdee5;
    }

    &-explain {
      margin-bottom: 3px;
      font-size: 14px;
    }
  }
}
</style>
