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
  <section
    class="index-set-container"
    data-test-id="logIndexSet_section_logIndexSetBox"
  >
    <t-alert data-v2-display="alert"
      v-if="searchParams.is_trace_log === '0'"
      class="alert-info"
      :message="alertText"
      :theme="'info'"
    ></t-alert>
    <div class="operate-box">
      <t-button
        v-cursor="{ active: isAllowedCreate === false }"
        style="min-width: 120px"
        :disabled="!collectProject || isTableLoading || isAllowedCreate === null"
        :loading="isCreateLoading"
        data-test-id="logIndexSetBox_button_newIndexSet"
        theme="primary"
        @click="addIndexSet"
      >
        {{ $t('新建索引集') }}
      </t-button>
      <t-input
        v-model="searchParams.keyword"
        style="width: 300px"
        :placeholder="$t('请输入索引集名称')"

        data-test-id="logIndexSetBox_input_searchIndexSet"
        @change="handleSearchChange"
        @enter="reFilter"
      >
      <template #suffix><i :class="'bk-icon icon-search'" /></template></t-input>
    </div>
    <bk-table
      :loading="isTableLoading"
      :data="indexSetList"
      :empty-text="$t('暂无内容')"
      :pagination="pagination"
      data-test-id="logIndexSetBox_table_indexSetTable"
      @page-change="handlePageChange"
      @page-limit-change="handleLimitChange"
    >
      <bk-table-column
        native-cell-slot
        :label="$t('索引集')"
      >
        <template #default="{ row }">
          <!-- <bk-button
              class="indexSet-name"
              text
              @click="manageIndexSet('manage', row)">
              {{ row.index_set_name }}
            </bk-button> -->
          <div class="index-set-name-box">
            <span
              v-log-overflow-tips
              v-cursor="{ active: !(row.permission && row.permission[authorityMap.MANAGE_INDICES_AUTH]) }"
              class="indexSet-name"
              @click="manageIndexSet('manage', row)"
            >
              {{ row.index_set_name }}
            </span>
            <span
              v-if="row.is_desensitize"
              v-log-tooltip.top="$t('已脱敏')"
              class="bk-icon bklog-icon bklog-masking"
            >
            </span>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        :label="$t('采集项')"
        :render-header="$renderHeader"
        min-width="180"
        prop="index_set_id"
      >
        <template #default="props">
          <span>{{ props.row.indexes.map(item => item.result_table_id).join('; ') }}</span>
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        :label="$t('日用量/总用量')"
        :render-header="$renderHeader"
        min-width="80"
      >
        <template #default="props">
          <span :class="{ 'text-disabled': props.row.status === 'stop' }">
            {{ formatUsage(props.row.daily_usage, props.row.total_usage) }}
          </span>
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        :label="$t('集群名')"
        :render-header="$renderHeader"
      >
        <template #default="props">
          <div>{{ props.row.storage_display_name || props.row.storage_cluster_name || '--' }}</div>
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        :label="$t('状态')"
        :render-header="$renderHeader"
        prop="apply_status_name"
      >
        <template #default="{ row }">
          <div :class="['status-text', row.apply_status === 'normal' && 'success-status']">
            {{ row.apply_status_name || '--' }}
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        width="200"
        :label="$t('标签')"
        :render-header="$renderHeader"
        min-width="200"
      >
        <template #default="props">
          <index-set-label-select
            :label.sync="props.row.tags"
            :row-data="props.row"
            :select-label-list="selectLabelList"
            @refresh-label-list="initLabelSelectList"
          />
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        width="190"
        :label="$t('创建时间')"
        :render-header="$renderHeader"
      >
        <template #default="props">
          <div>{{ props.row.created_at || '--' }}</div>
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        :label="$t('创建人')"
        :render-header="$renderHeader"
        prop="created_by"
      >
        <template #default="props">
          <bk-user-display-name :user-id="props.row.created_by"></bk-user-display-name>
        </template>
      </bk-table-column>
      <bk-table-column
        native-cell-slot
        :width="operatorWidth"
        :label="$t('操作')"
        :render-header="$renderHeader"
      >
        <template #default="props">
          <t-button :variant="(true) ? 'text' : ('base')"
            v-cursor="{ active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_INDICES_AUTH]) }"
            style="margin-right: 4px"
            theme="primary"

            @click="manageIndexSet('search', props.row)"
            >{{ $t('检索') }}
          </t-button>
          <!-- { active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_INDICES_AUTH]) } -->
          <t-button :variant="(true) ? 'text' : ('base')"
            v-if="isShowMaskingTemplate"
            style="margin-right: 4px"
            theme="primary"

            @click="manageIndexSet('masking', props.row)"
            >{{ $t('日志脱敏') }}
          </t-button>
          <t-button :variant="(true) ? 'text' : ('base')"
            v-cursor="{ active: !(props.row.permission && props.row.permission.manage_indices_v2) }"
            style="margin-right: 4px"
            :disabled="!props.row.is_editable"
            theme="primary"

            @click="manageIndexSet('edit', props.row)"
          >
            <span
              v-log-tooltip.top="{
                content: `${$t('内置索引集')}, ${$t('不可编辑')}`,
                disabled: props.row.is_editable,
              }"
              >{{ $t('编辑') }}</span
            >
          </t-button>
          <t-button :variant="(true) ? 'text' : ('base')"
            v-cursor="{ active: !(props.row.permission && props.row.permission.manage_indices_v2) }"
            theme="primary"

            @click="manageIndexSet('delete', props.row)"
          >
            <span>{{ $t('删除') }}</span>
          </t-button>
        </template>
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
  </section>
