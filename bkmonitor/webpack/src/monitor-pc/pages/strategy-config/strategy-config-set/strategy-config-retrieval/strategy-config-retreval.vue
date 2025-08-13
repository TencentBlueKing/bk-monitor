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
  <monitor-dialog
    :value.sync="show"
    :title="$t('添加日志关键字')"
    width="850"
    @change="handleValueChange"
    @on-confirm="handleConfirm"
  >
    <div
      v-bkloading="{ isLoading: loading }"
      class="retrieval-set"
    >
      <bk-tab
        :active.sync="scenarioType"
        type="unborder-card"
        @tab-change="handleTabChang"
      >
        <bk-tab-panel
          v-for="(panel, index) in scenarioListAll"
          v-bind="panel"
          :key="index"
        />
      </bk-tab>
      <!-- 搜索框 -->
      <div class="retrieval-set-header">
        <bk-input
          :placeholder="placeholder"
          :clearable="true"
          :right-icon="'bk-icon icon-search'"
          :value="origin.keyword"
          @change="handleKeywordSearch"
        />
      </div>
      <div class="retrieval-content">
        <!-- 左边栏 -->
        <ul class="retrieval-content-left">
          <li
            v-for="(item, index) in origin.list"
            :key="index"
            class="left-item"
            :class="{ 'item-active': item.id === origin.value }"
            @click="handleOrginChange(item.id)"
          >
            <span class="left-item-name">{{ item.name }}</span>
            <span
              class="left-item-num"
              :class="{ 'num-active': item.id === origin.value }"
              >{{ item.count }}</span
            >
          </li>
        </ul>
        <!-- 右侧表格 -->
        <div class="retrieval-content-right">
          <bk-table
            :data="table.data"
            class="retrieval-table"
            @row-click="handleRowClick"
          >
            <template v-if="origin.value === 'bkMonitor'">
              <bk-table-column width="52">
                <template #default="{ row }">
                  <bk-radio :value="row.checked" />
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('采集项ID')"
                prop="related_id"
              />
              <bk-table-column
                min-width="200"
                :label="$t('采集项名称')"
                prop="related_name"
              />
            </template>
            <template v-else>
              <bk-table-column width="52">
                <template #default="{ row }">
                  <bk-radio :value="row.checked" />
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('索引集')"
                prop="metric_field"
              />
              <bk-table-column
                min-width="200"
                :label="$t('索引')"
                prop="result_table_id"
              />
              <bk-table-column
                width="100"
                :label="$t('数据源')"
                prop="scenario_name"
              />
            </template>
          </bk-table>
        </div>
      </div>
    </div>
  </monitor-dialog>
</template>
<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import { getMetricList } from 'monitor-api/modules/strategies';
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';
import { debounce } from 'throttle-debounce';

import type { TranslateResult } from 'vue-i18n/types/index';

interface IMetricParams {
  bk_biz_id: number | string;
  data_source_label: string;
  data_type_label: string;
  page: number;
  result_table_label: string;
}
interface IOrigin {
  keyword: string;
  list: { count: number; id: string; name: TranslateResult }[];
  value: string;
}
interface IParams {
  bk_biz_id: number | string;
  page_size: number;
  search_data_source: string;
  search_value: string;
}
interface ITable {
  bkMonitorLogData: [];
  data: { checked: boolean }[];
  logData: [];
}
@Component({
  components: {
    MonitorDialog,
  },
})
export default class StrategyConfigRetreval extends Vue {
  @Prop(Boolean) // dialog展示控制
  readonly dialogShow: boolean;
  @Prop({ type: [String, Number], default: 0 }) // 回填的选择ID
  readonly indexId: number | string;
  @Prop({ type: String, default: 'service_module' }) // 监控对象
  readonly monitorType: string;
  @Prop() // 监控对象列表
  readonly scenarioList: any[];

  loading = false;
  show = false;
  //  左侧栏数据
  origin: IOrigin;
  scenarioType = '';
  table: ITable = {
    data: [], //  当前数据
    logData: [], //  日志平台数据
    bkMonitorLogData: [], //  监控采集数据
  };
  //  tableMap
  tableDataMap: { bkMonitor: string; logData: string } = {
    bkMonitor: 'bkMonitorLogData',
    logData: 'logData',
  };
  handleKeywordSearch: Function = null;

  //  搜索栏placeholder
  get placeholder(): TranslateResult {
    return this.origin.value === 'logData' ? this.$t('搜索 索引 / 索引集名称') : this.$t('支持监控项名称搜索');
  }

  //  处理监控对象数据结构
  get scenarioListAll() {
    let arr = [];
    const list = JSON.parse(JSON.stringify(this.scenarioList));
    list.reverse().forEach(item => {
      const child = item.children.map(({ name, id }) => ({
        label: name,
        name: id,
      }));
      arr = [...child, ...arr];
    });
    return arr;
  }

  //  dialog展示触发
  @Watch('dialogShow', { immediate: true })
  onDialogShowChange(v: boolean): void {
    this.scenarioType = this.monitorType;
    this.show = v;
    v && this.handleGetIndexSetList();
  }

