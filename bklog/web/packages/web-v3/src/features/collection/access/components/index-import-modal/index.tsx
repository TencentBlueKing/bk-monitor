/*
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
 */

import { Checkbox as TCheckbox, CheckboxGroup as TCheckboxGroup } from 'tdesign-vue-next';

import { MessagePlugin as TDesignMessage } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

import { Component, ModelSync, Watch, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Dialog, Table } from 'tdesign-vue-next';

import './index.scss';

interface IProps {
  value: boolean;

  // Public props/events already installed by the source decorators.
  "onSyncExport"?: () => void;
}

const { $i18n } = window.mainComponent;

@Component({
  components: { Dialog, Table },
})
export default class IndexImportModal extends tsc<IProps> {
  @ModelSync('value', 'change', { type: Boolean }) localIsShowValue!: boolean;

  syncTypeList = [
    { name: $i18n.t('同步源日志信息'), id: 'source_log_info' },
    { name: $i18n.t('同步字段清洗配置'), id: 'field_clear_config' },
    { name: $i18n.t('同步存储配置'), id: 'storage_config' },
    { name: $i18n.t('同步采集目标'), id: 'acquisition_target' },
  ];
  syncType = ['source_log_info'];
  isTableLoading = false;
  submitLoading = false;
  collectList = [];
  emptyType = 'empty';
  keyword = '';
  searchKeyword = '';
  currentCheckImportID = null;
  pagination = {
    current: 1,
    count: 0,
    limit: 10,
    limitList: [10, 20, 50],
  };

  get etlConfigList() {
    return this.$store.getters['globals/globalsData']?.etl_config || [];
  }

  get collectShowList() {
    let collect = this.collectList;
    if (this.keyword) {
      collect = collect.filter(item =>
        item.collector_config_name.toString().toLowerCase().includes(this.keyword.toLowerCase()),
      );
    }
    this.emptyType = this.keyword ? 'search-empty' : 'empty';
    this.changePagination({ count: collect.length });
    const { current, limit } = this.pagination;

    const startIndex = (current - 1) * limit;
    const endIndex = current * limit;
    return collect.slice(startIndex, endIndex);
  }

  @Watch('localIsShowValue')
  handleIsShowChange(val: unknown) {
    if (val) {
      this.requestData();
    }
  }

  @Emit('sync-export')
  handleExport() {
    this.localIsShowValue = false;
    return;
  }

