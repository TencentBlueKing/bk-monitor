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

import {defineComponent} from 'vue';
import {Tree, Input} from 'tdesign-vue-next';

/** Options-render + JSX slots reproduces the business field-tree boundary. */
export default defineComponent({
  data: () => ({expanded:['parent'], needle:''}),
  render() {
    return <section data-testid='native-tree-contract'>
      <Input placeholder='Filter test field tree' value={this.needle} onChange={value => {this.needle=String(value);}} />
      <Tree
        data={[{value:'parent',label:'parent',children:[{value:'leaf',label:'leaf'}]}]}
        expanded={this.expanded}
        expandOnClickNode
        transition={false}
        filter={this.needle ? node => String(node.value).includes(this.needle) : undefined}
        onExpand={values => {this.expanded=values.map(String);}}
        v-slots={{label:(scope: {node?: {value:unknown}} = {}) => scope.node ? <span>{'Tree node ' + String(scope.node.value)}</span> : []}}
      />
    </section>;
  },
});
