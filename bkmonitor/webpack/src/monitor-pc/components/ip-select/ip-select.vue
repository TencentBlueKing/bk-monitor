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
    class="ip-select"
    :style="{ minWidth: minWidth + 'px', height: height + 'px', maxWidth: maxWidth + 'px' }"
    v-bind="$attrs"
  >
    <!--IP选择器左侧tree区域-->
    <div
      class="ip-select-left"
      :style="{ 'flex-basis': left.width + 'px', width: left.width + 'px' }"
      data-tag="resizeTarget"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseout="handleMouseOut"
    >
      <!--静态/动态 tab页-->
      <div class="left-tab">
        <span
          class="left-tab-item"
          :class="[active === 0 ? 'active' : 'tab-item', { 'tab-disabled': tabDisabled === 0 }]"
          :style="{ 'border-right': active === 1 ? '1px solid #DCDEE5' : 'none' }"
          @click="tabDisabled !== 0 && handleTabClick(0)"
          @mouseleave="handleStaticMouseLeave"
          @mouseenter="handleStaticMouseEnter"
        >
          <span ref="staticTab"
            ><slot name="left-tab"> {{ $t('静态') }} </slot></span
          >
        </span>
        <span
          class="left-tab-item"
          :class="[active === 1 ? 'active' : 'tab-item', { 'tab-disabled': tabDisabled === 1 }]"
          :style="{ 'border-left': active === 0 ? '1px solid #DCDEE5' : 'none' }"
          @click="tabDisabled !== 1 && handleTabClick(1)"
          @mouseleave="handleDynamicMouseLeave"
          @mouseenter="handleDynamicMouseEnter"
        >
          <span ref="dynamicTab"
            ><slot name="left-tab"> {{ $t('动态') }} </slot></span
          >
        </span>
      </div>
      <!--静态/动态 tree-->
      <div class="left-content">
        <!--静态输入方式1. 业务拓扑 2. IP输入-->
        <bk-select
          v-if="active === 0 && !selectUnshow.includes(active)"
          v-model="select.staticActive"
          class="left-content-select"
          :popover-min-width="200"
          :clearable="false"
          :popover-options="selectOption"
          @change="handleActiveSelectChange"
        >
          <bk-option
            v-for="option in select.staticList"
            v-show="!activeUnshow.includes(option.id)"
            :id="option.id"
            :key="option.id"
            :disabled="activeDiabled.includes(option.id)"
            :name="option.name"
          >
            <span v-show="option.id !== 4 || isExtranet">{{ option.name }}</span>
          </bk-option>
        </bk-select>
        <!--动态输入方式1. 业务拓扑 2. 动态分组-->
        <bk-select
          v-if="active === 1 && !selectUnshow.includes(active)"
          v-model="select.dynamicActive"
          class="left-content-select"
          :popover-min-width="200"
          :clearable="false"
          @change="handleActiveSelectChange"
        >
          <bk-option
            v-for="option in select.dynamicList"
            v-show="!activeUnshow.includes(option.id)"
            :id="option.id"
            :key="option.id"
            :disabled="activeDiabled.includes(option.id)"
            :name="option.name"
          />
        </bk-select>
        <!--静态/动态 tree组件-->
        <div
          v-bkloading="{ isLoading: isShowTreeLoading && leftLoading }"
          class="left-content-wrap"
          :style="{ '--height': height + 'px' }"
        >
          <keep-alive>
            <!--静态-IP输入-->
            <slot
              v-if="curActive === 0"
              name="static-input"
              v-bind="{
                defaultText: staticInput.defaultText,
                checked: handleSelectChecked,
              }"
            >
              <template>
                <static-input
                  key="input"
                  type="static-ip"
                  :default-text="staticInput.defaultText"
                  @checked="handleSelectChecked"
                  @change-input="handleChangeInput"
                >
                  <slot name="change-input" />
                </static-input>
              </template>
            </slot>
            <!--静态-业务拓扑-->
            <slot
              v-else-if="curActive === 1"
              name="static-topo"
              v-bind="{
                treeData: staticTopo.treeData,
                checkedData: staticChecked,
                disabledData: staticTopo.disabledData,
                filterMethod: filterMethod,
                keyword: search.keyword,
                nodeCheck: handleSelectChecked,
              }"
            >
              <template>
                <static-topo
                  v-if="staticTopo.treeData.length"
                  ref="staticTopo"
                  :tree-data="staticTopo.treeData"
                  :checked-data="staticChecked"
                  :disabled-data="staticTopo.disabledData"
                  :filter-method="filterMethod"
                  :keyword="search.keyword"
                  :is-search-no-data.sync="isSearchNoData"
                  :default-expand-node="staticTopo.defaultExpandNode"
                  :height="topoHeight"
                  @node-check="handleSelectChecked"
                />
              </template>
            </slot>
            <!-- 静态 外网IP -->
            <slot
              v-else-if="curActive === 4"
              name="static-extranet-input"
              v-bind="{
                defaultText: staticExtranet.defaultText,
                checked: handleSelectChecked,
              }"
            >
              <template>
                <static-input
                  key="extranet"
                  type="static-extranet"
                  :default-text="staticExtranet.defaultText"
                  @checked="handleSelectChecked"
                  @change-input="handleChangeInput"
                >
                  <slot name="change-input" />
                </static-input>
              </template>
            </slot>
            <!--动态-业务拓扑-->
            <slot
              v-else-if="curActive === 2"
              name="dynamic-topo"
              v-bind="{
                treeData: dynamicTopo.treeData,
                checkedData: dynamicTopo.checkedData,
                disabledData: dynamicTopo.disabledData,
                filterMethod: filterMethod,
                keyword: search.keyword,
                refs: $refs.dynamicTopo,
                nodeCheck: handleSelectChecked,
              }"
            >
              <template>
                <dynamic-topo
                  v-if="dynamicTopo.treeData.length"
                  ref="dynamicTopo"
                  :tree-data="dynamicTopo.treeData"
                  :checked-data="dynamicTopo.checkedData"
                  :disabled-data="dynamicTopo.disabledData"
                  :filter-method="filterMethod"
                  :keyword="search.keyword"
                  :is-search-no-data.sync="isSearchNoData"
                  :default-expand-node="dynamicTopo.defaultExpandNode"
                  :height="topoHeight"
                  @node-check="handleSelectChecked"
                />
              </template>
            </slot>
            <!--动态-动态分组-->
            <slot
              v-else-if="curActive === 3"
              name="dynamic-group"
              v-bind="{
                treeData: dynamicGroup.treeData,
                checkedData: dynamicGroup.checkedData,
                disabledData: dynamicGroup.disabledData,
                filterMethod: filterMethod,
                keyword: search.keyword,
                refs: $refs.dynamicGroup,
                nodeCheck: handleSelectChecked,
              }"
            >
              <template>
                <dynamic-group
                  v-if="dynamicGroup.treeData.length"
                  ref="dynamicGroup"
                  :tree-data="dynamicGroup.treeData"
                  :checked-data="dynamicGroup.checkedData"
                  :disabled-data="dynamicGroup.disabledData"
                  :filter-method="filterMethod"
                  :keyword="search.keyword"
                  @node-check="handleSelectChecked"
                />
              </template>
            </slot>
          </keep-alive>
          <!--空数据-->
          <div
            v-if="isSearchNoData"
            class="search-none"
          >
            <slot name="search-noData" />
          </div>
        </div>
      </div>
      <!--tree搜索-->
      <div
        v-show="curActive !== 0 && curActive !== 4"
        class="left-footer"
        :class="{ 'input-focus': search.focus }"
      >
        <i class="bk-icon icon-search left-footer-icon" />
        <input
          v-model="search.keyword"
          class="left-footer-input"
          :placeholder="searchPlaceholder"
          @focus="handleSearchFocus"
          @blur="search.focus = false"
        />
      </div>
      <div
        v-show="resizeState.show"
        class="resize-line"
        :style="{ left: resizeState.left + 'px' }"
      />
    </div>
    <!--IP选择器右侧表格区域-->
    <div class="ip-select-right">
      <slot name="right-wrap">
        <div
          v-if="staticTableData.length"
          :key="staticIp.type"
          v-bkloading="{ isLoading: isShowTableLoading && staticLoading }"
          class="right-wrap"
          :class="{ 'is-expand': staticIp.expand }"
        >
          <right-panel
            v-model="staticIp.expand"
            type="staticIp"
            :title="{ num: staticTopo.tableData.length }"
            @change="handleCollapseChange"
          >
            <slot
              name="static-ip-panel"
              v-bind="{
                data: staticTableData,
                deleteClick: handleDeleteStaticIp,
              }"
            >
              <bk-table
                :data="staticTableData"
                :empty-text="$t('无数据')"
              >
                <bk-table-column
                  prop="ip"
                  label="IP"
                  min-width="210"
                />
                <bk-table-column
                  prop="agent"
                  :label="$t('状态')"
                />
                <bk-table-column
                  prop="cloud"
                  :label="$t('管控区域')"
                />
                <bk-table-column
                  :label="$t('操作')"
                  align="center"
                  width="80"
                >
                  <template slot-scope="scope">
                    <bk-button
                      text
                      @click="handleDeleteStaticIp(scope)"
                    >
                      {{ $t('移除') }}
                    </bk-button>
                  </template>
                </bk-table-column>
              </bk-table>
            </slot>
          </right-panel>
        </div>
        <div
          v-if="dynamicTopo.tableData.length"
          :key="dynamicTopo.type"
          v-bkloading="{ isLoading: isShowTableLoading && dynamicTopo.loading }"
          class="right-wrap"
          :class="{ 'is-expand': dynamicTopo.expand }"
        >
          <right-panel
            v-model="dynamicTopo.expand"
            type="dynamicTopo"
            :title="{ num: dynamicTopo.tableData.length, type: $t('拓扑节点') }"
            @change="handleCollapseChange"
          >
            <slot
              name="dynamic-topo-panel"
              v-bind="{
                data: dynamicTopo.tableData,
                deleteClick: handleDelDynamicTopo,
              }"
            >
              <ul class="topo-list">
                <li
                  v-for="(item, index) in dynamicTopo.tableData"
                  :key="index"
                  class="topo-list-item"
                >
                  <span class="item-name">{{ item.name }}</span>
                  <div class="item-desc">
                    {{ $t('现有主机') }}
                    <span class="status-host">{{ item.host }}</span
                    >，
                    <i18n path="{0}台主机Agent异常">
                      <span class="status-unusual">{{ item.unusual }}</span>
                    </i18n>
                  </div>
                  <bk-button
                    text
                    class="item-btn"
                    @click="handleDelDynamicTopo(index, item)"
                  >
                    {{ $t('移除') }}
                  </bk-button>
                </li>
              </ul>
            </slot>
          </right-panel>
        </div>
        <div
          v-if="dynamicGroup.tableData.length"
          :key="dynamicGroup.type"
          v-bkloading="{ isLoading: isShowTableLoading && dynamicGroup.loading }"
          class="right-wrap"
          :class="{ 'is-expand': dynamicGroup.expand }"
        >
          <right-panel
            v-model="curComp.expand"
            type="dynamicTopo"
            @change="handleCollapseChange"
          >
            <slot
              name="dynamic-group-panel"
              v-bind="{
                data: dynamicGroup.tableData,
              }"
            />
          </right-panel>
        </div>
        <div
          v-if="staticExtranet.tableData.length"
          :key="staticExtranet.type"
          v-bkloading="{ isLoading: isShowTableLoading && staticExtranet.loading }"
          class="right-wrap"
          :class="{ 'is-expand': staticExtranet.expand }"
        >
          <right-panel
            v-model="curComp.expand"
            type="staticExtranet"
            :title="{ num: staticExtranet.tableData.length, type: $t('外网IP') }"
            @change="handleCollapseChange"
          >
            <slot
              name="static-extranet-panel"
              v-bind="{
                data: staticExtranet.tableData,
              }"
            />
          </right-panel>
        </div>
        <div
          v-if="isNoData"
          key="right-empty"
          class="right-empty"
        >
          <span class="icon-monitor icon-hint" />
          <div class="right-empty-title">
            {{ $t('未选择任何内容') }}
          </div>
          <div class="right-empty-desc">
            {{ defaultEmptyDesc }}
          </div>
        </div>
      </slot>
    </div>
  </div>
