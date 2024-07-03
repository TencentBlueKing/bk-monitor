<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->

<template>
  <!-- 自定义上报列表页面 -->
  <div
    class="custom-item-container"
    data-test-id="custom_div_customContainer"
  >
    <section class="operation">
      <div class="top-operation">
        <bk-button
          v-cursor="{ active: isAllowedCreate === false }"
          class="fl"
          theme="primary"
          data-test-id="customContainer_button_addNewCustom"
          :disabled="!collectProject || isAllowedCreate === null || isRequest"
          @click="operateHandler({}, 'add')"
        >
          {{ $t('新建自定义上报') }}
        </bk-button>
        <div class="collect-search fr">
          <bk-input
            v-model="inputKeyWords"
            clearable
            data-test-id="customContainer_input_searchTableItem"
            :placeholder="$t('搜索名称、存储索引名')"
            :right-icon="'bk-icon icon-search'"
            @enter="search"
            @change="handleSearchChange"
          >
          </bk-input>
        </div>
      </div>

      <div
        class="table-operation"
        data-test-id="customContainer_table_container"
      >
        <bk-table
          v-bkloading="{ isLoading: isRequest }"
          class="custom-table"
          :data="collectList"
          :pagination="pagination"
          :limit-list="pagination.limitList"
          @page-change="handlePageChange"
          @page-limit-change="handleLimitChange"
        >
          <bk-table-column
            :label="$t('数据ID')"
            :render-header="$renderHeader"
            prop="collector_config_id"
            width="100"
          >
            <template slot-scope="props">
              <span>
                {{ props.row.bk_data_id || '--' }}
              </span>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('名称')"
            :render-header="$renderHeader"
            prop="collector_config_name"
          >
            <template slot-scope="props">
              <div class="custom-name-box">
                <span
                  class="collector-config-name"
                  @click="operateHandler(props.row, 'view')"
                >
                  {{ props.row.collector_config_name || '--' }}
                </span>
                <span
                  v-if="props.row.is_desensitize"
                  v-bk-tooltips.top="$t('已脱敏')"
                  class="bk-icon log-icon icon-masking"
                >
                </span>
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('监控对象')"
            :render-header="$renderHeader"
            prop="category_name"
          >
            <template slot-scope="props">
              <span>
                {{ props.row.category_name || '--' }}
              </span>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('数据类型')"
            :render-header="$renderHeader"
            prop="custom_name"
          >
            <template slot-scope="props">
              <span>
                {{ props.row.custom_name || '--' }}
              </span>
            </template>
          </bk-table-column>
          <bk-table-column
            min-width="200"
            width="200"
            :label="$t('标签')"
            :render-header="$renderHeader"
          >
            <template slot-scope="props">
              <index-set-label-select
                :row-data="props.row"
                :label.sync="props.row.tags"
                :select-label-list="selectLabelList"
                @refreshLabelList="initLabelSelectList"
              />
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('过期时间')"
            :render-header="$renderHeader"
            min-width="50"
          >
            <template slot-scope="props">
              <span>
                {{ props.row.retention ? `${props.row.retention} ${$t('天')}` : '--' }}
              </span>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('创建记录')"
            :render-header="$renderHeader"
            prop="created_at"
          >
            <template slot-scope="props">
              <span>
                {{ props.row.created_at || '--' }}
              </span>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('更新记录')"
            :render-header="$renderHeader"
            prop="updated_at"
            width="239"
          >
            <template slot-scope="props">
              <span>
                {{ props.row.updated_at || '--' }}
              </span>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('操作')"
            :render-header="$renderHeader"
            class-name="operate-column"
            width="202"
          >
            <div
              slot-scope="props"
              class="collect-table-operate"
            >
              <bk-button
                v-cursor="{ active: !(props.row.permission && props.row.permission[authorityMap.SEARCH_LOG_AUTH]) }"
                class="king-button"
                theme="primary"
                text
                :disabled="!props.row.is_active || (!props.row.index_set_id && !props.row.bkdata_index_set_ids.length)"
                @click="operateHandler(props.row, 'search')"
              >
                {{ $t('检索') }}</bk-button
              >
              <bk-button
                v-cursor="{
                  active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH])
                }"
                class="king-button"
                theme="primary"
                text
                @click="operateHandler(props.row, 'edit')"
              >
                {{ $t('编辑') }}</bk-button
              >
              <bk-button
                v-cursor="{
                  active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH])
                }"
                theme="primary"
                text
                :disabled="!props.row.table_id"
                @click="operateHandler(props.row, 'clean')"
              >
                {{ $t('清洗') }}
              </bk-button>
              <bk-popover
                class="dot-menu"
                placement="bottom-start"
                theme="dot-menu light"
                offset="15"
                :arrow="false"
                :distance="0"
              >
                <i
                  class="bk-icon icon-more"
                  style="margin-left: 5px; font-size: 14px; font-weight: bold"
                >
                </i>
                <ul
                  slot="content"
                  class="collection-operation-list"
                >
                  <!-- 查看详情 -->
                  <li>
                    <a
                      v-cursor="{
                        active: !(props.row.permission && props.row.permission[authorityMap.VIEW_COLLECTION_AUTH])
                      }"
                      href="javascript:;"
                      @click="operateHandler(props.row, 'view')"
                    >
                      {{ $t('详情') }}
                    </a>
                  </li>
                  <li v-if="isShowMaskingTemplate">
                    <a
                      v-cursor="{
                        active: !(props.row.permission && props.row.permission[authorityMap.VIEW_COLLECTION_AUTH])
                      }"
                      href="javascript:;"
                      @click="operateHandler(props.row, 'masking')"
                    >
                      {{ $t('日志脱敏') }}
                    </a>
                  </li>
                  <li v-if="props.row.is_active">
                    <a
                      v-if="!collectProject"
                      href="javascript:;"
                      class="text-disabled"
                    >
                      {{ $t('停用') }}
                    </a>
                    <a
                      v-else
                      v-cursor="{
                        active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH])
                      }"
                      href="javascript:;"
                      @click.stop="operateHandler(props.row, 'stop')"
                    >
                      {{ $t('停用') }}
                    </a>
                  </li>
                  <li v-else>
                    <a
                      v-if="!collectProject"
                      href="javascript:;"
                      class="text-disabled"
                    >
                      {{ $t('启用') }}
                    </a>
                    <a
                      v-else
                      v-cursor="{
                        active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH])
                      }"
                      href="javascript:;"
                      @click.stop="operateHandler(props.row, 'start')"
                    >
                      {{ $t('启用') }}
                    </a>
                  </li>
                  <li>
                    <a
                      v-if="!collectProject"
                      href="javascript:;"
                      class="text-disabled"
                    >
                      {{ $t('删除') }}
                    </a>
                    <a
                      v-else
                      v-cursor="{
                        active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH])
                      }"
                      href="javascript:;"
                      @click="deleteCollect(props.row)"
                    >
                      {{ $t('删除') }}
                    </a>
                  </li>
                </ul>
              </bk-popover>
            </div>
          </bk-table-column>
          <div slot="empty">
            <empty-status
              :empty-type="emptyType"
              @operation="handleOperation"
            />
          </div>
        </bk-table>
      </div>
    </section>
  </div>
