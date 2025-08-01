<!-- eslint-disable vue/no-v-html -->
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
    ref="accessContainerRef"
    class="es-access-container"
    data-test-id="esAccess_div_esAccessBox"
  >
    <div
      :style="`width: calc(100% - ${introWidth}px);`"
      class="es-cluster-list-container"
    >
      <div class="main-operator-container">
        <bk-button
          style="width: 120px"
          v-cursor="{ active: isAllowedCreate === false }"
          :disabled="isAllowedCreate === null || tableLoading"
          data-test-id="esAccessBox_button_addNewEsAccess"
          theme="primary"
          @click="addDataSource"
          >{{ $t('新建') }}
        </bk-button>
        <bk-input
          style="float: right; width: 360px"
          v-model="params.keyword"
          :clearable="true"
          :placeholder="$t('搜索ES源名称，地址，创建人')"
          data-test-id="esAccessBox_input_search"
          right-icon="bk-icon icon-search"
          @change="handleSearch"
        >
        </bk-input>
      </div>
      <bk-table
        ref="clusterTable"
        class="king-table"
        v-bkloading="{ isLoading: tableLoading }"
        :data="tableDataPaged"
        :pagination="pagination"
        data-test-id="esAccessBox_table_esAccessTableBox"
        @filter-change="handleFilterChange"
        @page-change="handlePageChange"
        @page-limit-change="handleLimitChange"
      >
        <bk-table-column
          :render-header="$renderHeader"
          label="ID"
          min-width="60"
          prop="cluster_config.cluster_id"
        >
        </bk-table-column>
        <bk-table-column
          :label="$t('名称')"
          :render-header="$renderHeader"
          min-width="170"
          prop="cluster_config.cluster_name"
        >
        </bk-table-column>
        <bk-table-column
          :label="$t('地址')"
          :render-header="$renderHeader"
          min-width="170"
        >
          <template #default="props">
            {{ props.row.cluster_config.domain_name || '--' }}
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('source_type')"
          :filter-method="sourceFilterMethod"
          :filter-multiple="false"
          :filters="sourceFilters"
          :label="$t('来源')"
          :render-header="$renderHeader"
          class-name="filter-column"
          column-key="source_type"
          min-width="80"
          prop="source_type"
        >
          <template #default="props">
            {{ props.row.source_name || '--' }}
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('port')"
          :label="$t('端口')"
          :render-header="$renderHeader"
          min-width="80"
          prop="cluster_config.port"
        >
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('schema')"
          :label="$t('协议')"
          :render-header="$renderHeader"
          min-width="80"
          prop="cluster_config.schema"
        >
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('cluster_config')"
          :filter-method="sourceStateFilterMethod"
          :filter-multiple="false"
          :filters="sourceStateFilters"
          :label="$t('连接状态')"
          :render-header="$renderHeader"
          class-name="filter-column"
          column-key="cluster_config.cluster_id"
          min-width="110"
          prop="cluster_config.cluster_id"
        >
          <template #default="{ row }">
            <div
              class="state-container"
              v-html="$xss(getStateText(row.cluster_config.cluster_id))"
            ></div>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('enable_hot_warm')"
          :label="$t('冷热数据')"
          :render-header="$renderHeader"
          min-width="80"
        >
          <template #default="{ row }">
            {{ row.cluster_config.enable_hot_warm ? $t('开') : $t('关') }}
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('storage_total')"
          width="90"
          :label="$t('总量')"
          :render-header="$renderHeader"
        >
          <template #default="{ row }">
            <span>{{ formatFileSize(row.storage_total) }}</span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('storage_usage')"
          width="110"
          :label="$t('空闲率')"
          :render-header="$renderHeader"
        >
          <template #default="{ row }">
            <div class="percent">
              <div class="percent-progress">
                <bk-progress
                  :percent="getPercent(row)"
                  :show-text="false"
                  :theme="'success'"
                ></bk-progress>
              </div>
              <span>{{ `${100 - row.storage_usage}%` }}</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('creator')"
          :label="$t('创建人')"
          :render-header="$renderHeader"
          min-width="80"
          prop="cluster_config.creator"
        >
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('create_time')"
          :label="$t('创建时间')"
          :render-header="$renderHeader"
          class-name="filter-column"
          min-width="170"
          prop="cluster_config.create_time"
          sortable
        >
        </bk-table-column>
        <bk-table-column
          width="180"
          :label="$t('操作')"
          :render-header="$renderHeader"
        >
          <template #default="props">
            <!-- 共享集群，平台默认时 无法新建索引集 -->
            <log-button
              class="mr10"
              :tips-conf="
                props.row.is_platform
                  ? $t('公共集群，禁止创建自定义索引集')
                  : $t('平台默认的集群不允许编辑和删除，请联系管理员。')
              "
              :button-text="$t('新建索引集')"
              :disabled="!props.row.is_editable || props.row.is_platform"
              theme="primary"
              text
              @on-click="createIndexSet(props.row)"
              >>
            </log-button>
            <log-button
              class="mr10"
              v-cursor="{ active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_ES_SOURCE_AUTH]) }"
              :button-text="$t('编辑')"
              :disabled="!props.row.is_editable"
              :tips-conf="$t('平台默认的集群不允许编辑和删除，请联系管理员。')"
              theme="primary"
              text
              @on-click="editDataSource(props.row)"
            >
            </log-button>
            <log-button
              class="mr10"
              v-cursor="{ active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_ES_SOURCE_AUTH]) }"
              :button-text="$t('删除')"
              :disabled="!props.row.is_editable"
              :tips-conf="$t('平台默认的集群不允许编辑和删除，请联系管理员。')"
              theme="primary"
              text
              @on-click="deleteDataSource(props.row)"
            >
            </log-button>
          </template>
        </bk-table-column>
        <bk-table-column
          :tippy-options="{ zIndex: 3000 }"
          type="setting"
        >
          <bk-table-setting-content
            v-en-style="'width: 530px'"
            :fields="clusterSetting.fields"
            :max="clusterSetting.max"
            :selected="clusterSetting.selectedFields"
            @setting-change="handleSettingChange"
          >
          </bk-table-setting-content>
        </bk-table-column>
        <template #empty>
          <div>
            <empty-status
              :empty-type="emptyType"
              @operation="handleOperation"
            />
          </div>
        </template>
      </bk-table>
    </div>

    <div
      :style="`width: ${introWidth}px`"
      :class="['intro-container', isDraging && 'draging-move']"
    >
      <div
        :style="`right: ${introWidth - 18}px`"
        :class="`drag-item ${!introWidth && 'hidden-drag'}`"
      >
        <span
          class="bk-icon icon-more"
          @mousedown.left="dragBegin"
        ></span>
      </div>
      <intro-panel
        :is-open-window="isOpenWindow"
        @handle-active-details="handleActiveDetails"
      />
    </div>

    <!-- 编辑或新建ES源 -->
    <es-slider
      v-if="isRenderSlider"
      :edit-cluster-id="editClusterId"
      :show-slider.sync="showSlider"
      @hidden="handleSliderHidden"
      @updated="handleUpdated"
    />
  </div>
