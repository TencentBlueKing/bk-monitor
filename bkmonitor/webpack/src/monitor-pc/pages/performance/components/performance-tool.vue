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
  <div>
    <div class="performance-tool">
      <!-- 左侧操作按钮 -->
      <div class="performance-tool-left">
        <bk-button
          class="tool-btn"
          :disabled="selectionsCount < 2"
          @click="handleContrastIndex"
        >
          {{ $t('button-指标对比') }}
        </bk-button>
        <bk-dropdown-menu :disabled="!selectionsCount">
          <bk-button
            :disabled="!selectionsCount"
            slot="dropdown-trigger"
          >
            {{ $t('复制IP') }}
          </bk-button>
          <ul
            class="bk-dropdown-list"
            slot="dropdown-content"
          >
            <li><a
              href="javascript:;"
              @click="handleCopyIp('bk_host_innerip')"
            >{{$t('内网IPv4')}}</a></li>
            <li><a
              href="javascript:;"
              @click="handleCopyIp('bk_host_innerip_v6')"
            >{{$t('内网IPv6')}}</a></li>
            <li><a
              href="javascript:;"
              @click="handleCopyIp('bk_host_outerip')"
            >{{$t('外网IPv4')}}</a></li>
            <li><a
              href="javascript:;"
              @click="handleCopyIp('bk_host_outerip_v6')"
            >{{$t('外网IPv6')}}</a></li>
          </ul>
        </bk-dropdown-menu>
      </div>
      <!-- 右侧筛选条件 -->
      <div class="performance-tool-right">
        <bk-input
          v-model="keyWord"
          class="tool-search"
          :placeholder="$t('输入关键字，模糊搜索')"
          clearable
          right-icon="bk-icon icon-search"
          @change="handleSearch"
        />
        <span
          :class="['tool-icon', { 'is-filter': isFilter }]"
          @click="handleShowPanel"
        >
          <i class="icon-monitor icon-filter" />
        </span>
        <bk-popover
          placement="bottom"
          width="515"
          theme="light performance-dialog"
          trigger="click"
          :offset="200"
        >
          <span class="tool-icon">
            <i class="bk-icon icon-cog" />
          </span>
          <div
            slot="content"
            class="tool-popover"
          >
            <div class="tool-popover-title">
              {{ $t('字段显示设置') }}
            </div>
            <ul class="tool-popover-content">
              <li
                v-for="item in fieldSettingData"
                :key="item.id"
                class="tool-popover-content-item"
              >
                <bk-checkbox
                  :value="item.checked"
                  @change="handleCheckColChange(item)"
                  :disabled="item.disable"
                >
                  <span
                    v-bk-overflow-tips
                    class="checkbox-text"
                  >{{ item.name }}</span>
                </bk-checkbox>
              </li>
            </ul>
          </div>
        </bk-popover>
        <filter-panel
          v-model="showFilterPanel"
          :field-data="filterPanelData"
          @filter="handleFilter"
          @reset="handleReset"
        />
      </div>
    </div>
    <filter-tag
      @filter-change="handleFilterChange"
      @filter-update="handleSearchUpdate"
    />
  </div>
</template>
<script lang="ts">
import { Debounce, copyText, typeTools } from 'monitor-common/utils/utils.js';
import { Component, Emit, Inject, Prop, Vue } from 'vue-property-decorator';

import type MonitorVue from '../../../types/index';
import type { CheckType, IFieldConfig, ITableRow } from '../performance-type';
import type TableStore from '../table-store';

import FilterPanel from './filter-panel.vue';
import FilterTag from './filter-tag.vue';

@Component({
  name: 'performance-tool',
  components: {
    FilterPanel,
    FilterTag,
  },
} as any)
export default class PerformanceTool extends Vue<MonitorVue> {
  @Prop({ default: 'current', type: String }) readonly checkType: CheckType;
  @Prop({ default: () => [], type: Array }) readonly selectionData: ITableRow[];
  @Prop({ default: () => [], type: Array }) readonly excludeDataIds: string[];
  @Prop({ default: 0 }) readonly selectionsCount: number;
  @Inject('tableInstance') readonly tableInstance: TableStore;

  // 采集下发按钮加载状态
  collectLoading = false;
  // 指标对比
  visiable = false;
  storageKey = `${this.$store.getters.userName}-${this.$store.getters.bizId}`;
  showFilterPanel = false;
  // 搜索关键字
  keyWord = '';
  selections: Readonly<Array<ITableRow>> = [];

  // 可用于筛选的字段信息
  get filterPanelData() {
    return this.fieldData.filter(item => Object.hasOwn(item, 'filterChecked'));
  }
  // 可用于设置自定义列的信息
  get fieldSettingData() {
    return this.fieldData.filter(item => Object.hasOwn(item, 'checked'));
  }

  get isFilter() {
    return this.fieldData.some(item => {
      if (Array.isArray(item.value)) {
        return item.type === 'condition'
          ? item.value.some(data => !typeTools.isNull(data.value) && data.condition)
          : item.value.some(item => !typeTools.isNull(item));
      }
      return !typeTools.isNull(item.value);
    });
  }

  get fieldData() {
    return this.tableInstance.fieldData;
  }

  created() {
    if (this.$route.query.queryString) {
      this.keyWord = this.$route.query.queryString as string;
      this.handleSearch();
    }
  }

  handleChangeKeyword(val: string) {
    this.keyWord = val;
  }

