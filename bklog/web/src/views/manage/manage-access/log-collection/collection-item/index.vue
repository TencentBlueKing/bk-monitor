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
    class="collection-item-container"
    data-test-id="logCollection_div_logCollectionBox"
  >
    <section class="top-operation">
      <bk-button
        class="fl"
        v-cursor="{ active: isAllowedCreate === false }"
        :disabled="!collectProject || isAllowedCreate === null || isTableLoading"
        data-test-id="logCollectionBox_button_addNewCollectionItem"
        theme="primary"
        @click="operateHandler({}, 'add')"
      >
        {{ $t('新建采集项') }}
      </bk-button>
      <div class="collect-search fr">
        <bk-input
          v-model="searchKeyword"
          data-test-id="logCollectionBox_input_searchCollectionItems"
          :placeholder="$t('搜索名称、存储索引名')"
          :clearable="true"
          :right-icon="'bk-icon icon-search'"
          @change="handleSearchChange"
          @enter="search"
        >
        </bk-input>
      </div>
    </section>
    <section class="collect-list">
      <bk-table
        ref="collectTable"
        class="collect-table"
        v-bkloading="{ isLoading: isTableLoading }"
        :data="collectShowList"
        :empty-text="$t('暂无内容')"
        :limit-list="pagination.limitList"
        :pagination="pagination"
        :row-class-name="handleRowClassName"
        :size="size"
        data-test-id="logCollectionBox_table_logCollectionTable"
        @filter-change="handleFilterChange"
        @page-change="handleCollectPageChange"
        @page-limit-change="handleCollectLimitChange"
        @row-mouse-enter="handleRowMouseEnter"
        @row-mouse-leave="handleRowMouseLeave"
      >
        <bk-table-column
          v-if="checkcFields('bk_data_id')"
          :label="$t('数据ID')"
          :render-header="$renderHeader"
          min-width="60"
        >
          <template #default="props">
            <span>
              {{ props.row.bk_data_id || '--' }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('名称')"
          :render-header="$renderHeader"
          min-width="90"
        >
          <template #default="props">
            <span
              class="text-active"
              v-cursor="{ active: !(props.row.permission && props.row.permission[authorityMap.VIEW_COLLECTION_AUTH]) }"
              @click="operateHandler(props.row, 'view')"
            >
              {{ props.row.collector_config_name }}
            </span>
            <span
              v-if="props.row.is_desensitize"
              class="bk-icon bklog-icon bklog-masking"
              v-bk-tooltips.top="$t('已脱敏')"
            >
            </span>
            <span
              v-if="!props.row.table_id"
              class="table-mark mark-mini mark-default"
            >
              {{ $t('未完成') }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('日用量/总用量')"
          :render-header="$renderHeader"
          min-width="80"
          sortable
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">
              {{ props.row.table_id ? formatUsage(props.row.daily_usage, props.row.total_usage) : '--' }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('table_id')"
          :label="$t('存储名')"
          :render-header="$renderHeader"
          min-width="80"
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">
              {{ props.row.table_id ? props.row.table_id_prefix + props.row.table_id : '--' }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('storage_cluster_name')"
          :label="$t('存储集群')"
          :render-header="$renderHeader"
          :filters="checkcFields('storage_cluster_name') ? filterStorageLabelList : []"
          :filter-multiple="false"
          class-name="filter-column"
          column-key="storage_cluster_name"
          prop="storage_cluster_name"
          min-width="70"
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">
              {{ props.row.storage_cluster_name || '--' }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('collector_scenario_name')"
          :filter-multiple="false"
          :filters="checkcFields('collector_scenario_name') ? scenarioFilters : []"
          :label="$t('日志类型')"
          :render-header="$renderHeader"
          class-name="filter-column"
          column-key="collector_scenario_id"
          min-width="50"
          prop="collector_scenario_id"
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">
              {{ props.row.collector_scenario_name }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('category_name')"
          :filter-multiple="false"
          :filters="checkcFields('category_name') ? categoryFilters : []"
          :label="$t('数据类型')"
          :render-header="$renderHeader"
          class-name="filter-column"
          column-key="category_id"
          min-width="50"
          prop="category_id"
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">
              {{ props.row.category_name }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('retention')"
          :label="$t('过期时间')"
          :render-header="$renderHeader"
          min-width="50"
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">
              {{ props.row.retention ? `${props.row.retention} ${$t('天')}` : '--' }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('label')"
          width="200"
          :label="$t('标签')"
          :render-header="renderTagsHeader"
          class-name="filter-column"
          prop="tags"
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
          v-if="checkcFields('es_host_state')"
          :filters="checkcFields('es_host_state') ? statusEnum : []"
          :filter-multiple="false"
          :class-name="'td-status filter-column'"
          :label="$t('采集状态')"
          :render-header="$renderHeader"
          prop="status"
          column-key="status"
          min-width="55"
        >
          <template #default="props">
            <bk-popover
              v-if="needGuide && props.$index === 0"
              :always="true"
              placement="bottom"
            >
              <div @click.stop="operateHandler(props.row, 'status')">
                <span
                  v-if="['prepare', 'pending', 'unknown', 'running'].includes(props.row.status)"
                  class="status status-running"
                >
                  <i class="bk-icon icon-refresh"></i>
                  {{ props.row.status_name || '--' }}
                </span>
                <span
                  v-else-if="props.row.status === 'stop'"
                  class="text-disabled"
                >
                  {{ props.row.status_name || '--' }}
                </span>
                <span
                  v-else-if="props.row.status === 'terminated'"
                  class="text-disabled cursor-disabled"
                >
                  {{ props.row.status_name || '--' }}
                </span>
                <span
                  v-else
                  :class="['status', 'status-' + props.row.status, { 'cursor-disabled': !loadingStatus }]"
                >
                  <span v-if="props.row.status">
                    <i class="icon-circle"></i>
                    {{ props.row.status_name || '--' }}
                  </span>
                  <span
                    v-if="props.row.status === ''"
                    class="status status-running"
                  >
                    <i class="bk-icon icon-refresh"></i>
                  </span>
                </span>
              </div>
              <template #content>
                <div style="padding: 7px 6px">
                  <span style="color: #d2d5dd"> {{ $t('点击查看') }} </span>{{ $t('采集状态') }}
                </div>
              </template>
            </bk-popover>
            <div
              v-else
              v-cursor="{
                active:
                  !(props.row.permission && props.row.permission[authorityMap.VIEW_COLLECTION_AUTH]) &&
                  props.row.status !== 'terminated',
              }"
              @click.stop="operateHandler(props.row, 'status')"
            >
              <span
                v-if="['prepare', 'pending', 'unknown', 'running'].includes(props.row.status)"
                class="status status-running"
              >
                <i class="bk-icon icon-refresh"></i>
                {{ props.row.status_name || '--' }}
              </span>
              <span
                v-else-if="props.row.status === 'stop'"
                class="text-disabled"
              >
                {{ props.row.status_name || '--' }}
              </span>
              <span
                v-else-if="props.row.status === 'terminated'"
                class="text-disabled cursor-disabled"
              >
                {{ props.row.status_name || '--' }}
              </span>
              <span
                v-else
                :class="['status', 'status-' + props.row.status, { 'cursor-disabled': !loadingStatus }]"
              >
                <span v-if="props.row.status">
                  <i class="icon-circle"></i>
                  {{ props.row.status_name || '--' }}
                </span>
                <span
                  v-if="props.row.status === ''"
                  class="status status-running"
                >
                  <i class="bk-icon icon-refresh"></i>
                </span>
              </span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('updated_by')"
          :label="$t('更新人')"
          :render-header="$renderHeader"
          min-width="55"
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">{{ props.row.updated_by }}</span>
          </template>
        </bk-table-column>
        <bk-table-column
          v-if="checkcFields('updated_at')"
          width="190"
          :label="$t('更新时间')"
          :render-header="$renderHeader"
        >
          <template #default="props">
            <span :class="{ 'text-disabled': props.row.status === 'stop' }">{{ props.row.updated_at }}</span>
          </template>
        </bk-table-column>
        <bk-table-column
          width="160"
          :label="$t('操作')"
          :render-header="$renderHeader"
          class-name="operate-column"
        >
          <template #default="props">
            <div class="collect-table-operate">
              <!-- 检索 -->
              <!-- 启用状态下 且存在 index_set_id 才能检索 -->
              <span
                class="king-button"
                v-bk-tooltips.top="{
                  content: getDisabledTipsMessage(props.row, 'search'),
                  disabled: getOperatorCanClick(props.row, 'search'),
                  delay: 500,
                }"
              >
                <bk-button
                  v-cursor="{ active: !(props.row.permission && props.row.permission[authorityMap.SEARCH_LOG_AUTH]) }"
                  :disabled="!getOperatorCanClick(props.row, 'search')"
                  theme="primary"
                  text
                  @click="operateHandler(props.row, 'search')"
                >
                  {{ $t('检索') }}
                </bk-button>
              </span>
              <!-- 编辑 -->
              <span
                class="king-button"
                v-bk-tooltips.top="{
                  content: getDisabledTipsMessage(props.row, 'edit'),
                  disabled: getOperatorCanClick(props.row, 'edit'),
                  delay: 500,
                }"
              >
                <bk-button
                  v-cursor="{
                    active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH]),
                  }"
                  :disabled="!getOperatorCanClick(props.row, 'edit')"
                  theme="primary"
                  text
                  @click.stop="operateHandler(props.row, 'edit')"
                >
                  {{ $t('编辑') }}
                </bk-button>
              </span>

              <!-- 清洗 -->
              <span
                class="king-button"
                v-bk-tooltips.top="{
                  content: getDisabledTipsMessage(props.row, 'clean'),
                  disabled: getOperatorCanClick(props.row, 'clean'),
                  delay: 500,
                }"
              >
                <bk-button
                  v-cursor="{
                    active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH]),
                  }"
                  :disabled="!getOperatorCanClick(props.row, 'clean')"
                  theme="primary"
                  text
                  @click.stop="operateHandler(props.row, 'clean')"
                >
                  {{ $t('清洗') }}
                </bk-button>
              </span>

              <bk-popover
                class="dot-menu"
                :arrow="false"
                :distance="0"
                offset="15"
                placement="bottom-start"
                theme="dot-menu light"
              >
                <i
                  style="margin-left: 5px; font-size: 14px; font-weight: bold"
                  class="bk-icon icon-more"
                >
                </i>
                <template #content>
                  <ul class="collection-operation-list">
                    <!-- 查看详情 -->
                    <li>
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'view'),
                          disabled: getOperatorCanClick(props.row, 'view'),
                          delay: 500,
                        }"
                        v-cursor="{
                          active: !(props.row.permission && props.row.permission[authorityMap.VIEW_COLLECTION_AUTH]),
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'view') }"
                        href="javascript:;"
                        @click="operateHandler(props.row, 'view')"
                      >
                        {{ $t('详情') }}
                      </a>
                    </li>
                    <li v-if="isShowMaskingTemplate">
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'masking'),
                          disabled: getOperatorCanClick(props.row, 'masking'),
                          delay: 500,
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'masking') }"
                        href="javascript:;"
                        @click.stop="operateHandler(props.row, 'masking')"
                      >
                        {{ $t('日志脱敏') }}
                      </a>
                    </li>
                    <!-- 存储设置 -->
                    <li>
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'storage'),
                          disabled: getOperatorCanClick(props.row, 'storage'),
                          delay: 500,
                        }"
                        v-cursor="{
                          active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH]),
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'storage') }"
                        href="javascript:;"
                        @click.stop="operateHandler(props.row, 'storage')"
                        >{{ $t('存储设置') }}</a
                      >
                    </li>
                    <!-- 克隆 -->
                    <li>
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'clone'),
                          disabled: getOperatorCanClick(props.row, 'clone'),
                          delay: 500,
                        }"
                        v-cursor="{
                          active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH]),
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'clone') }"
                        href="javascript:;"
                        @click.stop="operateHandler(props.row, 'clone')"
                      >
                        {{ $t('克隆') }}
                      </a>
                    </li>
                    <li v-if="props.row.is_active">
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'stop'),
                          disabled: getOperatorCanClick(props.row, 'stop'),
                          delay: 500,
                        }"
                        v-cursor="{
                          active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH]),
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'stop') }"
                        href="javascript:;"
                        @click.stop="stopCollectHandler(props.row)"
                      >
                        {{ $t('停用') }}
                      </a>
                    </li>
                    <li v-else>
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'start'),
                          disabled: getOperatorCanClick(props.row, 'start'),
                          delay: 500,
                        }"
                        v-cursor="{
                          active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH]),
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'start') }"
                        href="javascript:;"
                        @click.stop="operateHandler(props.row, 'start')"
                      >
                        {{ $t('启用') }}
                      </a>
                    </li>
                    <li>
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'delete'),
                          disabled: getOperatorCanClick(props.row, 'delete'),
                          delay: 500,
                        }"
                        v-cursor="{
                          active: !(props.row.permission && props.row.permission[authorityMap.MANAGE_COLLECTION_AUTH]),
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'delete') }"
                        href="javascript:;"
                        @click.stop="operateHandler(props.row, 'delete')"
                      >
                        {{ $t('删除') }}
                      </a>
                    </li>
                    <li v-if="enableCheckCollector">
                      <a
                        v-bk-tooltips.top="{
                          content: getDisabledTipsMessage(props.row, 'report'),
                          disabled: getOperatorCanClick(props.row, 'report'),
                          delay: 500,
                        }"
                        :class="{ 'text-disabled': !getOperatorCanClick(props.row, 'report') }"
                        href="javascript:;"
                        @click.stop="handleShowReport(props.row)"
                      >
                        {{ $t('一键检测') }}
                      </a>
                    </li>
                  </ul>
                </template>
              </bk-popover>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column type="setting">
          <bk-table-setting-content
            v-en-style="'width: 500px'"
            :fields="columnSetting.fields"
            :selected="columnSetting.selectedFields"
            :size="columnSetting.size"
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
    </section>
    <collection-report-view
      v-model="reportDetailShow"
      :check-record-id="checkRecordId"
      @close-report="() => (reportDetailShow = false)"
    />
    <issuedSlider
      ref="issuedSliderRef"
      :is-finish-create-step="true"
      :is-switch="true"
      :operate-type="'stop'"
      :is-stop-collection="true"
      :collector-config-id="currentRowCollectorConfigId"
    ></issuedSlider>
  </section>