</template>
<script>
import DynamicGroup from './dynamic-group';
import DynamicTopo from './dynamic-topo';
import RightPanel from './right-panel';
import StaticInput from './static-input';
import StaticTopo from './static-topo';

const EVENT_ACTIVESELECTCHANGE = 'active-select-change';

export default {
  name: 'IpSelect',
  components: {
    RightPanel,
    StaticInput,
    StaticTopo,
    DynamicTopo,
    DynamicGroup,
  },
  props: {
    // IP选择器最小宽度
    minWidth: {
      type: [Number, String],
      default: 850,
    },
    maxWidth: {
      type: [Number, String],
      default: 9999,
    },
    // IP选择器高度
    height: {
      type: [Number, String],
      default: 460,
    },
    idKey: {
      type: String,
      default: 'id',
    },
    nameKey: {
      type: String,
      default: 'name',
    },
    childrenKey: {
      type: String,
      default: 'children',
    },
    // 禁用 静态/动态 tab页
    tabDisabled: {
      type: Number,
      default: -1,
    },
    // 禁用 静态/动态 输入方式
    activeDiabled: {
      type: Array,
      default() {
        return [3];
      },
    },
    // 是否显示 静态/动态 输入方式（选项）
    activeUnshow: {
      type: Array,
      default() {
        return [];
      },
    },
    // 是否显示 静态/动态 输入方式（select框）
    selectUnshow: {
      type: Array,
      default() {
        return [];
      },
    },
    // 默认激活的 静态/动态 tab页
    defaultActive: {
      type: Number,
      required: true,
    },
    // 右侧表格空数据text
    defaultEmptyDesc: {
      type: String,
      default() {
        return this.$t('在左侧选择主机/节点/动态分组');
      },
    },
    inputIpSplit: {
      type: String,
      default: '|',
    },
    // 获取默认数据（tree数据、默认勾选数据、禁用数据、表格数据、默认展开节点数据）！！！！
    getDefaultData: {
      type: Function, // 需返回 treeData、checkedData（可选）、disabledData（可选）、tableData（可选）、defaultExpandNode（可选）
      required: true,
    },
    // 勾选树节点时会触发此方法获取数据 ！！！！
    getFetchData: {
      type: Function,
      required: true,
    },
    // 树过滤方法
    filterMethod: {
      type: Function,
      default: () => () => {},
    },
    isShowTreeLoading: {
      type: Boolean,
      default: true,
    },
    isShowTableLoading: {
      type: Boolean,
      default: true,
    },
    // 是否是实例（实例对象只能选择动态tab的业务拓扑）
    isInstance: Boolean,
    isExtranet: {
      type: Boolean,
      default: false,
    },
    // 拓扑树的高度（设置此属性可开启虚拟滚动）
    topoHeight: Number,
  },
  data() {
    return {
      selectOption: {
        boundary: 'window',
      },
      active: 0, // 当前 active 的 tab
      changeInput: false,
      // 静态/动态 输入方式数据
      select: {
        staticList: [
          {
            id: 0,
            name: this.$t('输入IP'),
            type: 'staticInput',
          },
          {
            id: 1,
            name: this.$t('业务拓扑'),
            type: 'staticTopo',
          },
          {
            id: 4,
            name: this.$t('外网IP'),
            type: 'staticExtranet',
          },
        ],
        dynamicList: [
          {
            id: 2,
            name: this.$t('业务拓扑'),
            type: 'dynamicTopo',
          },
          {
            id: 3,
            name: this.$t('动态分组'),
            type: 'dynamicGroup',
          },
        ],
        staticActive: 0,
        dynamicActive: 2,
      },
      // 静态输入
      staticInput: {
        name: 'staticIp',
        defaultText: '',
        expand: false,
        checkedData: [],
        tableData: [],
        type: 'static-ip',
        mark: false,
        loading: false,
      },
      // 静态拓扑（tree）
      staticTopo: {
        name: 'staticIp',
        treeData: [],
        checkedData: [],
        disabledData: [],
        expand: false,
        tableData: [],
        type: 'static-topo',
        loading: false,
        defaultExpandNode: 1,
      },
      staticExtranet: {
        name: 'staticExtranet',
        defaultText: '',
        expand: true,
        checkedData: [],
        tableData: [],
        type: 'static-extranet',
        mark: false,
        loading: false,
      },
      // 动态拓扑（tree）
      dynamicTopo: {
        name: 'dynamicTopo',
        treeData: [],
        checkedData: [],
        disabledData: [],
        expand: false,
        tableData: [],
        type: 'dynamic-topo',
        loading: false,
        defaultExpandNode: 1,
      },
      dynamicGroup: {
        name: 'dynamicGroup',
        treeData: [],
        checkedData: [],
        disabledData: [],
        expand: false,
        tableData: [],
        type: 'dynamic-group',
        loading: false,
      },
      // 搜索关键字
      search: {
        keyword: '',
        focus: false,
      },
      leftLoading: false,
      isSearchNoData: false,
      staticIp: {
        expand: false,
      },
      instance: {
        dynamic: null,
        static: null,
      },
      // 搜索框placeholder
      searchPlaceholder: this.$t('输入IP'),
      left: {
        width: 240,
      },
      resizeState: {
        show: false,
        ready: false,
        left: 0,
        dragging: false,
      },
    };
  },
  computed: {
    curComp() {
      return this[this.curItem.type];
    },
    // 当前输入方式
    curActive() {
      return this.active === 0 ? this.select.staticActive : this.select.dynamicActive;
    },
    curItem() {
      return this.active === 0
        ? this.select.staticList.find(item => item.id === this.select.staticActive)
        : this.select.dynamicList.find(item => item.id === this.select.dynamicActive);
    },
    staticTableData() {
      let arr = this.handleStaticTableData(this.staticInput.tableData, this.staticTopo.tableData);
      const hash = {};
      arr = arr.reduce((item, next) => {
        if (!hash[next.name]) {
          hash[next.name] = true;
          item.push(next);
        }
        return item;
      }, []);
      return arr;
    },
    staticChecked() {
      const ids = this.handleStaticTableData(this.staticInput.checkedData, this.staticTopo.checkedData, false);
      ids.concat(this.staticTopo.checkedData);
      return Array.from(new Set(ids));
    },
    staticLoading() {
      return this.staticInput.loading || this.staticTopo.loading;
    },
    isNoData() {
      return (
        !this.staticTableData.length &&
        !this.dynamicTopo.tableData.length &&
        !this.dynamicGroup.tableData.length &&
        !this.staticExtranet.tableData.length
      );
    },
  },
  watch: {
    curActive: {
      handler: 'handlerCurActiveChange',
      // immediate: true
    },
    defaultActive: {
      handler(v) {
        if (v === 0 || v === 1 || v === 4) {
          this.active = 0;
          this.select.staticActive = v;
          this.curComp.expand = true;
          this.staticIp.expand = true;
        } else if (v === 2 || v === 3) {
          this.active = 1;
          this.select.dynamicActive = v;
          this.curComp.expand = true;
        }
      },
      immediate: true,
    },
  },
  methods: {
    handleMouseDown(e) {
      if (this.resizeState.ready) {
        let { target } = event;
        while (target && target.dataset.tag !== 'resizeTarget') {
          target = target.parentNode;
        }
        this.resizeState.show = true;
        const rect = e.target.getBoundingClientRect();
        document.onselectstart = function () {
          return false;
        };
        document.ondragstart = function () {
          return false;
        };
        const handleMouseMove = event => {
          this.resizeState.dragging = true;
          this.resizeState.left = event.clientX - rect.left;
        };
        const handleMouseUp = () => {
          if (this.resizeState.dragging) {
            this.left.width = this.resizeState.left;
          }
          document.body.style.cursor = '';
          this.resizeState.dragging = false;
          this.resizeState.show = false;
          this.resizeState.ready = false;
          document.removeEventListener('mousemove', handleMouseMove);
          document.removeEventListener('mouseup', handleMouseUp);
          document.onselectstart = null;
          document.ondragstart = null;
          this.resize();
        };
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
      }
    },
    handleMouseMove() {
      let { target } = event;
      while (target && target.dataset.tag !== 'resizeTarget') {
        target = target.parentNode;
      }
      const rect = target.getBoundingClientRect();
      const bodyStyle = document.body.style;
      if (rect.width > 12 && rect.right - event.pageX < 8) {
        bodyStyle.cursor = 'col-resize';
        this.resizeState.ready = true;
      }
    },
    handleMouseOut() {
      document.body.style.cursor = '';
      this.resizeState.ready = false;
    },
    // 节点勾选时触发
    async handleSelectChecked(type, payload) {
      const { curComp } = this;
      try {
        curComp.loading = true;
        const { checkedData, tableData, disabledData } = await this.getFetchData(type, payload);
        if (type === 'static-extranet') {
          tableData.forEach(item => {
            if (!this.staticExtranet.tableData.find(el => el.ip === item.ip)) {
              this.staticExtranet.tableData.push(item);
            }
          });
          this.staticInput.expand = true;
          if (tableData.length) {
            this.handleCollapseChange(true, curComp.name);
          }
        } else {
          this.setCurActivedCheckedData(checkedData);
          this.setCurActivedDisabledData(disabledData);
          this.setCurActivedTableData(tableData);
          this.handleCollapseChange(true, curComp.name);
        }
      } catch (e) {
        return e;
      } finally {
        curComp.loading = false;
      }
    },
    // 切换 tab 时事件
    async handlerCurActiveChange(v, old) {
      if (old !== 4) {
        try {
          this.active === 0
            ? (this.searchPlaceholder = this.$t('输入IP'))
            : (this.searchPlaceholder = this.$t('搜索拓扑节点')); // 静态和动态搜索款Placeholder
          if (typeof this.getDefaultData === 'function') {
            this.leftLoading = true;
            if ((v > 0 && this.curComp.treeData.length === 0) || (v === 0 && !this.curComp.mark)) {
              const data = await this.getDefaultData(this.curComp.type);
              this.leftLoading = false;
              if (data) {
                if (v > 0) {
                  this.curComp.treeData = data.treeData || [];
                  this.curComp.checkedData = data.checkedData || [];
                  this.curComp.disabledData = data.disabledData || [];
                  this.curComp.tableData = data.tableData || [];
                  this.curComp.defaultExpandNode = data.defaultExpandNode || 1;
                  this.dynamicTopo.checkedData = data.checkedData;
                } else {
                  this.curComp.tableData = data.tableData || [];
                  this.curComp.mark = true;
                  this.curComp.defaultText = (data.defaultText || '').replace(
                    new RegExp(`\\${this.inputIpSplit}`, 'gm'),
                    '\n'
                  );
                }
              }
            }
          }
        } catch (e) {
          return e;
        } finally {
          this.leftLoading = false;
        }
      }
    },
    handleStaticTableData(data1, data2, value = true) {
      const data = new Map();
      let len = Math.max(data1.length, data2.length);
      while (len) {
        const item1 = data1[len - 1];
        const item2 = data2[len - 1];
        if (item1) {
          if (item1[this.idKey]) {
            data.set(item1[this.idKey], item1);
          } else {
            data.set(item1, item1);
          }
        }
        if (item2) {
          if (item2[this.idKey]) {
            data.set(item2[this.idKey], item2);
          } else {
            data.set(item2, item2);
          }
        }
        len -= 1;
      }
      return value ? Array.from(data.values()) : Array.from(data.keys());
    },
    handleSearchFocus() {
      this.search.focus = true;
    },
    handleCollapseChange(v, set) {
      if (v) {
        ['staticIp', 'dynamicTopo'].forEach(key => {
          this[key].expand = set === key;
        });
      } else {
        this[set].expand = v;
      }
    },
    handleDeleteStaticIp(scope) {
      this.staticInput.tableData = this.staticInput.tableData.filter(
        item => item[this.idKey] !== scope.row[this.idKey]
      );
      this.staticTopo.tableData = this.staticTopo.tableData.filter(item => item[this.idKey] !== scope.row[this.idKey]);
    },
    handleDelDynamicTopo(index, item) {
      const setIndex = this.dynamicTopo.checkedData.findIndex(setId => setId === item[this.idKey]);
      if (setIndex > -1) {
        this.$refs.dynamicTopo.handleSetChecked([this.dynamicTopo.checkedData[setIndex]], false);
        this.dynamicTopo.checkedData.splice(setIndex, 1);
      }
      this.dynamicTopo.tableData.splice(index, 1);
    },
    handleTabClick(active) {
      this.active = active;
    },
    getValues() {
      return {
        staticIp: this.staticTableData,
        dynamicTopo: this.dynamicTopo.tableData,
      };
    },
    setCurActivedCheckedData(checkedData, type) {
      if (['static-ip', 'static-topo'].includes(type || this.curComp.type)) {
        this.staticInput.checkedData = Array.isArray(checkedData) ? checkedData.slice() : [];
        this.staticTopo.checkedData = this.staticInput.checkedData;
      } else {
        this.curComp.checkedData = Array.isArray(checkedData) ? checkedData.slice() : [];
      }
    },
    setCurActivedDisabledData(disabledData, type) {
      if (['static-ip', 'static-topo'].includes(type || this.curComp.type)) {
        this.staticInput.disabledData = Array.isArray(disabledData) ? disabledData.slice() : [];
        this.staticTopo.disabledData = this.staticInput.disabledData;
      } else {
        this.curComp.disabledData = Array.isArray(disabledData) ? disabledData.slice() : [];
      }
    },
    setCurActivedTableData(tableData, type) {
      if (['static-ip', 'static-topo', 'static-extranet'].includes(type || this.curComp.type)) {
        this.staticInput.tableData = Array.isArray(tableData) ? tableData.slice() : [];
        this.staticTopo.tableData = this.staticInput.tableData;
      } else {
        this.curComp.tableData = Array.isArray(tableData) ? tableData.slice() : [];
      }
    },
    handleStaticMouseEnter() {
      if (this.tabDisabled === 1 || this.tabDisabled === -1) {
        if (this.instance.static) {
          this.instance.static.destroy(true);
          this.instance.static = null;
        }
        return false;
      }
      const staticRef = this.$refs.staticTab;
      let content = this.$t('支持静态IP的选择方式');
      if (this.tabDisabled === 0 && this.isInstance) {
        content = this.$t('监控对象为服务，只能选择动态方式');
      } else if (this.tabDisabled === 0) {
        content = this.$t('动态和静态不能混用');
      }
      if (!this.instance.static) {
        this.instance.static = this.$bkPopover(staticRef, {
          content,
          arrow: true,
          maxWidth: 250,
          showOnInit: true,
          distance: 14,
          placement: 'right',
        });
      }
      this.instance.static.set({ content });
      this.instance.static?.show(100);
    },
    handleStaticMouseLeave() {
      this.instance.static?.hide(0);
    },
    handleDynamicMouseEnter() {
      if (this.tabDisabled === 0 || this.tabDisabled === -1) {
        if (this.instance.dynamic) {
          this.instance.dynamic.destroy(true);
          this.instance.dynamic = null;
        }
        return false;
      }
      let content = this.$t('支持按拓扑节点动态变化进行采集');
      if (this.tabDisabled === 1) {
        content = this.$t('动态和静态不能混用');
      }
      const dynamicRef = this.$refs.dynamicTab;
      if (!this.instance.dynamic) {
        this.instance.dynamic = this.$bkPopover(dynamicRef, {
          content,
          arrow: true,
          maxWidth: 250,
          showOnInit: true,
          distance: 14,
          placement: 'right',
        });
      }
      this.instance.dynamic.set({ content });
      this.instance.dynamic?.show(100);
    },
    handleDynamicMouseLeave() {
      this.instance.dynamic?.hide(0);
    },
    handleChangeInput(v) {
      this.$emit('change-input', v);
    },
    // 当前active select选项改变
    handleActiveSelectChange(v, old) {
      this.$emit(EVENT_ACTIVESELECTCHANGE, {
        newValue: v,
        oldValue: old,
      });
    },
    setStaticExtranetData(data) {
      this.staticExtranet.tableData = data.map(item => ({ ip: item }));
    },
    // 重置虚拟滚动
    resize() {
      this.$nextTick(() => {
        const refsMap = {
          1: 'staticTopo',
          2: 'dynamicTopo',
        };
        const treeRefs = refsMap[this.curActive];
        treeRefs && this.$refs[treeRefs] && this.$refs[treeRefs].resize();
      });
    },
  },
};
</script>
<style lang="scss" scoped>
.ip-select {
  display: flex;
  font-size: 12px;
  color: #63656e;
  background-color: #fff;
  border-radius: 2px;

  &-left {
    position: relative;
    flex: 0 0 240px;
    min-width: 240px;
    background-image:
      linear-gradient(180deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
      linear-gradient(90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
      linear-gradient(-90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
      linear-gradient(0deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%);
    background-size: 100% 100%;

    .left-tab {
      display: flex;
      height: 42px;
      font-size: 14px;

      &-item {
        display: flex;
        flex: 1;
        align-items: center;
        justify-content: center;
        background: #fafbfd;
        border: 1px solid #dcdee5;

        &:first-child {
          border-right: 0;
        }

        &.active {
          height: 41px;
          background: #fff;
          border-bottom: 0;
        }

        &.tab-item:hover {
          color: #3a84ff;
          cursor: pointer;

          /* stylelint-disable-next-line declaration-no-important */
          border-color: #3a84ff !important;
        }

        &.tab-disabled {
          color: #c4c6cc;

          &:hover {
            color: #c4c6cc;
            cursor: not-allowed;

            /* stylelint-disable-next-line declaration-no-important */
            border-color: #dcdee5 !important;
          }
        }
      }
    }

    .left-content {
      padding: 20px 10px;

      &-select {
        min-width: 200px;
      }

      &-wrap {
        position: relative;
        height: calc(var(--height) - 142px);
        overflow: auto;
      }

      .search-none {
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 250px;
      }
    }

    .left-footer {
      position: absolute;
      right: 0;
      bottom: 0;
      left: 0;
      display: flex;
      align-items: center;
      height: 32px;
      color: #c4c6cc;
      border: 1px solid #dcdee5;

      ::placeholder {
        color: #979ba5;
      }

      &.input-focus {
        border-color: #3a84ff;

        .icon-search {
          color: #3a84ff;
        }
      }

      &-icon {
        flex: 0 0 34px;
        font-size: 14px;
        text-align: center;
      }

      &-input {
        width: 100%;
        height: 30px;
        color: #63656e;
        border: 0;
      }
    }
  }

  &-right {
    flex: 1;
    overflow: auto;
    background-image:
      linear-gradient(180deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
      linear-gradient(-90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
      linear-gradient(0deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%);
    background-size: 100% 100%;
    border-left: 0;

    .right-wrap {
      border: 1px solid #dcdee5;
      border-left: 0;

      &.is-expand {
        border-bottom: 0;
      }

      + .right-wrap {
        border-top: 0;
      }

      .topo-list {
        font-size: 12px;
        color: #63656e;

        &-item {
          display: flex;
          align-items: center;
          height: 40px;
          padding-left: 32px;
          border-bottom: 1px solid #dfe0e5;

          &:hover {
            background-color: #f0f1f5;
          }

          .item-desc {
            flex: 1;
            margin-left: 94px;
            color: #979ba5;

            .status-host {
              font-weight: bold;
              color: #3a84ff;
            }

            .status-unusual {
              font-weight: bold;
              color: #ea3636;
            }
          }

          .item-btn {
            margin-right: 21px;
            font-size: 12px;
          }
        }
      }
    }

    .right-empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      margin-top: 164px;

      .icon-monitor {
        margin-bottom: 8px;
        font-size: 28px;
        color: #dcdee5;
      }

      &-title {
        margin-bottom: 3px;
        font-size: 14px;
      }

      &-desc {
        color: #c4c6cc;
      }
    }
  }
}
</style>
