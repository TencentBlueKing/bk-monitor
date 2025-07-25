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
    v-monitor-loading="{ isLoading: loading }"
    class="migrate-dashboard"
  >
    <div class="migrate-dashboard-footer mb20 migrate-dashboard-header">
      <div>
        <span> {{ $t('该迁移工具用于协助Prometheus的grafana仪表盘、告警策略迁移，具备promql转换能力。') }} </span>
      </div>
    </div>
    <div class="migrate-dashboard-footer mb20 migrate-dashboard-header">
      <div>
        <bk-button
          class="mr10"
          theme="primary"
          @click="handleDialogShow(true)"
        >
          {{ $t('新建映射规则') }}
        </bk-button>
        <span
          v-if="docUrl"
          style="color: #3a84ff; cursor: pointer"
          @click="gotoDoc"
        >
          {{ $t('迁移指引') }}
        </span>
      </div>
      <biz-select
        class="biz-select"
        :value="bizId"
        :biz-list="bizList"
        :min-width="270"
        @change="handleChangeBizId"
      />
    </div>
    <bk-table
      v-monitor-loading="{ isLoading: tableLoading }"
      class="migrate-dashboard-table"
      :empty-text="$t('查无数据')"
      :data="tableData"
    >
      <bk-table-column
        :label="$t('选择')"
        width="80"
      >
        <template #default="{ row }">
          <span @click="handleRadioChange(row)">
            <bk-radio v-model="row.checked" />
          </span>
        </template>
      </bk-table-column>
      <bk-table-column :label="$t('规则名称')">
        <template #default="{ row }">
          <div v-bk-overflow-tips>
            {{ row.config_field }}
          </div>
        </template>
      </bk-table-column>
      <bk-table-column :label="$t('数据范围类型')">
        <template #default="{ row }">
          <div :title="row.range_type">
            {{ row.range_type }}
          </div>
        </template>
      </bk-table-column>
      <bk-table-column :label="$t('映射范围')">
        <template #default="{ row }">
          <div :title="row.mapping_range">
            {{ row.mapping_range }}
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        min-width="220"
        :label="$t('详细信息')"
      >
        <template #default="{ row }">
          <div :title="JSON.stringify(row.mapping_detail)">
            {{ JSON.stringify(row.mapping_detail) }}
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        width="80"
      >
        <template #default="{ row }">
          <bk-button
            text
            @click="handleDelTableRow(row)"
            >{{ $t('删除') }}</bk-button
          >
        </template>
      </bk-table-column>
    </bk-table>
    <bk-pagination
      v-show="totalData.data.length"
      class="migrate-dashboard-pagination"
      align="right"
      size="small"
      show-total-count
      pagination-able
      :current="totalData.page"
      :limit="totalData.pageSize"
      :count="totalData.data.length"
      :limit-list="pageList"
      @change="handlePageChange"
      @limit-change="handleLimitChange"
    />
    <div class="migrate-dashboard-footer">
      <bk-upload
        :files="fileList"
        :tip="$t('可批量导入, 导入策略请上传yaml配置，导入仪表盘请上传json配置')"
        :with-credentials="true"
        :theme="'button'"
        class="mb20 mt5"
        :handle-res-code="handleRes"
        :header="uploadHeader"
        :url="`${siteUrl}rest/v2/promql_import/upload_file/`"
        :limit="100"
        :accept="'.json,.yaml'"
        :multiple="true"
        @on-delete="handleFileList"
        @on-done="handleFileListDone"
      />
      <bk-button
        theme="primary"
        @click="importGrafanaDashboard"
      >
        {{ $t('导入仪表盘') }}
      </bk-button>
      <bk-button
        class="ml5"
        theme="primary"
        @click="importAlertrule"
      >
        {{ $t('导入告警策略') }}
      </bk-button>
      <div class="migrate-dashboard-tips mt10">
        <span
          v-for="(results, file) in fileResult"
          :key="file"
        >
          <span
            class="mb5"
            style="font-weight: bold"
            >"{{ file }}"<br
          /></span>
          <li
            v-for="result in results"
            :key="result.message"
          >
            {{ result.status }} --- {{ result.message }}<br />
          </li>
        </span>
      </div>
    </div>
    <bk-dialog
      v-model="isDialogShow"
      :theme="'primary'"
      :mask-close="false"
      header-position="left"
      :width="480"
      :z-index="commonZIndex"
      :title="$t('新建映射规则')"
      class="migrate-dashboard-dialog"
      @cancel="clearData"
      @confirm="handleConfirm"
    >
      <div>
        <div class="mb10">
          <span>{{ $t('规则名称') }}:</span>
          <bk-input
            v-model="configField"
            class="mt10"
            :clearable="true"
          />
        </div>
        <div class="mb10">
          <span>{{ $t('映射类型') }}:</span>
          <bk-radio-group
            v-model="rangeType"
            class="mt10"
            @change="clearTableIds"
          >
            <bk-radio
              class="method-radio mr15"
              value="kubernetes"
              >{{ $t('K8s内置') }}</bk-radio
            >
            <bk-radio
              class="method-radio mr15"
              value="bkPull"
              >{{ $t('BK-PULL插件') }}</bk-radio
            >
            <bk-radio
              class="method-radio"
              value="customTs"
              >{{ $t('自定义上报') }}</bk-radio
            >
          </bk-radio-group>
        </div>
        <div
          v-show="rangeType !== 'kubernetes'"
          class="mb10"
        >
          <span v-show="rangeType !== 'kubernetes'">{{ $t('映射范围') }}:</span>
          <bk-select
            v-show="rangeType !== 'kubernetes'"
            v-model="tableIds"
            :clearable="false"
            class="mt10"
            multiple
            show-select-all
            :loading="isLoading"
            :z-index="commonZIndex + 100"
            :placeholder="$t('选择上报指标映射范围')"
          >
            <bk-option
              v-for="(option, index) in tableList"
              :id="option.table_id"
              :key="index"
              :name="option.name"
            />
          </bk-select>
        </div>
        <div>
          <span>{{ $t('映射配置') }}:</span>
          <bk-upload
            :key="uploadKey"
            :tip="$t('指标映射规则文件格式为yaml')"
            :with-credentials="true"
            :theme="'button'"
            :multiple="false"
            class="mb20 mt5"
            :handle-res-code="handleRes"
            :url="`${siteUrl}rest/v2/promql_import/upload_file/`"
            :header="uploadHeader"
            :limit="1"
            :accept="'.yaml'"
            @on-success="handleFile"
            @on-delete="handleDeleteFile"
          />
        </div>
      </div>
    </bk-dialog>
  </div>
