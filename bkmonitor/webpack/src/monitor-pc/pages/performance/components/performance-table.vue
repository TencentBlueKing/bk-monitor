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
 * @Date: 2021-06-10 11:55:13
 * @LastEditTime: 2021-07-22 10:41:21
 * @LastEditors: Please set LastEditors
 * @Description:
-->
<template>
  <div
    class="performance"
    v-bkloading="{ isLoading }"
  >
    <div class="performance-table">
      <bk-table
        ref="table"
        v-if="Object.keys(columns).length"
        :key="tableKey"
        :data="tableData"
        :cell-class-name="cellClassName"
        :header-cell-class-name="cellClassName"
        @sort-change="handleSortChange"
        @row-mouse-enter="handleRowEnter"
        @row-mouse-leave="handleRowLeave"
      >
        <empty-status
          slot="empty"
          :type="emptyStatusType"
          @operation="handleOperation"
        />
        <template #prepend>
          <transition name="fade">
            <div
              class="selection-tips"
              v-show="allCheckValue === 2"
            >
              <i18n path="已选主机">
                <span class="tips-num">{{ selectionsCount }}</span>
              </i18n>
              <bk-button
                v-if="checkType === 'current'"
                ext-cls="tips-btn"
                text
                @click="handleSelectAll"
              >
                <i18n path="选择所有主机">
                  <span class="tips-num">{{ pageConfig.total }}</span>
                </i18n>
              </bk-button>
              <bk-button
                ext-cls="tips-btn"
                text
                v-else
                @click="handleClearAll"
              >
                {{ $t('清除所有数据') }}
              </bk-button>
            </div>
          </transition>
        </template>
        <bk-table-column
          :render-header="renderSelectionHeader"
          width="80"
          align="center"
        >
          <template #default="{ row }">
            <bk-checkbox
              v-model="row.selection"
              @change="handleRowCheck($event, row)"
            />
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.host_display_name.name"
          v-if="columns.host_display_name.checked"
          min-width="270"
        >
          <template #default="{ row }">
            <div
              class="ip-col"
              :key="row.bk_host_id"
            >
              <router-link
                class="ip-col-main"
                tag="span"
                v-bk-overflow-tips
                :to="{
                  name: 'performance-detail',
                  params: {
                    title: row.host_display_name,
                    id: row.bk_host_id,
                    osType: Number(row.bk_os_type)
                  }
                }"
              >
                {{ row.host_display_name }}
              </router-link>
              <i
                v-if="handleIpStatusData(row.ignore_monitoring, row.is_shielding).id"
                :class="`icon-monitor ip-status-icon ${
                  handleIpStatusData(row.ignore_monitoring, row.is_shielding).icon
                }`"
                @mouseenter="handleIpStatusTips($event, row)"
              />
              <svg
                viewBox="0 0 28 16"
                class="ip-col-mark"
                v-show="hoverMarkId === row.rowId || row.mark"
                @click.stop.prevent="handleIpMark(row)"
                v-if="$i18n.locale !== 'enUS'"
              >
                <path
                  :class="[row.mark ? 'path-primary' : 'path-default']"
                  d="M26,0H2C0.9,0,0,0.9,0,2v12c0,1.1,0.9,2,2,2h24c1.1,0,2-0.9,2-2V2C28,0.9,27.1,0,26,0z"
                />
                <path
                  fill="#FFFFFF"
                  d="M5.1,11.3h1V7.5h2.6V7.1H5.3V6.3h3.4V5.9H5.7V4h7.7v2h-3.3v0.4h3.6v0.8h-3.6v0.4h2.8v3.8h1v0.8H5.1V11.3z M6.8,5.2h1.1V4.7H6.8V5.2z M11.7,8.2H7.3v0.3h4.4V8.2z M7.3,9.5h4.4V9.1H7.3V9.5z M7.3,10.4h4.4V10H7.3V10.4z M7.3,11.3h4.4v-0.3H7.3V11.3z M9,5.2h1.1V4.7H9V5.2z M12.2,5.2V4.7h-1.1v0.5H12.2z"
                />
                <path
                  fill="#FFFFFF"
                  d="M14.1,4.1h3.1v1.2h-0.8v5.4c0,0.4-0.1,0.6-0.2,0.8c-0.1,0.2-0.3,0.3-0.5,0.4s-0.7,0.1-1.4,0.1c0-0.4-0.1-0.7-0.2-1.1c0.3,0,0.5,0,0.8,0c0.2,0,0.4-0.1,0.4-0.4V5.3h-1.1V4.1z M19.4,7.5h1.2c0,0.9-0.1,1.6-0.2,2.1c0.8,0.5,1.7,1.1,2.5,1.7l-0.7,0.9c-0.6-0.5-1.3-1-2.2-1.7c-0.4,0.7-1.2,1.2-2.5,1.7c-0.2-0.3-0.4-0.7-0.7-1.1c0.6-0.2,1.2-0.4,1.6-0.7c0.4-0.3,0.7-0.7,0.8-1.1C19.3,8.9,19.4,8.3,19.4,7.5z M17.4,4h5.4v1.1h-2.3l-0.2,0.8h2.2v4h-1.2V7h-2.7v3h-1.2V5.9h1.5l0.2-0.8h-1.7V4z"
                />
              </svg>
              <svg-icon
                icon-name="top"
                v-show="hoverMarkId === row.rowId || row.mark"
                @click.stop.prevent="handleIpMark(row)"
                class="ip-col-mark"
                :class="[row.mark ? 'path-primary' : 'path-default']"
                v-else
              />
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_host_id.name"
          min-width="120"
          v-if="columns.bk_host_id.checked"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_host_id | emptyStringFilter }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_host_innerip.name"
          v-if="columns.bk_host_innerip.checked"
          min-width="120"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_host_innerip | emptyStringFilter }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_host_outerip.name"
          min-width="120"
          v-if="columns.bk_host_outerip.checked"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_host_outerip | emptyStringFilter }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_host_innerip_v6.name"
          v-if="columns.bk_host_innerip_v6.checked"
          min-width="270"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_host_innerip_v6 | emptyStringFilter }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_host_outerip_v6.name"
          min-width="270"
          v-if="columns.bk_host_outerip_v6.checked"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_host_outerip_v6 | emptyStringFilter }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.status.name"
          min-width="120"
          v-if="columns.status.checked"
        >
          <template #default="{ row }">
            <div
              class="status-col"
              v-if="statusMap[row.status]"
            >
              <span :class="'status-' + statusMap[row.status].status" />
              <span
                class="status-name"
                @mouseenter="handleTipsMouseenter($event, row, 'Host')"
              >{{ statusMap[row.status].name }}</span>
            </div>
            <span v-else>--</span>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_host_name.name"
          min-width="140"
          v-if="columns.bk_host_name.checked"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_host_name || '--' }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_os_name.name"
          min-width="140"
          v-if="columns.bk_os_name.checked"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_os_name }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_cloud_name.name"
          v-if="columns.bk_cloud_name.checked"
          min-width="120px"
        >
          <template #default="{ row }">
            <span>{{ row.bk_cloud_name }}</span>
          </template>
        </bk-table-column>
        <template>
          <bk-table-column
            v-for="item in dynamicColumns"
            :key="item.id"
            :label="item.name"
            min-width="140px"
            v-if="item.checked"
          >
            <template #default="{ row }">
              <span
                v-bk-tooltips="{
                  content: getDynamicColumnValue(row, item.id),
                  showOnInit: false,
                  placements: ['top'],
                  interactive: false,
                  allowHTML: false
                }"
              >
                {{ getDynamicColumnValue(row, item.id) }}
                <!-- {{ row.bk_cluster.map((item) => item.name).join() }} -->
              </span>
            </template>
          </bk-table-column>
        </template>
        <bk-table-column
          :label="columns.bk_cluster.name"
          min-width="140px"
          v-if="columns.bk_cluster.checked"
        >
          <template #default="{ row }">
            <span
              v-bk-tooltips="{
                content: row.bk_cluster.map(item => item.name).join(),
                showOnInit: false,
                placements: ['top'],
                interactive: false,
                allowHTML: false
              }"
            >
              {{ row.bk_cluster.map(item => item.name).join() }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_inst_name.name"
          min-width="120px"
          v-if="columns.bk_inst_name.checked"
        >
          <template #default="{ row }">
            <span
              v-bk-tooltips="{
                content: row.bk_inst_name,
                showOnInit: false,
                placements: ['top'],
                interactive: false,
                allowHTML: false
              }"
            >{{ row.bk_inst_name }}</span>
          </template>
        </bk-table-column>
        <bk-table-column
          sortable="custom"
          prop="totalAlarmCount"
          min-width="150px"
          :label="columns.alarm_count.name"
          v-if="columns.alarm_count.checked"
        >
          <template #default="{ row }">
            <span
              class="status-label"
              @mouseenter="row.totalAlarmCount && handleUnresolveEnter(row, $event)"
              @mouseleave="row.totalAlarmCount && handleUnresolveLeave()"
              @click="handleGoEventCenter(row)"
              :class="{ 'status-unresolve': !!row.totalAlarmCount }"
              :style="{
                backgroundColor: getStatusLabelBgColor(row.alarm_count)
              }"
            >
              {{ row.totalAlarmCount >= 0 ? row.totalAlarmCount : '--' }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          sortable="custom"
          prop="cpu_load"
          align="right"
          min-width="140"
          :label="columns.cpu_load.name"
          v-if="columns.cpu_load.checked"
          :render-header="h => renderHeader(h, columns.cpu_load)"
        >
          <template #default="{ row }">
            <div class="cpu-col">
              <span>{{ row.cpu_load | isNumberFilter }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          sortable="custom"
          prop="cpu_usage"
          min-width="180"
          :label="columns.cpu_usage.name"
          v-if="columns.cpu_usage.checked"
          :render-header="h => renderHeader(h, columns.cpu_usage)"
        >
          <template #default="{ row }">
            <div>
              <div class="rate-name">
                {{ row.cpu_usage | emptyNumberFilter }}
              </div>
              <bk-progress
                :color="row.cpu_usage | progressColors"
                :show-text="false"
                :percent="+(row.cpu_usage * 0.01).toFixed(2) || 0"
              />
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          sortable="custom"
          prop="disk_in_use"
          min-width="180"
          :label="columns.disk_in_use.name"
          v-if="columns.disk_in_use.checked"
          :render-header="h => renderHeader(h, columns.disk_in_use)"
        >
          <template #default="{ row }">
            <div>
              <div class="rate-name">
                {{ row.disk_in_use | emptyNumberFilter }}
              </div>
              <bk-progress
                :color="row.disk_in_use | progressColors"
                :show-text="false"
                :percent="+(row.disk_in_use * 0.01).toFixed(2) || 0"
              />
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          sortable="custom"
          prop="io_util"
          min-width="180"
          :label="columns.io_util.name"
          v-if="columns.io_util.checked"
          :render-header="h => renderHeader(h, columns.io_util)"
        >
          <template #default="{ row }">
            <div>
              <div class="rate-name">
                {{ row.io_util | emptyNumberFilter }}
              </div>
              <bk-progress
                :color="row.io_util | progressColors"
                :show-text="false"
                :percent="+(row.io_util * 0.01).toFixed(2) || 0"
              />
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          sortable="custom"
          prop="mem_usage"
          min-width="240px"
          :label="columns.mem_usage.name"
          v-if="columns.mem_usage.checked"
          :render-header="h => renderHeader(h, columns.mem_usage)"
        >
          <template #default="{ row }">
            <div>
              <div class="rate-name">
                {{ row.mem_usage | emptyNumberFilter }}
              </div>
              <bk-progress
                :color="row.mem_usage | progressColors"
                :show-text="false"
                :percent="+(row.mem_usage * 0.01).toFixed(2) || 0"
              />
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          sortable="custom"
          prop="psc_mem_usage"
          min-width="180"
          :label="columns.psc_mem_usage.name"
          v-if="columns.psc_mem_usage.checked"
          :render-header="h => renderHeader(h, columns.psc_mem_usage)"
        >
          <template #default="{ row }">
            <div>
              <div class="rate-name">
                {{ row.psc_mem_usage | emptyNumberFilter }}
              </div>
              <bk-progress
                :show-text="false"
                :color="row.psc_mem_usage | progressColors"
                :percent="+(row.psc_mem_usage * 0.01).toFixed(2) || 0"
              />
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="columns.bk_biz_name.name"
          min-width="110"
          v-if="columns.bk_biz_name.checked"
        >
          <template #default="{ row }">
            <div class="ip-col">
              <span>{{ row.bk_biz_name }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :resizable="false"
          :label="columns.display_name.name"
          v-if="columns.display_name.checked"
          min-width="310"
        >
          <template #default="{ row, $index }">
            <div class="process-module">
              <div
                class="process-module-wrap"
                :ref="'table-row-' + $index"
              >
                <span
                  v-for="(item, index) in row.component"
                  :key="item.display_name + '__' + index"
                  :class="[
                    'process-status',
                    item.status === -1 ? 'process-status-default' : `process-status-${item.status}`
                  ]"
                  @click.stop="openProcessView(row, item.display_name)"
                  @mouseenter="handleTipsMouseenter($event, item, 'Thread')"
                >
                  {{ item.display_name }}
                </span>
                <span
                  v-if="overflowRowIds.includes(row.rowId)"
                  @click="openProcessView(row, 'row-overflow')"
                  class="process-status-3 process-overflow"
                >
                  {{ `...` }}
                </span>
              </div>
            </div>
          </template>
        </bk-table-column>
      </bk-table>
    </div>
    <div
      class="performance-footer"
      v-if="data.length"
    >
      <bk-pagination
        size="small"
        class="performance-footer-pagination"
        align="right"
        pagination-able
        show-total-count
        :current="pageConfig.page"
        :limit="pageConfig.pageSize"
        @change="handlePageChange"
        @limit-change="handleLimitChange"
        :count="pageConfig.total"
        :limit-list="pageConfig.pageList"
      />
    </div>
    <div v-show="false">
      <tips-tpl
        ref="tipsTpl"
        :tips-text="tipsData.tipsText"
        :link-text="tipsData.linkText"
        :link-url="tipsData.linkUrl"
        :doc-link="tipsData.docLink"
      />
    </div>
    <div v-show="false">
      <ip-status-tips
        ref="ipStatusTips"
        :ignore-monitoring="ipStatusData.ignoreMonitoring"
        :is-shielding="ipStatusData.isShielding"
        :host-id="ipStatusData.hostId"
      />
    </div>
    <input
      type="hidden"
      ref="hiddenFocus"
    >
  </div>
</template>
<script lang="ts">
import { CreateElement } from 'vue';
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { typeTools } from '../../../../monitor-common/utils/utils.js';
// import AbnormalTips from '../../../components/abnormal-tips/abnormal-tips.vue'
import TipsTpl from '../../../components/abnormal-tips/tips-tpl.vue';
import EmptyStatus from '../../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import PerformanceModule from '../../../store/modules/performance';
import MonitorVue from '../../../types/index';
import ColumnCheck from '../column-check/column-check.vue';
import { CheckType, ICheck, IPageConfig, ISort, ITableRow } from '../performance-type';
import { AlarmStatus } from '../types';
import UnresolveList from '../unresolve-list/unresolve-list.vue';

import IpStatusTips, { handleIpStatusData } from './ip-status-tips';

/** 告警类型对应的颜色 */
const alarmColorMap: { [key in AlarmStatus]: string } = {
  [AlarmStatus.DeadlyAlarm]: '#ea3636',
  [AlarmStatus.WarningAlarm]: '#ff8000',
  [AlarmStatus.RemindAlarm]: '#ffd000'
};

@Component({
  name: 'performance-table',
  components: {
    TipsTpl,
    IpStatusTips,
    EmptyStatus
  },
  filters: {
    progressColors(v) {
      if (v > 85 && v < 95) {
        return '#FF8000';
      }
      if (v >= 95) {
        return '#EA3636';
      }
      return '#2DCB56';
    },
    emptyStringFilter(v) {
      return typeTools.isNull(v) ? '--' : v;
    },
    emptyNumberFilter(v) {
      return v > 0 ? `${+v.toFixed(2)}%` : '--';
    },
    isNumberFilter(v) {
      return typeof v === 'number' ? v : '--';
    }
  }
} as any)
export default class PerformanceTable extends Vue<MonitorVue> {
  // 表格数据
  @Prop({ default: () => [], type: Array }) readonly data: any[];
  // 显示列配置
  @Prop({ default: () => ({}), type: Object }) readonly columns: any;
  // 分页配置
  @Prop({
    default: () => ({
      page: 1,
      pageSize: 10,
      pageList: [10, 20, 50, 100],
      total: 0
    }),
    type: Object
  })
  readonly pageConfig: IPageConfig;
  @Prop({ default: 0, type: Number }) readonly allCheckValue: 0 | 1 | 2; // 0: 取消全选 1: 半选 2: 全选
  @Prop({ default: 'current', type: String }) readonly checkType: CheckType;
  @Prop({ default: () => [], type: Array }) readonly selectionData: ITableRow[];
  @Prop({ default: () => [], type: Array }) readonly excludeDataIds: string[];
  @Prop({ default: 0, type: Number }) readonly selectionsCount: number;
  @Prop() readonly emptyStatusType: EmptyStatusType;

  @Ref('table') readonly tableRef!: any;
  @Ref('tipsTpl') readonly tipsTplTef: any;
  @Ref('ipStatusTips') readonly ipStatusTipsRef: IpStatusTips;

  // 提示组件实例
  tipsPopoverInstance = null;
  tipsData: any = {
    tipsText: '',
    linkText: '',
    linkUrl: '',
    docLink: ''
  };
  // 未恢复告警组件实例
  unresolveInstance = null;
  // 未恢复详情面板弹窗实例
  popoverInstance = null;
  // 表格Key（用于刷新表格数据）
  tableKey = +new Date();
  statusMap = {
    '-1': {
      name: window.i18n.t('未知'),
      status: '3'
    },
    0: {
      name: window.i18n.t('正常'),
      status: '1'
    },
    1: {
      name: window.i18n.t('离线'),
      status: '1'
    },
    2: {
      name: window.i18n.t('无Agent'),
      status: '2',
      tips: window.i18n.t('原因: Agent未安装或者状态异常'),
      url: `${this.$store.getters.bkNodemanHost}#/agent-manager/status`
    },
    3: {
      name: window.i18n.t('无数据上报'),
      status: '3',
      tips: window.i18n.t('原因:bkmonitorbeat未安装或者状态异常'),
      url: `${this.$store.getters.bkNodemanHost}#/plugin-manager/list`
    }
  };

  selectList = [
    {
      id: 'current',
      name: window.i18n.t('本页全选')
    },
    {
      id: 'all',
      name: window.i18n.t('跨页全选')
    }
  ];

  overflowRowIds: string[] = [];
  hoverMarkId = '';
  // 表格数据
  tableData: ITableRow[] = [];

  componentStatusMap: any = {
    1: {
      // 异常
      tipsText: window.i18n.t('原因:查看进程本身问题或者检查进程配置是否正常'),
      docLink: 'processMonitor'
    },
    2: {
      // 无数据
      tipsText: window.i18n.t('原因:bkmonitorbeat进程采集器未安装或者状态异常'),
      linkText: window.i18n.t('前往节点管理处理'),
      linkUrl: `${this.$store.getters.bkNodemanHost}#/plugin-manager/list`
    },
    3: {}
  };
  isLoading = false;

  handleIpStatusData: Function = handleIpStatusData;
  ipStatusData = {
    ignoreMonitoring: false,
    isShielding: false,
    hostId: null
  };
  get dynamicColumns() {
    const a = Object.values(this.columns).filter((item: any) => item.dynamic);
    return a;
  }
  getDynamicColumnValue(row, id) {
    const list = new Set();
    row?.module?.forEach((item) => {
      const index = item.topo_link?.findIndex(i => i.includes(`${id}|`));
      if (index > -1) {
        list.add(item.topo_link_display?.[index]);
      }
    });
    return list.size ?  Array.from(list).join(',') : '--';
  }
  mounted() {
    this.tableData = JSON.parse(JSON.stringify(this.data));
    this.unresolveInstance = new Vue(UnresolveList).$mount();
  }
  // activated() {
  //   this.tableData = JSON.parse(JSON.stringify(this.data));
  //   this.unresolveInstance = new Vue(UnresolveList).$mount();
  // }

  public updateDataSelection() {
    this.tableData.forEach((item) => {
      if (this.checkType === 'current') {
        item.selection = this.selectionData.some(item => item.rowId === item.rowId);
      } else {
        item.selection = !this.excludeDataIds.includes(item.rowId);
      }
    });
  }

  @Watch('data')
  async handleDataChange(data) {
    const tableData = JSON.parse(JSON.stringify(data));
    const [firstItem] = tableData;
    // 状态不存在则需要拉取当前页状态并合并
    if (firstItem && !this.statusMap[firstItem.status]) {
      PerformanceModule.searchHostMetric({
        bk_host_ids: tableData.map(item => item.bk_host_id)
      }).then((hostsMap) => {
        // 解决全量数据先返回的时序问题
        const [first] = this.tableData;
        if (!first || !this.statusMap[first.status]) {
          const data = this.tableData.map((item) => {
            const resetData = hostsMap[`${item.bk_host_innerip}|${item.bk_cloud_id}`] || {};
            return {
              ...item,
              ...resetData
            };
          });
          this.setTableData(data);
        }
      });
    }
    this.setTableData(tableData);
  }

  async setTableData(tableData) {
    this.tableData = tableData.map((item) => {
      if (this.checkType === 'all') {
        item.selection = !this.excludeDataIds.includes(item.rowId);
      }
      return item;
    });

    await this.$nextTick();
    this.overflowRowIds = [];
    this.tableData.forEach((item, index) => {
      const ref = this.$refs[`table-row-${index}`];
      const overflow = ref && (ref as HTMLElement).clientHeight > 30;
      overflow && this.overflowRowIds.push(item.rowId);
    });
  }

  @Emit('sort-change')
  handleSortChange({ order, prop }: ISort) {
    return {
      order,
      prop
    };
  }

  handleRowEnter(index) {
    this.hoverMarkId = this.tableData[index]?.rowId;
  }

  handleRowLeave() {
    this.hoverMarkId = '';
    this.$refs.hiddenFocus?.focus();
  }

  // 自定义check表头
  renderSelectionHeader(h: CreateElement) {
    return h(ColumnCheck, {
      props: {
        list: this.selectList,
        value: this.allCheckValue,
        defaultType: this.checkType
      },
      on: {
        change: this.handleCheckChange
      }
    });
  }

  @Emit('check-change')
  handleCheckChange({ value, type }: ICheck) {
    return {
      value,
      type
    };
  }

  @Emit('ip-mark')
  handleIpMark(row) {
    return row;
  }

  @Emit('limit-change')
  handleLimitChange(limit: number) {
    return limit;
  }

  @Emit('page-change')
  handlePageChange(page: number) {
    return page;
  }

  // 未恢复列表
  handleUnresolveEnter(data, e) {
    if (!data.alarm_count?.length) {
      return false;
    }
    this.unresolveInstance.list = data.alarm_count;
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.unresolveInstance.$el,
      arrow: true,
      placement: 'right',
      maxWidth: 520
    });
    this.popoverInstance?.show(100);
  }

  handleUnresolveLeave() {
    if (this.popoverInstance) {
      this.popoverInstance.hide(100);
      this.popoverInstance.destroy();
      this.popoverInstance = null;
    }
  }

  // 行勾选事件
  @Emit('row-check')
  handleRowCheck(value: boolean, row: ITableRow) {
    return {
      value,
      row
    };
  }

  updateTableKey() {
    this.$nextTick(() => {
      this.tableKey = +new Date();
    });
  }

  // 主机详情--进程视图
  openProcessView(row: ITableRow, process) {
    this.$router.push({
      name: 'performance-detail',
      params: {
        title: row.bk_host_innerip,
        id: row.bk_host_id,
        osType: Number(row.bk_os_type)
      },
      query: {
        dashboardId: 'process',
        'var-display_name': process
      }
    });
  }

  handleGoEventCenter(row) {
    if (!row.bk_host_innerip || !row.totalAlarmCount) return;
    const url = this.$router.resolve({
      name: 'event-center',
      query: {
        from: 'now-7d',
        to: 'now',
        queryString: ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale)
          ? `目标IP : ${row.bk_host_innerip}`
          : `ip : ${row.bk_host_innerip}`,
        activeFilterId: 'NOT_SHIELDED_ABNORMAL'
      }
    });
    window.open(url.href);
  }

  // 跨页全选操作
  handleSelectAll() {
    this.handleCheckChange({
      value: 2,
      type: 'all'
    });
  }

  // 清除勾选
  handleClearAll() {
    this.handleCheckChange({
      value: 0,
      type: 'current'
    });
  }
  /**
   * @description: 主机状态提示
   * @param {*} e MouseEvent
   * @param {*} row 表格行数据
   * @return {*}
   */
  handleIpStatusTips(e: MouseEvent, row) {
    this.ipStatusData.ignoreMonitoring = row.ignore_monitoring;
    this.ipStatusData.isShielding = row.is_shielding;
    this.ipStatusData.hostId = row.bk_host_id;
    this.$nextTick(() => {
      const tipsTpl = this.ipStatusTipsRef.$el;
      this.initTipsPopover(e.target, tipsTpl, { width: 215, theme: 'light' });
    });
  }

  handleTipsMouseenter(e: MouseEvent, item, type: 'Host' | 'Thread') {
    if (type === 'Host' && [2, 3].includes(item.status)) {
      this.tipsData.tipsText = this.statusMap[item.status].tips;
      this.tipsData.linkText = this.$t('前往节点管理处理');
      this.tipsData.linkUrl = this.statusMap[item.status].url;
      this.tipsData.docLink = '';
    } else if (type === 'Thread' && [2, 1].includes(item.status)) {
      this.tipsData.tipsText = this.componentStatusMap[item.status].tipsText;
      this.tipsData.linkText = this.componentStatusMap[item.status].linkText;
      this.tipsData.linkUrl = this.componentStatusMap[item.status].linkUrl;
      this.tipsData.docLink = this.componentStatusMap[item.status].docLink;
    } else {
      return;
    }
    this.initTipsPopover(e.target, this.tipsTplTef.$el);
  }

  /**
   * @description: 初始化tooltips
   * @param {*} target 目标
   * @param {*} content tips内容
   * @param {*} options 配置
   * @return {*}
   */
  initTipsPopover(target, content, options?) {
    if (!this.tipsPopoverInstance) {
      this.tipsPopoverInstance = this.$bkPopover(
        target,
        Object.assign(
          {
            content,
            interactive: true,
            arrow: true,
            placement: 'top',
            onHidden: () => {
              this.tipsPopoverInstance?.destroy();
              this.tipsPopoverInstance = null;
            }
          },
          options
        )
      );
      this.tipsPopoverInstance?.show();
    }
  }

  hiddenPopover() {
    this?.tipsPopoverInstance?.hide();
  }

  /** 自定义表格头部 */
  renderHeader(h, column) {
    return h('div', { class: ['header-custom-wrap'] }, [
      h('i', { class: ['icon-monitor', column.headerPreIcon] }),
      h(
        'div',
        {
          class: 'header-custom-title',
          directives: [{ name: 'bk-overflow-tips' }]
        },
        [column.name]
      )
    ]);
  }
  cellClassName({ column }) {
    const id = column.property;
    const columnData = this.columns[id];
    return !!columnData?.headerPreIcon ? 'has-header-pre-icon' : '';
  }
  // eslint-disable-next-line @typescript-eslint/member-ordering
  public sort({ prop, order }: ISort) {
    this?.tableRef?.sort(prop, order);
  }

  // eslint-disable-next-line @typescript-eslint/member-ordering
  public clearSort() {
    this?.tableRef?.clearSort();
  }

  /**
   * 根据警告等级调整背景色
   * 取有告警数且等级最高的
   * level 越低等级越高。
   */
  getStatusLabelBgColor(alarmCount: { count: number; level: number; color?: string }[]) {
    // 第一次执行会为空。
    if (!alarmCount || alarmCount.length === 0) {
      return '';
    }

    // 使用 reduce 方法遍历数组，找到最小的 level 且 count 不为 0 的告警项
    // 如果找到，则返回该项的颜色和等级，否则返回之前的 minColor
    return alarmCount
      .reduce((minColor, { count, level }) => {
        return count && (!minColor || level < minColor.level)
          ? { color: alarmColorMap[level], level }
          : minColor;
      }, null)?.color || '';
  }

  @Emit('empty-status-operation')
  handleOperation(type: EmptyStatusOperationType) {
    return type;
  }
}
</script>
<style lang="scss">
/* stylelint-disable function-no-unknown */

