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

import { defineComponent, useTemplateRef, type PropType, computed } from 'vue';
import { shallowRef } from 'vue';

import { Tag } from 'bkui-vue';

import { ENABLED_TABLE_CONDITION_MENU_CLASS_NAME } from '../../constants';
import { useTagsEllipsis } from '../../hooks/use-tag-ellipsis';
import CollapseTags from './collapse-tags';

import type { ExploreTableColumn, ExploreTableColumnTypeEnum, GetTableCellRenderValue } from '../../typing';

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
      type: Object as PropType<GetTableCellRenderValue<ExploreTableColumnTypeEnum.TAGS>>,
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
      <CollapseTags
        class='explore-col explore-tags-col'
        v-slots={{
          customTag: (tag, index) => (
            <Tag
              key={index}
              style={{
                '--tag-color': tag.tagColor || DEFAULT_TAG_COLOR.tagColor,
                '--tag-bg-color': tag.tagBgColor || DEFAULT_TAG_COLOR.tagBgColor,
              }}
            >
              {{
                default: () => (
                  <span
                    class={`${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
                    data-col-id={this.colId}
                    data-index={index}
                    data-row-id={this.rowId}
                  >
                    {tag.alias}
                  </span>
                ),
              }}
            </Tag>
            // <div
            //   key={tag.alias}
            //   style={{
            //     '--tag-color': tag.tagColor || DEFAULT_TAG_COLOR.tagColor,
            //     '--tag-bg-color': tag.tagBgColor || DEFAULT_TAG_COLOR.tagBgColor,
            //   }}
            //   class='bk-tag tag-item'
            // >

            // </div>
          ),
        }}
        data={this.tags}
        ellipsisTip={ellipsisTags => ellipsisTags.map(tag => tag.alias).join('，')}
      />
    );
  },
});
