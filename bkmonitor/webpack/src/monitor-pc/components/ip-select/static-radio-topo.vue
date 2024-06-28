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
  <section class="static-topo-radio">
    <bk-radio-group v-model="checkedIp">
      <bk-big-tree
        ref="tree"
        :check-strictly="false"
        :data="treeData"
        :filter-method="handlerSearch"
        :default-checked-nodes="checkedData"
        :default-expanded-nodes="defaultExpanded"
        :height="height"
      >
        <template #default="{ node, data }">
          <bk-radio
            v-if="data && data.ip"
            :value="`${data.ip}|${data.bk_cloud_id}`"
            @change="selectChange(data)"
          >
            {{ node.name }}
          </bk-radio>
          <span v-else>
            {{ node ? node.name : '' }}
          </span>
        </template>
      </bk-big-tree>
    </bk-radio-group>
  </section>
</template>
<script>
import { debounce } from 'throttle-debounce';

import mixin from './topo-mixins';

export default {
  name: 'StaticRadioTopo',
  mixins: [mixin],
  data() {
    return {
      watchKeword: null,
      defaultExpanded: [],
      checkedIp: '',
      checkedNodeData: null,
    };
  },
  watch: {
    treeData: {
      handler(v) {
        this.$refs.tree?.setData(v || []);
      },
    },
    checkedData: {
      handler(v) {
        if (v.length === 0) {
          this.checkedIp = '';
          this.checkedNodeData = null;
        } else {
          this.checkedIp = v[0] ? `${v[0].ip}|${v[0].bkCloudId}` : '';
        }
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
    checkedIp: {
      handler(v) {
        if (v) {
          this.handleTreeCheck(Boolean(v), this.checkedNodeData);
        }
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
    handleTreeCheck(checked = false, data = {}) {
      this.$emit('node-check', 'static-topo-radio', { checked, data });
    },
    handleFilter(v) {
      this.$emit('update:isSearchNoData', this.$refs?.tree?.filter(v).length < 1);
    },
    handlerSearch(keyword, node) {
      return node.data.ip.toString().indexOf(keyword) > -1 || node.data.name.toString().indexOf(keyword) > -1;
    },
    handlerGetInterOrDiff(v, old) {
      const intersection = v.filter(item => old.indexOf(item) > -1);
      let difference = v.filter(i => old.indexOf(i) === -1).concat(old.filter(i => !v.includes(i)));
      difference = difference.filter(set => !~v.indexOf(set));
      return {
        difference,
        intersection,
      };
    },
    handleDefaultExpanded() {
      if (this.checkedData.length) {
        // 回显数据
        this.defaultExpanded = this.checkedData;
        return;
      }
      if (Array.isArray(this.defaultExpandNode)) {
        this.defaultExpanded = this.defaultExpandNode;
        return;
      }
      // 默认展开树
      this.defaultExpanded = this.handleGetExpandNodeByDeep(this.defaultExpandNode, this.treeData);
    },
    selectChange(data) {
      this.checkedNodeData = data;
    },
  },
};
</script>
<style lang="scss" scoped>
.static-topo-radio {
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