</template>

<script>
  import EmptyStatus from '@/components/empty-status';
  import dragMixin from '@/mixins/drag-mixin';
  import { mapGetters } from 'vuex';

  import * as authorityMap from '../../../../common/authority-map';
  import {
    formatFileSize,
    clearTableFilter,
    isIPv6,
    getDefaultSettingSelectFiled,
    setDefaultSettingSelectFiled,
  } from '../../../../common/util';
  import IntroPanel from './components/intro-panel.vue';
  import EsSlider from './es-slider';

  export default {
    name: 'EsClusterMess',
    components: {
      EsSlider,
      IntroPanel,
      EmptyStatus,
    },
    mixins: [dragMixin],
    data() {
      const settingFields = [
        // 数据ID
        {
          id: 'cluster_id',
          label: 'ID',
          disabled: true,
        },
        // 集群名称
        {
          id: 'collector_config_name',
          label: this.$t('名称'),
          disabled: true,
        },
        // 地址
        {
          id: 'domain_name',
          label: this.$t('地址'),
          disabled: true,
        },
        // 来源
        {
          id: 'source_type',
          label: this.$t('来源'),
        },
        // 端口
        {
          id: 'port',
          label: this.$t('端口'),
        },
        // 协议
        {
          id: 'schema',
          label: this.$t('协议'),
        },
        // 连接状态
        {
          id: 'cluster_config',
          label: this.$t('连接状态'),
        },
        // 冷热数据
        {
          id: 'enable_hot_warm',
          label: this.$t('冷热数据'),
        },
        // 总量
        {
          id: 'storage_total',
          label: this.$t('总量'),
        },
        // 空闲率
        {
          id: 'storage_usage',
          label: this.$t('空闲率'),
        },
        // 创建人
        {
          id: 'creator',
          label: this.$t('创建人'),
        },
        // 创建时间
        {
          id: 'create_time',
          label: this.$t('创建时间'),
        },
      ];
      return {
        tableLoading: true,
        tableDataOrigin: [], // 原始数据
        tableDataSearched: [], // 搜索过滤数据
        tableDataPaged: [], // 前端分页
        pagination: {
          count: 0,
          limit: 10,
          current: 1,
        },
        stateMap: {},
        params: {
          keyword: '',
        },
        isAllowedCreate: null, // 是否有权限新建
        isRenderSlider: true, // 渲染侧边栏组件，关闭侧滑时销毁组件，避免接口在 pending 时关闭侧滑后又马上打开
        showSlider: false, // 显示编辑或新建ES源侧边栏
        editClusterId: null, // 编辑ES源ID,
        isOpenWindow: false,
        sourceStateFilters: [
          { text: this.$t('正常'), value: true },
          { text: this.$t('失败'), value: false },
        ],
        clusterSetting: {
          fields: settingFields,
          selectedFields: settingFields.slice(0, 10),
        },
        introWidth: 1,
        emptyType: 'empty',
        filterSearchObj: {},
        isFilterSearch: false,
        settingCacheKey: 'collection',
      };
    },
    computed: {
      ...mapGetters({
        bkBizId: 'bkBizId',
        spaceUid: 'spaceUid',
        globalsData: 'globals/globalsData',
      }),
      authorityMap() {
        return authorityMap;
      },
      sourceFilters() {
        const { es_source_type: esSourceType } = this.globalsData;
        const target = [];
        esSourceType?.forEach(data => {
          target.push({
            text: data.name,
            value: data.id,
          });
        });
        return target;
      },
    },
    created() {
      this.checkCreateAuth();
      this.getTableData();
      this.formatFileSize = formatFileSize;
      const { selectedFields } = this.clusterSetting;
      this.clusterSetting.selectedFields = getDefaultSettingSelectFiled(this.settingCacheKey, selectedFields);
      this.$nextTick(() => {
        this.maxIntroWidth = this.$refs.accessContainerRef.clientWidth - 580;
      });
    },
    methods: {
      async checkCreateAuth() {
        try {
          const res = await this.$store.dispatch('checkAllowed', {
            action_ids: [authorityMap.CREATE_ES_SOURCE_AUTH],
            resources: [
              {
                type: 'space',
                id: this.spaceUid,
              },
            ],
          });
          this.isAllowedCreate = res.isAllowed;
        } catch (err) {
          console.warn(err);
          this.isAllowedCreate = false;
        }
      },
      /**
       * 获取存储集群列表
       */
      async getTableData() {
        try {
          this.tableLoading = true; // 表格数据
          const tableRes = await this.$http.request('/source/list', {
            query: {
              bk_biz_id: this.bkBizId,
            },
          });
          this.tableLoading = false;
          const list = tableRes.data;
          if (!list.length) return;
          this.tableDataOrigin = list;
          this.tableDataSearched = list;
          this.pagination.count = list.length;
          this.computePageData();
          // 连接状态
          try {
            const stateRes = await this.$http.request('/source/connectionStatus', {
              query: {
                bk_biz_id: this.bkBizId,
              },
              data: {
                cluster_list: list.map(item => item.cluster_config.cluster_id),
              },
            });
            this.stateMap = stateRes.data;
          } catch (e) {
            console.warn(e);
            this.stateMap = {};
          }
        } catch (e) {
          console.warn(e);
          this.tableLoading = false;
          this.tableDataOrigin.splice(0);
          this.tableDataSearched.splice(0);
          this.pagination.count = 0;
        }
      },
      getStateText(id) {
        const info = this.stateMap[id]; // 兼容接口布尔值和对象
        const state = typeof info === 'boolean' ? info : info?.status;
        if (state === true) {
          return `<span class="bk-badge bk-danger"></span> ${this.$t('正常')}`;
        }
        if (state === false) {
          return `<span class="bk-badge bk-warning"></span> ${this.$t('失败')}`;
        }
        return '--';
      },
      handlePageChange(page) {
        if (this.pagination.current !== page) {
          this.pagination.current = page;
          this.computePageData();
        }
      },
      handleLimitChange(limit) {
        this.pagination.current = 1;
        this.pagination.limit = limit;
        this.computePageData();
      },
      // 搜索ES源名称，地址，创建人
      handleSearch() {
        this.searchTimer && clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(this.searchCallback, 300);
      },
      // 来源过滤
      sourceFilterMethod(value, row, column) {
        const { property } = column;
        this.handlePageChange(1);
        return row[property] === value;
      },
      searchCallback() {
        const keyword = this.params.keyword.trim();
        if (keyword) {
          this.tableDataSearched = this.tableDataOrigin.filter(item => {
            // 若是ipv6 则拿补全后的keyword与补全后的原地址对比
            if (isIPv6(keyword)) {
              return this.completeIPv6Address(item.cluster_config.domain_name) === this.completeIPv6Address(keyword);
            }
            if (item.cluster_config.cluster_name) {
              return (
                item.cluster_config.cluster_name +
                item.cluster_config.creator +
                item.cluster_config.domain_name
              ).includes(keyword);
            }
            return (item.source_name + item.updated_by).includes(keyword);
          });
        } else {
          this.tableDataSearched = this.tableDataOrigin;
        }
        this.emptyType = this.params.keyword || this.isFilterSearch ? 'search-empty' : 'empty';
        this.pagination.current = 1;
        this.pagination.count = this.tableDataSearched.length;
        this.computePageData();
      },
      // ipv6补全
      completeIPv6Address(address) {
        const sections = address.split(':');
        const missingSections = 8 - sections.length;

        for (let i = 0; i < missingSections; i++) {
          sections.splice(sections.indexOf(''), 1, '0000');
        }

        return sections
          .map(section => {
            if (section.length < 4) {
              section = '0'.repeat(4 - section.length) + section;
            }
            return section;
          })
          .join(':');
      },
      // 根据分页数据过滤表格
      computePageData() {
        const { current, limit } = this.pagination;
        const start = (current - 1) * limit;
        const end = this.pagination.current * this.pagination.limit;
        this.tableDataPaged = this.tableDataSearched.slice(start, end);
      },
      // 新建ES源
      async addDataSource() {
        if (this.isAllowedCreate) {
          this.showSlider = true;
          this.editClusterId = null;
        } else {
          try {
            this.tableLoading = true;
            const res = await this.$store.dispatch('getApplyData', {
              action_ids: [authorityMap.CREATE_ES_SOURCE_AUTH],
              resources: [
                {
                  type: 'space',
                  id: this.spaceUid,
                },
              ],
            });
            this.$store.commit('updateAuthDialogData', res.data);
          } catch (err) {
            console.warn(err);
          } finally {
            this.tableLoading = false;
          }
        }
      },
      // 建索引集
      createIndexSet(row) {
        this.$router.push({
          name: 'es-index-set-create',
          query: {
            spaceUid: this.$store.state.spaceUid,
            cluster: row.cluster_config.cluster_id,
          },
        });
      },
      // 编辑ES源
      async editDataSource(item) {
        const id = item.cluster_config.cluster_id;
        if (!item.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH]) {
          try {
            const paramData = {
              action_ids: [authorityMap.MANAGE_ES_SOURCE_AUTH],
              resources: [
                {
                  type: 'es_source',
                  id,
                },
              ],
            };
            this.tableLoading = true;
            const res = await this.$store.dispatch('getApplyData', paramData);
            this.$store.commit('updateAuthDialogData', res.data);
          } catch (err) {
            console.warn(err);
          } finally {
            this.tableLoading = false;
          }
          return;
        }

        this.showSlider = true;
        this.editClusterId = id;
      },
      // 删除ES源
      async deleteDataSource(row) {
        const id = row.cluster_config.cluster_id;
        if (!row.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH]) {
          try {
            const paramData = {
              action_ids: [authorityMap.MANAGE_ES_SOURCE_AUTH],
              resources: [
                {
                  type: 'es_source',
                  id,
                },
              ],
            };
            this.tableLoading = true;
            const res = await this.$store.dispatch('getApplyData', paramData);
            this.$store.commit('updateAuthDialogData', res.data);
          } catch (err) {
            console.warn(err);
          } finally {
            this.tableLoading = false;
          }
          return;
        }

        this.$bkInfo({
          type: 'warning',
          subTitle: this.$t('当前集群为{n}，确认要删除？', { n: row.cluster_config.domain_name }),
          confirmFn: () => {
            this.handleDelete(row);
          },
        });
      },
      handleDelete(row) {
        this.$http
          .request('source/deleteEs', {
            params: {
              bk_biz_id: this.bkBizId,
              cluster_id: row.cluster_config.cluster_id,
            },
          })
          .then(res => {
            if (res.result) {
              if (this.tableDataPaged.length <= 1) {
                this.pagination.current = this.pagination.current > 1 ? this.pagination.current - 1 : 1;
              }
              const deleteIndex = this.tableDataSearched.findIndex(item => {
                return item.cluster_config.cluster_id === row.cluster_config.cluster_id;
              });
              this.tableDataSearched.splice(deleteIndex, 1);
              this.computePageData();
            }
          })
          .catch(() => {});
      },
      // 新建、编辑源更新
      handleUpdated() {
        this.showSlider = false;
        this.pagination.count = 1;
        this.getTableData();
      },
      handleSliderHidden() {
        this.isRenderSlider = false;
        this.$nextTick(() => {
          this.isRenderSlider = true;
        });
      },
      handleSettingChange({ fields }) {
        this.clusterSetting.selectedFields = fields;
        setDefaultSettingSelectFiled(this.settingCacheKey, fields);
      },
      handleActiveDetails(state) {
        this.isOpenWindow = state;
        this.introWidth = state ? 360 : 1;
      },
      // 状态过滤
      sourceStateFilterMethod(value, row) {
        const info = this.stateMap[row.cluster_config.cluster_id]; // 兼容接口布尔值和对象
        const state = typeof info === 'boolean' ? info : info?.status;
        return state === value;
      },
      checkcFields(field) {
        return this.clusterSetting.selectedFields.some(item => item.id === field);
      },
      getPercent($row) {
        return (100 - $row.storage_usage) / 100;
      },
      handleFilterChange(data) {
        Object.entries(data).forEach(([key, value]) => (this.filterSearchObj[key] = value.length));
        this.isFilterSearch = Object.values(this.filterSearchObj).reduce((pre, cur) => ((pre += cur), pre), 0);
        this.searchCallback();
      },
      handleOperation(type) {
        if (type === 'clear-filter') {
          this.params.keyword = '';
          clearTableFilter(this.$refs.clusterTable);
          this.getTableData();
          return;
        }

        if (type === 'refresh') {
          this.emptyType = 'empty';
          this.getTableData();
          return;
        }
      },
    },
  };