</template>

<script>
  import {
    projectManages,
    clearTableFilter,
    getDefaultSettingSelectFiled,
    setDefaultSettingSelectFiled,
    updateLastSelectedIndexId
  } from '@/common/util';
  import collectedItemsMixin from '@/mixins/collected-items-mixin';
  import { mapGetters } from 'vuex';
  import { formatBytes, requestStorageUsage } from '../../util.js';
  import * as authorityMap from '../../../../../common/authority-map';
  import EmptyStatus from '../../../../../components/empty-status';
  import IndexSetLabelSelect from '../../../../../components/index-set-label-select';
  import CollectionReportView from '../../components/collection-report-view';
  import ClusterFilter from '../../../../retrieve-v2/search-result-panel/log-clustering/components/finger-tools/cluster-filter.tsx';
  import issuedSlider from '@/components/collection-access/issued-slider.vue';

  export default {
    name: 'CollectionItem',
    components: {
      CollectionReportView,
      EmptyStatus,
      IndexSetLabelSelect,
      issuedSlider,
    },
    mixins: [collectedItemsMixin],
    data() {
      const settingFields = [
        // 数据ID
        {
          id: 'bk_data_id',
          label: this.$t('数据ID'),
        },
        // 采集配置名称
        {
          id: 'collector_config_name',
          label: this.$t('名称'),
          disabled: true,
        },
        // 用量展示
        {
          id: 'storage_usage',
          label: this.$t('日用量/总用量'),
          disabled: true,
        },
        // 存储名
        {
          id: 'table_id',
          label: this.$t('存储名'),
        },
        // 日志类型
        {
          id: 'collector_scenario_name',
          label: this.$t('日志类型'),
        },
        // 过期时间
        {
          id: 'retention',
          label: this.$t('过期时间'),
        },
        {
          id: 'label',
          label: this.$t('标签'),
        },
        // 采集状态
        {
          id: 'es_host_state',
          label: this.$t('采集状态'),
        },
        // 更新人
        {
          id: 'updated_by',
          label: this.$t('更新人'),
        },
        // 更新时间
        {
          id: 'updated_at',
          label: this.$t('更新时间'),
        },
        // 存储集群
        {
          id: 'storage_cluster_name',
          label: this.$t('存储集群'),
        },
        // 数据类型
        {
          id: 'category_name',
          label: this.$t('数据类型'),
        },
        // 操作
        {
          id: 'operation',
          label: this.$t('操作'),
          disabled: true,
        },
      ];
      const statusEnum = [
        {
          text: this.$t('label-正常').replace('label-', ''),
          value: 'success',
        },
        {
          text: this.$t('label-失败').replace('label-', ''),
          value: 'failed',
        },
        {
          text: this.$t('label-部署中').replace('label-', ''),
          value: 'running',
        },
        {
          text: this.$t('label-已停用').replace('label-', ''),
          value: 'terminated',
        },
        {
          text: this.$t('label-未知').replace('label-', ''),
          value: 'unknown',
        },
        {
          text: this.$t('label-准备中').replace('label-', ''),
          value: 'prepare',
        },
      ];

      return {
        keyword: '',
        searchKeyword: '',
        count: 0,
        size: 'small',
        needGuide: false,
        timer: null,
        loadingStatus: false,
        isTableLoading: true,
        pagination: {
          current: 1,
          count: 0,
          limit: 10,
          limitList: [10, 20, 50, 100],
        },
        collectList: [],
        collectorIdStr: '',
        collectProject: projectManages(this.$store.state.topMenu, 'collection-item'),
        filterParams: {
          status: '',
          collector_scenario_id: '',
          category_id: '',
          tags: '',
          storage_cluster_name: '',
        },
        isAllowedCreate: null,
        columnSetting: {
          fields: settingFields,
          selectedFields: [...settingFields.slice(3, 8), settingFields[2]],
        },
        statusEnum: statusEnum,
        // 是否支持一键检测
        enableCheckCollector: JSON.parse(window.ENABLE_CHECK_COLLECTOR),
        // 一键检测弹窗配置
        reportDetailShow: false,
        // 一键检测采集项标识
        checkRecordId: '',
        emptyType: 'empty',
        filterSearchObj: {},
        isShouldPollCollect: false, // 当前列表是否需要轮询
        settingCacheKey: 'clusterList',
        selectLabelList: [],
        filterLabelList: [],
        tagSelect: ['all'],
        tagsData: {
          tags: [],
        },
        tagBaseList: [
          {
            id: 'all',
            name: this.$t('全部'),
          },
        ],
        filterStorageLabelList: [],
        currentRowCollectorConfigId: '',
      };
    },
    computed: {
      ...mapGetters({
        spaceUid: 'spaceUid',
        bkBizId: 'bkBizId',
        authGlobalInfo: 'globals/authContainerInfo',
        isShowMaskingTemplate: 'isShowMaskingTemplate',
      }),
      ...mapGetters('globals', ['globalsData']),
      authorityMap() {
        return authorityMap;
      },
      scenarioFilters() {
        const { collector_scenario: collectorScenario } = this.globalsData;
        const target = [];

        collectorScenario?.forEach(data => {
          if (data.is_active) {
            target.push({
              text: data.name,
              value: data.id,
            });
          }
        });
        return target;
      },
      categoryFilters() {
        const { category } = this.globalsData;
        const target = [];
        category?.forEach(data => {
          data.children.forEach(val => {
            target.push({
              text: val.name,
              value: val.id,
            });
          });
        });
        return target;
      },
      collectShowList() {
        let collect = this.collectList;
        if (this.isFilterSearch) {
          const fParams = this.filterParams;
          collect = collect.filter(item =>
            Object.keys(fParams).every(key =>
              this.filterIsNotCompared(fParams[key]) ? true : this.compareFilter(item[key], fParams[key], key),
            ),
          );
        }
        if (this.keyword) {
          collect = collect.filter(item =>
            item.collector_config_name.toString().toLowerCase().includes(this.keyword.toLowerCase()),
          );
        }
        this.emptyType = this.keyword || this.isFilterSearch ? 'search-empty' : 'empty';
        this.changePagination({ count: collect.length });
        const { current, limit } = this.pagination;
        const startIndex = (current - 1) * limit;
        const endIndex = current * limit;
        return collect.slice(startIndex, endIndex);
      },
      isFilterSearch() {
        return !!Object.values(this.filterParams).some(item => !this.filterIsNotCompared(item));
      },
    },
    created() {
      !this.authGlobalInfo && this.checkCreateAuth();
      const { selectedFields } = this.columnSetting;
      this.columnSetting.selectedFields = getDefaultSettingSelectFiled(this.settingCacheKey, selectedFields);
    },
    async mounted() {
      this.needGuide = !localStorage.getItem('needGuide');
      !this.authGlobalInfo && (await this.initLabelSelectList());
      !this.authGlobalInfo && this.requestData();
    },
    beforeDestroy() {
      this.isShouldPollCollect = false;
      this.stopStatusPolling();
    },
    watch: {
      collectShowList: {
        handler(val) {
          if (val) {
            const callbackFn = (item, key, value) => {
              this.$set(item, key, value[key]);
            };
            requestStorageUsage(this.bkBizId, val, true, callbackFn)
              .catch(error => {
                console.error('Error loading data:', error);
              })
              .finally(() => {
                this.isTableLoading = false;
              });
          }
        },
      },
    },
    methods: {
      async stopCollectHandler(row) {
        if (this.getOperatorCanClick(row, 'stop')) {
          this.$store.commit('collect/setCurCollect', row);
          await this.$refs.issuedSliderRef.requestIssuedClusterList();
          this.$refs.issuedSliderRef?.viewDetail();
          this.currentRowCollectorConfigId = row?.collector_config_id ?? '';
        }
      },
      handleSearchChange(val) {
        if (val === '') {
          this.changePagination({ current: 1 });
          this.keyword = '';
          this.searchKeyword = '';
        }
      },
      search() {
        this.keyword = this.searchKeyword;
        this.emptyType = this.keyword || this.isFilterSearch ? 'search-empty' : 'empty';
      },
      checkcFields(field) {
        return this.columnSetting.selectedFields.some(item => item.id === field);
      },
      // 离开当前页路由操作
      leaveCurrentPage(row, operateType) {
        if (operateType === 'status' && (!this.loadingStatus || row.status === 'terminated')) return; // 已停用禁止操作
        if (operateType === 'status' && (!row.status || row.status === 'prepare')) {
          return this.operateHandler(row, 'edit');
        }
        // running、prepare 状态不能启用、停用
        if (operateType === 'start' || operateType === 'stop') {
          if (!this.loadingStatus || row.status === 'running' || row.status === 'prepare' || !this.collectProject)
            return;
          if (operateType === 'start') {
            // 启用
            this.toggleCollect(row);
          } else {
            // 如果是容器采集项则停用页显示状态页
            this.$router.push({
              name: 'collectStop',
              params: {
                collectorId: row.collector_config_id || '',
              },
              query: {
                spaceUid: this.$store.state.spaceUid,
              },
            });
          }
          return;
        }
        // running 状态不能删除
        if (operateType === 'delete') {
          if (!this.collectProject) return;
          if (!row.is_active && row.status !== 'running') {
            this.$bkInfo({
              type: 'warning',
              subTitle: this.$t('当前采集项名称为{n}，确认要删除？', { n: row.collector_config_name }),
              confirmFn: () => {
                this.requestDeleteCollect(row);
              },
            });
          }
          return;
        }

        let backRoute = undefined;
        const params = {};
        const query = {};
        const routeMap = {
          add: 'collectAdd',
          view: 'manage-collection',
          status: 'manage-collection',
          edit: 'collectEdit',
          field: 'collectField',
          search: 'retrieve',
          clean: 'clean-edit',
          storage: 'collectStorage',
          clone: 'collectAdd',
          masking: 'collectMasking',
        };
        const targetRoute = routeMap[operateType];
        // 查看详情 - 如果处于未完成状态，应该跳转到编辑页面
        if (targetRoute === 'manage-collection') {
          if (!row.table_id) {
            return this.operateHandler(row, 'edit');
          }
        }
        if (
          ['manage-collection', 'collectEdit', 'collectField', 'collectStorage', 'collectMasking'].includes(targetRoute)
        ) {
          params.collectorId = row.collector_config_id;
        }
        if (operateType === 'status') {
          query.type = 'collectionStatus';
        }
        if (operateType === 'search') {
          updateLastSelectedIndexId(this.spaceUid, row.index_set_id)
          if (!row.index_set_id && !row.bkdata_index_set_ids.length) return;
          params.indexId = row.index_set_id ? row.index_set_id : row.bkdata_index_set_ids[0];
        }
        if (operateType === 'clean') {
          params.collectorId = row.collector_config_id;
          if (row.itsm_ticket_status === 'applying') {
            return this.operateHandler(row, 'field');
          }
          backRoute = this.$route.name;
        }
        // 克隆操作需要ID进行数据回显
        if (operateType === 'clone') {
          params.collectorId = row.collector_config_id;
          query.collectorId = row.collector_config_id;
          query.type = 'clone';
        }
        if (operateType === 'masking') {
          // 直接跳转到脱敏页隐藏左侧的步骤
          query.type = 'masking';
        }
        this.$store.commit('collect/setCurCollect', row);

        this.$router.push({
          name: targetRoute,
          params,
          query: {
            ...query,
            spaceUid: this.$store.state.spaceUid,
            backRoute,
          },
        });
      },
      // 表头过滤
      handleFilterChange(data) {
        this.changePagination({ current: 1 });
        Object.keys(data).forEach(item => {
          this.filterParams[item] = item !== 'tags' ? data[item].join('') : data[item];
        });
      },
      handleSettingChange({ fields }) {
        this.columnSetting.selectedFields = fields;
        setDefaultSettingSelectFiled(this.settingCacheKey, fields);
      },
      // 轮询
      startStatusPolling() {
        this.stopStatusPolling();
        this.timer = setTimeout(() => {
          this.isShouldPollCollect && this.collectorIdStr && this.requestCollectStatus(true);
        }, 10000);
      },
      stopStatusPolling() {
        clearTimeout(this.timer);
      },
      requestData() {
        this.isTableLoading = true;
        const ids = this.$route.query.ids; // 根据id来检索
        const collectorIdList = ids ? decodeURIComponent(ids) : [];
        this.$http
          .request('collect/getAllCollectors', {
            query: {
              bk_biz_id: this.bkBizId,
              collector_id_list: collectorIdList,
              have_data_id: 1,
              not_custom: 1,
            },
          })
          .then(async res => {
            const { data } = res;
            if (data && data.length) {
              const idList = [];
              const indexIdList = data.filter(item => !!item.index_set_id).map(item => item.index_set_id);
              const { data: desensitizeStatus } = await this.getDesensitizeStatus(indexIdList);
              const setStorageClusterName = new Set();
              data.forEach(row => {
                row.status = '';
                row.status_name = '';
                idList.push(row.collector_config_id);
                row.is_desensitize = desensitizeStatus[row.index_set_id]?.is_desensitize ?? false;
                if (!!row.storage_cluster_name) setStorageClusterName.add(row.storage_cluster_name);
              });
              this.filterStorageLabelList = Array.from(setStorageClusterName).map(item => ({
                text: item,
                value: item,
              }));
              this.collectList = data;
              this.changePagination({ count: data.length });
              this.collectorIdStr = idList.join(',');
              if (this.needGuide) {
                setTimeout(() => {
                  localStorage.setItem('needGuide', 'false');
                  this.needGuide = false;
                }, 3000);
              }
            }
            if (this.collectorIdStr) {
              this.requestCollectStatus();
            }
          })
          .catch(() => {
            this.emptyType = '500';
          })
          .finally(() => {
            this.isTableLoading = false;
            // 如果有ids 重置路由
            if (ids)
              this.$router.replace({
                query: {
                  spaceUid: this.$route.query.spaceUid,
                },
              });
          });
      },
      handleOperation(type) {
        if (type === 'clear-filter') {
          this.keyword = '';
          this.searchKeyword = '';
          this.changePagination({ current: 1 });
          clearTableFilter(this.$refs.collectTable);
          return;
        }

        if (type === 'refresh') {
          this.emptyType = 'empty';
          this.changePagination({ current: 1 });
          this.requestData();
          return;
        }
      },
      requestCollectStatus(isPrivate) {
        this.$http
          .request('collect/getCollectStatus', {
            query: {
              collector_id_list: this.collectorIdStr,
            },
          })
          .then(res => {
            this.statusHandler(res.data || []);
            if (this.isShouldPollCollect) this.startStatusPolling();
            if (!isPrivate) this.loadingStatus = true;
          })
          .catch(() => {
            if (isPrivate) this.stopStatusPolling();
          });
      },
      // 启用
      toggleCollect(row) {
        const { isActive, status, statusName } = row;
        row.status = 'running';
        row.status_name = this.$t('部署中');
        this.$http
          .request('collect/startCollect', {
            params: {
              collector_config_id: row.collector_config_id,
            },
          })
          .then(res => {
            if (res.result) {
              row.is_active = !row.is_active;
              this.startStatusPolling();
            }
          })
          .catch(() => {
            row.is_active = isActive;
            row.status = status;
            row.status_name = statusName;
          });
      },
      // PREPARE  RUNNING  UNKNOWN
      statusHandler(data) {
        this.isShouldPollCollect = false;
        data.forEach(item => {
          if (['prepare', 'running', 'unknown'].includes(item.status.toLowerCase())) this.isShouldPollCollect = true;
          this.collectList.forEach(row => {
            if (row.collector_config_id === item.collector_id) {
              row.status = item.status.toLowerCase();
              row.status_name = item.status_name;
            }
          });
        });
      },
      handleShowReport(row) {
        this.$http
          .request('collect/runCheck', {
            data: {
              collector_config_id: row.collector_config_id,
            },
          })
          .then(res => {
            if (res.data?.check_record_id) {
              this.reportDetailShow = true;
              this.checkRecordId = res.data.check_record_id;
            }
          });
      },
      async getDesensitizeStatus(indexIdList = []) {
        try {
          return await this.$http.request('masking/getDesensitizeState', {
            data: { index_set_ids: indexIdList },
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
          const cloneTagBase = structuredClone(this.tagBaseList);
          const notBuiltInList = res.data
            .filter(item => !item.is_built_in)
            .map(item => ({
              id: item.name,
              name: item.name,
            }));
          this.filterLabelList = cloneTagBase.concat(notBuiltInList);
        } catch (error) {
          this.selectLabelList = [];
          this.filterLabelList = [];
        }
      },
      handleRowClassName({ row }) {
        if (row.itsm_ticket_status === 'applying') {
          return 'itsm-ticket-applying';
        }

        return '';
      },
      handleRowMouseEnter(_index, e, row) {
        if (row.itsm_ticket_status === 'applying') {
          if (!this.itsmApplyingPopoverInstance) {
            this.itsmApplyingPopoverInstance = this.$bkPopover(e.target, {
              content: this.$t('容量审核中，请等待'),
              placement: 'top',
              arrow: true,
              extCls: 'itsm-applying-popover',
              onHidden: () => {
                this.itsmApplyingPopoverInstance?.destroy();
                this.itsmApplyingPopoverInstance = null;
              },
            });
          }
          this.itsmApplyingPopoverInstance?.show(300);
        }
      },
      handleRowMouseLeave() {
        this.itsmApplyingPopoverInstance?.destroy();
        this.itsmApplyingPopoverInstance = null;
      },
      handleCollectPageChange(current) {
        this.changePagination({ current });
      },
      handleCollectLimitChange(limit) {
        this.changePagination({ limit, current: 1 });
      },
      changePagination(pagination = {}) {
        Object.assign(this.pagination, pagination);
      },
      filterIsNotCompared(val) {
        if (typeof val === 'string' && val === '') return true;
        if (typeof val === 'obj' && JSON.stringify(val) === '{}') return true;
        if (Array.isArray(val) && !val.length) return true;
        return false;
      },
      compareFilter(compare, fCompare, key) {
        if (key === 'tags') return compare.some(item => fCompare.includes(item.name));
        return compare === fCompare;
      },
      handleTagSelectChange(v) {
        if (!v.length) {
          this.tagSelect = ['all'];
          return;
        }
        const lastSelect = v[v.length - 1];
        if (lastSelect === 'all') {
          this.tagSelect = [lastSelect];
        } else {
          this.tagSelect = v.filter(item => !(item === 'all'));
        }
      },
      handleTagSubmit(v) {
        this.tagsData.tags = !v.includes('all') ? v : [];
        this.handleFilterChange(this.tagsData);
      },
      handleToggleTagSelect() {
        this.tagSelect = !!this.tagsData.tags.length ? structuredClone(this.tagsData.tags) : ['all'];
      },
      renderTagsHeader(h, { column }) {
        const isActive = !!this.filterLabelList.length && !this.tagSelect.includes('all');
        return h(ClusterFilter, {
          props: {
            title: column.label,
            disabled: false,
            select: this.tagSelect,
            selectList: this.filterLabelList,
            toggle: this.handleToggleTagSelect,
            isActive,
          },
          on: {
            selected: this.handleTagSelectChange,
            submit: this.handleTagSubmit,
          },
        });
      },
      formatUsage(dailyUsage, totalUsage) {
        return `${formatBytes(dailyUsage)} / ${formatBytes(totalUsage)}`;
      },
    },
  };
</script>

<style lang="scss">
  @import '../../../../../scss/mixins/clearfix';
  @import '../../../../../scss/conf';
  @import '../../../../../scss/devops-common.scss';

  .collection-item-container {
    padding: 20px 24px;

    .top-operation {
      margin-bottom: 20px;

      @include clearfix;

      .bk-button {
        width: 120px;
      }
    }

    .collect-search {
      width: 360px;
    }

    .collect-table {
      overflow: visible;

      .text-disabled {
        color: #c4c6cc;
      }

      .text-active {
        color: #3a84ff;
        cursor: pointer;
      }

      .filter-column {
        .cell {
          /* stylelint-disable-next-line declaration-no-important */
          display: flex !important;
        }
      }

      .itsm-ticket-applying {
        .cell {
          pointer-events: none;
        }
      }
    }

    .bk-table-body-wrapper {
      overflow-x: auto;
    }

    /* stylelint-disable-next-line no-descending-specificity */
    .operate-column .cell {
      overflow: visible;
    }

    .td-status .cursor-disabled {
      cursor: not-allowed;
    }

    .table-mark {
      display: inline-block;
      height: 17px;
      padding: 0 2px;
      margin-left: 4px;
      font-size: 10px;
      line-height: 17px;
      color: #fff;
      background: #979ba5;
      border-radius: 2px;
    }

    .icon-masking {
      color: #ff9c01;
    }

    .status {
      cursor: pointer;

      .icon-circle {
        display: inline-block;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        transform: translateY(-2px);

        &::before {
          content: '';
        }
      }

      &.status-running i {
        display: inline-block;
        animation: button-icon-loading 1s linear infinite;
      }

      &.status-success i {
        background: $iconSuccessColor;
      }

      &.status-failed i {
        background: $iconFailColor;
      }
    }

    .collect-table-operate {
      display: flex;
      align-items: center;

      .king-button {
        margin-right: 14px;

        &:last-child {
          margin-right: 0;
        }
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
    flex-direction: column;
    justify-content: center;
    min-width: 50px;
    margin: 0;
    list-style: none;

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

    /* stylelint-disable-next-line no-descending-specificity */
    .text-disabled {
      color: #c4c6cc;

      &:hover {
        cursor: not-allowed;
      }
    }
  }

  .bk-table-setting-popover-content-theme.tippy-tooltip {
    padding: 15px 0 0;

    .bk-table-setting-content .content-line-height {
      display: none;
    }
  }

  .itsm-applying-popover {
    .tippy-content {
      font-size: 12px;
    }
  }
</style>