  // 指标对比
  handleContrastIndex() {
    const selections = this.getSelections();
    const firstRow = selections[0];
    const compares = selections.reduce((total, item, index) => {
      if (index)
        total.push({
          bk_host_id: item.bk_host_id,
          bk_target_cloud_id: item.bk_cloud_id,
          bk_target_ip: item.bk_host_innerip,
        });
      return total;
    }, []);
    this.$router.push({
      name: 'performance-detail',
      query: {
        compares: encodeURIComponent(
          JSON.stringify({
            targets: compares,
          })
        ),
      },
      params: {
        id: firstRow.bk_host_id.toString(),
      },
    } as any);
    // this.selections = Object.freeze(JSON.parse(JSON.stringify(this.getSelections())));
    // this.visiable = true;
  }

  // 复制IP
  handleCopyIp(field: 'bk_host_innerip' | 'bk_host_innerip_v6' | 'bk_host_outerip' | 'bk_host_outerip_v6') {
    const selections = this.getSelections();
    const ipList = selections.map(item => item[field]).filter(Boolean);
    copyText(ipList.join('\n'), err => {
      this.$bkMessage('error', err);
    });
    this.$bkMessage({
      theme: 'success',
      message: this.$t('复制成功 {num} 个IP', { num: ipList.length }),
    });
  }

  // 字段显示勾选事件
  @Emit('check-change')
  handleCheckColChange(item: IFieldConfig) {
    const data = this.getLocalStorage();
    if (item.checked) {
      delete data[item.id];
    } else {
      data[item.id] = 1;
    }
    localStorage.setItem(this.storageKey, JSON.stringify(data));
    // 更新store
    const index = this.tableInstance.fieldData.findIndex(field => field.id === item.id);
    if (index > -1) {
      const data = this.tableInstance.fieldData[index];
      data.checked = !data.checked;
    }
    return item;
  }

  getLocalStorage() {
    try {
      return JSON.parse(localStorage.getItem(this.storageKey)) || {};
    } catch {
      return {};
    }
  }

  handleShowPanel() {
    this.showFilterPanel = true;
  }

  @Emit('search-change')
  @Emit('filter')
  handleFilter() {
    if (this.isFilter) {
      const search = this.fieldData.reduce((pre, next) => {
        const isEmpty = Array.isArray(next.value) ? next.value.length === 0 : typeTools.isNull(next.value);
        if (!isEmpty) {
          pre.push({
            id: next.id,
            value: next.value,
          });
        }
        return pre;
      }, []);
      this.updateRouteQuery(search);
    }
    this.showFilterPanel = false;
  }

  @Emit('search-change')
  handleReset() {
    this.updateRouteQuery([]);
  }

  @Debounce(300)
  @Emit('search-change')
  handleSearch() {
    this.tableInstance.page = 1;
    this.tableInstance.keyWord = this.keyWord;

    const params = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        queryString: this.keyWord.trim?.().length ? this.keyWord : undefined,
      },
    };
    this.$router.replace(params).catch(() => {});
  }

  @Emit('search-change')
  handleFilterChange() {}

  /** 更新搜索条件 */
  handleSearchUpdate({ search, panelKey }) {
    this.updateRouteQuery(search, panelKey);
  }

  getSelections() {
    if (this.checkType === 'current') {
      return this.selectionData;
    }
    return this.tableInstance.filterData.filter(item => !this.excludeDataIds.includes(item.rowId));
  }

  /** 更新搜索条件到路由query中 */
  @Emit('filter-update')
  updateRouteQuery(search?, panelKey?) {
    return {
      search,
      panelKey,
    };
  }
}
</script>
<style lang="scss" scoped>
/* stylelint-disable declaration-no-important */
@import '../../../theme/index.scss';

.performance-tool {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 18px 20px 20px;
  font-size: 0;
  border: 1px solid #dcdee5;
  border-top: 0;
  border-bottom: 0;

  &-left {
    display: flex;

    .tool-btn {
      margin-right: 8px;
    }

    :deep(.bk-dropdown-menu.disabled) {
      color: #c4c6cc;
      background-color: #fff!important;
      border-color: #dcdee5!important;
    }

    :deep(.bk-dropdown-menu.disabled *) {
      color: #c4c6cc;
      background-color: #fff!important;
      border-color: #dcdee5!important;
    }
  }

  &-right {
    display: flex;
    flex-basis: 515px;
    align-items: center;
    justify-content: flex-end;

    .tool-search {
      flex: 1;
    }

    .tool-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      margin-left: 8px;
      font-size: 16px;
      color: #979ba5;
      cursor: pointer;
      border: 1px solid #c4c6cc;
      border-radius: 2px;

      &.is-filter {
        color: #3a83ff;
        background: #f1f6ff;
        border-color: #699df4;
      }

      &.disabled {
        cursor: not-allowed;
      }
    }
  }
}

.tool-popover {
  margin: -7px -14px;
  color: #63656e;

  &-title {
    margin: 15px 24px 0;
    font-size: 24px;
    line-height: 32px;
    color: #444;
  }

  &-content {
    display: flex;
    flex-flow: row;
    flex-wrap: wrap;
    align-items: center;
    padding: 0;
    margin: 15px 20px 22px 24px;

    &-item {
      flex-basis: 33.33%;
      flex-flow: 0;
      flex-shrink: 0;
      max-width: 200px;
      margin: 8px 0;

      @include ellipsis;

      :deep(.bk-form-checkbox) {
        margin-bottom: 0;

        .bk-checkbox {
          &::after {
            box-sizing: content-box;
          }
        }

        .checkbox-text {
          display: inline-block;
          width: 130px;

          @include ellipsis;
        }
      }
    }
  }
}
</style>
