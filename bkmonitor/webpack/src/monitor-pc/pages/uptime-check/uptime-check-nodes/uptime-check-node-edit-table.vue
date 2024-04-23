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
  <bk-dialog
    width="850"
    :value="isShow"
    :show-footer="false"
    @after-leave="handleback"
  >
    <div class="host-header">
      <div>{{ $t('选择主机') }}</div>
    </div>
    <div class="host-body">
      <bk-input
        v-model.trim="keyword"
        class="body-search"
        :placeholder="$t('输入')"
        clearable
        right-icon="bk-icon icon-search"
        @change="handleKeywordChange"
      />
      <div class="body-table">
        <bk-table
          ref="hostTableRef"
          height="313"
          :empty-text="$t('无数据')"
          highlight-current-row
          :data="tableData"
          :row-class-name="getRowClassName"
          @row-click="handleRowClick"
        >
          <bk-table-column
            label="IP"
            prop="ip"
          />
          <bk-table-column :label="$t('Agent状态')">
            <template slot-scope="scope">
              <span :style="{ color: agentColorMap[scope.row.agentStatus] }">{{
                agentStatusMap[scope.row.agentStatus]
              }}</span>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('管控区域')"
            prop="cloudName"
          />
        </bk-table>
      </div>
    </div>
  </bk-dialog>
</template>

<script>
export default {
  name: 'UptimeCheckNodeEditTable',
  props: {
    isShow: Boolean,
    ipList: Array,
  },
  data() {
    return {
      keyword: '', // 搜索关键字
      index: -1,
      tableData: [],
      handleKeywordChange: this.debounce(this.filterIP, 200), // 处理搜索关键字改变事件
      agentStatusMap: {
        '-1': this.$t('Agent异常'),
        0: this.$t('Agent正常'),
        2: this.$t('无Agent'),
      },
      agentColorMap: {
        '-1': '#EA3636',
        0: '#2DCB56',
        2: '#C4C6CC',
      },
    };
  },
  mounted() {
    this.tableData = this.ipList;
  },
  methods: {
    handleback() {
      this.$emit('show-change', false);
    },
    getRowClassName({ row }) {
      return row.isBuilt ? 'table-row-disabled' : '';
    },
    /**
     * @desc 处理表格行点击事件
     */
    handleRowClick(row) {
      if (row.isBuilt) {
        this.$refs.hostTableRef.setCurrentRow();
        return false;
      }
      this.tableData = this.ipList;
      this.keyword = '';
      this.$refs.hostTableRef.setCurrentRow();
      this.$emit('configIp', row.ip);
      this.$emit('show-change', false);
    },
    debounce(fn, delay) {
      let timer = null;
      return (...args) => {
        if (timer) {
          clearTimeout(timer);
        }
        timer = setTimeout(() => {
          fn.apply(this, args);
        }, delay);
      };
    },
    filterIP() {
      if (this.keyword.length) {
        const tableData = this.ipList.filter(item => item.ip.includes(this.keyword));
        this.tableData = tableData;
      } else {
        this.tableData = this.ipList;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.host-header {
  width: 120px;
  height: 31px;
  margin-top: -20px;
  margin-bottom: 7px;
  font-size: 24px;
  line-height: 31px;
  color: #444;
}

.host-body {
  width: 802px;

  .body-search {
    margin-bottom: 10px;
  }

  .body-table {
    :deep(.bk-table-row.table-row-disabled) {
      color: #c4c6cc;
      cursor: not-allowed;
      background: #fafbfd;
    }
  }
}
</style>
