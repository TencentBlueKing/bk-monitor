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
import {
  type PropType,
  ref as deepRef,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  shallowRef,
  TransitionGroup,
  useTemplateRef,
  watch,
} from 'vue';
import { computed } from 'vue';

import { useThrottleFn } from '@vueuse/core';
import { $bkPopover, Button, Exception, Input } from 'bkui-vue';
import { ArrowsRight, Close, Transfer } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import FieldTypeIcon from '../field-type-icon';

import type { IDimensionField } from '../../typing';

import './explore-field-setting.scss';

export type FieldSettingItem = Pick<IDimensionField, 'alias' | 'name' | 'type'> | { [key in string]: any };
export default defineComponent({
  name: 'ExploreFieldSetting',
  props: {
    /** 穿梭框数据源（所有选项列表） */
    sourceList: {
      type: Array as PropType<FieldSettingItem[]>,
      default: () => [],
    },
    /** 已选择的数据（唯一标识 setting-key 的数组） */
    targetList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 固定选中的数据 */
    fixedDisplayList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 具有唯一标识的 key 值 */
    settingKey: {
      type: String,
      default: 'name',
    },
    /** 展示的 key 值 */
    displayKey: {
      type: String,
      default: 'alias',
    },
    /** 数据源kv结构集合（性能优化方案，非必填） */
    sourceMap: {
      type: Object as PropType<{ [key: string]: FieldSettingItem }>,
    },
  },
  emits: {
    confirm: (targetList: string[]) => Array.isArray(targetList),
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 拖拽容器 */
    let dragContainer = null;

    /** popover 弹窗实例 */
    const popoverInstance = shallowRef(null);
    /** popover 弹出显示内容容器 */
    const containerRef = useTemplateRef<HTMLElement | null>('containerRef');
    /** input搜索框输入的值 */
    const searchKeyword = shallowRef('');
    /** 穿梭框数据源（所有选项列表） key 映射集合 */
    const sourceListMap = deepRef({});
    /** 选中的列表key值 */
    const selectedList = deepRef([]);
    /** 当前正在拖拽的元素的 key 值 */
    const draggingField = shallowRef('');
    /** 选中的集合(待选列表筛选使用) */
    const selectedSet = computed(() => new Set(selectedList.value));
    /** 固定选中的集合 */
    const fixedDisplaySet = computed(() => new Set(props.fixedDisplayList));
    /** 待选列表 */
    const toBeChosenList = computed(() => {
      if (!popoverInstance.value) {
        return [];
      }
      return props.sourceList.filter(item => {
        const field = item[props.settingKey];
        const label = item[props.displayKey];
        const matchReg = new RegExp(`${searchKeyword.value}`.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&'), 'ig');
        return !selectedSet.value.has(field) && matchReg.test(label);
      });
    });
    const selectedListLen = computed(() => selectedList.value.length);
    const toBeChosenListLen = computed(() => toBeChosenList.value.length);

    /** 待选区域空数据时展示类型 */
    const emptyConfig = computed<null | { description: string; type: 'empty' | 'search-empty' }>(() => {
      if (toBeChosenList.value.length) {
        return null;
      }
      if (searchKeyword.value) {
        return {
          description: t('搜索为空'),
          type: 'search-empty',
        };
      }
      return {
        description: t('没有数据'),
        type: 'empty',
      };
    });

    watch(
      () => popoverInstance.value,
      v => {
        if (!v) {
          init();
          removeDragListener();
          return;
        }
        sourceListMap.value = props.sourceMap
          ? props.sourceMap
          : props.sourceList.reduce((prev, curr) => {
              const field = curr[props.settingKey];
              if (prev[field]) return prev;
              prev[field] = curr;
              return prev;
            }, {});
        selectedList.value = props.targetList.filter(v => sourceListMap.value[v]);

        nextTick(() => {
          addDragListener();
        });
      }
    );

    onBeforeUnmount(() => {
      removeDragListener();
    });

    /** 添加监听事件(消除拖拽元素拖拽时鼠标图标变为黑色的禁止图标的默认行为) */
    function addDragListener() {
      dragContainer = containerRef.value?.querySelector?.('.transfer-list.target-list');
      if (!dragContainer) {
        return;
      }
      dragContainer.addEventListener('dragover', dragPreventDefault);
      dragContainer.addEventListener('dragenter', dragPreventDefault);
    }

    /** 移除监听事件 */
    function removeDragListener() {
      if (!dragContainer) {
        return;
      }
      dragContainer?.removeEventListener('dragover', dragPreventDefault);
      dragContainer?.removeEventListener('dragenter', dragPreventDefault);
      dragContainer = null;
    }

    function init() {
      selectedList.value = [];
      sourceListMap.value = {};
      searchKeyword.value = '';
    }

    /**
     * @description 打开 menu下拉菜单 popover 弹窗
     *
     */
    function handleSettingPopoverShow(e: MouseEvent) {
      if (popoverInstance.value) {
        handlePopoverHide();
        return;
      }
      popoverInstance.value = $bkPopover({
        target: e.currentTarget as HTMLElement,
        content: containerRef.value,
        trigger: 'click',
        placement: 'bottom-end',
        theme: 'light explore-table-field-setting',
        arrow: true,
        boundary: 'viewport',
        popoverDelay: 0,
        isShow: false,
        always: false,
        disabled: false,
        clickContentAutoHide: false,
        height: '',
        maxWidth: '',
        maxHeight: '',
        renderDirective: 'if',
        allowHtml: false,
        renderType: 'auto',
        padding: 0,
        offset: 0,
        zIndex: 0,
        disableTeleport: false,
        autoPlacement: false,
        autoVisibility: false,
        disableOutsideClick: false,
        disableTransform: false,
        modifiers: [],
        extCls: '',
        referenceCls: '',
        hideIgnoreReference: true,
        componentEventDelay: 0,
        forceClickoutside: false,
        immediate: false,
        // @ts-ignore
        onHide: () => {
          handlePopoverHide();
        },
      });
      popoverInstance.value.install();
      setTimeout(() => {
        popoverInstance.value?.vm?.show();
      }, 100);
    }

    /**
     * @description 关闭 menu下拉菜单 popover 弹窗
     *
     */
    function handlePopoverHide() {
      popoverInstance.value?.hide?.();
      popoverInstance.value?.close?.();
      popoverInstance.value = null;
    }

    /**
     * @description 添加选中值回调
     *
     */
    function handleSelectedField(field) {
      if (selectedSet.value.has(field)) {
        return;
      }
      selectedList.value.push(field);
    }

    /**
     * @description 移除选中值回调
     *
     */
    function handleRemoveField(field, index) {
      if (!selectedSet.value.has(field)) {
        return;
      }
      selectedList.value.splice(index, 1);
    }

    /**
     * @description 全部添加按钮点击回调
     *
     */
    function handleSelectedAll() {
      if (!toBeChosenListLen.value) {
        return;
      }
      const fields = props.sourceList.reduce((prev: string[], curr) => {
        const field = curr[props.settingKey];
        if (selectedSet.value.has(field)) {
          return prev;
        }
        prev.push(field);
        return prev;
      }, []);
      selectedList.value = [...selectedList.value, ...fields];
    }

    /**
     * @description 清空按钮点击回调
     *
     */
    function handleRemoveAll() {
      if (!selectedListLen.value) {
        return;
      }
      selectedList.value = [...props.fixedDisplayList];
    }

    /**
     * @description 确认按钮点击回调
     *
     */
    function handleConfirm() {
      emit('confirm', selectedList.value);
      handlePopoverHide();
    }

    /**
     * @description 源对象开始被拖动时触发，记录当前拖拽的key值
     *
     */
    function handleDragstart(e: DragEvent, field: string) {
      draggingField.value = field;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', field);
      // @ts-ignore
      e.target.closest('.target-item').classList.add('dragging');
    }

    /**
     * @description 源对象开始进入目标对象范围内触发，源对象和目标对象互换位置
     *
     */
    function handleDragover(e: DragEvent, field: string) {
      dragPreventDefault(e);
      const sourceField = draggingField.value;
      if (!sourceField || !field || field === draggingField.value) {
        return;
      }
      const list = [...selectedList.value];
      const targetIndex = list.indexOf(field);
      const sourceIndex = list.indexOf(sourceField);
      if (sourceIndex > targetIndex) {
        list.splice(sourceIndex, 1);
        list.splice(targetIndex, 0, sourceField);
      } else {
        list.splice(targetIndex + 1, 0, sourceField);
        list.splice(sourceIndex, 1);
      }
      selectedList.value = list;
    }
    const debounceDragover = useThrottleFn(handleDragover, 300);

    /**
     * @description 源对象拖动结束时触发
     *
     */
    function handleDragend(e: DragEvent) {
      const target = e.target as HTMLElement;
      const dragDom = target.closest('.target-item');
      if (dragDom) {
        dragDom?.classList.remove('dragging');
        // @ts-ignore
        dragDom.draggable = false;
      }
      draggingField.value = '';
    }

    /**
     * @description 阻止默认事件
     */
    function dragPreventDefault(e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    }

    /**
     * @description drag 操作句柄鼠标 按下/松开 触发回调事件
     *
     */
    function dragHandleMouseOperation(e: MouseEvent, draggable) {
      // @ts-ignore
      e.target.closest('.target-item').draggable = draggable;
    }

    /**
     * @description 选中列表渲染
     *
     */
    function targetListRender() {
      return (
        <TransitionGroup
          class='transfer-list target-list'
          name='drag'
          tag='ul'
        >
          {selectedList.value.map((field, index) => {
            const fieldItem = sourceListMap.value[field];
            const label = fieldItem?.[props.displayKey];
            const fieldType = fieldItem.type;
            return (
              <li
                key={field}
                class='list-item target-item'
                onDragend={handleDragend}
                onDragover={e => debounceDragover(e, field)}
                onDragstart={e => handleDragstart(e, field)}
              >
                <div class='list-item-left'>
                  <i
                    class='icon-monitor icon-mc-tuozhuai'
                    onMousedown={e => dragHandleMouseOperation(e, true)}
                    onMouseup={e => dragHandleMouseOperation(e, false)}
                  />
                  <FieldTypeIcon
                    class='item-prefix'
                    type={fieldType}
                  />
                  <span class='item-label'>{label}</span>
                </div>
                {!fixedDisplaySet.value.has(field) ? (
                  <div
                    class='item-suffix'
                    onClick={() => handleRemoveField(field, index)}
                  >
                    <Close />
                  </div>
                ) : null}
              </li>
            );
          })}
        </TransitionGroup>
      );
    }

    /**
     * @description 待选列表渲染
     *
     */
    function sourceListRender() {
      return (
        <ul class='transfer-list source-list'>
          {toBeChosenList.value.map(item => {
            const field = item[props.settingKey];
            const label = item[props.displayKey];
            const fieldType = item.type;
            return (
              <li
                key={field}
                class='list-item source-item'
                onClick={() => handleSelectedField(field)}
              >
                <div class='list-item-left'>
                  <FieldTypeIcon
                    class='item-prefix'
                    type={fieldType}
                  />
                  <span class='item-label'>{label}</span>
                </div>
                <div class='item-suffix'>
                  <ArrowsRight />
                </div>
              </li>
            );
          })}
          {emptyConfig.value ? (
            <Exception
              description={emptyConfig.value.description}
              scene='part'
              type={emptyConfig.value.type}
            />
          ) : null}
        </ul>
      );
    }

    /**
     * @description popover 弹窗内容区域渲染
     *
     */
    function settingContainerRender() {
      return (
        <div
          ref='containerRef'
          class='setting-container'
        >
          <span class='setting-title'>{t('字段显示')}</span>
          <div class='setting-transfer'>
            <div class='transfer-source'>
              <div class='transfer-header source-header'>
                <div class='header-title'>
                  <span class='title-label'>{t('待选字段')}</span>
                  <span class='list-count'>（{toBeChosenListLen.value}）</span>
                </div>
                <span
                  class={`header-operation ${!toBeChosenListLen.value ? 'disabled' : ''}`}
                  onClick={handleSelectedAll}
                >
                  {t('全部添加')}
                </span>
              </div>
              <div class='source-search-input'>
                <Input
                  v-model={searchKeyword.value}
                  v-slots={{ prefix: () => <i class='icon-monitor icon-mc-search' /> }}
                  behavior='simplicity'
                  placeholder={t('请输入关键字')}
                  clearable
                />
              </div>
              {sourceListRender()}
            </div>
            <Transfer class='transfer-icon bk-transfer-icon' />
            <div class='transfer-target'>
              <div class='transfer-header target-header'>
                <div class='header-title'>
                  <span class='title-label'>{t('已选字段')}</span>
                  <span class='list-count'>（{selectedListLen.value}）</span>
                </div>
                <span
                  class={`header-operation ${!selectedListLen.value ? 'disabled' : ''}`}
                  onClick={handleRemoveAll}
                >
                  {t('清空')}
                </span>
              </div>
              {targetListRender()}
            </div>
          </div>
          <div class='setting-operation'>
            <Button
              theme='primary'
              onClick={handleConfirm}
            >
              {t('确定')}
            </Button>
            <Button onClick={handlePopoverHide}>{t('取消')}</Button>
          </div>
        </div>
      );
    }
    return { popoverInstance, settingContainerRender, handleSettingPopoverShow };
  },
  render() {
    const { popoverInstance, settingContainerRender, handleSettingPopoverShow } = this;
    return (
      <div class={{ 'explore-field-setting': true, active: !!popoverInstance }}>
        <div
          class='popover-trigger'
          onClick={handleSettingPopoverShow}
        >
          <i class='icon-monitor icon-shezhi1' />
        </div>
        <div style='display: none'>{settingContainerRender()}</div>
      </div>
    );
  },
});
