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
  <div class="select-input">
    <!-- 左边主选框 -->
    <bk-select
      v-model="value"
      class="all-select"
      :clearable="false"
      :z-index="10"
      style="width: 160px"
      @change="handlemainBoxSwitch"
    >
      <bk-option
        v-for="option in list"
        :id="option.id"
        :key="option.id"
        :name="option.name"
      />
    </bk-select>
    <!-- 选择：全部 搜索框 -->
    <bk-input
      v-show="value === 1"
      v-model="allFind.value"
      :clearable="true"
      :placeholder="$t('采集名称 / 策略名称 / 仪表盘名称')"
      :right-icon="'bk-icon icon-search'"
      @change="handleSearch"
      @clear="handlemainBoxSwitch"
    />
    <!-- 选择：节点 节点树 -->
    <select-input-template
      v-show="value === 2"
      ref="node"
      :value="selectNode.value"
      :placeholder="$t('业务/集群/节点')"
      @clear="handlemainBoxSwitch"
    >
      <div
        v-if="treeData.length"
        class="node-padding"
      >
        <bk-big-tree :data="treeData">
          <template slot-scope="scope">
            <div
              class="tree-data"
              @mouseenter="handleNodeEnter(scope.node.id)"
              @mouseleave="handleNodeLeave"
            >
              <div :class="{ choice: selectNode.id === scope.node.id }">
                {{ scope.node.name }}
              </div>
              <div
                v-show="selectNode.hoverId === scope.node.id"
                class="selection-data choice"
                @click="handleChoiceNode(scope.node)"
              >
                {{ $t('选取') }}
              </div>
            </div>
          </template>
        </bk-big-tree>
      </div>
    </select-input-template>
    <!-- 选择：服务分类 二级选框 -->
    <select-input-template
      v-show="value === 3"
      ref="server"
      :value="serverSearch.value"
      @clear="handlemainBoxSwitch"
    >
      <div
        v-if="serviceCategory.length"
        class="server-content"
      >
        <div class="content-left">
          <div
            v-for="(item, index) in serviceCategory"
            :key="index"
            class="content-item"
            :class="{ 'click-item': serverSearch.firstIndex === index }"
            @mouseenter="handleFirstServerMove(index, item)"
          >
            {{ item.name }}
            <i class="bk-select-angle bk-icon icon-angle-right" />
          </div>
        </div>
        <div
          v-show="serverSearch.children.length"
          class="content-right"
        >
          <div
            v-for="(item, index) in serverSearch.children"
            :key="index"
            class="content-item"
            :class="{
              'click-item':
                serverSearch.secondIndex === index && serverSearch.copyFirstIndex === serverSearch.firstIndex,
            }"
            @click="handleServerClick(index, item)"
          >
            {{ item.name }}
          </div>
        </div>
      </div>
    </select-input-template>
    <!-- 选择：数据对象 二级下拉框 -->
    <bk-select
      v-show="value === 4"
      v-model="dataObj.value"
      class="data-obj"
      :scroll-height="427"
      @change="handleDataObjChange"
      @clear="handlemainBoxSwitch"
    >
      <bk-option-group
        v-for="(group, index) in dataObject"
        :key="index"
        :name="group.name"
      >
        <bk-option
          v-for="(option, groupIndex) in group.children"
          :id="option.id"
          :key="groupIndex"
          :name="option.name"
        />
      </bk-option-group>
    </bk-select>
  </div>
</template>

<script>
import { debounce } from 'throttle-debounce';
import { mapActions, mapGetters } from 'vuex';

import selectInputTemplate from './select-input-template';

