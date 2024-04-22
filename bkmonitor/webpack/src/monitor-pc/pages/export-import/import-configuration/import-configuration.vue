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
  <article
    v-bkloading="{ isLoading: loading }"
    class="import-config"
  >
    <!--折叠内容-->
    <section
      ref="collapse"
      class="import-config-content"
      :style="{ marginBottom: isScroll ? '34px' : '' }"
    >
      <bk-collapse
        v-model="collapse.activeName"
        @item-click="handleClickCollapse"
      >
        <bk-collapse-item
          v-for="item in collapseList"
          :key="item.name"
          :name="item.name"
          ext-cls="collapse-item"
        >
          <!--折叠title-->
          <template #default>
            <!--左侧名称-->
            <div class="collapse-item-left">
              <i
                class="bk-icon icon-play-shape collapse-item-icon"
                :class="{ 'icon-rotate': collapse.activeName.includes(item.name) }"
              />
              <span
                v-if="item.name === 'bkmonitor.models.fta.plugin'"
                class="collapse-item-title"
                >{{ getItemTitle(item) }}</span
              >
              <span
                v-else
                class="collapse-item-title"
                >{{ selectedTitle(item) }}</span
              >
              <span
                v-if="item.markName"
                class="collapse-item-mark"
                >{{ item.markName }}</span
              >
            </div>
            <!--右侧状态-->
            <div
              v-show="table.statistics && table.statistics[item.name]"
              class="collapse-item-right"
            >
              <!-- eslint-disable-next-line vue/no-v-html -->
              <span>
                <template v-for="(val, key) in statusMap">
                  <i18n
                    v-if="table.statistics[item.name] && table.statistics[item.name][key]"
                    :key="key"
                    :path="key === 'success' ? '{0} 个检测成功' : '{0} 个检测失败'"
                  >
                    <span :class="`total-${key}`">{{ table.statistics[item.name][key] }}</span>
                  </i18n>
                </template>
              </span>
            </div>
          </template>
          <!--折叠表格-->
          <template #content>
            <bk-table
              v-show="table.tableData[item.name]"
              :ref="item.name"
              max-height="410"
              :data="table.tableData[item.name]"
              row-key="uuid"
              :collapse="item.name"
              @select="handleSelectChange"
              @select-all="handleSelectAll($event, item.name)"
            >
              <bk-table-column
                v-if="!item.markName"
                align="left"
                header-align="left"
                type="selection"
                width="40"
                :selectable="handleItemSelectable"
                reserve-selection
              />
              <bk-table-column
                align="left"
                :label="$t('配置名称')"
                prop="name"
                header-align="left"
                width="206"
              />
              <bk-table-column
                width="190"
                :label="$t('监控对象')"
                prop="label"
              />
              <bk-table-column
                width="153"
                :label="$t('任务状态')"
                :render-header="renderHeader"
              >
                <template #default="{ row }">
                  <div
                    v-if="statusMap[row.status]"
                    class="status-col"
                  >
                    <span :class="'status-' + row.status" />
                    <span class="fix-same-code">{{ statusMap[row.status].name }}</span>
                  </div>
                  <div
                    v-else
                    class="status-col"
                  >
                    <span class="status-failed" />
                    <span> {{ $t('状态未知') }} </span>
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('详情')">
                <template #default="{ row }">
                  <div class="detail-col">
                    <span>{{ row.errorMsg ? row.errorMsg : '--' }}</span>
                  </div>
                </template>
              </bk-table-column>
            </bk-table>
          </template>
        </bk-collapse-item>
      </bk-collapse>
    </section>
    <!--底部按钮-->
    <section
      v-if="collapseList.length"
      class="import-config-footer"
    >
      <!--背景占位-->
      <div :class="{ 'footer-banner': isScroll }" />
      <span class="is-overwrite">
        <span>{{ $t('是否覆盖') }}</span>
        <bk-switcher
          v-model="isOverwriteMode"
          theme="primary"
          size="small"
        />
      </span>
      <bk-button
        theme="primary"
        class="mr10"
        :class="{ 'footer-button1': isScroll }"
        :disabled="disabledConfirmBtn"
        @click="handleImportClick"
      >
        {{ $t('导入') }}
      </bk-button>
      <bk-button
        class="button-cancel"
        :class="{ 'footer-button2': isScroll }"
        @click="handleImportCancel"
      >
        {{ $t('取消') }}
      </bk-button>
    </section>
    <!--空数据-->
    <section
      v-if="!collapseList.length"
      class="config-empty"
    >
      <content-empty
        :title="$t('无数据')"
        :sub-title="$t('导入数据为空')"
      />
    </section>
    <!--筛选数据-->
    <template>
      <div v-show="false">
        <div
          ref="labelMenu"
          class="label-menu-wrapper"
        >
          <ul
            v-if="filterHeader[currentStatus]"
            class="label-menu-list"
          >
            <li
              v-for="(item, index) in filterHeader[currentStatus].list"
              :key="index"
              class="item"
              @click="handleSelectLabel(item)"
            >
              <bk-checkbox
                :value="item.value"
                :true-value="item.checked"
                :false-value="item.cancel"
              />
              <span class="name">{{ item.name }}</span>
            </li>
          </ul>
          <div class="footer">
            <div class="btn-group">
              <bk-button
                :text="true"
                @click="handleStatusChange"
              >
                {{ $t('确定') }}
              </bk-button>
              <bk-button
                :text="true"
                @click="handleResetSelected"
              >
                {{ $t('重置') }}
              </bk-button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </article>
