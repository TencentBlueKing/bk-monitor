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
    :value="conf.isShow"
    :show-footer="false"
    @input="close"
    @after-leave="handleAfterLeaveChange"
  >
    <div class="host-header">
      <div class="host-header-title">
        {{ title }}
      </div>
    </div>
    <div class="host-body">
      <bk-input
        class="body-search"
        :placeholder="$t('输入')"
        clearable
        right-icon="bk-icon icon-search"
        v-model.trim="keyword"
        @input="handleKeywordChange"
        ref="selectInput"
      />
      <div
        class="body-table"
        v-bkloading="{ isLoading: isLoading }"
      >
        <bk-table
          class="select-host-table-wrap"
          ref="hostTableRef"
          :height="313"
          :virtual-render="tableData.length ? true : false"
          highlight-current-row
          :data="tableData"
          :row-class-name="getRowClassName"
          @row-click="handleRowClick"
        >
          <empty-status
            :type="emptyStatusType"
            slot="empty"
            @operation="handleOperation"
          />
          <bk-table-column
            label="IP"
            prop="ip"
          />
          <bk-table-column
            show-overflow-tooltip
            label="IPv6"
            prop="ipv6"
          />
          <bk-table-column
            :label="$t('系统')"
            prop="osName"
          />
          <bk-table-column :label="$t('Agent状态')">
            <template slot-scope="scope">
              <span
                :class="scope.row.agentStatus === 0 ? 'success' : 'error'"
                v-bk-tooltips="{
                  content: `${scope.row.agentStatusName}${$t('不能进行调试')}`,
                  boundary: 'window',
                  disabled: scope.row.agentStatus === 0,
                  allowHTML: false
                }"
              >{{ scope.row.agentStatusName }}</span>
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
import { hostAgentStatus } from '../../../../../../monitor-api/modules/commons';
import { isFullIpv6, padIPv6 } from '../../../../../../monitor-common/utils/ip-utils';
import { deepClone } from '../../../../../../monitor-common/utils/utils';
import EmptyStatus from '../../../../../components/empty-status/empty-status';

