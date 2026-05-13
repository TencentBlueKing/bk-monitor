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

import { computed, defineComponent, nextTick, ref, watch } from 'vue';

import { deepClone, contextHighlightColor } from '@/common/util';
import useLocale from '@/hooks/use-locale';

import HighlightControl from '@/views/retrieve-v3/search-result/original-log/components/data-filter/highlight-control';

import './index.scss';

/** 高亮颜色项 */
interface ColorHighlightItem {
  heightKey: string;
  colorIndex: number;
  color: {
    dark: string;
    light: string;
  };
}

export default defineComponent({
  name: 'ClientLogToolbar',
  components: {
    HighlightControl,
  },
  props: {
    /** 左侧文件树是否收起 */
    isFileTreeCollapsed: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['handle-filter', 'toggle-file-tree'],
  setup(_, { emit, expose }) {
    const { t } = useLocale();

    const highlightControlRef = ref<any>(null);
    const tagInputRef = ref<any>(null);
    const filterType = ref('include');
    const filterKey = ref<string[]>([]);
    const catchFilterKey = ref<string[]>([]);
    const highlightList = ref<string[]>([]);
    const colorHighlightList = ref<ColorHighlightItem[]>([]);

    const filterTypeList = [
      { id: 'include', name: t('包含') },
      { id: 'uninclude', name: t('不包含') },
    ];

    const catchColorIndexList = computed(() => colorHighlightList.value.map(item => item.colorIndex));

    /** 执行过滤 */
    const filterLog = () => {
      catchFilterKey.value = [...filterKey.value];
      emit('handle-filter', 'filterKey', filterKey.value);
    };

    /** 粘贴过滤条件 */
    const filterPasteFn = (pasteValue: string) => {
      const trimPasteValue = pasteValue.trim();
      if (!filterKey.value.includes(trimPasteValue)) {
        filterKey.value.push(trimPasteValue);
        filterLog();
      }
      return [];
    };

    /** 更新高亮颜色列表 */
    const changeLightList = () => {
      const colorIndex = contextHighlightColor.findIndex((_, index) => !catchColorIndexList.value.includes(index));
      const catchCloneColorList = deepClone(colorHighlightList.value);
      colorHighlightList.value = highlightList.value.map((item) => {
        const notChangeItem = catchCloneColorList.find(cItem => cItem.heightKey === item);
        if (notChangeItem) return notChangeItem;
        return {
          heightKey: item,
          colorIndex,
          color: contextHighlightColor[colorIndex],
        };
      });
      nextTick(() => {
        initTagInputColor();
      });
      emit('handle-filter', 'highlightList', colorHighlightList.value);
    };

    /** 切换过滤类型 */
    const handleFilterType = (val: string) => {
      filterType.value = val;
      emit('handle-filter', 'filterType', val);
    };

    /** 粘贴高亮条件 */
    const pasteFn = (pasteValue: string) => {
      const trimPasteValue = pasteValue.trim();
      if (!highlightList.value.includes(trimPasteValue) && highlightList.value.length < 5) {
        highlightList.value.push(trimPasteValue);
        changeLightList();
      }
      return [];
    };

    /** 更新 tag-input 组件中的颜色 */
    const initTagInputColor = () => {
      if (!tagInputRef.value) return;
      const childEl = tagInputRef.value.$el.querySelectorAll('.key-node');
      childEl.forEach((child) => {
        const tag = child.querySelectorAll('.tag')[0];
        const colorObj = colorHighlightList.value.find(item => item.heightKey === tag.innerText);
        if (colorObj) {
          [child, tag].forEach((el) => {
            Object.assign(el.style, {
              backgroundColor: colorObj.color.light,
            });
          });
        }
      });
    };

    /** 重置所有状态 */
    const reset = () => {
      highlightList.value = [];
      colorHighlightList.value = [];
      filterKey.value = [];
      catchFilterKey.value = [];
      filterType.value = 'include';
    };

    /** 从外部设置过滤和高亮状态 */
    const setFilters = (params: {
      filterKey?: string[];
      filterType?: string;
      highlightList?: string[];
    }) => {
      if (params.filterKey) {
        filterKey.value = [...params.filterKey];
        catchFilterKey.value = [...params.filterKey];
        emit('handle-filter', 'filterKey', filterKey.value);
      }
      if (params.filterType) {
        filterType.value = params.filterType;
        emit('handle-filter', 'filterType', filterType.value);
      }
      if (params.highlightList) {
        highlightList.value = [...params.highlightList];
        // 触发 changeLightList 生成 colorHighlightList
        changeLightList();
      }
    };

    expose({
      reset,
      setFilters,
      getHighlightControl: () => highlightControlRef.value,
    });

    /** 切换文件树展开/收起 */
    const handleToggleFileTree = () => {
      emit('toggle-file-tree');
    };

    return () => (
      <div class='client-log-toolbar'>
        <div class='toolbar-main'>
          {/* 文件树折叠按钮 */}
          <div
            class={['file-tree-toggle', { 'is-active': !_.isFileTreeCollapsed }]}
            onClick={handleToggleFileTree}
          >
            <i class='bklog-icon bklog-celan'></i>
          </div>
          {/* 过滤类型 + 关键词输入 */}
          <div class='filter-main'>
            <bk-select
              ext-cls='filter-select'
              ext-popover-cls='filter-select-popover'
              clearable={false}
              value={filterType.value}
              on-change={handleFilterType}
            >
              {filterTypeList.map((option, index) => (
                <bk-option
                  id={option.id}
                  key={index}
                  name={option.name}
                />
              ))}
            </bk-select>
            <bk-tag-input
              class='filter-key-input'
              placeholder={t('输入关键字进行过滤')}
              value={filterKey.value}
              allow-create
              has-delete-icon
              paste-fn={filterPasteFn}
              on-change={(value: string[]) => {
                filterKey.value = value;
                filterLog();
              }}
            />
          </div>
          {/* 高亮关键词 */}
          <div class='highlight-main'>
            <div class='prefix-text'>{t('label-高亮').replace('label-', '')}</div>
            <bk-tag-input
              ref={tagInputRef}
              class='highlight-tag-input'
              max-data={5}
              paste-fn={pasteFn}
              value={highlightList.value}
              allow-create
              has-delete-icon
              on-change={(value: string[]) => {
                highlightList.value = value;
                changeLightList();
              }}
            />
            {highlightList.value.length > 0 && (
              <HighlightControl
                ref={highlightControlRef}
                lightList={highlightList.value}
                showType='code'
                containerSelector='.client-log-viewer'
              />
            )}
          </div>
        </div>
      </div>
    );
  },
});