  created() {
    this.handleKeywordSearch = debounce(300, this.handleSearchKeyword);
    this.origin = {
      list: [
        {
          id: 'bkMonitor',
          name: this.$t('监控采集'),
          count: 0,
        },
        {
          id: 'logData',
          name: this.$t('日志平台'),
          count: 0,
        },
      ],
      value: 'bkMonitor',
      keyword: '',
    };
  }

  //  切换监控对象 tabCard
  handleTabChang() {
    this.handleGetIndexSetList();
  }

  //  获取tabl数据
  async handleGetIndexSetList(): Promise<any> {
    this.loading = true;
    const getIndexSetList = this.$store.dispatch('strategy-config/getIndexSetList', this.handleGetParams());
    const data: any[] = await Promise.all([getMetricList(this.handleGetMetricParams()), getIndexSetList]);
    const retreavlData: any = data[1];
    const bkMonitorData: any = data[0];
    //  索引集部分数据处理
    if (retreavlData) {
      this.table.logData = retreavlData.metric_list.map(item => ({
        ...item,
        id: item.index_set_id,
        checked: this.indexId === item.index_set_id,
      }));
      this.origin.list.forEach(item => {
        if (item.id === 'logData') {
          item.count = this.table.logData.length;
        }
      });
    }
    //  监控采集部分数据处理
    if (bkMonitorData) {
      this.table.bkMonitorLogData = bkMonitorData.metric_list.map(item => ({
        ...item,
        checked: this.indexId === item.id,
      }));
      this.origin.list.forEach(item => {
        if (item.id === 'bkMonitor') {
          item.count = this.table.bkMonitorLogData.length;
        }
      });
    }
    this.handleSearch();
    this.loading = false;
  }

  //  获取索引集请求参数
  handleGetParams(): IParams {
    return {
      bk_biz_id: this.$store.getters.bizId,
      page_size: -1,
      search_data_source: this.origin.value,
      search_value: this.origin.keyword,
    };
  }

  //  获取监控采集请求参数
  handleGetMetricParams(): IMetricParams {
    return {
      bk_biz_id: this.$store.getters.bizId,
      data_source_label: 'bk_monitor',
      data_type_label: 'log',
      result_table_label: this.scenarioType,
      page: -1,
    };
  }

  //  左边列表点击事件
  handleOrginChange(v: string): void {
    this.origin.value = v;
    this.handleSearch();
  }

  //  搜索框输入事件
  handleSearchKeyword(v: string): void {
    this.origin.keyword = v;
    this.handleSearch();
  }

  //  搜索逻辑处理
  handleSearch(): void {
    const { value, keyword }: { keyword: string; value: string } = this.origin;
    const data = this.table[this.tableDataMap[value]];
    if (this.origin.value === 'logData') {
      this.table.data = data.filter(
        item => item.result_table_id.includes(keyword) || item.metric_field.includes(keyword)
      );
    } else {
      this.table.data = data.filter(item => item.metric_field_name.includes(keyword));
    }
  }

  //   dialog显示变更触发
  handleValueChange(v: boolean): void {
    this.$emit('on-hide', v);
  }

  //  点击行触发
  handleRowClick(row: any): void {
    this.table[this.tableDataMap[this.origin.value]].forEach(item => (item.checked = false));
    row.checked = !row.checked;
  }

  //  点击确定触发
  handleConfirm(): void {
    const item = this.table.data.find(item => item.checked);
    this.$emit('set-retrieval', item);
    this.$emit('update:monitorType', this.scenarioType);
    this.$emit('on-hide', false);
  }
}
</script>
<style lang="scss" scoped>
.retrieval-set {
  position: relative;
  height: 528px;
  margin-top: 18px;

  :deep(.bk-tab-section) {
    padding: 8px;
  }

  &-header {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
  }

  .retrieval-content {
    display: flex;

    &-left {
      display: flex;
      flex: 0 0 185px;
      flex-direction: column;
      font-size: 14px;
      background-image:
        linear-gradient(180deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
        linear-gradient(90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
        linear-gradient(-90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%);
      background-size: 100% 100%;
      border-radius: 2px 0 0 0;

      .left-item {
        display: flex;
        flex: 0 0 42px;
        align-items: center;
        cursor: pointer;

        &-name {
          flex: 1;
          max-width: 110px;
          margin-left: 17px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        &-num {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 24px;
          height: 16px;
          padding: 0 5px;
          margin-right: 16px;
          margin-left: auto;
          font-size: 12px;
          color: #fff;
          background: #c4c6cc;
          border-radius: 16px;
        }

        .num-active {
          color: #3a84ff;
          background: #fff;
        }
      }

      .item-active {
        color: #fff;
        background: #3a84ff;
      }
    }

    &-right {
      flex-grow: 1;
      width: calc(100% - 185px);

      .retrieval-table {
        :deep(&.bk-table) {
          border-left: 0;
        }

        :deep(.bk-table-body-wrapper) {
          height: 384px;
          overflow-x: hidden;
          overflow-y: auto;
        }
      }
    }
  }
}
</style>