</template>
<script>
import { transformDataKey } from 'monitor-common/utils/utils';
import { mapActions } from 'vuex';

import ContentEmpty from '../components/content-empty';
import mixin from './import-mixin';

export default {
  name: 'ImportConfiguration',
  components: {
    ContentEmpty,
  },
  mixins: [mixin],
  props: {
    // 导入界面数据
    importData: {
      type: Object,
    },
  },
  data() {
    return {
      // 当前statusMap
      statusMap: {
        success: {
          name: this.$t('检测成功'),
          status: 'success',
        },
        failed: {
          name: this.$t('检测失败'),
          status: 'failed',
        },
      },
      // 表格对象（含mixin公共部分）
      table: {
        firstCheckedAll: [],
        selection: [],
        tableData: {},
      },
      // 状态列筛选状态
      filterHeader: {
        collect: null,
        strategy: null,
        view: null,
        plugin: null,
      },
      // 任务状态下拉列表
      status: {
        list: [
          {
            value: '',
            id: 'failed',
            name: this.$t('检测失败'),
            checked: 'failed',
            cancel: '',
          },
          {
            value: '',
            id: 'success',
            name: this.$t('检测成功'),
            checked: 'success',
            cancel: '',
          },
        ],
        instance: null,
      },
      // 当前筛选的状态表格
      currentStatus: '',
      isOverwriteMode: false,
    };
  },
  computed: {
    // 开始导入按钮禁用状态
    disabledConfirmBtn() {
      return !this.table.list?.some(item => item.checked);
    },
    // 当前表格已选总数
    selectedTitle() {
      return collapse => {
        const checkedCount = this.table.list.filter(item => item.type === collapse.name && item.checked).length;
        return `${collapse.title}（${this.$t('已选{count}个', { count: checkedCount })}）`;
      };
    },
    // 需要显示的 collapse (无数据的不显示)
    collapseList() {
      return this.collapse.list.filter(item => this.table.statistics[item.name]?.total);
    },
    // 状态列是否勾选
    hasSelectStatus() {
      return collapseName =>
        this.filterHeader[collapseName]?.list
          .filter(item => item.value)
          .map(item => item.value)
          .join(',');
    },
  },
  created() {
    if (!this.importData) {
      this.$router.back();
    }
    // just do it
    this.handleInit();
  },
  methods: {
    ...mapActions('import', ['handleImportConfig']),
    async handleInit() {
      // 初始化任务状态列状态
      this.handleInitStatusCol();
      await this.handleInitImportConfigData();
      // 默认展开第一个有数据的项
      this.handleExpandCollapse();
      // 首次展开勾选表格所有项
      this.handleClickCollapse();
    },
    // 初始化任务状态列
    handleInitStatusCol() {
      Object.keys(this.filterHeader).forEach(key => {
        this.filterHeader[key] = JSON.parse(JSON.stringify(this.status));
      });
    },
    // 开始导入界面数据初始化
    async handleInitImportConfigData() {
      const data = transformDataKey(this.importData);
      // if (!data.importHistoryId) return
      // this.table.taskId = data.importHistoryId
      this.table.list = data.configList
        ? data.configList.map(item => {
            item.checked = item.type !== 'bkmonitor.models.fta.plugin' && item.fileStatus === 'success'; // 默认勾选所有成功项
            item.status = item.fileStatus;
            return item;
          })
        : [];
      this.collapse.list.forEach(item => {
        this.table.tableData[item.name] = this.table.list.filter(list => list.type === item.name);
      });
      this.table.statistics = this.handleCountData(data);
    },
    /**
     * Collapse点击事件
     */
    handleClickCollapse() {
      this.$nextTick().then(() => {
        // 首次展开默认全选
        this.collapse.activeName.forEach(activeItem => {
          if (!this.table.firstCheckedAll.includes(activeItem) && this.$refs[activeItem]?.length === 1) {
            this.$refs[activeItem][0].toggleAllSelection();
            this.table.firstCheckedAll.push(activeItem);
          }
        });
      });
    },
    /**
     * 当前row是否支持勾选
     * @param {Object} v 当前行
     * @param {Number} index 当前索引
     */
    handleItemSelectable(v) {
      // 只有成功的item支持勾选
      return v.status === 'success';
    },
    /**
     * 表格行勾选事件
     * @param {Array} selection 选中项
     * @param {Object} row 当前行
     */
    handleSelectChange(selection, row) {
      const index = this.table.list.findIndex(item => item.uuid === row.uuid);
      if (index > -1) {
        this.table.list[index].checked = selection.findIndex(item => item.uuid === row.uuid) > -1;
      }
    },
    /**
     * 全选按钮事件
     * @param {Array} selection 选中项
     * @param {String} name collapse name
     */
    handleSelectAll(selection, name) {
      this.table.list.forEach(item => {
        if (item.type === name && item.status === 'success' && item.type !== 'bkmonitor.models.fta.plugin') {
          item.checked = !(selection.length === 0);
        }
      });
    },
    /**
     * 开始导入
     */
    async handleImportClick() {
      const uuids = this.table.list
        .filter(item => item.checked && item.type !== 'bkmonitor.models.fta.plugin')
        .map(item => item.uuid);
      this.loading = true;
      const data = await this.handleImportConfig({ uuids, isOverwriteMode: this.isOverwriteMode });
      this.loading = false;
      // 等待状态设置为importing后跳转
      if (data?.importHistoryId) {
        this.$router.push({ name: 'import-configuration-importing', params: { id: data.importHistoryId } });
      }
    },
    /**
     * 取消按钮
     */
    handleImportCancel() {
      this.$router.back();
    },
    /**
     * 统计当前表格总数
     * @param {Object} item 当前 collapse 项
     */
    getItemTitle(item) {
      if (this.table.statistics[item.name]?.total) {
        return `${item.title}（${this.$t('共 {0} 个', [this.table.statistics[item.name].total])}）`;
      }
      return `${item.title}（${this.$t('共 {0} 个', [0])}）`;
    },
    /**
     * 自定义渲染表头（状态列）
     * @param {createElement 函数} h 渲染函数
     * @param {Object} data
     */
    renderHeader(h, data) {
      const collapseName = data.store.table.$attrs.collapse;
      return h(
        'span',
        {
          class: {
            'dropdown-trigger': true,
            selected: this.hasSelectStatus(collapseName),
          },
          on: {
            click: e => this.handleShow(e, collapseName),
          },
        },
        [
          this.$t('任务状态'),
          h('i', {
            class: {
              'icon-monitor': true,
              'icon-filter-fill': true,
            },
          }),
        ]
      );
      // (
      //   <span
      //     onClick={(e) => this.handleShow(e, collapseName)}
      //     class={{ 'dropdown-trigger': true, selected: this.hasSelectStatus(collapseName) }}
      //   >
      //     {this.$t('任务状态')}
      //     <i class="icon-monitor icon-filter-fill"></i>
      //   </span>
      // );
    },
    /**
     * 展示筛选列表页
     */
    handleShow(e, collapseName) {
      this.currentStatus = collapseName;
      const target = e.target.tagName === 'SPAN' ? e.target : e.target.parentNode;
      const status = this.filterHeader[collapseName];
      if (!status.instance) {
        status.instance = this.$bkPopover(target, {
          content: this.$refs.labelMenu,
          trigger: 'click',
          arrow: false,
          theme: 'light common-monitor',
          maxWidth: 520,
          offset: '0, -10',
          sticky: true,
          duration: [275, 0],
          interactive: true,
          onHidden: () => {
            status.instance.destroy();
            status.instance = null;
          },
        });
      }
      status.instance?.show(100);
    },
    /**
     * 勾选状态事件
     */
    handleSelectLabel(item) {
      item.value = item.value === item.id ? '' : item.id;
    },
    /**
     * 状态列确定事件
     */
    handleStatusChange() {
      const collapseName = this.currentStatus;
      this.filterHeader[collapseName].instance.hide(100);
      const status = this.filterHeader[collapseName].list.filter(item => item.value).map(item => item.value);
      if (status && status.length === 1) {
        this.table.tableData[collapseName] = this.table.list.filter(
          item => item.type === collapseName && item.status === status[0]
        );
      } else {
        this.table.tableData[collapseName] = this.table.list.filter(item => item.type === collapseName);
      }
      this.$forceUpdate();
    },
    /**
     * 状态列重置事件
     */
    handleResetSelected() {
      this.filterHeader[this.currentStatus].list.forEach(item => {
        item.value = '';
      });
      this.handleStatusChange();
    },
  },
};
</script>
<style lang="scss" scoped>
@import './import-common.scss';

