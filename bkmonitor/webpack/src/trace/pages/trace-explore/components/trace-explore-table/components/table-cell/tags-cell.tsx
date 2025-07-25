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

import { type PropType, computed, defineComponent, useTemplateRef } from 'vue';
import { shallowRef } from 'vue';

import { ENABLED_TABLE_CONDITION_MENU_CLASS_NAME } from '../../constants';
import { useTagsEllipsis } from '../../hooks/use-tag-ellipsis';

import type { ExploreTableColumn, ExploreTableColumnTypeEnum, TableCellRenderValueType } from '../../typing';

import './tags-cell.scss';

const DEFAULT_TAG_COLOR = {
  tagColor: '#63656e',
  tagBgColor: 'rgba(151,155,165,.1)',
};
export default defineComponent({
  name: 'TagsCell',
  props: {
    column: {
      type: Object as PropType<ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>>,
    },
    tags: {
      type: Object as PropType<TableCellRenderValueType[ExploreTableColumnTypeEnum.TAGS]>,
    },
    colId: {
      type: String,
    },
    rowId: {
      type: String,
    },
  },
  setup(props) {
    const tagContainerRef = useTemplateRef<HTMLElement>('tagContainerRef');
    const tagsRef = shallowRef<Element[]>([]);
    const collapseTagRef = useTemplateRef<HTMLElement>('collapseTagRef');

    /** 需要渲染的 tag 总数 */
    const tagTotal = computed(() => props.tags?.length || 0);

    const { canShowIndex } = useTagsEllipsis({
      tagContainerRef,
      // @ts-ignore
      tagsRef,
      collapseTagRef: collapseTagRef,
      tagTotal: tagTotal.value,
      horizontalSpacing: 4,
    });

    /** 是否需要显示折叠 tag */
    const showCollapseTag = computed(() => !tagTotal.value || canShowIndex.value < tagTotal.value - 1);

    /** 折叠 tag 的tip提示内容 */
    const tipContent = computed(() => {
      if (!showCollapseTag.value) return;
      return props.tags
        .slice(canShowIndex.value + 1)
        .map(tag => tag.alias)
        .join('，');
    });

    return {
      tagsRef,
      collapseTagRef,
      canShowIndex,
      tagTotal,
      tipContent,
      showCollapseTag,
    };
  },
  render() {
    return (
      <div
        ref='tagContainerRef'
        class='explore-col explore-tags-col'
      >
        {this.tags?.map?.((tag, index) => (
          <div
            key={tag.alias}
            ref={el => {
              this.tagsRef[index] = el as Element;
            }}
            style={{
              '--tag-color': tag.tagColor || DEFAULT_TAG_COLOR.tagColor,
              '--tag-bg-color': tag.tagBgColor || DEFAULT_TAG_COLOR.tagBgColor,
              display: index > this.canShowIndex ? 'none' : '',
            }}
            class='tag-item'
          >
            <span
              class={`${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
              data-col-id={this.colId}
              data-index={index}
              data-row-id={this.rowId}
            >
              {tag.alias}
            </span>
          </div>
        ))}
        <div
          ref='collapseTagRef'
          style={{
            '--tag-color': DEFAULT_TAG_COLOR.tagColor,
            '--tag-bg-color': DEFAULT_TAG_COLOR.tagBgColor,
            visibility: this.showCollapseTag ? 'visible' : 'hidden',
          }}
          class='tag-item collapse-tag'
          v-bk-tooltips={{ content: this.tipContent, placement: 'top', disabled: !this.showCollapseTag }}
        >
          <span> +{this.tagTotal - this.canShowIndex - 1}</span>
        </div>
      </div>
    );
  },
});
