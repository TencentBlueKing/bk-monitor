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
  <ShadowWrapper :shadow-content="false">
    <!-- 骨架屏：渲染完成前显示 -->
    <div
      v-if="isRendering"
      class="json-skeleton-wrapper"
    >
      <div
        v-for="n in 8"
        :key="n"
        class="json-skeleton-item"
      >
        <div class="skeleton skeleton-key"></div>
        <div class="skeleton skeleton-value"></div>
      </div>
    </div>
    <!-- JSON 内容：分页渲染 -->
    <div
      v-else
      ref="jsonContainer"
      class="json-pagination-wrapper"
    >
      <!-- 渲染当前页的数据 -->
      <VueJsonPretty
        :key="`json-page-${currentPage}`"
        :data="paginatedData"
        :deep="deep"
      >
        <template #nodeValue="{ defaultValue }">
          <span v-text="defaultValue" />
        </template>
      </VueJsonPretty>
      <!-- 加载更多按钮 -->
      <div
        v-if="hasMoreData"
        class="load-more-btn"
        @click="loadMore"
      >
        <span
          v-if="isLoadingMore"
          class="bklog-icon bklog-log-loading"
        />
        <span
          v-else
          class="bklog-icon bklog-more"
        />
        <span>{{ isLoadingMore ? $t('加载中...') : $t('点击加载更多') }}</span>
      </div>
      <!-- 全部加载完成提示 -->
      <div
        v-else-if="totalKeys > pageSize"
        class="json-load-complete"
      >
        <span>{{ $t('已加载全部数据 ({total} 个字段)', { total: totalKeys }) }}</span>
      </div>
    </div>
  </ShadowWrapper>
</template>
<script>
import VueJsonPretty from 'vue-json-pretty';

import ShadowWrapper from './shadow-wrapper.vue';

import 'vue-json-pretty/lib/styles.css';

