/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
 * WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
import { defineComponent } from 'vue';

import './detail-skeleton.scss';

/** 原始数据面板固定 5 个折叠块（Span / Attributes / Resource / Links / Events） */
const ORIGIN_BLOCK_COUNT = 5;
/** 标题区公共信息占位行数，与真实 header-item 每行 5 个对齐 */
const INFO_ITEM_COUNT = 5;

/**
 * Span 详情加载骨架屏。
 * 层级与真实内容一一对应（标题区 / Tab 栏 / 卡片区内的详情区块与原始数据折叠块），
 * 尺寸取自各真实组件样式，保证加载完成切换时布局不跳动。
 */
export default defineComponent({
  name: 'RumDetailSkeleton',
  setup() {
    return () => (
      <div class='rum-detail-skeleton'>
        {/* 标题区：logo + 标题行 + 公共信息，对应 DetailHeader */}
        <div class='skeleton-header'>
          <div class='skeleton-element skeleton-logo' />
          <div class='skeleton-header-main'>
            <div class='skeleton-title-row'>
              <div class='skeleton-element skeleton-title' />
              <div class='skeleton-element skeleton-badge' />
              <div class='skeleton-element skeleton-badge' />
            </div>
            <div class='skeleton-info-items'>
              {Array.from({ length: INFO_ITEM_COUNT }, (_, index) => (
                <div
                  key={index}
                  class='skeleton-element skeleton-info-item'
                />
              ))}
            </div>
          </div>
        </div>
        {/* Tab 栏：基础信息 / 链路上下文 */}
        <div class='skeleton-tabs'>
          <div class='skeleton-element skeleton-tab' />
          <div class='skeleton-element skeleton-tab' />
        </div>
        {/* 卡片区：详情区块 + 原始数据折叠块 */}
        <div class='skeleton-card'>
          <div class='skeleton-sections'>
            {/* 卡片区块：标题 + 卡片*/}
            <div class='skeleton-section'>
              <div class='skeleton-element skeleton-section-title' />
              <div class='skeleton-section-body'>
                {Array.from({ length: 5 }, (_, index) => (
                  <div
                    key={index}
                    class='skeleton-element skeleton-section-card'
                  />
                ))}
              </div>
            </div>
            {/* 图表类区块：标题 + 整块占位 */}
            <div class='skeleton-section'>
              <div class='skeleton-element skeleton-section-title' />
              <div class='skeleton-element skeleton-section-block' />
            </div>
          </div>
          <div class='skeleton-origin-panel'>
            {Array.from({ length: ORIGIN_BLOCK_COUNT }, (_, index) => (
              <div
                key={index}
                class='skeleton-origin-block'
              >
                <div class='skeleton-element skeleton-origin-arrow' />
                <div class='skeleton-element skeleton-origin-title' />
                <div class='skeleton-element skeleton-origin-summary' />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  },
});
