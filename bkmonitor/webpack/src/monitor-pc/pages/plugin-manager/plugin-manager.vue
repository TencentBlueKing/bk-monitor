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
  <guide-page
    v-if="showGuidePage"
    :guide-data="curIntroduceData"
  />
  <div
    v-else
    class="plugin-container"
  >
    <div class="plugin-manager">
      <page-tips
        style="margin-bottom: 16px"
        :link-text="$t('采集器安装前往节点管理')"
        :link-url="`${$store.getters.bkNodeManHost}#/plugin-manager/list`"
        :tips-text="$t('可以通过制作各种监控插件满足数据采集的需求，该功能依赖服务器安装bkmonitorbeat采集器。')"
      />
      <div class="plugin-manager-header">
        <div class="left">
          <bk-button
            v-authority="{ active: !authority.MANAGE_AUTH }"
            class="left-button mc-btn-add"
            theme="primary"
            @click="authority.MANAGE_AUTH ? handlePluginAdd(null) : handleShowAuthorityDetail()"
          >
            <span class="icon-monitor icon-plus-line mr-6" />
            {{ $t('新建') }}
          </bk-button>
          <bk-button
            v-authority="{ active: !authority.MANAGE_AUTH }"
            class="left-button mc-btn-add"
            @click="!authority.MANAGE_AUTH && handleShowAuthorityDetail()"
          >
            {{ $t('导入') }}
            <input
              v-if="authority.MANAGE_AUTH"
              ref="importInput"
              class="left-button-file"
              accept=".gz, .tgz"
              hidden="true"
              multiple="multiple"
              title=""
              type="file"
              @change="handleFileChange"
            />
          </bk-button>
          <!-- <bk-button class="left-button" :disabled="header.delete" @click="handleDeletePlugin">
                        删除
                    </bk-button> -->
        </div>
        <div class="right">
          <bk-input
            :clearable="true"
            :placeholder="$t('插件名称(ID或别名)')"
            :value="header.keyword"
            right-icon="bk-icon icon-search"
            @change="handleSearchKey"
            @clear="cancelListRequest"
          />
        </div>
      </div>
      <div class="plugin-manager-content">
        <ul class="tab-list">
          <li
            v-for="(item, index) in panel.tabs"
            :key="item.name"
            class="tab-list-item"
            :class="{ 'tab-active': index === panel.active }"
            @click="handlePanelChange(item, index)"
          >
            <span class="tab-name">{{ item.name }}</span>
            <span class="tab-num">{{ item.num }}</span>
          </li>
          <li class="tab-list-blank" />
        </ul>
        <table-skeleton
          v-if="loading || table.loading"
          class="plugin-table-skeleton"
          :type="2"
        />
        <template v-else>
          <bk-table
            class="plugin-table"
            :data="table.data"
            :empty-text="table.message"
            tooltip-effect="dark"
            @row-mouse-enter="i => (table.hoverIndex = i)"
            @row-mouse-leave="i => (table.hoverIndex = -1)"
            @sort-change="handleSortChange"
          >
            <!-- <bk-table-column
                        type="selection"
                        :selectable="handleSelectAble"
                        align="center"
                        width="50">
                    </bk-table-column> -->
            <div slot="empty">
              <empty-status
                :type="emptyType"
                @operation="handleOperation"
              />
            </div>
            <bk-table-column
              :label="$t('插件名称')"
              min-width="250"
              prop="plugin_id"
              sortable="custom"
            >
              <template slot-scope="scope">
                <div class="col-name">
                  <div
                    :style="{
                      'background-image': scope.row.logo ? `url(data:image/gif;base64,${scope.row.logo})` : 'none',
                      'background-color': scope.row.logo ? '' : colorMap[scope.row.plugin_type],
                      borderRadius: scope.row.log ? '2px' : '100%',
                    }"
                    class="col-name-icon"
                  >
                    {{ scope.row.logo ? '' : scope.row.plugin_display_name.slice(0, 1).toLocaleUpperCase() }}
                  </div>
                  <div
                    v-authority="{
                      active: !authority.MANAGE_AUTH && scope.row.status === 'draft',
                    }"
                    class="col-name-desc"
                    @click="
                      getManageAuth(scope.row) && scope.row.status === 'draft'
                        ? showAuthorityDetail(scope.row)
                        : showPluginInfo(scope.row)
                    "
                  >
                    <div class="desc-alias">
                      <span
                        v-bk-overflow-tips
                        class="desc-alias-title"
                      >
                        {{ scope.row.plugin_display_name ? scope.row.plugin_display_name : scope.row.plugin_id }}
                      </span>
                      <span
                        v-if="scope.row.is_official"
                        class="desc-alias-gov"
                      >
                        <span> {{ $t('官方') }} </span>
                      </span>
                    </div>
                    <span class="desc-category">{{ scope.row.plugin_id }}</span>
                  </div>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column :label="$t('类型')">
              <template slot-scope="scope">
                <div>{{ pluginTypeMap[scope.row.plugin_type] }}</div>
              </template>
            </bk-table-column>
            <bk-table-column
              width="150"
              :label="$t('分类')"
              :render-header="renderHeader"
              class-name="label-title"
            >
              <template slot-scope="scope">
                <div class="col-label">
                  <span v-if="scope.$index !== table.editIndex"
                    >{{ scope.row.label_info.first_label_name }}/{{ scope.row.label_info.second_label_name }}</span
                  >
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              v-if="false"
              :label="$t('所属')"
              min-width="120"
              prop="bk_biz_id"
              sortable="custom"
            >
              <template slot-scope="scope">
                {{ bizMap[scope.row.bk_biz_id] || '--' }}
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('关联配置')"
              :width="$store.getters.lang === 'en' ? 160 : 80"
              align="right"
            >
              <template slot-scope="scope">
                <div
                  class="col-right"
                  :class="{ 'col-set': scope.row.related_conf_count > 0 }"
                  @click="handleToCollectorConfig(scope)"
                >
                  {{ scope.row.related_conf_count > 0 ? scope.row.related_conf_count : '--' }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('状态')"
              min-width="100"
              prop="status"
              sortable="custom"
            >
              <template slot-scope="scope">
                <div :style="{ color: table.statusMap[scope.row.status].color }">
                  {{ table.statusMap[scope.row.status].desc }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('创建记录')"
              min-width="150"
              prop="create_time"
              sortable="custom"
            >
              <template slot-scope="scope">
                <div class="user-time">
                  <div class="col-create">
                    <bk-user-display-name :user-id="scope.row.create_user" />
                  </div>
                  <div class="col-create">
                    {{ scope.row.create_time }}
                  </div>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('更新记录')"
              min-width="150"
              prop="update_time"
              sortable="custom"
            >
              <template slot-scope="scope">
                <div class="user-time">
                  <div class="col-create">
                    <bk-user-display-name :user-id="scope.row.update_user" />
                  </div>
                  <div class="col-create">
                    {{ scope.row.update_time }}
                  </div>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              width="100"
              :label="$t('操作')"
            >
              <template slot-scope="scope">
                <div class="col-operate">
                  <bk-button
                    v-authority="{ active: getManageAuth(scope.row) }"
                    class="edit-btn"
                    :disabled="!scope.row.edit_allowed"
                    :text="true"
                    type="primary"
                    @click="
                      !getManageAuth(scope.row) ? handlePluginEdit(scope.row.plugin_id) : showAuthorityDetail(scope.row)
                    "
                  >
                    {{ $t('button-编辑') }}
                  </bk-button>
                  <span
                    :ref="'operator-' + scope.$index"
                    v-authority="{ active: getManageAuth(scope.row) }"
                    class="col-operator-more"
                    :class="{ 'operator-active': tablePopover.hover === scope.$index }"
                    data-popover="true"
                    @click="
                      !getManageAuth(scope.row)
                        ? handleOperatorOver(scope.row, $event, scope.$index)
                        : showAuthorityDetail(scope.row)
                    "
                  >
                    <i
                      class="bk-icon icon-more"
                      data-popover="true"
                    />
                  </span>
                </div>
              </template>
            </bk-table-column>
          </bk-table>
          <bk-pagination
            v-show="table.data.length"
            class="plugin-pagination list-pagination"
            :count="panel.active ? panel.tabs[panel.active].num : pagination.total"
            :current="pagination.page"
            :limit="pagination.pageSize"
            :limit-list="pagination.pageList"
            align="right"
            size="small"
            pagination-able
            show-total-count
            @change="handlePageChange"
            @limit-change="handleLimitChange"
          />
        </template>
      </div>
    </div>
    <plugin-dialog-single :dialog="dialog" />
    <plugin-dialog-multiple
      :files="fileArr"
      :show.sync="fileArrShow"
      @refalsh-table-data="getPluginListData"
    />
    <div v-show="false">
      <ul
        ref="popoverContent"
        class="popover-tag"
        data-mark="popover-tag-mark"
      >
        <li
          v-for="tag in popover.list"
          v-show="tag.includes(popover.active)"
          :key="tag"
          class="popover-tag-item"
          data-mark="popover-tag-mark"
          @click="handleTagSelect(tag)"
        >
          <span data-mark="popover-tag-mark">{{ tag }}</span>
          <!-- <i data-mark="popover-tag-mark" class="bk-icon icon-check-1" v-show="popover.active === tag"></i> -->
        </li>
      </ul>
    </div>
    <div v-show="false">
      <div
        ref="labelMenu"
        class="label-menu-wrapper"
      >
        <ul class="label-menu-list">
          <li
            v-for="(item, index) in label.list"
            :key="index"
            class="item"
            @click="handleSelectLabel(item)"
          >
            <bk-checkbox
              :false-value="item.cancel"
              :true-value="item.checked"
              :value="item.value"
            />
            <span class="name">{{ item.firstName }}-{{ item.name }}</span>
          </li>
        </ul>
        <div class="footer">
          <div class="btn-group">
            <span
              class="monitor-btn"
              @click="handleLabelChange"
            >
              {{ $t('确定') }}
            </span>
            <span
              class="monitor-btn"
              @click="handleResetLable"
            >
              {{ $t('清空') }}
            </span>
          </div>
        </div>
      </div>
    </div>
    <div v-show="false">
      <div
        ref="operatorGroup"
        v-en-style="'width: 170px'"
        class="operator-group"
      >
        <span
          class="operator-group-btn"
          :class="{ 'btn-disabled': tablePopover.data.status === 'draft' || tablePopover.data.is_official }"
          :text="true"
          @click="handleShowMeticr"
        >
          {{ $t('设置指标&维度') }}
        </span>
        <span
          class="operator-group-btn"
          :class="{ 'btn-disabled': !tablePopover.data.export_allowed }"
          :text="true"
          @click="tablePopover.data.export_allowed && handlePluginExport(tablePopover.data.plugin_id)"
        >
          {{ $t('导出') }}
        </span>
        <span
          class="operator-group-btn"
          :class="{ 'btn-disabled': !tablePopover.data.delete_allowed }"
          :text="true"
          @click="
            tablePopover.data.delete_allowed &&
            handleDeletePlugin(tablePopover.data.plugin_id, tablePopover.data.plugin_display_name)
          "
        >
          {{ $t('删除') }}
        </span>
      </div>
    </div>
    <div style="display: none">
      <delete-subtitle
        ref="deleteSubTitle"
        :key="delSubTitle.name"
        :name="delSubTitle.name"
        :title="delSubTitle.title"
      />
    </div>
  </div>
</template>
<script>
import { CancelToken } from 'monitor-api/cancel';
import { getLabel } from 'monitor-api/modules/commons';
import {
  deleteCollectorPlugin,
  editCollectorPlugin,
  exportPluginCollectorPlugin,
  importPluginCollectorPlugin,
  listCollectorPlugin,
  tagOptionsCollectorPlugin,
} from 'monitor-api/modules/model';
import { saveAndReleasePlugin } from 'monitor-api/modules/plugin';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { debounce } from 'throttle-debounce';
import { createNamespacedHelpers } from 'vuex';

import introduce from '../../common/introduce';
import EmptyStatus from '../../components/empty-status/empty-status.tsx';
import GuidePage from '../../components/guide-page/guide-page';
import pageTips from '../../components/pageTips/pageTips';
import TableSkeleton from '../../components/skeleton/table-skeleton.tsx';
import authorityMixinCreate from '../../mixins/authorityMixin';
import { SET_PLUGIN_CONFIG, SET_PLUGIN_DATA, SET_PLUGIN_ID } from '../../store/modules/plugin-manager';
import { downFile } from '../../utils/index';
import DeleteSubtitle from '../strategy-config/strategy-config-common/delete-subtitle';
import * as pluginManageAuth from './authority-map';
import pluginDialogMultiple from './plugin-dialog-multiple';
import pluginDialogSingle from './plugin-dialog-single';

const { mapMutations } = createNamespacedHelpers('plugin-manager');
export default {
  name: 'PluginManager',
  components: {
    pluginDialogSingle,
    pluginDialogMultiple,
    pageTips,
    DeleteSubtitle,
    EmptyStatus,
    GuidePage,
    TableSkeleton,
  },
  mixins: [authorityMixinCreate(pluginManageAuth)],
  beforeRouteEnter(to, from, next) {
    next(async vm => {
      if (!['plugin-add', 'plugin-edit', 'plugin-detail'].includes(from.name)) {
        vm.header.keyword = '';
        vm.pagination.page = 1;
        vm.panel.active = 0;
        vm.pagination.pageSize = commonPageSizeGet();
      }
      !vm.loading && vm.getPluginListData(true);
    });
  },
  beforeRouteLeave(to, from, next) {
    if (to.name !== 'plugin-update' && to.name !== 'plugin-add') this[SET_PLUGIN_CONFIG](null);
    next();
  },
  data() {
    const defaultDialog = this.getDefaultDialogData();
    return {
      pluginManageAuth,
      loading: false,
      cancelListRequest: null, // 清空搜索条件时，假有一个表格数据请求在pending中，则取消这个请求
      header: {
        delete: true,
        keyword: '',
      },
      panel: {
        tabs: [
          {
            name: this.$t('全部'),
            num: 0,
          },
          {
            name: 'Exporter',
            num: 0,
          },
          {
            name: 'Script',
            num: 0,
          },
          {
            name: 'DataDog',
            num: 0,
          },
          {
            name: 'JMX',
            num: 0,
          },
          // {
          //     name: 'BK-Monitor',
          //     alias: 'Built-In',
          //     num: 0
          // },
          {
            name: 'BK-Pull',
            alias: 'Pushgateway',
            num: 0,
          },
          {
            name: 'SNMP',
            alias: 'SNMP',
            num: 0,
          },
        ],
        active: 0,
      },
      table: {
        loading: false,
        data: [],
        statusMap: {
          normal: {
            desc: this.$t('可用'),
            color: '#2DCB56',
          },
          draft: {
            desc: this.$t('草稿'),
            color: '#FF9C01',
          },
        },
        editIndex: -1,
        hoverIndex: -1,
        selected: [],
        order: '-update_time',
        message: this.$t('无数据'),
      },
      pagination: {
        page: 1,
        pageList: [10, 20, 50, 100],
        pageSize: commonPageSizeGet(),
        total: 0,
      },
      plugin: {
        show: false,
        infoShow: false,
        type: 0, // 0 新增 1 编辑 2 导入
        data: {},
        id: '',
      },
      headTitle: null,
      dialog: defaultDialog,
      handleSearchKey: null,
      colorMap: {
        Exporter: '#B6CAEC',
        Script: '#E3D5C2',
        JMX: '#A1CEAC',
        DataDog: '#F0D3A5',
        'Built-In': '#E3D5C2',
        Pushgateway: '#B6CAEC',
        SNMP: '#B6CAEC',
      },
      popover: {
        list: [],
        instance: null,
        active: -1,
      },
      tablePopover: {
        instance: null,
        hover: -1,
        edit: false,
        status: '',
        data: {},
      },
      label: {
        list: [],
        instance: null,
        values: [],
        selectedLabels: '',
        isFilter: false,
      },
      bizMap: { 0: this.$t('全业务') },
      pluginTypeMap: {
        Exporter: 'Exporter',
        Script: 'Script',
        JMX: 'JMX',
        DataDog: 'DataDog',
        'Built-In': 'BK-Monitor',
        Pushgateway: 'BK-Pull',
        SNMP: 'SNMP',
      },
      fileArr: [],
      fileArrShow: false,
      delSubTitle: {
        title: window.i18n.t('插件名称'),
        name: '',
      },
      emptyType: 'empty',
    };
  },
  computed: {
    labelKeyword() {
      return this.label.list
        .filter(item => item.value)
        .map(item => item.value)
        .join(',');
    },
    curIntroduceData() {
      return introduce.data['plugin-manager'].introduce;
    },
    // 是否显示引导页
    showGuidePage() {
      return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
    },
  },
  created() {
    this.$store.getters.bizList.forEach(item => {
      this.bizMap[item.id] = item.text;
    });
    this.handleSearchKey = debounce(300, v => {
      this.pagination.page = 1;
      this.header.keyword = v;
      this.getPluginListData();
    });
    !this.loading && this.getPluginListData(true);
    this.getLabelList();
  },
  deactivated() {
    this.handleDestoryLabelInstance();
  },
  beforeDestroy() {
    // 清空文件缓存
    this[SET_PLUGIN_CONFIG](null);
    this.handleDestoryLabelInstance();
  },
  methods: {
    ...mapMutations([SET_PLUGIN_DATA, SET_PLUGIN_ID, SET_PLUGIN_CONFIG]),
    async handleShowMeticr() {
      if (this.tablePopover.data.status === 'normal' && !this.tablePopover.data.is_official) {
        this.$router.push({
          name: 'plugin-setmetric',
          params: {
            pluginId: this.tablePopover.data.plugin_id,
          },
        });
      }
    },
    handleOperatorOver(data, e, index) {
      if (this.tablePopover.index === index) {
        return;
      }
      this.tablePopover.hover = index;
      this.tablePopover.edit = data.needUpdate;
      this.tablePopover.status = data.status;
      this.tablePopover.data = data;
      if (!this.tablePopover.instance) {
        this.tablePopover.instance = this.$bkPopover(e.target, {
          content: this.$refs.operatorGroup,
          arrow: false,
          trigger: 'manual',
          placement: 'bottom',
          theme: 'light common-monitor',
          maxWidth: 520,
          duration: [275, 0],
          onHidden: () => {
            this.tablePopover.instance.destroy();
            this.tablePopover.hover = -1;
            this.tablePopover.instance = null;
          },
        });
      } else {
        this.tablePopover.instance.reference = e.target;
      }
      this.tablePopover.instance?.show(100);
    },
    getLabelList() {
      return getLabel({ include_admin_only: false }).then(data => {
        data.forEach(item => {
          const children = item.children.map(label => ({
            firstName: item.name,
            value: '',
            checked: `${label.id}`,
            cancel: '',
            ...label,
          }));
          this.label.list.push(...children);
        });
      });
    },
    getPluginListData(needLoading = false) {
      this.loading = needLoading;
      this.table.loading = !needLoading;
      this.table.data = [];
      this.table.message = this.$t('加载中...');
      const params = {
        search_key: this.header.keyword,
        plugin_type: this.panel.active
          ? this.panel.tabs[this.panel.active].alias || this.panel.tabs[this.panel.active].name
          : '',
        page: this.pagination.page,
        page_size: this.pagination.pageSize,
        order: this.table.order,
        labels: this.labelKeyword,
      };
      this.emptyType = this.header.keyword ? 'search-empty' : 'empty';
      !this.popover.list.length && this.getTagList();
      listCollectorPlugin(params, { cancelToken: new CancelToken(c => (this.cancelListRequest = c)) })
        .then(data => {
          let total = 0;
          if (data.count) {
            this.panel.tabs.forEach(item => {
              item.num = data.count[item.alias || item.name] || 0;
              total += item.num;
            });
            this.panel.tabs[0].num = total;
          }
          this.pagination.total = total;
          this.table.data = data.list;
        })
        .catch(() => {
          this.emptyType = '500';
        })
        .finally(() => {
          this.loading = false;
          this.table.loading = false;
          this.table.message = params.search_key ? this.$t('搜索无数据') : this.$t('查无数据');
        });
    },
    getTagList() {
      tagOptionsCollectorPlugin()
        .then(data => {
          this.popover.list = data;
        })
        .catch(() => {
          this.popover.list = [];
        });
    },
    handleDestoryLabelInstance() {
      if (this.label.instance) {
        this.label.instance.hide();
        this.label.instance.destroy();
        this.label.instance = null;
      }
    },
    handlePanelChange(item, index) {
      this.panel.active = index;
      this.pagination.page = 1;
      this.getPluginListData();
    },
    handleSortChange({ order, prop }) {
      if (!prop) {
        this.table.order = null;
      } else {
        this.table.order = order === 'descending' ? `-${prop}` : prop;
      }
      this.getPluginListData();
    },
    handleLimitChange(v) {
      this.pagination.page = 1;
      this.pagination.pageSize = v;
      commonPageSizeSet(v);
      this.getPluginListData();
    },
    handlePageChange(v) {
      this.pagination.page = v;
      this.getPluginListData();
    },
    handleLabelKey(data, val, e) {
      if (e.code === 'Enter' || e.code === 'NumpadEnter') {
        this.handleTagSelect(val);
      }
    },
    handlePluginAdd(pluginId, pluginData = null, isImportPlugin = false) {
      if (pluginData?.is_official) {
        pluginData.bk_biz_id = 0;
      }
      this.$router.push({
        name: 'plugin-add',
        params: {
          pluginId,
          pluginData,
          isImportPlugin, // 导入插件跳转到新增
        },
      });
    },
    handleEditLabel(scope) {
      this.table.editIndex = scope.$index;
      this.$nextTick().then(() => {
        this.$refs[`label-${scope.$index}`].focus();
      });
    },
    handleTagClickout(e) {
      if (this.table.editIndex > -1 && e.target.dataset.mark !== 'popover-tag-mark') {
        const data = this.table.data[this.table.editIndex];
        if (this.popover.active !== -1 && this.popover.active !== data.tag) {
          this.handleTagSelect(this.popover.active);
        } else {
          this.table.editIndex = -1;
          this.table.active = '';
        }
      }
    },
    handleTagChange(v, e) {
      this.popover.active = v;
      if (!this.popover.instance) {
        this.popover.instance = this.$bkPopover(e.target, {
          content: this.$refs.popoverContent,
          arrow: false,
          trigger: 'click',
          placement: 'bottom',
          theme: 'light common-monitor',
          maxWidth: 520,
          offset: '-1, -11',
          sticky: true,
          duration: [275, 0],
          onHidden: () => {
            this.popover.instance.destroy();
            // this.popover.hover = -1
            this.popover.instance = null;
          },
        });
        // .instances[0]
      } else {
        this.popover.instance.reference = e.target;
      }
      this.popover.instance?.show(100);
    },
    handleTagSelect(v) {
      this.popover.active = v;
      const data = this.table.data[this.table.editIndex];
      this.popover.instance?.hide(100);
      this.table.editIndex = -1;
      this.loading = true;
      if (data.tag !== v) {
        data.label = v;
        editCollectorPlugin(data.plugin_id, {
          bk_biz_id: data.bk_biz_id,
          tag: v,
        })
          .then(() => {
            this.getPluginListData();
          })
          .catch(() => {
            this.loading = false;
          })
          .finally(() => {
            this.popover.active = -1;
          });
      }
    },
    handleFileChange(e) {
      if (e.target.files.length === 1) {
        const [file] = e.target.files;
        this.handeFileSingel(file);
      } else {
        this.handleFileMultiple([...e.target.files]);
      }
      e.target.value = '';
    },
    // 多个插件包导入逻辑
    handleFileMultiple(files) {
      this.fileArrShow = true;
      this.fileArr = files.map(item => ({
        file: item,
        percent: 0,
        percentShow: true,
        name: item.name,
        status: this.$t('解析中...'),
        text: '',
        verson: '',
        versonShow: true,
        isOk: false,
        data: null,
      }));
      this.fileArr.forEach((item, index) => {
        const interval = setInterval(
          () => {
            item.percent += 0.16;
            if (item.percent > 0.96) {
              window.clearInterval(interval);
            }
          },
          50 + index * 50
        );
        importPluginCollectorPlugin({ file_data: item.file })
          .then(data => {
            item.data = data;
            item.percent = 1;
            item.percentShow = false;
            item.verson = `${data.config_version}.${data.info_version}`;
            // if (data.is_official) { // 是否是官方插件
            if ((data.is_official || data.is_safety) && !data.duplicate_type) {
              // 是否重名
              item.status = this.$t('上传中...');
              data.bk_biz_id = !data.is_official ? this.$store.getters.bizId : 0;
              saveAndReleasePlugin(data)
                .then(() => {
                  item.status = this.$t('成功');
                })
                .catch(() => {
                  item.percent = 1;
                  item.percentShow = false;
                  item.status = this.$t('上传失败');
                })
                .finally(() => {
                  item.isOk = true;
                });
            } else {
              if (!data.is_safety) {
                item.status = this.$t('插件包不完整');
                item.text = this.$t('不支持“插件包不完整”的批量导入');
              } else {
                item.status = this.$t('注意: 名字冲突');
                item.text = data.conflict_detail;
                if (data.conflict_title) {
                  item.status = this.$t('注意: 插件冲突');
                }
              }
              item.isOk = true;
            }
            // } else {
            //     item.status = this.$t('非官方插件')
            //     item.text = this.$t('不支持“非官方认证插件”的批量导入')
            //     item.isOk = true
            // }
          })
          .catch(() => {
            item.percent = 1;
            item.percentShow = false;
            item.status = this.$t('解析失败');
            item.versonShow = false;
            item.isOk = true;
          })
          .finally(() => {
            window.clearInterval(interval);
          });
      });
    },
    // 单个插件包导入处理逻辑
    handeFileSingel(file) {
      this.dialog.name = file.name;
      this.dialog.show = true;
      this.dialog.percent = 0;
      this.dialog.status = 1;
      this.dialog.size = `${(file.size / 1000).toFixed(2)}KB`;
      const interval = setInterval(() => {
        this.dialog.percent += 0.16;
        if (this.dialog.percent > 0.96) {
          window.clearInterval(interval);
        }
      }, 50);
      importPluginCollectorPlugin({ file_data: file })
        .then(data => {
          // 缓存导入的配置数据
          this[SET_PLUGIN_CONFIG](data);

          this.dialog.percent = 1;
          const { isSuperUser } = this.$store.getters;
          if (data.conflict_detail) {
            if (!isSuperUser) {
              data.conflict_detail = `${data.is_official ? `${this.$t('您没有权限导入官方插件')},` : ''}${
                data.conflict_detail
              }`;
            }
            this.dialog.status = 4; // 重名
            this.dialog.data = data;
            this.dialog.update =
              (data.is_official && data.duplicate_type === 'official' && data.conflict_title.length === 0) ||
              (data.is_official && data.duplicate_type === 'custom') ||
              (!data.is_official && data.duplicate_type === 'custom' && data.conflict_title.length === 0);
          } else if (!isSuperUser && data.is_official) {
            data.conflict_detail = this.$t('您没有权限导入官方插件');
            this.dialog.data = data;
            this.dialog.status = 5; // 普通用户无权限直接导入官方插件，需要新建
          } else {
            if (data.is_official) {
              this.dialog.status = 1;
              this.dialog.data = data;
              this.handleSetUpdatePlugin();
            } else {
              this.dialog.status = 3; // 成功
              this.dialog.show = false;
              this.handlePluginAdd(null, data, true);
            }
          }
        })
        .catch(() => {
          this.dialog.percent = 1;
          this.dialog.status = 2;
        })
        .finally(() => {
          window.clearInterval(interval);
        });
    },
    //
    handleSetUpdatePlugin() {
      this.dialog.loading = true;
      this.dialog.data.bk_biz_id = !this.dialog.data.is_official ? this.$store.getters.bizId : 0;
      saveAndReleasePlugin(this.dialog.data)
        .then(() => {
          this.dialog.loading = false;
          this.$bkMessage({
            theme: 'success',
            message: this.$t('更新成功'),
          });
          this.handleHideDialog();
          this.getPluginListData();
        })
        .catch(() => {
          this.dialog.show = false;
          this.dialog.loading = false;
        });
    },
    handleHideDialog() {
      this.dialog = this.getDefaultDialogData();
    },
    getDefaultDialogData() {
      return {
        show: false,
        title: this.$t('导入中'),
        percent: 0,
        name: '',
        status: 0,
        size: 0,
        loading: false,
        update: false,
        data: {},
      };
    },
    showPluginInfo(pluginInfo) {
      this[SET_PLUGIN_ID](pluginInfo.plugin_id);
      if (pluginInfo.status === 'draft') {
        this.handlePluginEdit(pluginInfo.plugin_id);
      } else {
        this.$router.push({
          name: 'plugin-detail',
          params: {
            pluginId: pluginInfo.plugin_id,
          },
        });
      }
    },
    handlePluginEdit(pluginId) {
      this.$router.push({
        name: 'plugin-edit',
        params: {
          pluginId,
        },
      });
    },
    handlePluginExport(pluginId) {
      this.loading = true;
      exportPluginCollectorPlugin(pluginId)
        .then(data => {
          const url = data.download_url;
          if (url) {
            downFile(url);
          } else {
            this.$bkMessage({
              theme: 'error',
              message: this.$t('导出失败'),
            });
          }
        })
        .finally(() => {
          this.loading = false;
        });
    },
    handleSelectAble(row) {
      return row.delete_allowed;
    },
    handleSelectionChange(val) {
      this.table.selected = val;
      this.header.delete = !val.length;
    },
    async handleDeletePlugin(id, name) {
      this.delSubTitle.name = name;
      await this.$nextTick();
      const subHeader = this.$refs.deleteSubTitle.$vnode;
      this.$bkInfo({
        type: 'warning',
        title: this.$t('确认要删除？'),
        subHeader,
        okText: this.$t('删除'),
        maskClose: true,
        confirmFn: () => {
          this.loading = true;
          deleteCollectorPlugin({ plugin_ids: [id] })
            .then(() => {
              this.$bkMessage({
                message: this.$t('删除插件成功'),
                theme: 'success',
              });
              this.getPluginListData();
            })
            .catch(() => {
              this.loading = false;
            });
        },
      });
    },
    handleToCollectorConfig(v) {
      if (v.row.related_conf_count > 0) {
        this.$router.push({
          name: 'collect-config',
          params: {
            searchType: 'correlation',
            pluginId: v.row.plugin_id,
          },
        });
      }
    },
    handleShow(e) {
      if (!this.label.instance) {
        this.label.instance = this.$bkPopover(e.target, {
          content: this.$refs.labelMenu,
          trigger: 'manual',
          arrow: false,
          theme: 'light common-monitor table-filter',
          maxWidth: 280,
          offset: '0, 5',
          sticky: true,
          duration: [275, 0],
          interactive: true,
          onHidden: () => {
            const list = this.label.selectedLabels.split(',');
            this.label.list.forEach(item => {
              if (list.includes(item.id)) {
                item.value = item.id;
              } else {
                item.value = '';
              }
            });
          },
        });
      }
      this.label.instance?.show(100);
    },
    handleSelectLabel(item) {
      item.value = item.value === item.id ? '' : item.id;
    },
    handleLabelChange() {
      this.label.instance.hide(100);
      this.label.isFilter = true;
      this.label.selectedLabels = this.labelKeyword;
      this.getPluginListData();
    },
    handleResetLable() {
      this.label.instance.hide(100);
      this.label.list.forEach(item => {
        item.value = '';
      });
      this.label.selectedLabels = '';
      if (this.label.isFilter) {
        this.label.isFilter = false;
        this.getPluginListData();
      }
    },
    renderHeader(h) {
      // 这里原先是用 jsx 实现，但由于 VSCode 对 .vue 文件的 jsx 格式支持不太友好，
      // 导致下面的代码没法正常显示其应有的样式，故将 jsx 换成手写 render funtion。
      return h(
        'span',
        {
          on: {
            click: e => this.handleShow(e),
          },
          class: {
            'dropdown-trigger': true,
            ' plugin-label': true,
            selected: this.labelKeyword,
          },
          slot: 'dropdown-trigger',
        },
        [
          this.$t('分类'),
          h('i', {
            class: 'icon-monitor icon-filter-fill',
          }),
        ]
      );
    },
    getManageAuth(row) {
      if (row.bk_biz_id === 0) {
        // 公共插件有管理和公共插件管理两个权限
        return !this.authority.MANAGE_AUTH || !this.authority.MANAGE_PUBLIC_AUTH;
      }
      return !this.authority.MANAGE_AUTH;
    },
    showAuthorityDetail(row) {
      const actionIds = [];
      if (!this.authority.MANAGE_AUTH) {
        actionIds.push(pluginManageAuth.MANAGE_AUTH);
      }
      if (!this.authority.MANAGE_PUBLIC_AUTH && row.bk_biz_id === 0) {
        actionIds.push(pluginManageAuth.MANAGE_PUBLIC_AUTH);
      }
      this.handleShowAuthorityDetail(actionIds);
    },
    handleOperation(type) {
      if (type === 'clear-filter') {
        this.header.keyword = '';
        this.getPluginListData();
        return;
      }

      if (type === 'refresh') {
        this.emptyType = 'empty';
        this.getPluginListData();
        return;
      }
    },
  },
};
</script>
<style lang="scss" scoped>
@import '../home/common/mixins';

.mr-6 {
  margin-right: 6px;
}

.plugin-table-skeleton {
  padding: 16px 16px 0 16px;
}

.popover-tag {
  display: flex;
  flex-direction: column;
  width: 170px;
  max-height: 180px;
  padding: 0;
  margin: 0;
  overflow: auto;
  font-size: 12px;
  color: #63656e;
  background: #fff;

  &-item {
    display: flex;
    flex: 0 0 32px;
    align-items: center;
    height: 32px;
    padding: 0 16px;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
      background: rgba(234, 243, 255, 0.7);
    }

    span {
      flex: 1;
    }

    i {
      font-weight: bold;
      color: #3a84ff;
    }
  }
}

.plugin-container {
  margin: 24px;

  &.plugin-loading {
    min-height: calc(100vh - 80px);
  }

  .plugin-manager {
    color: $defaultFontColor;

    &-header {
      display: flex;
      margin-bottom: 16px;

      .left {
        flex: 1;

        &-button {
          position: relative;
          margin-right: 8px;

          &-file {
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            display: block;
            cursor: pointer;
            opacity: 0;
          }
        }
      }

      .right {
        width: 300px;
      }
    }

    &-content {
      background: #fff;
      border-radius: 2px;

      @include border-1px();

      .tab-list {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        padding: 0;
        margin: 0;
        font-size: 14px;
        line-height: 42px;
        background: #fafbfd;

        &-item {
          flex: 0 0 120px;
          text-align: center;
          border-right: 1px solid #dcdee5;
          border-bottom: 1px solid #dcdee5;

          .tab-num {
            display: inline-block;
            padding: 2px 5px;
            font-size: 12px;
            line-height: 10px;
            color: #fff;
            background: #c4c6cc;
            border-radius: 8px;
          }

          &.tab-active {
            color: #3a84ff;
            background: #fff;
            border-bottom: 0;

            .tab-num {
              background: #3a84ff;
            }
          }

          &:hover {
            color: #3a84ff;
            cursor: pointer;
          }
        }

        &-blank {
          flex: 1 1 auto;
          height: 42px;
          border-bottom: 1px solid #dcdee5;
        }
      }

      .plugin-table {
        margin-top: 16px;
        font-size: 12px;
        border-right: 0;
        border-left: 0;

        :deep(.cell) {
          color: #63656e;

          .bk-dropdown-menu {
            width: 100%;

            .bk-dropdown-content {
              background-color: #fff;
            }
          }

          .plugin-label {
            display: inline-block;
            width: 100%;
            cursor: pointer;

            &.selected {
              color: #3a84ff;
            }

            .bk-icon {
              margin-left: 6px;
            }
          }

          .icon-filter-fill {
            margin-left: 6px;
            color: #c0c4cc;
          }

          label {
            margin: 0px;
          }
        }

        :deep(.label-title) {
          .cell {
            padding: 0;
          }

          span {
            padding: 0 15px;
          }
        }

        .col-name {
          display: flex;
          flex-direction: row;
          align-items: center;
          justify-content: flex-start;
          height: 32px;
          margin: 10px 0;

          &-icon {
            flex: 0 0 32px;
            width: 32px;
            height: 32px;
            font-size: 16px;
            font-weight: bold;
            line-height: 32px;
            color: #fff;
            text-align: center;
            background-repeat: no-repeat;
            background-size: cover;
          }

          &-desc {
            display: flex;
            // flex: 1 1 auto;
            flex: 1;
            flex-direction: column;
            flex-wrap: nowrap;
            align-items: flex-start;
            justify-content: space-between;
            width: 0;
            margin: 0 10px;
            font-size: 12px;
            color: #63656e;

            .desc-category,
            %desc-category {
              overflow: hidden;
              text-overflow: ellipsis;
              line-height: 16px;
              white-space: nowrap;
              cursor: pointer;
            }

            .desc-alias {
              display: flex;
              align-items: center;
              width: 100%;
              font-weight: bold;
              color: #3a84ff;
              //justify-content: center;

              @extend %desc-category;

              &-title {
                // flex: 1;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
              }

              &-gov {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 32px;
                height: 16px;
                margin-left: 5px;
                color: #fff;
                background: #2dcb56;
                border-radius: 2px;

                span {
                  *font-size: 10px;
                  transform: scale(0.83, 0.83);
                }
              }
            }
          }
        }

        .col-set {
          color: #3a84ff;
          cursor: pointer;
        }

        .col-right {
          padding-right: 3px;
        }

        .col-create {
          margin-bottom: 3px;
          line-height: 16px;
        }

        .col-operate {
          display: flex;
          color: #3a84ff;
          cursor: pointer;

          .edit-btn {
            padding: 0;
            margin: 0 8px 0 0;
          }
        }

        .col-label {
          display: flex;
          align-items: center;
          justify-content: flex-start;

          .icon-bianji {
            margin-left: 5px;
            font-size: 24px;
            color: #3a84ff;
            cursor: pointer;
          }
        }

        &:after {
          width: 0;
        }

        &:before {
          height: 0;
        }

        .col-operator {
          display: flex;
          align-items: center;

          &-btn {
            margin-right: 12px;
            color: #3a84ff;
            cursor: pointer;
          }

          &-more {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 50%;

            .icon-more {
              font-size: 14px;
              color: #3a84ff;
            }

            &:hover {
              cursor: pointer;
              background: #ddd;
            }

            &.operator-active {
              background: #ddd;
            }
          }
        }
      }

      .plugin-pagination {
        margin: 15px;
      }

      .user-time {
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 58px;
      }
    }
  }

  :deep(.full-screen) {
    padding: 50px 83px 35px;
    overflow: scroll;
    background: #f5f6fa;
  }
}

.label-menu-wrapper {
  .label-menu-list {
    display: flex;
    flex-direction: column;
    padding: 6px 0;
    background-color: #fff;
    border-radius: 2px;

    .item {
      display: flex;
      align-items: center;
      height: 32px;
      min-height: 32px;
      padding: 0 10px;
      color: #63656e;
      cursor: pointer;

      .name {
        margin-left: 6px;
      }

      &:hover {
        color: #3a84ff;
        background: #e1ecff;
      }
    }
  }

  .footer {
    display: flex;
    justify-content: center;
    height: 32px;
    background-color: #fff;
    border-top: solid 2px #f0f1f5;

    .btn-group {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 70px;
      height: 100%;

      .monitor-btn {
        color: #3a84ff;
        cursor: pointer;

        &:hover {
          color: #699df4;
        }
      }
    }
  }
}

.operator-group {
  display: flex;
  flex-direction: column;
  width: 116px;
  height: 110px;
  padding: 6px 0;
  font-size: 12px;
  color: #63656e;
  border: 1px solid #dcdee5;

  &-btn {
    display: flex;
    flex: 1;
    align-items: center;
    padding-left: 15px;
    background: #fff;

    &:hover {
      color: #3a84ff;
      cursor: pointer;
      background: #f0f1f5;
    }

    &.btn-disabled {
      color: #c4c6cc;
      cursor: not-allowed;

      /* stylelint-disable-next-line declaration-no-important */
      background: #fff !important;
    }
  }
}
</style>
