/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { defineComponent, ref } from 'vue';

import './view-legend.scss';

export default defineComponent({
  name: 'ViewLegend',

  setup() {
    const legendList = ref<{ id: string; label: string }[]>([
      { id: 'wangye', label: '网页' },
      { id: 'yuanchengfuwu', label: '远程调用' },
      { id: 'shujuku', label: '数据库' },
      { id: 'xiaoxizhongjianjian', label: '消息队列' },
      { id: 'renwu', label: '后台任务' },
      { id: 'zidingyi', label: '其他' },
      // { id: 'tongbu', label: '同步调用' },
      { id: 'yibu', label: '异步调用' },
      { id: 'neibutiaoyong', label: '内部调用' },
      { id: 'undefined', label: '未知' },
      { id: 'Network1', label: '网络请求' },
      { id: 'System1', label: '系统调用' },
    ]);

    return {
      legendList,
    };
  },
  render() {
    return (
      <div class='trace-view-legend'>
        {this.legendList.map(item => (
          <div class='length-item'>
            <i class={`icon-monitor icon-${item.id} legend-icon`} />
            <span class='legend-label'>{item.label}</span>
          </div>
        ))}
      </div>
    );
  },
});
