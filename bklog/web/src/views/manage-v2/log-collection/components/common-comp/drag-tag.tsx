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

import { defineComponent, onBeforeUnmount, onMounted, ref, nextTick, watch, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import draggable from 'vuedraggable';

import './drag-tag.scss';
export type TagItem = {
  id: number | string;
  label: string;
  [key: string]: any;
};

export default defineComponent({
  name: 'DragTag',
  components: { draggable },
  props: {
    value: {
      type: Array,
      default: () => [],
    },
    editable: {
      type: Boolean,
      default: true,
    },
    sortable: {
      type: Boolean,
      default: true,
    },
    showAddButton: {
      type: Boolean,
      default: true,
    },
    addType: {
      type: String as PropType<'custom' | 'input' | 'popover' | 'select'>,
      default: 'input',
    },
    maxTags: {
      type: Number,
      default: 0,
    },
    type: {
      type: String,
      default: 'default',
    },
    closable: {
      type: Boolean,
      default: true,
    },
    selectList: {
      type: Array,
      default: () => [],
    },
    nameKey: {
      type: String,
      default: 'name',
    },
    idKey: {
      type: String,
      default: 'id',
    },
    isError: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['input', 'add', 'remove', 'change', 'custom-add'],

  setup(props, { emit, slots }) {
    const { t } = useLocale();
    const tagList = ref<TagItem[]>([]);
    const isAdding = ref(false);
    const newTagInput = ref('');
    const tagInput = ref(null);
    const rootRef = ref<HTMLSpanElement>();
    const addPanelRef = ref<HTMLDivElement>();
    let tippyInstance: Instance | null = null;

    watch(
      () => props.value,
      (val) => {
        tagList.value = [...val];
      },
      { immediate: true, deep: true },
    );
    const emitInput = () => {
      emit('input', tagList.value);
    };
    const emitAdd = (tag: TagItem) => {
      emit('add', tag);
    };

    const emitRemove = (tag: TagItem, index: number) => {
      emit('remove', { tag, index });
    };
    const emitChange = () => {
      emit('change', [...tagList.value]);
    };

    // 删除tag
    const removeTag = (index: number) => {
      if (!props.editable) {
        return;
      }

      const removedTag = tagList.value[index];
      tagList.value.splice(index, 1);
      emitRemove(removedTag, index);
      emitChange();
      emitInput();
    };

    // 新增tag
    const addTag = () => {
      if (!(props.editable && newTagInput.value.trim())) {
        return;
      }

      // 检查是否重复
      const isDuplicate = tagList.value.some(tag => tag.label === newTagInput.value.trim());
      if (isDuplicate) {
        // 可以在这里添加提示
        return;
      }

      // 检查最大数量限制
      if (props.maxTags > 0 && tagList.value.length >= props.maxTags) {
        return;
      }

      const newTag: TagItem = {
        id: Date.now(),
        label: newTagInput.value.trim(),
      };

      tagList.value.push(newTag);
      emitAdd(newTag);
      emitChange();
      emitInput();

      // 重置输入
      newTagInput.value = '';
      isAdding.value = false;
    };

    // 开始新增
    const startAdd = () => {
      if (!props.editable) {
        return;
      }
      if (props.addType === 'input') {
        isAdding.value = true;
        nextTick(() => {
          tagInput.value?.focus();
        });
      }
      if (props.addType === 'custom') {
        nextTick(() => {
          emit('custom-add');
        });
      }
    };

    // 取消新增
    const cancelAdd = () => {
      isAdding.value = false;
      newTagInput.value = '';
    };

    // 处理输入框回车
    const handleInputEnter = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        addTag();
      }
    };

    // 处理输入框失焦
    const handleInputBlur = () => {
      if (newTagInput.value.trim()) {
        addTag();
      } else {
        cancelAdd();
      }
    };

    // 拖拽结束处理
    const onDragEnd = () => {
      emitChange();
      emitInput();
    };

    // 获取tag样式类
    const getTagClass = () => {
      const baseClass = 'tag-item';
      const typeClass = `tag-${props.type}`;
      return `${baseClass} ${typeClass}`;
    };
    const initActionPop = () => {
      tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: addPanelRef.value as any,
        trigger: 'click',
        placement: 'top-start',
        theme: 'light add-drag-tag-popover',
        interactive: true,
        hideOnClick: true,
        appendTo: () => document.body,
      });
    };
    onMounted(() => {
      if (props.addType === 'popover') {
        initActionPop();
      }
    });
    onBeforeUnmount(() => {
      tippyInstance?.hide();
      tippyInstance?.destroy();
    });

    const handleInputChange = (e: Event) => {
      newTagInput.value = (e.target as HTMLInputElement).value;
    };
    /** 下拉选中 */
    const handleAddSortFields = (value) => {
      const options = props.selectList.find(item => item.id === value);
      tagList.value.push(options.id);
      emitChange();
    };

    const isDisabled = (id: string) => {
      return tagList.value.some(item => item === id);
    };

    const renderSelect = () => (
      <bk-select
        class='tag-select-add'
        searchable
        on-selected={handleAddSortFields}
      >
        <div
          class='tag-add-btn'
          slot='trigger'
        >
          <i class='bk-icon icon-plus left-icon' />
        </div>
        {props.selectList.map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            disabled={isDisabled(item)}
            name={item.name}
          />
        ))}
      </bk-select>
    );

    return () => (
      <div class='drag-tag-box'>
        <draggable
          class='tag-container'
          animation={150}
          chosenClass='tag-chosen'
          disabled={!props.sortable}
          dragClass='tag-drag'
          draggable='.tag-item'
          ghostClass='tag-ghost'
          value={tagList.value}
          onEnd={onDragEnd}
          onInput={(val: TagItem[]) => {
            tagList.value = val;
          }}
        >
          {tagList.value.map((tag, index) => (
            <div
              key={tag[props.idKey] ? tag[props.idKey] : tag}
              class={getTagClass()}
            >
              {props.sortable && <span class='bklog-icon drag-icon bklog-ketuodong' />}
              <span class='tag-label'>{tag[props.nameKey] || tag}</span>
              {props.editable && props.closable && (
                <span
                  class='bk-icon icon-close tag-close'
                  on-Click={() => removeTag(index)}
                />
              )}
            </div>
          ))}
          {props.addType !== 'select'
            && props.editable
            && props.showAddButton
            && !isAdding.value
            && (props.maxTags === 0 || tagList.value.length < props.maxTags) && (
              <div
                ref={rootRef}
                class={{
                  'tag-add-btn': true,
                  'is-error': props.isError,
                }}
                on-Click={startAdd}
              >
                <i class='bk-icon icon-plus left-icon' />
              </div>
          )}
          <div style='display: none'>
            <div
              ref={addPanelRef}
              class='drag-tag-add-panel'
            >
              {slots.popover?.()}
            </div>
          </div>
          {props.addType === 'select' && renderSelect()}

          {isAdding.value && props.addType === 'input' && (
            <div class='tag-input-wrapper'>
              <input
                ref={tagInput}
                class='tag-input'
                placeholder={t('请输入标签')}
                value={newTagInput.value}
                onBlur={handleInputBlur}
                onInput={handleInputChange}
                onKeydown={handleInputEnter}
              />
            </div>
          )}
        </draggable>
      </div>
    );
  },
});
