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
import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import { Alert } from 'bkui-vue';

import { SectionKeyEnum } from '../../constants';
import { renderSection } from '../../registry/section-registry';
import { RumSectionTypeEnum } from '../../typings';

import type { IRumDetailSectionVM } from '../../typings';

import './detail-sections.scss';

/** 卡片骨架的默认占位数量：关联数据未回时拿不到行结构，按一行 5 张兜底 */
const SKELETON_CARD_COUNT = 5;
/** 键值列表骨架的默认行数（版本关联区块实际为 3 行） */
const SKELETON_ROW_COUNT = 3;

/**
 * 区块骨架：按展示类型占位，尺寸取自对应真实组件的样式，
 * 保证关联数据返回、切换到真实内容时布局不跳动。
 */
function renderSectionSkeleton(section: IRumDetailSectionVM) {
  /** 键值列表区块：沿用真实行数占位，行高与 .rum-key-value-list 一致 */
  if (section.type === RumSectionTypeEnum.KEY_VALUE_LIST) {
    return (
      <div class='section-skeleton skeleton-key-value-list'>
        {Array.from({ length: section.keyValues?.length || SKELETON_ROW_COUNT }, (_, index) => (
          <div
            key={index}
            class='skeleton-row'
          >
            <div class='skeleton-element skeleton-row-label' />
            <div class='skeleton-element skeleton-row-value' />
          </div>
        ))}
      </div>
    );
  }
  /** 瀑布图区块：整块占位，高度与 .rum-waterfall 的时间轴 + 阶段行接近 */
  if (section.type === RumSectionTypeEnum.WATERFALL) {
    return (
      <div class='section-skeleton'>
        <div class='skeleton-element skeleton-block' />
      </div>
    );
  }
  /** 卡片区块沿用真实的行列结构占位 */
  const rowCounts = section.cardRows?.length ? section.cardRows.map(row => row.length) : [SKELETON_CARD_COUNT];
  return (
    <div class='section-skeleton'>
      {rowCounts.map((count, rowIndex) => (
        <div
          key={rowIndex}
          class='skeleton-card-row'
        >
          {Array.from({ length: count }, (_, index) => (
            <div
              key={index}
              class='skeleton-element skeleton-card'
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * 详情区块列表：负责区块外壳（标题、说明、提示条、加载态），
 * 区块内容交给 section-registry 按展示类型分发。
 */
export default defineComponent({
  name: 'RumDetailSections',
  props: {
    sections: {
      type: Array as PropType<IRumDetailSectionVM[]>,
      default: () => [],
    },
  },
  setup(props) {
    return () => (
      <div class='rum-detail-sections'>
        {props.sections.map(section => (
          <div
            key={section.key}
            class={`detail-section detail-section-${section.key}`}
          >
            {section.title ? (
              <div class='section-title-row'>
                <span class='section-title'>{section.title}</span>
                {section.subTitle ? <span class='section-divider' /> : null}
                {section.subTitle ? <span class='section-sub-title'>{section.subTitle}</span> : null}
              </div>
            ) : null}
            {section.tip ? (
              <Alert
                class='section-tip'
                theme='info'
                title={section.tip}
              />
            ) : null}
            <div
              class={{
                'section-body': true,
                /** 资源详情与瀑布图外层有独立底色，其余区块直接贴白底 */
                'is-boxed': section.key === SectionKeyEnum.RESOURCE_INFO,
                'is-bordered': section.key === SectionKeyEnum.LOADING_TIMING,
              }}
            >
              {section.loading ? renderSectionSkeleton(section) : renderSection(section)}
            </div>
          </div>
        ))}
      </div>
    );
  },
});