</template>

<script lang="ts">
import { Component, Mixins, Watch } from 'vue-property-decorator';

import { customTimeSeriesList } from 'monitor-api/modules/custom_report';
import { listCollectorPlugin } from 'monitor-api/modules/model';
import {
  createMappingConfig,
  deleteMappingConfig,
  getMappingConfig,
  importAlertRule,
  importGrafanaDashboard,
} from 'monitor-api/modules/promql_import';
import { getCookie, random } from 'monitor-common/utils/utils';

import BizSelect from '../../components/biz-select/biz-select';
import authorityMixinCreate from '../../mixins/authorityMixin';
import commonPageSizeMixin from '../../mixins/commonPageSizeMixin';
import documentLinkMixin from '../../mixins/documentLinkMixin';
import * as migrageAuth from './authority-map';

import type MonitorVue from '../../types/index';

const COMMON_ZINDEX = 2500;
/** 弹窗的层级控制 */
@Component({
  name: 'migrate-dashboard',
  components: {
    BizSelect,
  },
})
export default class MigrateDashboard extends Mixins(
  commonPageSizeMixin,
  authorityMixinCreate(migrageAuth),
  documentLinkMixin
)<MonitorVue> {
  loading = false;
  tableLoading = false;
  statusMap: {} = {};
  rangeType = 'kubernetes';
  pageList: number[] = [10, 20, 50, 100];
  totalData = {
    data: [],
    page: 1,
    pageSize: this.handleGetCommonPageSize(),
  };
  tableList = [];
  file: any = null;
  fileList: any = [];
  siteUrl = window.site_url;
  uploadHeader = [
    { name: 'X-CSRFToken', value: window.csrf_token || getCookie(window.csrf_cookie_name) },
    { name: 'X-Requested-With', value: 'XMLHttpRequest' },
    { name: 'Source-App', value: window.source_app },
  ];
  fileResult = {};
  isDialogShow = false;
  currentField = '';
  isLoading = false;
  tableIds = [];
  configField = '';
  uploadKey = random(8);
  commonZIndex = COMMON_ZINDEX;
  localBiz: number = null;
  docUrl = window.migrate_guide_url;

  get tableData(): Array<any> {
    return this.totalData.data
      .slice(this.totalData.pageSize * (this.totalData.page - 1), this.totalData.pageSize * this.totalData.page)
      .map(item => ({
        ...item,
        checked: false,
      }));
  }

  /** 业务id, 本业组件所有接口使用此业务id，非全局的业务id */
  get bizId(): number {
    return this.localBiz || this.$store.getters.bizId;
  }

  /** 业务列表 */
  get bizList() {
    return this.$store.getters.bizList;
  }

  @Watch('rangeType', { immediate: true })
  handleDataChange(v) {
    this.handleResetList(v);
  }

  async handleResetList(type) {
    this.tableList = [];
    if (type === 'customTs') {
      const params = {
        search_key: '',
        page: 1,
        page_size: 10,
        bk_biz_id: this.bizId,
      };
      this.isLoading = true;
      const originData = await customTimeSeriesList(params)
        .catch(() => ({ list: [], total: 0 }))
        .finally(() => {
          this.isLoading = false;
        });
      params.page_size = originData.total;
      const totalData = await customTimeSeriesList(params)
        .catch(() => ({ list: [], total: 0 }))
        .finally(() => {
          this.isLoading = false;
        });
      this.tableList = totalData.list;
    }
    if (type === 'bkPull') {
      const params = {
        search_key: '',
        plugin_type: 'Pushgateway',
        page: -1,
        order: '-update_time',
        status: 'release',
        bk_biz_id: this.bizId,
      };
      this.isLoading = true;
      const data = await listCollectorPlugin(params)
        .catch(() => ({ list: [], total: 0 }))
        .finally(() => {
          this.isLoading = false;
        });
      this.tableList = data.list.map(plugin => ({
        table_id: plugin.plugin_id,
        name: plugin.plugin_display_name,
      }));
    }
  }

  get isDisabled(): boolean {
    if (this.file && this.tableIds.length !== 0 && this.configField) {
      return false;
    }
    return true;
  }

  async created() {
    this.getTableData();
  }

  gotoDoc() {
    window.open(this.docUrl, '_blank'); // 在新窗口打开外链接
  }

  downloadFile(json, file) {
    const downlondEl = document.createElement('a');
    const blob = new Blob([JSON.stringify(json, null, 4)]);
    const fileUrl = URL.createObjectURL(blob);
    downlondEl.href = fileUrl;
    downlondEl.download = file;
    downlondEl.style.display = 'none';
    document.body.appendChild(downlondEl);
    downlondEl.click();
    document.body.removeChild(downlondEl);
  }

  async getTableData() {
    this.tableLoading = true;
    const data = await getMappingConfig({ bk_biz_id: this.bizId }).catch(() => []);
    this.totalData.data = data;
    this.tableLoading = false;
  }

  importGrafanaDashboard() {
    this.$bkInfo({
      title: this.$t('是否开始迁移仪表盘？'),
      subTitle: this.$t('自定义上报指标和插件采集指标请勾选映射规则，K8S系统指标可以不勾选。'),
      zIndex: this.commonZIndex,
      extCls: 'custom-info-dialog',
      confirmFn: async vm => {
        vm.close();
        this.loading = true;
        const formData = new FormData();
        formData.append('bk_biz_id', `${this.bizId}`);
        this.fileList.forEach(file => {
          formData.append('file_list', file.origin);
        });
        if (this.currentField) formData.append('config_field', this.currentField);
        const data = await importGrafanaDashboard(formData).catch(e => {
          this.$bkMessage({
            theme: 'error',
            message: e,
          });
        });
        if (data) {
          this.fileResult = data;
          for (const file in data) {
            const results = data[file];
            results.forEach(result => {
              if (result.json) {
                this.downloadFile(result.json, file);
              }
            });
          }
        }
        this.loading = false;
      },
    });
  }

  importAlertrule() {
    this.$bkInfo({
      title: this.$t('是否开始迁移策略？'),
      subTitle: this.$t('自定义上报指标和插件采集指标请勾选映射规则，K8S系统指标可以不勾选。'),
      zIndex: this.commonZIndex,
      extCls: 'custom-info-dialog',
      width: '500px',
      confirmFn: async vm => {
        vm.close();
        this.loading = true;
        const formData = new FormData();
        formData.append('bk_biz_id', `${this.bizId}`);
        this.fileList.forEach(file => {
          formData.append('file_list', file.origin);
        });
        if (this.currentField) formData.append('config_field', this.currentField);
        const data = await importAlertRule(formData).catch(e => {
          this.$bkMessage({
            theme: 'error',
            message: e,
          });
        });
        if (data) {
          this.fileResult = data;
          for (const file in data) {
            const results = data[file];
            results.forEach(result => {
              if (result.json) {
                this.downloadFile(result.json, file);
              }
              if (result.fail_info) {
                this.downloadFile(result.fail_info, 'fail_info');
              }
            });
          }
          this.$bkMessage({
            theme: 'success',
            message: this.$t('迁移策略完成'),
          });
        }
        this.loading = false;
      },
    });
  }

  handleFile(file) {
    this.file = file;
  }
  handleDeleteFile() {
    this.file = null;
  }

  handleFileList(file, fileList) {
    this.fileList = fileList;
  }

  handleFileListDone(fileList) {
    this.fileList = fileList;
  }

  handleRes(response) {
    return response?.code === 200;
  }

  handleRadioChange(row) {
    const { checked } = row;
    this.currentField = checked ? '' : row.config_field;
    this.tableData.forEach(item => {
      if (checked) {
        item.checked = false;
      } else {
        if (item.id !== row.id) {
          item.checked = false;
        }
      }
    });
  }

  async handleDialogShow(status) {
    this.isDialogShow = status;
  }

  clearData() {
    this.tableIds = [];
    this.configField = '';
    this.uploadKey = random(8);
    this.handleDeleteFile();
  }

  clearTableIds() {
    this.tableIds = [];
  }

  // 切换当前页
  handlePageChange(page: number) {
    this.totalData.page = page;
  }

  // 切换页码
  handleLimitChange(limit: number) {
    this.totalData.page = 1;
    this.totalData.pageSize = limit;
    this.handleSetCommonPageSize(`${limit}`);
  }

  // 确认创建规则
  async handleConfirm() {
    const formData = new FormData();
    formData.append('bk_biz_id', `${this.bizId}`);
    formData.append('range_type', this.rangeType);
    if (this.tableIds.length > 0) {
      formData.append('mapping_range', this.tableIds.join(','));
    }
    formData.append('config_field', this.configField);
    if (this.file) {
      formData.append('file_data', this.file.origin);
    }
    await createMappingConfig(formData)
      .catch(e => console.log(e))
      .then(() => {
        this.getTableData();
        this.clearData();
      });
  }

  // 切换业务
  handleChangeBizId(v: number) {
    this.localBiz = v;
    this.totalData.page = 1;
    this.fileList = [];
    this.getTableData();
  }

  /**
   * 删除表格数据
   */
  handleDelTableRow(row) {
    this.loading = true;
    const params = {
      bk_biz_id: this.bizId,
      config_field: row.config_field,
    };
    deleteMappingConfig(params)
      .catch(() => [])
      .then(() => {
        /** 删除成功，更新表格数据 */
        this.getTableData();
      })
      .finally(() => (this.loading = false));
  }
}
</script>
<style lang="scss">
.custom-info-dialog .bk-info-box .bk-dialog-sub-header .bk-dialog-header-inner {
  word-break: normal;
}
</style>
<style lang="scss" scoped>
@import '../home/common/mixins';
$statusBorderColors: #c4c6cc #2dcb56 #ea3636;
$statusColors: #f0f1f5 #94f5a4 #fd9c9c;