</template>

<script>
import { mapState as mapPiniaState } from 'pinia';

import { useApplicationStore } from '@/app/state/domains/application-store';
import { useCollectionStore } from '@/app/state/domains/collection-store';
import { ServicesInstance } from '@/platform/services';

  import { projectManages, updateLastSelectedIndexId } from '@/shared/lib/util';
  import EmptyStatus from '@/shared/ui/empty-status/index';
  import IndexSetLabelSelect from '@/features/index-sets/label-select/index';

  import { formatBytes, requestStorageUsage } from '../../../util';
  import * as authorityMap from '../../../../../shared/lib/authority-map';
  import useUtils from '@/shared/composables/use-utils';
  import useFullscreenLoading from '@/shared/composables/use-fullscreen-loading';

  export default {
    name: 'IndexSetList',
    components: {
      EmptyStatus,
      IndexSetLabelSelect,
    },
    setup() {
      return useFullscreenLoading();
    },
    data() {
      const scenarioId = this.$route.name.split('-')[0];
      return {
        scenarioId,
        searchParams: {
          scenario_id: scenarioId,
          is_trace_log: this.$route.name.includes('track') ? '1' : '0',
          keyword: '',
          show_more: true,
        },
        indexSetList: [],
        pagination: {
          current: 1,
          count: 0,
          limit: 10,
        },
        isTableLoading: false,
        isCreateLoading: false, // 新建索引集
        isAllowedCreate: null,
        emptyType: 'empty',
        isInit: true,
        selectLabelList: [],
      };
    },
    computed: {
      ...mapPiniaState(useApplicationStore, {
        bkBizId: 'bkBizId',
        spaceUid: 'spaceUid',
        isShowMaskingTemplate: 'isShowMaskingTemplate',
      }),
      authorityMap() {
        return authorityMap;
      },
      collectProject() {
        return projectManages(useApplicationStore().topMenu, 'collection-item');
      },
      alertText() {
        const textMap = {
          log: this.$t('索引集允许用户可以跨多个采集的索引查看日志。'),
          es: this.$t(
            '如果日志已经存储在Elasticsearch，可以在“集群管理”中添加Elasticsearch集群，就可以通过创建索引集来使用存储中的日志数据。',
          ),
          bkdata: this.$t(
            '通过新建索引集添加计算平台中的Elasticsearch的索引，就可以在日志平台中进行检索、告警、可视化等。',
          ),
        };
        return textMap[this.scenarioId];
      },
      operatorWidth() {
        return useApplicationStore().isEnLanguage ? 300 : 190;
      },
    },
    created() {
      this.initLabelSelectList();
      this.checkCreateAuth();
      this.getIndexSetList();
    },
    methods: {
      async checkCreateAuth() {
        try {
          const res = await useApplicationStore().checkAllowed({
            action_ids: [authorityMap.CREATE_INDICES_AUTH],
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
       * 获取索引集列表
       */
      getIndexSetList() {
        this.isTableLoading = true;
        const { ids } = this.$route.query; // 根据id来检索
        const indexSetIDList = ids ? decodeURIComponent(ids) : [];
        const query = structuredClone(this.searchParams);
        query.page = this.pagination.current;
        query.pagesize = this.pagination.limit;
        query.space_uid = this.spaceUid;
        query.index_set_id_list = indexSetIDList;
        this.emptyType = this.searchParams.keyword ? 'search-empty' : 'empty';
        const { formatResponseListTimeZoneString } = useUtils();

        ServicesInstance.indexSet.list({
            query,
          })
          .then(async res => {
            const resList = res.data.list;
            const indexIdList = resList.filter(item => !!item.index_set_id).map(item => item.index_set_id);
            const { data: desensitizeStatus } = await this.getDesensitizeStatus(indexIdList);
            this.indexSetList = formatResponseListTimeZoneString(resList, item => ({
              is_desensitize: desensitizeStatus[item.index_set_id]?.is_desensitize ?? false,
            }));
            this.pagination.count = res.data.total;
            this.loadData();
          })
          .catch(err => {
            console.warn(err);
            this.emptyType = '500';
          })
          .finally(() => {
            this.isTableLoading = false;
            if (!this.isInit)
              this.$router.replace({
                query: {
                  spaceUid: this.$route.query.spaceUid,
                },
              });
            this.isInit = false;
          });
      },
      loadData() {
        const callbackFn = (item, key, value) => {
          this.$set(item, key, value[key]);
        };
        requestStorageUsage(this.bkBizId, this.indexSetList, false, callbackFn)
          .catch(error => {
            console.error('Error loading data:', error);
          })
          .finally(() => {
            this.isTableLoading = false;
          });
      },
      /**
       * 分页变换
       * @param  {Number} page 当前页码
       * @return {[type]}      [description]
       */
      handlePageChange(page) {
        if (this.pagination.current !== page) {
          this.pagination.current = page;
          this.getIndexSetList();
        }
      },
      /**
       * 分页限制
       * @param  {Number} page 当前页码
       * @return {[type]}      [description]
       */
      handleLimitChange(page) {
        if (this.pagination.limit !== page) {
          this.pagination.current = 1;
          this.pagination.limit = page;
          this.getIndexSetList();
        }
      },
      /**
       * 筛选条件变更，重新获取列表
       */
      reFilter() {
        this.pagination.current = 1;
        this.getIndexSetList();
      },
      /**
       * 跳转新增页面
       */
      async addIndexSet() {
        if (this.isAllowedCreate === false) {
          try {
            this.isCreateLoading = true;
            const res = await useApplicationStore().getApplyData({
              action_ids: [authorityMap.CREATE_INDICES_AUTH],
              resources: [
                {
                  type: 'space',
                  id: this.spaceUid,
                },
              ],
            });
            useApplicationStore().updateState({ authDialogData: res.data });
          } catch (err) {
            console.warn(err);
          } finally {
            this.isCreateLoading = false;
          }
          return;
        }

        this.$router.push({
          name: this.$route.name.replace('list', 'create'),
          query: {
            spaceUid: useApplicationStore().spaceUid,
          },
        });
      },
      async manageIndexSet(type, row) {
        if (!row.permission?.[authorityMap.MANAGE_INDICES_AUTH]) {
          try {
            this.isTableLoading = true;
            const res = await useApplicationStore().getApplyData({
              action_ids: [authorityMap.MANAGE_INDICES_AUTH],
              resources: [
                {
                  type: 'indices',
                  id: row.index_set_id,
                },
              ],
            });
            useApplicationStore().updateState({ authDialogData: res.data });
          } catch (err) {
            console.warn(err);
          } finally {
            this.isTableLoading = false;
          }
          return;
        }

        if (type === 'manage') {
          // 管理索引集
          useCollectionStore().updateCurIndexSet(row);
          this.$router.push({
            name: this.$route.name.replace('list', 'manage'),
            params: {
              indexSetId: row.index_set_id,
            },
            query: {
              spaceUid: useApplicationStore().spaceUid,
            },
          });
        } else if (type === 'search') {
          // 检索
          updateLastSelectedIndexId(this.spaceUid, row.index_set_id);
          this.$router.push({
            name: 'retrieve',
            params: {
              indexId: row.index_set_id ? row.index_set_id : row.bkdata_index_set_ids[0],
            },
            query: {
              spaceUid: useApplicationStore().spaceUid,
            },
          });
        } else if (type === 'edit') {
          // 编辑索引集
          useCollectionStore().updateCurIndexSet(row);
          this.$router.push({
            name: this.$route.name.replace('list', 'edit'),
            params: {
              indexSetId: row.index_set_id,
            },
            query: {
              spaceUid: useApplicationStore().spaceUid,
              editName: row.index_set_name,
            },
          });
        } else if (type === 'delete') {
          // 删除索引集
          this.$bkInfo({
            subTitle: this.$t('当前索引集为{n}，确认要删除？', { n: row.index_set_name }),
            maskClose: true,
            confirmFn: async () => {
              const loading = this.showFullscreenLoading({ opacity: 0.6 });
              try {
                await ServicesInstance.indexSet.remove({
                  params: {
                    index_set_id: row.index_set_id,
                  },
                });
                this.getIndexSetList();
              } finally {
                loading.hide();
              }
            },
          });
        } else if (type === 'masking') {
          // 删除索引集
          this.$router.push({
            name: this.$route.name.replace('list', 'masking'),
            params: {
              indexSetId: row.index_set_id ? row.index_set_id : row.bkdata_index_set_ids[0],
            },
            query: {
              spaceUid: useApplicationStore().spaceUid,
              editName: row.index_set_name,
            },
          });
        }
      },
      handleSearchChange() {
        setTimeout(() => {
          if (this.searchParams.keyword === '' && !this.isTableLoading) {
            this.getIndexSetList();
          }
        });
      },
      handleOperation(type) {
        if (type === 'clear-filter') {
          this.searchParams.keyword = '';
          this.pagination.current = 1;
          this.getIndexSetList();
          return;
        }

        if (type === 'refresh') {
          this.emptyType = 'empty';
          this.pagination.current = 1;
          this.getIndexSetList();
          return;
        }
      },
      async getDesensitizeStatus(indexIdList = []) {
        try {
          return await ServicesInstance.masking.getDesensitizeState({
            data: { index_set_ids: indexIdList },
          });
        } catch {
          return [];
        }
      },
      /** 初始化标签列表 */
      async initLabelSelectList() {
        try {
          const res = await ServicesInstance.unionSearch.unionLabelList({
            query: {
              space_uid: this.spaceUid,
            },
          });
          this.selectLabelList = res.data;
        } catch {
          this.selectLabelList = [];
        }
      },
      formatUsage(dailyUsage, totalUsage) {
        return `${formatBytes(dailyUsage)} / ${formatBytes(totalUsage)}`;
      },
    },
  };
</script>

<style lang="scss" scoped>
@use '../../../../../shared/styles/mixins/clearfix' as *;
  @use '../../../../../shared/styles/conf' as *;
  /* stylelint-disable no-descending-specificity */
  .index-set-container {
    padding: 20px 24px;

    .alert-info {
      margin-bottom: 20px;
    }

    .operate-box {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
    }

    .status-text {
      color: #ea3636;

      &.success-status {
        color: #2dcb56;
      }
    }

    .index-set-name-box {
      display: flex;
      align-items: center;

      .icon-masking {
        flex-shrink: 0;
      }
    }

    .indexSet-name {
      display: inline-block;
      overflow: hidden;
      color: #3a84ff;
      // width: 100%;
      text-overflow: ellipsis;
      white-space: nowrap;
      cursor: pointer;
    }

    .icon-masking {
      margin-left: 8px;
      color: #ff9c01;
    }
  }
</style>
