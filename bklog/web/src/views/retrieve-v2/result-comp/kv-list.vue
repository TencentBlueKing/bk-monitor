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
  <div class="kv-list-wrapper">
    <div class="kv-content">
      <!-- 骨架屏：计算完成前显示 -->
      <div
        v-if="isCalculating"
        class="skeleton-list-wrapper"
      >
        <div
          v-for="n in 10"
          :key="n"
          class="skeleton-list-item"
        >
          <div class="skeleton-field-label">
            <div class="skeleton skeleton-icon"></div>
            <div class="skeleton skeleton-text"></div>
          </div>
          <div class="skeleton-field-value">
            <div class="skeleton skeleton-value"></div>
          </div>
        </div>
      </div>
      <template v-if="!isCalculating && renderList.length > 0">
        <div
          v-for="field in renderList"
          :key="field.field_name"
          class="log-item"
        >
          <div class="field-label">
            <span
              v-if="hiddenFieldsSet.has(field)"
              class="field-eye-icon bklog-icon bklog-eye-slash"
              v-bk-tooltips="{ content: $t('隐藏') }"
              @click="
                e => {
                  e.stopPropagation();
                  handleShowOrHiddenItem(true, field);
                }
              "
            ></span>
            <span
              v-else
              class="field-eye-icon bklog-icon bklog-eye"
              v-bk-tooltips="{ content: $t('展示') }"
              @click="
                e => {
                  e.stopPropagation();
                  handleShowOrHiddenItem(false, field);
                }
              "
            ></span>
            <span
              :style="{
                backgroundColor: getFieldIconColor(field.field_type),
                color: getFieldIconTextColor(field.field_type),
              }"
              class="field-type-icon mr5"
              v-bk-tooltips="fieldTypePopover(field.field_name)"
              :class="getFieldIcon(field.field_name)"
            ></span>
            <span class="field-text">{{ getFieldName(field) }}</span>
          </div>
          <div class="field-value">
            <span
              v-if="getRelationMonitorField(field.field_name)"
              class="relation-monitor-btn"
              @click="handleViewMonitor(field.field_name)"
            >
              <span>{{ getRelationMonitorField(field.field_name) }}</span>
              <i class="bklog-icon bklog-jump"></i>
            </span>
            <JsonFormatter
              :fields="getFieldItem(field.field_name)"
              :json-value="listData"
              @menu-click="agrs => handleJsonSegmentClick(agrs, field.field_name)"
            ></JsonFormatter>
          </div>
        </div>
        <div
          v-if="hasMoreData"
          class="load-more-btn"
          @click="handleLoadMore"
        >
          <span class='bklog-icon bklog-more'></span>
          <span>{{ $t('点击加载更多') }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
  // import { getTextPxWidth, TABLE_FOUNT_FAMILY } from '@/common/util';
  import JsonFormatter from '@/global/json-formatter.vue';
  import { getFieldNameByField } from '@/hooks/use-field-name';
  import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
  import _escape from 'lodash/escape';
  import { mapGetters, mapState } from 'vuex';

  // import TextSegmentation from '../search-result-panel/log-result/text-segmentation';
  import { BK_LOG_STORAGE } from '@/store/store.type';

  export default {
    components: {
      // TextSegmentation,
      JsonFormatter,
    },
    mixins: [tableRowDeepViewMixin],
    inheritAttrs: false,
    props: {
      data: {
        type: Object,
        default: () => {},
      },
      fieldList: {
        type: Array,
        default: () => [],
      },
      visibleFields: {
        type: Array,
        required: true,
      },
      totalFields: {
        type: Array,
        required: true,
      },
      kvShowFieldsList: {
        type: Array,
        require: true,
      },
      sortList: {
        type: Array,
        require: true,
      },
      listData: {
        type: Object,
        default: () => {},
      },
      searchKeyword: {
        type: String,
        default: '',
      },
    },
    data() {
      return {
        toolMenuList: [
          { id: 'is', icon: 'bk-icon icon-enlarge-line search' },
          { id: 'not', icon: 'bk-icon icon-narrow-line search' },
          { id: 'display', icon: 'bk-icon icon-arrows-up-circle' },
          // { id: 'chart', icon: 'bklog-icon bklog-chart' },
          { id: 'copy', icon: 'bklog-icon bklog-copy' },
        ],
        toolMenuTips: {
          is: this.$t('添加 {n} 过滤项', { n: '=' }),
          not: this.$t('添加 {n} 过滤项', { n: '!=' }),
          hiddenField: this.$t('将字段从表格中移除'),
          displayField: this.$t('将字段添加至表格中'),
          copy: this.$t('复制'),
          text_is: this.$t('文本类型不支持 {n} 操作', { n: '=' }),
          text_not: this.$t('文本类型不支持 {n} 操作', { n: '!=' }),
        },
        mappingKay: {
          // is is not 值映射
          is: '=',
          'is not': '!=',
        },
        renderList: [],
        renderCount: 50, // 初始仅渲染首屏50个字段
        showFieldListCache: [], // 非响应式字段列表缓存，不参与Vue响应式依赖收集
        isCalculating: true, // 是否正在计算字段列表
        // 性能优化：缓存已计算的字段格式化值，避免重复计算
        formattedValueCache: new Map(),
        // 分批渲染配置
        batchSize: 25, // 每批次处理的字段数量（可调整测试）
        initialRenderCount: 50, // 初始渲染的字段总数
        processedCount: 0, // 已处理的字段数量
        batchProcessingTimer: null, // 批次处理定时器
        batchThreshold: 100, // 启用分批渲染的字段数量阈值（超过此值才分批处理）
        skeletonStartTime: null, // 骨架屏开始显示的时间
        skeletonMinDuration: 200, // 骨架屏最小显示时长（ms），避免闪烁
      };
    },
    computed: {
      ...mapState('globals', ['fieldTypeMap']),
      ...mapGetters({
        retrieveParams: 'retrieveParams',
      }),
      ...mapState({
        formatJson: state => state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT],
        showFieldAlias: state => state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS],
        isAllowEmptyField: state => state.storage[BK_LOG_STORAGE.TABLE_ALLOW_EMPTY_FIELD],
      }),
      apmRelation() {
        return this.$store.state.indexSetFieldConfig.apm_relation;
      },
      bkBizId() {
        return this.$store.state.bkBizId;
      },
      // 缓存映射：kvShowFieldsList 转为 Set
      kvShowFieldsSet() {
        return new Set(this.kvShowFieldsList);
      },
      // 缓存映射：field_name -> field item
      fieldItemMapByName() {
        const map = {};
        for (const item of this.fieldList) {
          map[item.field_name] = item;
        }
        return map;
      },
      fieldKeyMap() {
        return this.totalFields
          .filter(item => this.kvShowFieldsSet.has(item.field_name))
          .map(el => el.field_name);
      },

      hiddenFields() {
        return this.fieldList.filter(item => !this.visibleFields.some(visibleItem => item === visibleItem));
      },
      hiddenFieldsSet() {
        return new Set(this.hiddenFields);
      },
      filedSettingConfigID() {
        // 当前索引集的显示字段ID
        return this.$store.state.retrieve.filedSettingConfigID;
      },
      isHaveBkHostIDAndHaveValue() {
        // 当前是否有bk_host_id字段且有值
        return !!this.data?.bk_host_id;
      },
      hasMoreData() {
        return this.renderCount < this.showFieldListCache.length;
      },
    },
    watch: {
      isAllowEmptyField() {
        // 清空缓存，因为过滤条件改变了
        this.formattedValueCache.clear();
        this.resetRenderList();
      },
      searchKeyword() {
        this.resetRenderList();
      },
      // 禁止 deep watch，避免整行日志对象进入 Vue2 深度响应式系统
      // data: {
      //   handler() {
      //     this.formattedValueCache.clear();
      //   },
      //   deep: true,
      // },
    },
    mounted() {
      // 根据预估字段数量决定处理策略
      const estimatedFieldCount = this.kvShowFieldsList ? this.kvShowFieldsList.length : this.totalFields.length;
      
      if (estimatedFieldCount < this.batchThreshold) {
        // 字段数量 < 100，数据量小，直接同步处理，避免异步导致的闪烁
        this.isCalculating = false; // 不显示骨架屏
        // 直接同步执行计算和渲染
        this.showFieldListCache = this.calcShowFieldList();
        this.renderList = this.showFieldListCache.slice(0, this.initialRenderCount);
        } else {
          // 字段数量 >= 100，使用异步处理，避免阻塞主线程
          // 记录骨架屏开始显示的时间
          this.skeletonStartTime = Date.now();
          // 先渲染容器和骨架屏，然后异步执行计算
          // 使用 nextTick 确保 Vue 完成首次渲染
          this.$nextTick(() => {
          // 使用双重异步确保真正不阻塞主线程
          // 第一层：setTimeout 确保脱离当前执行栈
          setTimeout(() => {
            // 第二层：requestIdleCallback 在浏览器空闲时执行（如果支持）
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
              // 执行计算，获取完整的字段列表
              this.showFieldListCache = this.calcShowFieldList();
              // 开始分批处理初始渲染
              this.startBatchProcessing();
            });
          }, 0);
        });
      }
    },
    beforeDestroy() {
      // 清理批次处理定时器
      if (this.batchProcessingTimer) {
        if (typeof cancelIdleCallback !== 'undefined') {
          cancelIdleCallback(this.batchProcessingTimer);
        } else {
          clearTimeout(this.batchProcessingTimer);
        }
        this.batchProcessingTimer = null;
      }
    },
    methods: {
      calcShowFieldList() {
        // 原 showFieldList 逻辑完整迁移为 method
        const kvShowFieldsSet = this.kvShowFieldsSet;
        const emptyValues = ['--', '{}', '[]'];
        const totalFields = this.totalFields;
        
        // 步骤1：快速过滤出候选字段
        const candidateFields = [];
        for (let i = 0; i < totalFields.length; i++) {
          if (kvShowFieldsSet.has(totalFields[i].field_name)) {
            candidateFields.push(totalFields[i]);
          }
        }
        
        // 如果允许空字段，直接返回候选字段列表
        if (this.isAllowEmptyField) {
          let result = candidateFields;
          // 根据搜索关键字过滤（不区分大小写）
          if (this.searchKeyword) {
            const keyword = this.searchKeyword.toLowerCase();
            const filteredList = [];
            for (let i = 0; i < candidateFields.length; i++) {
              const item = candidateFields[i];
              if (item.field_name.toLowerCase().includes(keyword)) {
                filteredList.push(item);
              }
            }
            result = filteredList;
          }
          return result;
        }
        
        // 步骤2：检查空值（需要调用 formatterStr）
        const list = [];
        const rowData = this.listData;
        
        for (let i = 0; i < candidateFields.length; i++) {
          const item = candidateFields[i];
          const fieldName = item.field_name;
          
          // 性能优化：先快速检查字段是否为空，避免调用 formatterStr
          let shouldSkip = false;
          
          if (fieldName.indexOf('.') === -1 && fieldName.indexOf('[') === -1) {
            // 简单字段：直接检查原始值
            const rawValue = rowData[fieldName];
            
            // 快速检查：如果是明显的空值，直接跳过
            if (rawValue === null || rawValue === undefined || rawValue === '') {
              shouldSkip = true;
            } else if (typeof rawValue === 'object') {
              // 快速检查：如果是空对象或空数组，直接跳过
              if (Array.isArray(rawValue) && rawValue.length === 0) {
                shouldSkip = true;
              } else if (!Array.isArray(rawValue) && Object.keys(rawValue).length === 0) {
                shouldSkip = true;
              }
            }
          } else {
            // 复杂字段（嵌套字段）：尝试快速路径检查
            // 先尝试直接访问路径，如果访问不到或为空，再调用 formatterStr
            const firstDotIndex = fieldName.indexOf('.');
            if (firstDotIndex > 0) {
              const firstPart = fieldName.substring(0, firstDotIndex);
              const firstValue = rowData[firstPart];
              
              // 如果第一层就是空值，直接跳过
              if (firstValue === null || firstValue === undefined || firstValue === '') {
                shouldSkip = true;
              } else if (typeof firstValue === 'object') {
                // 如果第一层是空对象或空数组，直接跳过
                if (Array.isArray(firstValue) && firstValue.length === 0) {
                  shouldSkip = true;
                } else if (!Array.isArray(firstValue) && Object.keys(firstValue).length === 0) {
                  shouldSkip = true;
                } else {
                  // 尝试访问完整路径（如果路径不太深）
                  const pathParts = fieldName.split('.');
                  if (pathParts.length <= 3) {
                    // 对于不超过3层的路径，尝试快速访问
                    try {
                      let currentValue = firstValue;
                      for (let j = 1; j < pathParts.length; j++) {
                        if (currentValue === null || currentValue === undefined) {
                          shouldSkip = true;
                          break;
                        }
                        if (typeof currentValue === 'object' && !Array.isArray(currentValue)) {
                          currentValue = currentValue[pathParts[j]];
                        } else {
                          // 无法继续访问，需要调用 formatterStr
                          break;
                        }
                      }
                      // 如果成功访问到最终值，检查是否为空
                      if (shouldSkip === false && currentValue !== undefined) {
                        if (currentValue === null || currentValue === '' || 
                            (typeof currentValue === 'object' && 
                             ((Array.isArray(currentValue) && currentValue.length === 0) ||
                              (!Array.isArray(currentValue) && Object.keys(currentValue).length === 0)))) {
                          shouldSkip = true;
                        }
                      }
                    } catch (e) {
                      // 访问失败，需要调用 formatterStr
                    }
                  }
                }
              }
            }
          }
          
          if (shouldSkip) {
            continue;
          }
          
          // 使用缓存，避免重复计算
          let formattedValue;
          if (this.formattedValueCache.has(fieldName)) {
            formattedValue = this.formattedValueCache.get(fieldName);
          } else {
            // 性能优化：对于复杂字段，先尝试轻量级空值检查
            // 如果确定是空值，直接跳过，不调用完整的 formatterStr
            let isDefinitelyEmpty = false;
            if (fieldName.indexOf('.') !== -1 || fieldName.indexOf('[') !== -1) {
              // 复杂字段：尝试快速空值检查
              try {
                const pathParts = fieldName.split('.');
                let currentValue = rowData;
                let canAccess = true;
                
                for (let j = 0; j < pathParts.length && canAccess; j++) {
                  const part = pathParts[j];
                  if (currentValue === null || currentValue === undefined) {
                    isDefinitelyEmpty = true;
                    canAccess = false;
                    break;
                  }
                  if (typeof currentValue === 'object' && !Array.isArray(currentValue)) {
                    if (!(part in currentValue)) {
                      // 字段不存在，尝试使用完整路径作为key
                      const remainingPath = pathParts.slice(j).join('.');
                      if (remainingPath in currentValue) {
                        currentValue = currentValue[remainingPath];
                        break;
                      } else {
                        isDefinitelyEmpty = true;
                        canAccess = false;
                        break;
                      }
                    }
                    currentValue = currentValue[part];
                  } else if (Array.isArray(currentValue)) {
                    // 数组处理：跳过，需要完整解析
                    canAccess = false;
                    break;
                  } else {
                    // 无法继续访问
                    isDefinitelyEmpty = true;
                    canAccess = false;
                    break;
                  }
                }
                
                // 如果成功访问到最终值，检查是否为空
                if (canAccess && currentValue !== undefined) {
                  if (currentValue === null || currentValue === '' || 
                      (typeof currentValue === 'object' && 
                       ((Array.isArray(currentValue) && currentValue.length === 0) ||
                        (!Array.isArray(currentValue) && Object.keys(currentValue).length === 0)))) {
                    isDefinitelyEmpty = true;
                  }
                }
              } catch (e) {
                // 检查失败，需要调用 formatterStr
              }
            }
            
            if (isDefinitelyEmpty) {
              formattedValue = '--';
              this.formattedValueCache.set(fieldName, formattedValue);
              continue; // 直接跳过，不加入列表
            }
            
            formattedValue = this.formatterStr(this.data, fieldName);
            this.formattedValueCache.set(fieldName, formattedValue);
          }
          
          if (!emptyValues.includes(formattedValue)) {
            list.push(item);
          }
        }

        // 步骤3：根据搜索关键字过滤
        let result = list;
        if (this.searchKeyword) {
          const keyword = this.searchKeyword.toLowerCase();
          const filteredList = [];
          for (let i = 0; i < list.length; i++) {
            const item = list[i];
            if (item.field_name.toLowerCase().includes(keyword)) {
              filteredList.push(item);
            }
          }
          result = filteredList;
        }

        return result;
      },
      resetRenderList() {
        // 清理之前的批次处理
        if (this.batchProcessingTimer) {
          clearTimeout(this.batchProcessingTimer);
          this.batchProcessingTimer = null;
        }
        
        // 根据预估字段数量决定处理策略
        const estimatedFieldCount = this.kvShowFieldsList ? this.kvShowFieldsList.length : this.totalFields.length;
        
        this.renderCount = this.initialRenderCount; // 重置为首屏数量
        this.processedCount = 0; // 重置已处理数量
        
        if (estimatedFieldCount < this.batchThreshold) {
          // 字段数量 < 100，数据量小，直接同步处理，避免异步导致的闪烁
          this.isCalculating = false; // 不显示骨架屏
          // 直接同步执行计算和渲染
          this.showFieldListCache = this.calcShowFieldList();
          this.renderList = this.showFieldListCache.slice(0, this.initialRenderCount);
        } else {
          // 字段数量 >= 100，使用异步处理，避免阻塞主线程
          this.isCalculating = true; // 开始计算，显示骨架屏
          // 记录骨架屏开始显示的时间
          this.skeletonStartTime = Date.now();
          // 异步重新计算字段列表，使用 setTimeout 确保真正异步
          setTimeout(() => {
            const scheduleCalculation = (callback) => {
              if (typeof requestIdleCallback !== 'undefined') {
                requestIdleCallback(callback, { timeout: 50 });
              } else {
                setTimeout(callback, 0);
              }
            };

            scheduleCalculation(() => {
              this.showFieldListCache = this.calcShowFieldList();
              // 开始分批处理初始渲染
              this.startBatchProcessing();
            });
          }, 0);
        }
      },
      // 开始分批处理初始渲染
      startBatchProcessing() {
        const totalFields = this.showFieldListCache.length;
        
        // 如果字段数量 <= 阈值，直接渲染，不需要分批处理
        if (totalFields <= this.batchThreshold) {
          this.renderList = this.showFieldListCache.slice(0, this.initialRenderCount);
          this.$nextTick(() => {
            // 确保骨架屏至少显示200ms，避免闪烁
            this.hideSkeletonSmoothly();
          });
          return;
        }
        
        // 字段数量 > 阈值，执行分批渲染逻辑
        this.processedCount = 0;
        // 处理第一批次，立即显示并停止骨架屏
        this.processBatch(true);
      },
      // 处理一批数据
      processBatch(isFirstBatch = false) {
        const targetCount = Math.min(this.initialRenderCount, this.showFieldListCache.length);
        const endIndex = Math.min(this.processedCount + this.batchSize, targetCount);
        
        // 更新已处理的数量
        this.processedCount = endIndex;
        
        // 更新渲染列表
        this.renderList = this.showFieldListCache.slice(0, endIndex);
        
        // 如果是第一批次，立即显示并停止骨架屏
        if (isFirstBatch) {
          this.$nextTick(() => {
            // 确保骨架屏至少显示200ms，避免闪烁
            this.hideSkeletonSmoothly(() => {
              // 如果还有剩余数据，继续异步处理
              if (this.processedCount < targetCount) {
                this.continueBatchProcessing();
              }
            });
          });
        } else {
          // 继续处理下一批次
          if (this.processedCount < targetCount) {
            this.continueBatchProcessing();
          }
        }
      },
      // 继续异步处理剩余批次
      continueBatchProcessing() {
        // 使用 requestIdleCallback 或 setTimeout 在空闲时处理下一批次
        if (typeof requestIdleCallback !== 'undefined') {
          this.batchProcessingTimer = requestIdleCallback(() => {
            this.processBatch(false);
          }, { timeout: 50 });
        } else {
          this.batchProcessingTimer = setTimeout(() => {
            this.processBatch(false);
          }, 0);
        }
      },
      // 平滑隐藏骨架屏，确保至少显示200ms
      hideSkeletonSmoothly(callback) {
        if (!this.skeletonStartTime) {
          // 如果没有记录开始时间，说明骨架屏没有显示，直接执行回调
          if (callback) callback();
          return;
        }
        
        const elapsed = Date.now() - this.skeletonStartTime;
        const remaining = Math.max(0, this.skeletonMinDuration - elapsed);
        
        if (remaining > 0) {
          // 如果显示时间不足200ms，延迟隐藏
          setTimeout(() => {
            this.isCalculating = false;
            this.skeletonStartTime = null; // 重置开始时间
            if (callback) callback();
          }, remaining);
        } else {
          // 已经显示足够时间，立即隐藏
          this.isCalculating = false;
          this.skeletonStartTime = null; // 重置开始时间
          if (callback) callback();
        }
      },
      handleLoadMore() {
        if (!this.hasMoreData) return;
        this.renderCount += 50; // 每次加载50个
        this.renderList = this.showFieldListCache.slice(0, this.renderCount);
      },
      isJsonFormat(content) {
        return this.formatJson && /^\[|\{/.test(content);
      },
      formatterStr(row, field) {
        let result;
        
        // 性能优化：对于简单字段（无嵌套），直接访问，避免调用 parseTableRowData
        // 这样可以显著提升性能，特别是当字段数量很大时
        if (field.indexOf('.') === -1 && field.indexOf('[') === -1) {
          // 简单字段：直接访问
          const rowData = this.listData;
          const value = rowData[field];
          
          // 快速检查空值（与 parseTableRowData 的逻辑保持一致）
          if (value === null || value === undefined || value === '') {
            result = '--';
          } else if (typeof value === 'object') {
            // 检查是否为对象或数组
            if (Array.isArray(value)) {
              result = value.length === 0 ? '[]' : value; // 空数组返回 '[]'，非空返回实际值
            } else {
              // 对象：空对象返回 '{}'，非空需要序列化
              const keys = Object.keys(value);
              if (keys.length === 0) {
                result = '{}';
              } else {
                // 非空对象，返回序列化后的字符串（但这里只是为了检查，所以返回非空标记）
                // 注意：这里返回的不是 '--'，所以不会被过滤掉
                result = JSON.stringify(value);
              }
            }
          } else {
            // 其他类型直接返回
            result = value;
          }
        } else {
          // 复杂字段（嵌套字段）：使用 tableRowDeepView
          const fieldType = this.getFieldType(field);
          const rowData = this.listData;
          result = this.tableRowDeepView(rowData, field, fieldType) ?? '--';
        }
        
        return result;
      },
      getFieldType(fieldName) {
        return this.fieldItemMapByName[fieldName]?.field_type || '';
      },
      getFieldIcon(fieldName) {
        const fieldType = this.getFieldType(fieldName);
        return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'bklog-icon bklog-unkown';
      },
      fieldTypePopover(fieldName) {
        const fieldType = this.getFieldType(fieldName);
        return {
          content: this.fieldTypeMap[fieldType]?.name,
          disabled: !this.fieldTypeMap[fieldType],
        };
      },
      getFieldIconColor(type) {
        return this.fieldTypeMap?.[type] ? this.fieldTypeMap?.[type]?.color : '#EAEBF0';
      },
      getFieldIconTextColor(type) {
        return this.fieldTypeMap?.[type]?.textColor;
      },
      checkDisable(id, field) {
        const type = this.getFieldType(field);
        const isExist = this.filterIsExist(id, field);
        return (['is', 'not'].includes(id) && type === 'text') || type === '__virtual__' || isExist
          ? 'is-disabled'
          : '';
      },
      handleJsonSegmentClick({ isLink, option }, fieldName) {
        // 为了兼容旧的逻辑，先这么写吧
        // 找时间梳理下这块，写的太随意了
        const { operation, value, depth, isNestedField } = option;
        const operator = operation === 'not' ? 'is not' : operation;
        const field = this.totalFields.find(f => f.field_name === fieldName);
        this.$emit('value-click', operator, value, isLink, field, depth, isNestedField);
      },

      /**
       * @desc 关联跳转
       * @param { string } field
       */
      handleViewMonitor(field) {
        const key = field.toLowerCase();
        const trace_id = String(this.data[field])
          .replace(/<mark>/g, '')
          .replace(/<\/mark>/g, '');
        let path = '';
        switch (key) {
          // trace检索
          case 'trace_id':
          case 'traceid':
            if (this.apmRelation.is_active) {
              const { app_name: appName, bk_biz_id: bkBizId } = this.apmRelation.extra;
              path = `/?bizId=${bkBizId}#/trace/home?app_name=${appName}&search_type=accurate&trace_id=${trace_id}`;
            } else {
              this.$bkMessage({
                theme: 'warning',
                message: this.$t('未找到相关的应用，请确认是否有Trace数据的接入。'),
              });
            }
            break;
          // 主机监控
          case 'serverip':
          case 'ip':
          case 'bk_host_id':
            {
              const endStr = `${trace_id}${field === 'bk_host_id' && this.isHaveBkHostIDAndHaveValue ? '' : '-0'}`;
              path = `/?bizId=${this.bkBizId}#/performance/detail/${endStr}`;
            }
            break;
          // 容器
          case 'container_id':
          case '__ext.container_id':
            path = `/?bizId=${this.bkBizId}#/k8s?dashboardId=pod`;
            break;
          default:
            break;
        }

        if (path) {
          const url = `${window.__IS_MONITOR_COMPONENT__ ? location.origin : window.MONITOR_URL}${path}`;
          window.open(url, '_blank');
        }
      },
      /**
       * @desc 判断是否有关联监控跳转
       * @param { string } field
       */
      getRelationMonitorField(field) {
        // 外部版不提供外链跳转
        if (this.$store.state.isExternal) return false;

        const key = field.toLowerCase();
        switch (key) {
          // trace检索
          case 'trace_id':
          case 'traceid':
            return this.$t('trace检索');
          // 主机监控
          case 'serverip':
          case 'ip':
          case 'bk_host_id': {
            const lowerKeyData = Object.entries(this.data).reduce((pre, [curKey, curVal]) => {
              pre[curKey.toLowerCase()] = curVal;
              return pre;
            }, {});
            return !!lowerKeyData[key] ? this.$t('主机') : null; // 判断ip和serverIp是否有值 无值则不显示主机
          }
          // 容器
          case 'container_id':
          case '__ext.container_id':
            return this.$t('容器');
          default:
            return;
        }
      },
      filterIsExist(id, field) {
        if (this.retrieveParams?.addition.length) {
          if (id === 'not') id = 'is not';
          const curValue = this.tableRowDeepView(this.data, field, this.getFieldType(field), false);
          return this.retrieveParams.addition.some(addition => {
            return (
              addition.field === field &&
              addition.operator === (this.mappingKay[id] ?? id) && // is is not 值映射 判断是否
              addition.value.toString() === curValue.toString()
            );
          });
        }
        return false;
      },
      getFieldItem(fieldName) {
        return this.fieldItemMapByName[fieldName];
      },
      getFieldName(field) {
        return getFieldNameByField(field, this.$store);
      },
      // 显示或隐藏字段
      handleShowOrHiddenItem(visible, field) {
        const displayFields = [];
        this.visibleFields.forEach(child => {
          if (field.field_name !== child.field_name) {
            displayFields.push(child.field_name);
          }
        });

        if (visible) {
          displayFields.push(field.field_name);
        }
        this.$store.dispatch('userFieldConfigChange', { displayFields }).then(() => {
          this.$store.commit('resetVisibleFields', displayFields);
          this.$store.commit('updateIsSetDefaultTableColumn');
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
  /* stylelint-disable no-descending-specificity */
  .kv-list-wrapper {
    max-height: 50vh;
    overflow-y: auto;
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);

    .log-item:nth-child(even) {
      background-color: #f5f7fa;
    }

    .log-item:nth-child(odd) {
      background-color: #ffffff;
    }

    .log-item {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 24px;
      padding-left: 8px;

      .field-value {
        display: flex;
        align-items: flex-start;
        color: #16171a;
        word-break: break-all;
        :deep(.valid-text) {
          &:hover {
            text-decoration: underline; /* 悬停时添加下划线 */
            text-decoration-color: #498eff; /* 设置下划线颜色为蓝色 */
          }
        }
      }

      .field-label {
        display: flex;
        flex-shrink: 0;
        flex-wrap: nowrap;
        align-items: stretch;
        height: 100%;
        margin: 5px 0;
        margin-right: 18px;
        align-self: flex-start;
        width: 300px;

        .field-eye-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 12px;
          margin-right: 8px;
          font-size: 12px;
          color: #4d4f56;
          border-radius: 2px;

          &:hover {
            color: #3a84ff;
          }
        }

        .field-type-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 16px;
          min-width: 16px;
          margin: 0 5px 0 0;
          font-size: 14px;
          color: #63656e;
          background: #dcdee5;
          border-radius: 2px;
        }

        .field-text {
          display: block;
          width: auto;
          overflow: hidden;
          font-family: Roboto-Regular;
          color: #313238;
          word-break: normal;
          word-wrap: break-word;
        }

        :deep(.bklog-ext) {
          min-width: 22px;
          height: 22px;
          transform: translateX(-3px) scale(0.7);
        }
      }
    }

    .relation-monitor-btn {
      display: flex;
      column-gap: 2px;
      align-items: center;
      min-width: fit-content;
      padding-top: 1px;
      padding-right: 6px;
      // margin-left: 12px;
      font-size: 12px;
      line-height: 22px;
      color: #3a84ff;
      cursor: pointer;

      .bklog-jump {
        font-size: 14px;
      }
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

    // 骨架屏列表样式 - 模拟实际的 log-item 结构
    .skeleton-list-wrapper {
      padding: 2px 15px 14px 15px;

      .skeleton-list-item {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 24px;
        padding-left: 8px;
        margin: 0;

        // 模拟实际列表的交替背景色
        &:nth-child(even) {
          background-color: #f5f7fa;
        }

        &:nth-child(odd) {
          background-color: #ffffff;
        }

        .skeleton-field-label {
          display: flex;
          flex-shrink: 0;
          flex-wrap: nowrap;
          align-items: center;
          height: 100%;
          margin: 5px 0;
          margin-right: 18px;
          align-self: flex-start;
          width: 300px;

          // 模拟眼睛图标
          .skeleton-icon {
            width: 12px;
            min-width: 12px;
            height: 12px;
            margin-right: 8px;
            border-radius: 2px;
          }

          // 模拟字段类型图标
          &::before {
            content: '';
            display: inline-block;
            width: 16px;
            min-width: 16px;
            height: 16px;
            margin-right: 5px;
            border-radius: 2px;
            background: linear-gradient(90deg, #f0f2f5 25%, #e6e9ed 50%, #f0f2f5 70%);
            background-size: 400% 100%;
            animation: shimmer 1.8s infinite linear;
          }

          // 模拟字段名称文本
          .skeleton-text {
            flex: 1;
            height: 14px;
            min-width: 80px;
            max-width: 200px;
            border-radius: 2px;
          }
        }

        .skeleton-field-value {
          display: flex;
          align-items: flex-start;
          flex: 1;
          min-width: 0;
          color: #16171a;
          word-break: break-all;

          // 模拟字段值
          .skeleton-value {
            height: 14px;
            width: 100%;
            min-width: 100px;
            max-width: 500px;
            border-radius: 2px;
          }
        }

        .skeleton {
          background: linear-gradient(90deg, #f0f2f5 25%, #e6e9ed 50%, #f0f2f5 70%);
          background-size: 400% 100%;
          animation: shimmer 1.8s infinite linear;
        }
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
  }
</style>