.migrate-dashboard {
  margin: 20px;

  .migrate-dashboard-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .biz-select {
    min-width: 270px;
    height: 32px;

    :deep(.biz-select-target-main) {
      height: 32px;
    }
  }

  &-table {
    font-size: 12px;

    .status-col {
      display: flex;
      align-items: center;
      height: 20px;
      line-height: 14px;

      @for $i from 1 through length($statusColors) {
        .status-#{$i} {
          display: inline-block;
          width: 12px;
          height: 12px;
          margin-right: 5px;

          /* stylelint-disable-next-line function-no-unknown */
          background: nth($statusColors, $i);

          /* stylelint-disable-next-line function-no-unknown */
          border: 1px solid nth($statusBorderColors, $i);
          border-radius: 50%;
        }
      }

      .status-name {
        font-size: 12px;
        color: $defaultFontColor;
      }
    }
  }

  &-pagination {
    padding: 15px;
    margin-bottom: 10px;
    background: #fff;
    border: 1px solid #ddd;
    border-top: 0;

    :deep(.bk-page-count) {
      width: 115px;
    }
  }

  &-tips {
    font-size: 14px;
  }

  &-footer {
    margin-top: 10px;
  }

  &-dialog {
    display: flex;
    align-items: center;
  }
}
</style>