/* stylelint-disable no-descending-specificity */
@import '../../../theme/index.scss';

$statusBorderColors: #2dcb56 #c4c6cc #ea3636;
$statusColors: #94f5a4 #f0f1f5 #fd9c9c;
$processBorderColors: #fd9c9c #dcdee5 #dcdee5;
$processColors: #ea3636 #c4c6cc #63656e;

.performance {
  &-table {
    .bk-table {
      .header-custom-wrap {
        position: relative;
        display: flex;

        @include method-icons;

        .header-custom-title {
          @include ellipsis;
        }
      }

      .bk-table-header {
        .has-header-pre-icon {
          .cell {
            padding-left: 0;
          }

          .header-custom-wrap {
            padding-left: 25px;
          }
        }
      }

      .bk-table-body {
        .has-header-pre-icon {
          .cell {
            padding-left: 25px;
          }
        }
      }
    }

    .selection-tips {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 30px;
      background: #ebecf0;

      .tips-num {
        font-weight: bold;
      }

      .tips-btn {
        margin-left: 5px;
        font-size: 12px;
      }
    }

    .bk-table td,
    .bk-table th {
      padding: 0;
      font-size: 12px;
    }

    .bk-table-header {
      .is-first {
        .bk-table-header-label {
          overflow: visible;
        }
      }
    }

    .select-count {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 30px;
      margin-bottom: 5px;
      font-size: 12px;
      color: #63656e;
      background-color: #f0f1f5;

      .select-all {
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .ip-col {
      display: flex;
      align-items: center;
      font-size: 12px;
      color: $defaultFontColor;

      &-main {
        display: inline-block;
        overflow: hidden;
        color: #3a84ff;
        text-overflow: ellipsis;
        white-space: nowrap;
        cursor: pointer;
      }

      &-mark {
        width: 28px;
        min-width: 28px;
        height: 16px;
        margin-left: 6px;

        @include hover();

        &.path-primary {
          color: #3a84ff;
        }

        &.path-default {
          color: #979ba5;
        }

        .path-primary {
          fill: #3a84ff;
        }

        .path-default {
          fill: #979ba5;
        }
      }

      .ip-status-icon {
        margin-left: 6px;
        font-size: 18px;
        color: #ffb848;

        &.icon-menu-shield,
        &.icon-celvepingbi {
          font-size: 16px;
        }
      }
    }

    .status-col {
      display: flex;
      align-items: center;
      height: 20px;

      @for $i from 1 through length($statusColors) {
        .status-#{$i} {
          display: inline-block;
          width: 12px;
          height: 12px;
          margin-right: 5px;
          background: nth($statusColors, $i);
          border: 1px solid nth($statusBorderColors, $i);
          border-radius: 50%;
        }
      }

      .status-name {
        font-size: 12px;
        color: $defaultFontColor;
      }
    }

    .status-label {
      display: inline-block;
      padding: 2px 7px;
      font-size: 12px;
      color: #fff;
      text-align: center;
      background: #dcdee5;
      border-radius: 2px;
    }

    .status-unresolve {
      @include hover();
    }

    .rate-name {
      font-size: 12px;
      line-height: 16px;
      color: $defaultFontColor;
    }

    .process-module {
      position: relative;
      height: 30px;

      &-wrap {
        margin-right: 25px;
        overflow: hidden;

        @for $i from 1 through length($processColors) {
          .process-status-#{$i} {
            float: left;
            padding: 3px 7px;
            margin: 3px;
            font-size: 12px;
            line-height: 16px;
            color: nth($processColors, $i);
            text-align: center;
            cursor: pointer;
            background: #fafbfd;
            border: 1px solid nth($processBorderColors, $i);
            border-radius: 2px;
          }
        }

        .process-status-default {
          float: left;
          padding: 3px 7px;
          margin: 3px;
          font-size: 12px;
          line-height: 16px;
          color: #63656e;
          text-align: center;
          cursor: pointer;
          background: #fafbfd;
          border: 1px solid #dcdee5;
          border-radius: 2px;
        }

        .process-overflow {
          position: absolute;
          top: 0;
        }
      }
    }
  }

  &-footer {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    height: 60px;
    padding: 0 20px;
    border: 1px solid $defaultBorderColor;
    border-top: 0;

    &-pagination {
      flex: 1;
    }
  }
}
</style>