</script>

<style lang="scss">
  .es-access-container {
    position: relative;
    display: flex;
    justify-content: space-between;
    transition: padding 0.5s;

    .main-operator-container {
      margin-bottom: 20px;
    }

    .king-table {
      .state-container {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        white-space: nowrap;

        .bk-badge {
          width: 5px;
          height: 5px;
          margin-right: 4px;
          border-radius: 50%;
        }

        .bk-danger {
          background-color: #2dcb56;
        }

        .bk-warning {
          background-color: #ea3636;
        }
      }

      :deep(.cell) {
        padding: 4px 15px;
      }

      .filter-column {
        .cell {
          display: flex;
        }
      }
    }

    .es-cluster-list-container {
      padding: 20px 24px;
    }

    .intro-container {
      position: relative;
      top: 2px;
      width: 400px;
      height: calc(100vh - 104px);
      overflow: hidden;

      &.draging-move {
        border-left-color: #3a84ff;
      }
    }

    .drag-item {
      position: absolute;
      top: 48%;
      right: 304px;
      z-index: 99;
      display: inline-block;
      width: 20px;
      height: 40px;
      color: #c4c6cc;
      cursor: col-resize;
      user-select: none;

      &.hidden-drag {
        display: none;
      }

      .icon-more::after {
        position: absolute;
        top: 12px;
        left: 0;
        content: '\e189';
      }
    }

    .percent {
      display: flex;
      align-items: center;

      .percent-progress {
        width: 40px;
        margin-right: 4px;
      }
    }
  }

  .bk-table-setting-popover-content-theme.tippy-tooltip {
    padding: 15px 0 0;

    .bk-table-setting-content .content-line-height {
      display: none;
    }
  }
</style>