export default {
  name: 'JsonFormatWrapper',
  components: {
    VueJsonPretty,
    ShadowWrapper,
  },
  props: {
    data: {
      type: Object,
      default: () => {},
    },
    deep: {
      type: Number,
      default: 5,
    },
  },
  data() {
    return {
      isRendering: true, // 是否正在渲染
      jsonShowDataCache: null, // 缓存的 JSON 数据
      currentPage: 1, // 当前页码（初始为 1，显示 50 个字段）
      pageSize: 50, // 每页显示的字段数量
      isLoadingMore: false, // 是否正在加载更多
      allKeys: [], // 所有顶层字段的 key 列表
    };
  },
  computed: {
    jsonShowData() {
      // 如果已有缓存，直接返回缓存
      if (this.jsonShowDataCache !== null) {
        return this.jsonShowDataCache;
      }
      // 使用 Object.freeze 创建非响应式数据副本，避免 vue-json-pretty 内部响应式追踪
      const frozenData = Object.freeze(JSON.parse(JSON.stringify(this.data)));
      this.jsonShowDataCache = frozenData;
      return frozenData;
    },
    // 分页后的数据（只对顶层字段分页，保持嵌套结构完整）
    paginatedData() {
      if (!this.jsonShowDataCache) {
        return {};
      }

      // 如果还没有提取 keys 或 keys 为空，返回完整数据（首次渲染）
      if (this.allKeys.length === 0) {
        return this.jsonShowDataCache;
      }
      
      // 计算当前页应该显示的字段范围
      const endIndex = Math.min(this.currentPage * this.pageSize, this.allKeys.length);
      const currentKeys = this.allKeys.slice(0, endIndex);
      const result = {};
      
      // 根据当前页的顶层 keys 构建数据对象（保持嵌套结构）
      for (let i = 0; i < currentKeys.length; i++) {
        const key = currentKeys[i];
        const value = this.jsonShowDataCache[key];
        if (value !== undefined) {
          result[key] = value;
        }
      }
      
      // 返回新的对象，确保 Vue 能检测到变化
      // 注意：不使用 Object.freeze，让 Vue 能正常追踪变化
      return result;
    },
    // 总字段数
    totalKeys() {
      return this.allKeys.length;
    },
    // 是否还有更多数据
    hasMoreData() {
      return this.currentPage * this.pageSize < this.totalKeys;
    },
    // 当前已加载的字段数量
    currentKeysCount() {
      return Math.min(this.currentPage * this.pageSize, this.totalKeys);
    },
    isShadowContent() {
      return false;
    },
  },
  watch: {
    // 监听 data 变化，清空缓存
    data: {
      handler() {
        this.jsonShowDataCache = null;
        this.allKeys = [];
        this.currentPage = 1;
        this.isRendering = true;
        this.scheduleRender();
      },
      deep: false, // 禁止深度监听，避免性能问题
    },
  },
  mounted() {
    // 延迟渲染，避免阻塞首帧
    this.scheduleRender();
  },
  methods: {
    scheduleRender() {
      // 使用 nextTick 确保 Vue 完成首次渲染
      this.$nextTick(() => {
        // 使用双重异步确保真正不阻塞主线程
        setTimeout(() => {
          const scheduleCalculation = (callback) => {
            if (typeof requestIdleCallback !== 'undefined') {
              // 优先使用 requestIdleCallback，在浏览器空闲时执行
              requestIdleCallback(callback, { timeout: 50 });
            } else {
              // 降级使用 setTimeout，确保真正异步
              setTimeout(callback, 0);
            }
          };

          scheduleCalculation(() => {
            // 触发 computed 计算，生成缓存
            // eslint-disable-next-line no-unused-expressions
            this.jsonShowData;
            // 提取所有 keys（异步执行，避免阻塞）
            this.allKeys = this.extractKeys(this.jsonShowDataCache);
            // 重置分页状态
            this.currentPage = 1;
            // 使用 nextTick 确保 DOM 更新完成后再隐藏骨架屏
            this.$nextTick(() => {
              this.isRendering = false;
            });
          });
        }, 0);
      });
    },
    // 提取顶层字段的 key（只提取第一层，不递归嵌套）
    extractKeys(obj) {
      if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
        return [];
      }

      // 只提取顶层 key，不递归嵌套（保持 JSON 结构完整）
      return Object.keys(obj);
    },
    // 加载更多数据（每次增加 50 个字段）
    loadMore() {
      if (this.isLoadingMore || !this.hasMoreData) {
        return;
      }

      // 保存当前滚动位置，避免加载后自动滚动到底
      const container = this.$refs.jsonContainer;
      const scrollTop = container ? container.scrollTop : 0;

      this.isLoadingMore = true;

      // 使用 requestIdleCallback 或 setTimeout 延迟加载，避免阻塞
      const scheduleLoad = (callback) => {
        if (typeof requestIdleCallback !== 'undefined') {
          requestIdleCallback(callback, { timeout: 50 });
        } else {
          setTimeout(callback, 0);
        }
      };

      scheduleLoad(() => {
        // 每次点击增加一页（50 个字段）
        this.currentPage += 1;
        
        this.$nextTick(() => {
          this.isLoadingMore = false;
          // 恢复滚动位置，确保不会自动滚动到底
          if (container) {
            container.scrollTop = scrollTop;
          }
        });
      });
    },
  },
};
</script>
<style lang="scss" scoped>
  .json-skeleton-wrapper {
    padding: 10px 0;

    .json-skeleton-item {
      display: flex;
      align-items: center;
      margin-bottom: 8px;
      padding-left: 20px;

      .skeleton-key {
        width: 120px;
        height: 14px;
        margin-right: 12px;
        border-radius: 2px;
      }

      .skeleton-value {
        flex: 1;
        height: 14px;
        min-width: 100px;
        max-width: 400px;
        border-radius: 2px;
      }

      .skeleton {
        background: linear-gradient(90deg, #f0f2f5 25%, #e6e9ed 50%, #f0f2f5 70%);
        background-size: 400% 100%;
        animation: shimmer 1.8s infinite linear;
      }
    }
  }

  .json-pagination-wrapper {
    max-height: 50vh;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 10px 0;
    position: relative;

    // JSON 样式
    :deep(.vjs-tree) {
      font-size: var(--table-fount-size, 12px);
    }

    .load-more-btn {
      display: flex;
      align-items: center;
      color: #3a84ff;
      margin-top: 8px;
      margin-left: 4px;
      cursor: pointer;
      font-size: 12px;

      span {
        font-size: 12px;
      }

      .bklog-more,
      .bklog-log-loading {
        margin-right: 4px;
        font-size: 12px;
        color: #3a84ff;
      }

      .bklog-more {
        font-size: 18px;
        transform: rotate(90deg);
      }
    }

    .json-load-complete {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 16px 0;
      color: #979ba5;
      font-size: 12px;
    }
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  @keyframes rotate {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }
</style>