  handleCollectPageChange(current: unknown) {
    this.changePagination({ current });
  }
  handleCollectLimitChange(limit: unknown) {
    this.changePagination({ limit, current: 1 });
  }
  changePagination(pagination = {}) {
    Object.assign(this.pagination, pagination);
  }
  handleSearchChange(val: string) {
    if (val === '') {
      this.changePagination({ current: 1 });
      this.keyword = '';
      this.searchKeyword = '';
    }
  }
  search() {
    this.keyword = this.searchKeyword;
    this.emptyType = this.keyword ? 'search-empty' : 'empty';
  }
  dialogValueChange(v: unknown) {
    if (!v) {
      this.syncType = ['source_log_info'];
      this.currentCheckImportID = null;
      this.emptyType = 'empty';
      this.keyword = '';
      this.searchKeyword = '';
    }
  }
  requestData() {
    this.isTableLoading = true;
    const ids = this.$route.query.ids as string; // 根据id来检索
    const collectorIdList = ids ? decodeURIComponent(ids) : [];
    this.collectList.length = 0;
    this.collectList = [];
    ServicesInstance.collect.getAllCollectors({
        query: {
          bk_biz_id: this.$store.state.bkBizId,
          collector_id_list: collectorIdList,
          have_data_id: 1,
          not_custom: 1,
        },
      })
      .then((res: { data: any; }) => {
        const { data } = res;
        if (data?.length) {
          this.collectList = data.map((item: { collector_config_id: any; collector_config_name: any; storage_display_name: any; etl_config: any; retention: any; params: any; bk_data_id: any; }) => {
            const {
              collector_config_id,
              collector_config_name: collectorConfigName,
              storage_display_name: storageDisplayName,
              etl_config: etlConfig,
              retention,
              params,
              bk_data_id,
            } = item;
            let paths: string[] = [];
            try {
              const value = JSON.parse(this.pythonDictString(params));
              paths = value?.paths ?? [];
            } catch (e) {
              console.error(e);
            }
            return {
              bk_data_id,
              collector_config_id,
              collector_config_name: collectorConfigName || '--',
              storage_display_name: storageDisplayName || '--',
              retention: retention ? `${retention}${$i18n.t('天')}` : '--',
              paths: paths?.join('; ') ?? '',
              etl_config: this.etlConfigList.find((newItem: { id: any; }) => newItem.id === etlConfig)?.name ?? '--',
            };
          });
        }
      })
      .catch(() => {
        this.emptyType = '500';
      })
      .finally(() => {
        this.isTableLoading = false;
      });
  }
  pythonDictString(pythonString: string) {
    return pythonString
      .replace(/'/g, '"') // 将单引号替换为双引号
      .replace(/None/g, 'null') // 将 None 替换为 null
      .replace(/True/g, 'true') // 将 True 替换为 true
      .replace(/False/g, 'false'); // 将 False 替换为 false
  }
  getCheckedStatus(row: { collector_config_id: null; }) {
    return row.collector_config_id === this.currentCheckImportID;
  }
  handleRowCheckChange(row: { collector_config_id: null; }) {
    if (this.currentCheckImportID === row.collector_config_id) {
      this.currentCheckImportID = null;
      return;
    }
    this.currentCheckImportID = row.collector_config_id;
  }
  handleConfirmDialog() {
    if (!(this.currentCheckImportID && this.syncType.length)) {
      if (!this.currentCheckImportID) {
        TDesignMessage("error", { content: $i18n.t('请选择目标索引集') });
      }
      if (!this.syncType.length) {
        setTimeout(() => {
          TDesignMessage("error", { content: $i18n.t('请选择需要同步的配置') });
        }, 100);
      }
      return;
    }
    this.submitLoading = true;
    ServicesInstance.collect.details({
        params: {
          collector_config_id: this.currentCheckImportID,
        },
      })
      .then((res: { data: any; }) => {
        if (res.data) {
          const collect = res.data;
          const isPhysics = collect.environment !== 'container';
          if (collect.collector_scenario_id !== 'wineventlog' && isPhysics && collect?.params.paths) {
            collect.params.paths = collect.params.paths.map((item: unknown) => ({ value: item }));
          }
          this.$store.commit('collect/updateExportCollectObj', {
            collectID: this.currentCheckImportID,
            syncType: this.syncType,
            collect,
          });
          this.handleExport();
        }
      })
      .catch((err: unknown) => {
        console.warn(err);
      })
      .finally(() => {
        this.submitLoading = false;
      });
  }

  render() {
    const spanSlot = {
      default: ({ row, column }) => (
        <div
          class='title-overflow'
          v-log-overflow-tips
        >
          <span>{row[column.property] || '--'}</span>
        </div>
      ),
    };
    const checkBoxSlot = {
      default: ({ row }) => (
        <div class='import-check-box'>
          <TCheckbox
            class='group-check-box'
            checked={this.getCheckedStatus(row)}
          />
        </div>
      ),
    };
    return (
      <bk-dialog
        width={1200}
        ext-cls='index-import-modal'
        v-model={this.localIsShowValue}
        position={{
          top: 100,
        }}
        confirm-fn={this.handleConfirmDialog}
        header-position='left'
        mask-close={false}
        render-directive='if'
        theme='primary'
        title={this.$t('索引配置导入')}
        onValueChange={this.dialogValueChange}
      >
        <div
          class='content'
          v-loading={{ loading: this.submitLoading }}
        >
          <bk-form
            form-type='vertical'
            label-width={200}
          >
            <bk-form-item required={true}>
              <div class='top-sync-select'>
                <TCheckboxGroup v-model={this.syncType}>
                  {this.syncTypeList.map(item => (
                    <TCheckbox
                      key={item.id}
                      style='margin-right: 24px;'
                      value={item.id}
                    >
                      {item.name}
                    </TCheckbox>
                  ))}
                </TCheckboxGroup>
                <bk-input
                  v-model={this.searchKeyword}
                  placeholder={$i18n.t('搜索名称')}
                  right-icon='bk-icon icon-search'
                  onChange={this.handleSearchChange}
                  onEnter={this.search}
                />
              </div>
            </bk-form-item>
            <bk-form-item label={this.$t('请选择目标索引集')}>
              <bk-table
                v-loading={{ loading: this.isTableLoading }}
                data={this.collectShowList}
                limit-list={this.pagination.limitList}
                pagination={this.pagination}
                onPageChange={this.handleCollectPageChange}
                onPageLimitChange={this.handleCollectLimitChange}
                onRowClick={this.handleRowCheckChange}
              >
                <bk-table-column
                  nativeCellSlot={true}
                  width='60'
                  label=''
                  prop=''
                  v-slots={checkBoxSlot}
                />
                <bk-table-column
                  nativeCellSlot={true}
                  label='索引集'
                  prop='collector_config_name'
                  v-slots={spanSlot}
                />
                <bk-table-column
                  nativeCellSlot={true}
                  label='采集路径'
                  prop='paths'
                  v-slots={spanSlot}
                />
                <bk-table-column
                  label='采集模式'
                  prop='etl_config'
                />
                <bk-table-column
                  nativeCellSlot={true}
                  label='存储集群'
                  prop='storage_display_name'
                  v-slots={spanSlot}
                />
                <bk-table-column
                  label='存储时长'
                  prop='retention'
                />
              </bk-table>
            </bk-form-item>
          </bk-form>
        </div>
      </bk-dialog>
    );
  }
}