$filterIconColor: #64656e;
$footerBorderColor: #f0f1f5;
$itemHoverColor: #e1ecff;

.config-empty {
  margin-top: 226px;
}

.import-config {
  :deep(.dropdown-trigger) {
    display: inline-block;
    width: 100%;
    height: 42px;
    cursor: pointer;

    .icon-filter-fill {
      margin-left: 6px;
      color: $filterIconColor;
    }

    &.selected {
      color: $primaryFontColor;

      .icon-filter-fill {
        color: $primaryFontColor;
      }
    }
  }
}

.label-menu-wrapper {
  .label-menu-list {
    padding: 6px 0;
    background-color: $whiteColor;
    border-radius: 2px;

    @include layout-flex(column);

    .item {
      height: 32px;
      min-height: 32px;
      padding: 0 10px;
      color: $defaultFontColor;
      cursor: pointer;

      @include layout-flex(row, center);

      .name {
        display: inline-block;
        height: 18px;
        margin-left: 6px;
        line-height: 18px;
      }

      &:hover {
        color: $primaryFontColor;
        background: $itemHoverColor;
      }
    }
  }

  .footer {
    height: 29px;
    background-color: $whiteColor;
    border-top: solid 2px $footerBorderColor;

    @include layout-flex(row, stretch, center);

    .btn-group {
      width: 70px;
      height: 100%;

      @include layout-flex(row, center, space-between);
    }

    .bk-button-text {
      position: relative;
      top: -1px;
      padding: 0;
      font-size: 12px;
    }
  }
}

.is-overwrite {
  font-size: 12px;
  color: #313238;

  .bk-switcher {
    margin: 0 16px 0 8px;
  }
}
</style>