export default {
  name: 'SelectInput',
  components: {
    selectInputTemplate,
  },
  inject: ['emptyStatus'],
  props: {
    parentLoading: Boolean,
    defaultValue: {
      type: Object,
      default: () => ({ value: 1, searchValue: '' }),
    },
  },
  data() {
    return {
      value: 1,
      list: [
        { id: 1, name: this.$t('全部') },
        { id: 2, name: this.$t('拨测节点') },
        { id: 3, name: this.$t('服务分类') },
        { id: 4, name: this.$t('数据对象') },
      ],
      // 全部
      allFind: {
        value: '',
        handleSearch() {},
      },
      // 数据对象
      dataObj: {
        value: '',
      },
      // 节点
      selectNode: {
        id: 0,
        hoverId: -1,
        value: '',
      },
      // 服务分类
      serverSearch: {
        children: [],
        firstIndex: -1,
        firstValue: '',
        secondIndex: -1,
        value: '',
      },
      selectValue: '',
    };
  },
  computed: {
    ...mapGetters('common', ['treeData', 'dataObject', 'serviceCategory']),
  },
  async created() {
    this.handleSearch = debounce(500, this.handleFindAll);
    await this.getSelectData();
    this.handleRouterJump();
  },
  methods: {
    ...mapActions('export', ['getAllExportList']),
    ...mapActions('common', ['getTopoTree', 'getDataObject', 'getServiceCategory']),
    async getSelectData() {
      // 获取动态拓扑树选择框的数据
      if (!this.treeData.length) {
        await this.getTopoTree().catch(() => {
          this.$bkMessage({ theme: 'error', message: this.$t('获取节点拓扑树失败') });
        });
      }
      // 获取数据对象选择框的数据
      if (!this.dataObject.length) {
        await this.getDataObject().catch(() => {
          this.$bkMessage({ theme: 'error', message: this.$t('数据对象分类请求失败') });
        });
      }
      // 获取服务分类选择框的数据
      if (!this.serviceCategory.length) {
        await this.getServiceCategory().catch(() => {
          this.$bkMessage({ theme: 'error', message: this.$t('获取服务分类失败') });
        });
      }
    },
    // 主选框切换事件 clear-icon事件
    handlemainBoxSwitch() {
      if (this.parentLoading) return;
      this.selectNode.id = -1;
      if (this.allFind.value || this.dataObj.value || this.selectNode.value || this.serverSearch.value) {
        this.getQueryTableData();
      }
      this.allFind.value = '';
      this.dataObj.value = '';
      this.selectNode.value = '';
      this.serverSearch.value = '';
    },
    // 全部搜索事件
    handleFindAll(v) {
      this.selectValue = v;
      this.getQueryTableData({ search_value: v });
    },
    // 节点搜索事件
    handleChoiceNode(node) {
      this.selectValue = node;
      const nameArr = node.parents.map(item => item.data.name);
      nameArr.push(node.name);
      this.selectNode.show = false;
      this.selectNode.value = nameArr.join('/');
      this.selectNode.id = this.selectNode.hoverId;
      this.getQueryTableData({ cmdb_node: `${node.data.bk_obj_id}|${node.data.bk_inst_id}` });
      this.$refs.node.handleSelectBlur();
    },
    // 服务分类一级选择mousehover事件
    handleFirstServerMove(index, item) {
      this.serverSearch.children = item.children;
      this.serverSearch.firstIndex = index;
      this.serverSearch.firstValue = item.name;
    },
    // 服务分类搜索事件
    handleServerClick(index, item) {
      this.selectValue = item;
      this.serverSearch.value = `${this.serverSearch.firstValue}：${item.name}`;
      this.serverSearch.secondIndex = index;
      this.serverSearch.copyFirstIndex = this.serverSearch.firstIndex;
      this.serverSearch.show = false;
      this.getQueryTableData({ service_category_id: item.id });
      this.$refs.server.handleSelectBlur();
    },
    // 数据对象搜索事件
    handleDataObjChange(newV) {
      this.selectValue = newV;
      this.getQueryTableData({ label: newV });
    },
    // 节点划入高亮事件
    handleNodeEnter(id) {
      this.selectNode.hoverId = id;
    },
    // 节点划出事件
    handleNodeLeave() {
      this.selectNode.hoverId = -1;
    },
    // 处理其他路由跳转导出页面
    handleRouterJump() {
      const { defaultValue } = this;
      this.value = defaultValue.value;
      if (defaultValue.routeName === 'service-classify') {
        this.serverSearch.firstValue = defaultValue.serverFirst;
        const el = this.serviceCategory.some(item => {
          if (item.name === defaultValue.serverFirst) {
            const index = item.children.findIndex(child => child.name === defaultValue.serverSecond);
            index > -1 && this.handleServerClick(index, item.children[index]);
            return true;
          }
          return false;
        });
        if (!el) {
          this.$emit('change-table-loading', false);
        }
      }
    },
    handleOperation(type) {
      if (type === 'clear-filter') {
        if (this.value === 1) {
          this.allFind.value = '';
          this.getQueryTableData();
        } else {
          this.value = 1;
        }
        return;
      }
      if (type === 'refresh') {
        switch (this.value) {
          case 1:
            this.handleFindAll(this.selectValue);
            break;
          case 2:
            this.handleChoiceNode(this.selectValue);
            break;
          case 3:
            this.handleServerClick(this.selectValue);
            break;
          case 4:
            this.handleDataObjChange(this.selectValue);
            break;
        }
        return;
      }
    },
    // 搜索接口
    async getQueryTableData(params = {}) {
      this.$emit('change-table-loading', true);
      this.emptyStatus.changeType(Object.keys(params).length ? 'search-empty' : 'empty');
      const data = await this.getAllExportList(params);
      if (data.error) this.emptyStatus.changeType('500');
      this.$emit('select-data', data);
      this.$emit('change-table-loading', false);
    },
  },
};
</script>

<style lang="scss" scoped>
.select-input {
  display: flex;
  width: 506px;
  margin-bottom: 20px;

  :deep(.bk-big-tree-node) {
    padding-left: calc(var(--level) * 30px + 20px);
  }

  .all-select {
    min-width: 120px;
    margin-right: 6px;
    background: #fff;
  }

  .data-obj {
    width: 380px;
    background: #fff;
  }

  .node-padding {
    width: 380px;
    max-height: 760px;
    padding-top: 6px;
    overflow: scroll;
  }

  .server-content {
    display: flex;

    .content-left {
      width: 190px;
      padding-top: 6px;
      background: #fff;
      border-right: 1px solid #dcdee5;
    }

    .content-right {
      width: 190px;
      padding-top: 6px;
      background: #fff;
    }

    .content-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 32px;
      padding: 0 10px 0 15px;

      &:hover {
        color: #3a84ff;
        cursor: pointer;
        background: #e1ecff;
      }
    }

    .click-item {
      color: #3a84ff;
      background: #fafbfd;
    }
  }
}

.tree-data {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .selection-data {
    margin-right: 11px;
  }

  .choice {
    color: #3a84ff;
  }
}
</style>
