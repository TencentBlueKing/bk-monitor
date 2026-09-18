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

import { Alert, Loading } from 'bkui-vue';

import { SectionKeyEnum } from '../../constants';
import { renderSection } from '../../registry/section-registry';

import type { IRumDetailSectionVM } from '../../typings';

import './detail-sections.scss';

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
            <Loading loading={!!section.loading}>
              <div
                class={{
                  'section-body': true,
                  /** 资源详情与瀑布图外层有独立底色，其余区块直接贴白底 */
                  'is-boxed': section.key === SectionKeyEnum.RESOURCE_INFO,
                  /** view 类 span 的瀑布图自带边框外壳（span-type-view-rum-waterfall），外层不再加边框避免双层 */
                  'is-bordered': section.key === SectionKeyEnum.LOADING_TIMING && section.spanType !== 'view',
                }}
              >
                {renderSection(section)}
              </div>
            </Loading>
          </div>
        ))}
      </div>
    );
  },
});
