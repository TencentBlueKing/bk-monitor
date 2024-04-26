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
  <div class="static-topo">
    <bk-big-tree
      ref="tree"
      class="static-topo-content"
      show-checkbox
      :filter-method="handlerSearch"
      :default-checked-nodes="checkedData"
      :default-expanded-nodes="defaultExpanded"
      :data="treeData"
      :height="height"
      @check-change="handleTreeCheck"
    />
  </div>
</template>
<script>
import { debounce } from 'throttle-debounce';

import mixin from './topo-mixins';

export default {
  name: 'StaticTopo',
  mixins: [mixin],
  data() {
    return {
      watchKeword: null,
      defaultExpanded: [],
    };
  },
  watch: {
    treeData: {
      handler(v) {
        this.$refs.tree?.setData(v || []);
      },
    },
    checkedData: {
      handler(v, old) {
        const { difference } = this.handlerGetInterOrDiff(v, old);
        this.$refs.tree?.setChecked(v, {
          checked: true,
        });
        this.$refs.tree?.setChecked(difference, {
          checked: old.length === 0,
        });
      },
    },
    disabledData: {
      handler(v, old) {
        const { difference } = this.handlerGetInterOrDiff(v, old);
        this.$refs.tree?.setDisabled(v, {
          disabled: true,
        });
        this.$refs.tree?.setDisabled(difference, {
          disabled: old.length === 0,
        });
      },
    },
  },
  created() {
    this.watchKeword = this.$watch('keyword', debounce(300, this.handleFilter));
    this.handleDefaultExpanded();
  },
  mounted() {
    if (this.keyword.length) {
      this.handleFilter(this.keyword);
    }
  },
  beforeDestory() {
    this.watchKeword?.();
  },
  methods: {
    handleTreeCheck(checkedList, node) {
      this.$emit('node-check', 'static-topo', {
        data: node.data,
        checked: node.state.checked,
      });
    },
    handleFilter(v) {
      this.$emit('update:isSearchNoData', !this.$refs.tree.filter(v).length);
    },
    handlerSearch(keyword, node) {
      return `${node.data.ip}`.includes(keyword) || `${node.data.name}`.indexOf(keyword) > -1;
    },
    handlerGetInterOrDiff(v, old) {
      const intersection = v.filter(item => old.includes(item));
      let difference = v.filter(item => !old.includes(item)).concat(old.filter(item => !v.includes(item)));
      difference = difference.filter(set => !~v.indexOf(set));
      return { intersection, difference };
    },
    handleDefaultExpanded() {
      if (this.checkedData.length) {
        // 回显数据
        this.defaultExpanded = this.checkedData;
        return;
      }
      // 默认展开树
      if (Array.isArray(this.defaultExpandNode)) {
        this.defaultExpanded = this.defaultExpandNode;
      } else {
        this.defaultExpanded = this.handleGetExpandNodeByDeep(this.defaultExpandNode, this.treeData);
      }
      // this.defaultExpanded.push(this.treeData[0].id)
    },
  },
};
</script>
<style lang="scss" scoped>
.static-topo {
  padding-top: 15px;

  :deep(.bk-big-tree) {
    .node-content {
      overflow: inherit;
      font-size: 14px;
      text-overflow: inherit;
      white-space: nowrap;
    }
  }
}
</style>