</template>

<script>
import { projectManages } from '@/common/util';
import collectedItemsMixin from '@/mixins/collected-items-mixin';
import { mapGetters } from 'vuex';
import * as authorityMap from '../../../../common/authority-map';
import IndexSetLabelSelect from '@/components/index-set-label-select';
import EmptyStatus from '@/components/empty-status';

export default {
  name: 'CustomReportList',
  components: {
    EmptyStatus,
    IndexSetLabelSelect
  },
  mixins: [collectedItemsMixin],
  data() {
    return {
      inputKeyWords: '',
      collectList: [],
      selectLabelList: [],
      isAllowedCreate: null,
      collectProject: projectManages(this.$store.state.topMenu, 'collection-item'), // 权限
      isRequest: false,
      params: {
        collector_config_id: ''
      },
      pagination: {
        current: 1,
        count: 100,
        limit: 10,
        limitList: [10, 20, 50, 100]
      },
      emptyType: 'empty'
    };
  },
  computed: {
    ...mapGetters({
      spaceUid: 'spaceUid',
      bkBizId: 'bkBizId',
      authGlobalInfo: 'globals/authContainerInfo',
      isShowMaskingTemplate: 'isShowMaskingTemplate'
    }),
    authorityMap() {
      return authorityMap;
    }
  },
  created() {
    !this.authGlobalInfo && this.checkCreateAuth();
  },
  mounted() {
    !this.authGlobalInfo && this.initLabelSelectList();
    !this.authGlobalInfo && this.search();
  },
  methods: {
    search() {
      this.pagination.current = 1;
      this.requestData();
    },
    // 路由跳转
    leaveCurrentPage(row, operateType) {
      if (operateType === 'start' || operateType === 'stop') {
        if (!this.collectProject) return;
        if (operateType === 'stop') {
          this.$bkInfo({
            type: 'warning',
            title: this.$t('确认停用当前采集项？'),
            confirmFn: () => {
              this.toggleCollect(row, operateType);
            }
          });
        } else {
          this.toggleCollect(row, operateType);
        }
        return;
      }

      let backRoute;
      let editName;
      const params = {};
      const query = {};
      const routeMap = {
        add: 'custom-report-create',
        edit: 'custom-report-edit',
        search: 'retrieve',
        clean: 'clean-edit',
        view: 'custom-report-detail',
        masking: 'custom-report-masking'
      };

      if (operateType === 'search') {
        if (!row.index_set_id && !row.bkdata_index_set_ids.length) return;
        params.indexId = row.index_set_id ? row.index_set_id : row.bkdata_index_set_ids[0];
      }

      if (operateType === 'masking') {
        if (!row.index_set_id && !row.bkdata_index_set_ids.length) return;
        params.indexSetId = row.index_set_id ? row.index_set_id : row.bkdata_index_set_ids[0];
        editName = row.collector_config_name;
      }

      if (['clean', 'edit', 'view'].includes(operateType)) {
        params.collectorId = row.collector_config_id;
      }

      if (operateType === 'clean') {
        backRoute = this.$route.name;
      }

      if (operateType === 'edit') {
        editName = row.collector_config_name;
      }

      const targetRoute = routeMap[operateType];
      // this.$store.commit('collect/setCurCollect', row);
      this.$router.push({
        name: targetRoute,
        params,
        query: {
          ...query,
          spaceUid: this.$store.state.spaceUid,
          backRoute,
          editName
        }
      });
    },
    // 启用 || 停用
    toggleCollect(row, type) {
      const { isActive } = row;
      this.$http
        .request(`collect/${type === 'start' ? 'startCollect' : 'stopCollect'}`, {
          params: {
            collector_config_id: row.collector_config_id
          }
        })
        .then(res => {
          if (res.result) {
            row.is_active = !row.is_active;
            res.result && this.messageSuccess(this.$t('修改成功'));
            this.requestData();
          }
        })
        .catch(() => {
          row.is_active = isActive;
        });
    },
    // 删除
    deleteCollect(row) {
      this.$bkInfo({
        type: 'warning',
        subTitle: this.$t('当前上报名称为{n}，确认要删除？', { n: row.collector_config_name }),
        confirmFn: () => {
          this.requestDeleteCollect(row);
        }
      });
    },
    requestData() {
      this.isRequest = true;
      this.emptyType = this.inputKeyWords ? 'search-empty' : 'empty';
      const { ids } = this.$route.query; // 根据id来检索
      const collectorIdList = ids ? decodeURIComponent(ids) : [];
      this.$http
        .request('collect/getCollectList', {
          query: {
            bk_biz_id: this.bkBizId,
            keyword: this.inputKeyWords,
            page: this.pagination.current,
            pagesize: this.pagination.limit,
            collector_scenario_id: 'custom',
            collector_id_list: collectorIdList
          }
        })
        .then(async res => {
          const { data } = res;
          if (data && data.list) {
            const resList = data.list;
            const indexIdList = resList.filter(item => !!item.index_set_id).map(item => item.index_set_id);
            const { data: desensitizeStatus } = await this.getDesensitizeStatus(indexIdList);
            const newCollectList = resList.map(item => ({
              ...item,
              is_desensitize: desensitizeStatus[item.index_set_id]?.is_desensitize ?? false
            }));
            this.collectList.splice(0, this.collectList.length, ...newCollectList);
            this.pagination.count = data.total;
          }
        })
        .catch(() => {
          this.emptyType = '500';
        })
        .finally(() => {
          this.isRequest = false;
          // 如果有ids 重置路由
          if (ids)
            this.$router.replace({
              query: {
                spaceUid: this.$route.query.spaceUid
              }
            });
        });
    },
    handleSearchChange(val) {
      if (val === '' && !this.isRequest) {
        this.requestData();
      }
    },
    handleOperation(type) {
      if (type === 'clear-filter') {
        this.inputKeyWords = '';
        this.pagination.current = 1;
        this.requestData();
        return;
      }

      if (type === 'refresh') {
        this.emptyType = 'empty';
        this.pagination.current = 1;
        this.requestData();
        return;
      }
    },
    async getDesensitizeStatus(indexIdList = []) {
      try {
        return await this.$http.request('masking/getDesensitizeState', {
          data: { index_set_ids: indexIdList }
        });
      } catch (error) {
        return [];
      }
    },
    /** 初始化标签列表 */
    async initLabelSelectList() {
      try {
        const res = await this.$http.request('unionSearch/unionLabelList');
        this.selectLabelList = res.data;
      } catch (error) {
        this.selectLabelList = [];
      }
    }
  }
};
</script>

