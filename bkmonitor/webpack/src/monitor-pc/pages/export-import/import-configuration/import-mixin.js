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
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { debounce } from 'throttle-debounce';

export default {
  data() {
    return {
      // collapse 数据
      collapse: {
        list: [
          {
            name: 'collect',
            title: this.$t('采集配置'),
          },
          {
            name: 'strategy',
            title: this.$t('策略配置'),
          },
          {
            name: 'view',
            title: this.$t('视图配置'),
          },
          {
            name: 'bkmonitor.models.fta.plugin',
            title: this.$t('被关联插件'),
            markName: this.$t('被关联'),
          },
        ],
        activeName: [],
      },
      // 表格相关属性
      table: {
        list: [],
        statistics: {},
        firstCheckedAll: [],
        runingQueue: [],
        timer: null,
        interval: 300,
        selection: [],
        filterStatusName: this.$t('任务状态'),
        taskId: 0,
      },
      listenResize() {},
      // 当前可视区域是否出现滚动（用于按钮悬浮）
      isScroll: false,
      loading: false,
    };
  },
  computed: {},
  mounted() {
    this.listenResize = debounce(200, v => this.handleResize(v));
    addListener(this.$el, this.listenResize);
  },
  beforeDestroy() {
    removeListener(this.$el, this.listenResize);
  },
  methods: {
    /**
     * 默认展开第一个有数据的 Collapse item
     */
    handleExpandCollapse() {
      this.collapse.activeName = [];
      const data = this.collapse.list.find(item => {
        const { name } = item;
        return this.table.statistics[name]?.total;
      });
      if (data) {
        this.collapse.activeName.push(data.name);
      }
    },
    /**
     * 规整统计数据
     * @param {Object} data 统计数据
     */
    handleCountData(data) {
      if (!data) return {};
      return {
        collect: data.collectCount || {},
        plugin: data.pluginCount || {},
        strategy: data.strategyCount || {},
        view: data.viewCount || {},
        allCount: data.allCount || {},
      };
    },
    /**
     * 处理底部按钮组是否悬浮
     */
    handleResize() {
      if (!this.$el.parentElement) return;
      this.isScroll = this.$el.scrollHeight > this.$el.parentElement.clientHeight;
    },
  },
};
