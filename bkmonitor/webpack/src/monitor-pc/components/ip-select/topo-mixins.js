/*
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
 */
export default {
  props: {
    defaultExpandNode: {
      type: [Array, Number], // Array类型：需要展开节点的ID, String类型：展开层次
      default() {
        return 1;
      },
      validator(value) {
        if (typeof value === 'number') {
          return value > 0;
        }
        return true;
      },
    },
    treeData: {
      type: Array,
      required: true,
    },
    // 单选项
    checkedData: {
      type: Array,
      default() {
        return [];
      },
      validator(value) {
        return value.length <= 1;
      },
    },
    disabledData: {
      type: Array,
      default() {
        return [];
      },
    },
    filterMethod: {
      type: Function,
      default: () => () => {},
    },
    keyword: {
      type: String,
      default: '',
    },
    isSearchNoData: Boolean,
    height: Number,
  },
  methods: {
    handleGetExpandNodeByDeep(deep = 1, treeData = []) {
      return treeData.reduce((pre, node) => {
        (deep => {
          if (deep > 1 && Array.isArray(node.children) && node.children.length > 0) {
            deep -= 1;

            pre = pre.concat(this.handleGetExpandNodeByDeep(deep, node.children));
          } else {
            pre = pre.concat(node.id);
          }
        })(deep);
        return pre;
      }, []);
    },
    resize() {
      this.$refs.tree?.resize();
    },
  },
};