<style lang="scss">
@import '@/scss/mixins/clearfix';
@import '@/scss/conf';
@import '@/scss/devops-common.scss';
@import '@/scss/mixins/cursor.scss';

.custom-item-container {
  padding: 20px 24px;

  .top-operation {
    margin-bottom: 20px;

    @include clearfix;

    .bk-button {
      width: 150px;
    }

    .collect-search {
      width: 360px;
    }
  }

  .table-operation {
    .custom-table {
      overflow: visible;

      .bk-table-pagination-wrapper {
        background-color: #fafbfd;
      }

      .operate-column .cell {
        overflow: visible;
      }

      .bk-table-body-wrapper {
        overflow: auto;
      }

      .collect-table-operate {
        display: flex;
        align-items: center;

        .king-button {
          margin-right: 14px;
        }
      }

      .bk-dropdown-list a.text-disabled:hover {
        color: #c4c6cc;
        cursor: not-allowed;
      }
    }

    .collector-config-name {
      @include cursor;
    }

    .icon-masking {
      margin-left: 8px;
      color: #ff9c01;
    }
  }

  .custom-name-box {
    display: flex;
    align-items: center;

    .icon-masking {
      flex-shrink: 0;
    }
  }
}

.dot-menu {
  display: inline-block;
  vertical-align: middle;
}

.dot-menu-theme {
  /* stylelint-disable-next-line declaration-no-important */
  padding: 0 !important;

  &::before {
    /* stylelint-disable-next-line declaration-no-important */
    background: #fff !important;
  }
}

.collection-operation-list {
  display: flex;
  min-width: 50px;
  margin: 0;
  list-style: none;
  flex-direction: column;
  justify-content: center;

  li {
    padding: 4px 16px;
    font-size: 12px;
    line-height: 26px;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
      background-color: #eaf3ff;
    }
  }

  a {
    display: inline-block;
    width: 100%;
    height: 100%;
    color: #63656e;
  }

  .text-disabled {
    color: #c4c6cc;

    &:hover {
      cursor: not-allowed;
    }
  }
}
</style>