export default {
  name: 'SelectHost',
  components: {
    EmptyStatus
  },
  props: {
    conf: {
      type: Object,
      default: () => ({
        isShow: false,
        id: '',
        param: {}
      })
    },
    getHost: Function,
    filter: Function
  },
  data() {
    return {
      isLoading: false,
      keyword: '', // 搜索关键字
      host: {
        index: -1
      }, // 主机信息
      index: -1,
      tableData: [],
      allHost: [],
      handleKeywordChange: this.debounce(this.filterHost, 200), // 处理搜索关键字改变事件
      emptyStatusType: 'empty'
    };
  },
  computed: {
    title() {
      return this.conf.param?.osType === 'windows'
        ? this.$t('选择{0}调试主机', ['Windows'])
        : this.$t('选择{0}调试主机', ['Linux']);
    }
  },
  watch: {
    'conf.param': {
      handler(val) {
        this.host = val;
        this.requestHost(this.conf.id);
      },
      deep: true
    },
    'conf.isShow': {
      handler(val) {
        if (val) {
          this.handleGetData();
          setTimeout(() => {
            this.$refs.selectInput.focus();
          }, 300);
        }
      }
    }
  },
  mounted() {
    this.handleGetData();
  },
  methods: {
    handleGetData() {
      if (this.getHost) {
        this.isLoading = true;
        this.getHost()
          .then((data) => {
            this.allHost = data.map(item => ({
              osType: item.bk_os_type, // 系统类型
              agentStatus: item.agent_status, // Agent 状态代码
              agentStatusName: item.agent_status_display, // Agent 状态名称
              osName: item.bk_os_name, // 系统名称
              supplierId: item.bk_supplier_account,
              ip: item.bk_host_innerip, // IP
              cloudId: item.bk_cloud_id, // cloudId
              bk_biz_id: item.bk_biz_id,
              bk_host_id: item.bk_host_id,
              companyId: '', // 服务商 ID
              cloudName: item.bk_cloud_name // 云区域
            }));
            this.tableData = Object.freeze(this.allHost);
          })
          .finally(() => {
            this.isLoading = false;
          });
      }
    },
    /**
     * @desc 关闭弹框
     */
    close(isShow = false) {
      const conf = deepClone(this.conf);
      conf.isShow = isShow;
      this.$emit('update:conf', conf);
    },
    /**
     * @desc 弹框关闭回调函数
     */
    handleAfterLeaveChange() {
      this.keyword = '';
      this.host = {};
      this.$refs.hostTableRef.setCurrentRow();
    },
    /**
     * @desc 搜索主机
     */
    requestHost(id) {
      if (this.getHost) return;
      this.isLoading = true;
      hostAgentStatus({
        bk_biz_id: id
      })
        .then((data) => {
          this.allHost = Object.freeze(this.handleHostData(data));
          this.filterHost();
        })
        .catch(() => {
          this.emptyStatusType = '500';
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    /**
     * @desc 处理主机数据
     * @param {Arrya} data - 源数据
     * @return {Array}
     */
    handleHostData(data) {
      if (Array.isArray(data) && data.length > 0) {
        return data.map(item => ({
          bk_host_id: item.bk_host_id, // host_id
          ip: item.bk_host_innerip || '--', // IP
          ipv6: item.bk_host_innerip_v6 || '--', // IP
          osType: item.bk_os_type, // 系统类型
          osName: item.bk_os_name, // 系统名称
          agentStatus: item.agent_status, // Agent 状态代码
          agentStatusName: item.agent_status_display, // Agent 状态名称
          cloudName: item.bk_cloud_name, // 云区域
          cloudId: item.bk_cloud_id, // cloudId
          companyId: '', // 服务商 ID
          bk_biz_id: item.bk_biz_id,
          display_name: item.display_name || '--'
        }));
      }
      return [];
    },
    /**
     * @desc 获取表格行样式
     */
    getRowClassName({ row }) {
      return row.agentStatus === 0 ? 'table-row-selected' : 'table-row-disabled';
    },
    /**
     * @desc 处理表格行点击事件
     */
    handleRowClick(row) {
      if (row.agentStatus !== 0) {
        this.$bkMessage({
          theme: 'warning',
          message: this.$t('无法选择Agent状态异常的服务器')
        });
        this.$refs.hostTableRef.setCurrentRow();
        return;
      }
      this.$emit('confirm', { ...this.host, ...row, osType: this.host.osType, osName: this.host.osType });
      this.close();
    },
    /**
     * @desc 去抖函数
     */
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
    /**
     * @desc 过滤主机
     */
    filterHost(val) {
      const curVal = String(val).trim();
      let newVal = '';
      if (isFullIpv6(padIPv6(curVal))) {
        newVal = padIPv6(curVal);
      }
      this.emptyStatusType = val ? 'search-empty' : 'empty';
      if (val) {
        this.tableData = this.filter
          ? this.filter(curVal, this.allHost)
          : this.allHost
            .filter(item => this.matchOsType(item.osType)
              && (
                (curVal && (item.ipv6.includes(curVal) || item.ip.includes(curVal)))
                || (newVal && item.ipv6.includes(newVal))
              )).sort((itemPre, itemNext) => itemPre.ip.length - itemNext.ip.length);
      } else {
        this.tableData = this.filter
          ? this.filter(val, this.allHost)
          : this.allHost.filter(item => this.matchOsType(item.osType));
      }
    },
    // 目标主机匹配条件
    matchOsType(osType, osTypeId = this.host.osTypeId) {
      if (osTypeId === '4') {
        // Liunx_arrch64平台
        return osType === '1';
      }
      return osType === osTypeId;
    },
    handleOperation(type) {
      if (type === 'clear-filter') {
        this.keyword = '';
        this.handleKeywordChange(this.keyword);
        return;
      }
      if (type === 'refresh') {
        this.requestHost(this.conf.id);
        return;
      }
    }
  }
};
</script>

<style lang="scss" scoped>
.host-header {
  width: 120px;
  height: 26px;
  margin-top: -15px;
  margin-bottom: 18px;
  font-size: 20px;
  line-height: 26px;
  color: #444;

  &-title {
    width: 400px;
  }
}

.host-body {
  width: 802px;

  .body-search {
    margin-bottom: 10px;
  }

  .body-table {
    .success {
      color: #2dcb56;
    }

    .error {
      color: #ea3636;
    }

    :deep(.bk-table-row.table-row-selected) {
      cursor: pointer;
    }

    :deep(.bk-table-row.table-row-disabled) {
      cursor: not-allowed;
    }

    .empty-status-container {
      padding: 0;
    }
  }
}
</style>
<style lang="scss">
.select-host-table-wrap {
  .bk-table-body-wrapper {
    /* stylelint-disable-next-line declaration-no-important */
    height: initial!important;
  }
}
</style>
