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
import { computed, defineComponent, nextTick, onMounted, onUnmounted, type Ref, ref, watch } from 'vue';

import useRetrieveEvent from '@/hooks/use-retrieve-event';

import { getCharLength } from '../../../common/util';
import PopInstanceUtil from '../../../global/pop-instance-util';
import useLocale from '../../../hooks/use-locale';
import useResizeObserve from '../../../hooks/use-resize-observe';
import { RetrieveEvent } from '../../retrieve-helper';

import './bklog-tag-choice.scss';

export default defineComponent({
  model: {
    prop: 'value',
    event: 'change',
  },
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    id: {
      type: String,
      default: 'id',
    },
    name: {
      type: String,
      default: 'id',
    },
    minWidth: {
      type: String,
      default: '120px',
    },
    maxWidth: {
      type: String,
      default: '560px',
    },
    maxHeight: {
      type: String,
      default: null,
    },
    minHeight: {
      type: String,
      default: '32px',
    },

    valueTagMaxWidth: {
      type: String,
      default: '200px',
    },

    value: {
      type: [String, Number, Array],
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
    placeholder: {
      type: String,
      default: '请选择...',
    },
    foucsFixed: {
      type: Boolean,
      default: false,
    },
    /**
     * 模板
     * tag-choice：下拉弹出，支持键入标签
     * tag-input：输入框，支持键入标签，没有下拉
     */
    template: {
      type: String,
      default: 'tag-choice',
    },
    onTagRender: {
      type: Function,
      default: undefined,
    },
    borderColor: {
      type: String,
      default: '#c4c6cc',
    },
    focusBorderColor: {
      type: String,
      default: '#3a84ff',
    },
    zIndex: {
      type: Number,
      default: undefined,
    },
    bdiDir: {
      type: String,
      default: 'ltr',
    },
  },
  emits: ['change', 'input', 'toggle', 'focus', 'blur', 'custom-tag-enter', 'enter'],
  setup(props, { slots, emit }) {
    const isListOpended = ref(false);
    const refRootElement: Ref<HTMLElement> = ref(null);
    const refChoiceList: Ref<HTMLElement> = ref(null);
    const refTagInputElement: Ref<HTMLElement> = ref(null);
    const refTagInputContainer: Ref<HTMLElement> = ref(null);
    const refFixedPointerElement: Ref<HTMLElement> = ref(null);

    let focusFixedElement: HTMLElement = null;
    let fixedInstance: PopInstanceUtil = null;
    let popInstance: PopInstanceUtil = null;

    const inputTagValue = ref('');
    const tagInputIndex = ref(null);
    const containerWidth = ref(0);
    const activeItemIndex = ref(null);
    const isFixedOverflowY = ref(false);

    const editItemOption = ref({
      index: null,
      width: 12,
    });

    const isInputFocused = ref(false);

    const INPUT_MIN_WIDTH = 12;

    const { t } = useLocale();

    useResizeObserve(refRootElement, (entry) => {
      const newWidth = (entry.target as HTMLElement).offsetWidth;

      if (newWidth !== containerWidth.value) {
        containerWidth.value = newWidth;
        if (focusFixedElement?.children?.[0]) {
          (focusFixedElement.children[0] as HTMLElement).style.width = `${newWidth + 4}px`;
        }

        fixedInstance?.repositionTippyInstance();
        popInstance?.repositionTippyInstance();
      }
    });

    const containerStyle = computed(() => {
      return {
        width: `${containerWidth.value}px`,
      };
    });

    const maxTagWidthNumber = computed(() => {
      return Number.parseFloat(props.valueTagMaxWidth.replace('px', ''));
    });

    const tagInputStyle = computed(() => {
      const charLen = Math.max(getCharLength(inputTagValue.value), 1);
      const wordWidth = charLen * INPUT_MIN_WIDTH;
      const width = wordWidth > maxTagWidthNumber.value ? maxTagWidthNumber.value : wordWidth;

      return {
        minWidth: `${INPUT_MIN_WIDTH}px`,
        width: `${width}px`,
      };
    });

    const stopDefaultPrevented = (e) => {
      e.stopPropagation?.();
      e.stopImmediatePropagation?.();
      e.preventDefault?.();
    };

    if (!props.foucsFixed && props.template === 'tag-choice') {
      popInstance = new PopInstanceUtil({
        refContent: () => refChoiceList.value,
        arrow: false,
        onShowFn: () => {
          emit('toggle', true);
          return true;
        },
        onHiddenFn: () => {
          emit('toggle', false);
          return true;
        },
        tippyOptions: {
          hideOnClick: true,
          interactive: true,
          appendTo: document.body,
          placement: 'bottom-start',
          onShown: () => {
            popInstance.setIsShowing(false);
          },
        },
      });
    }

    const dropdownIconName = computed(() => {
      if (isListOpended.value) {
        return 'bk-icon icon-angle-up';
      }

      return 'bk-icon icon-angle-down';
    });

    const getListItemId = (item: any) => {
      if (typeof item === 'object') {
        return item[props.id] ?? item;
      }

      return item;
    };

    const getItemKey = (item: any, index) => {
      return `key_${index}_${getListItemId(item)}`;
    };

    const getListItemName = (item: any) => {
      if (typeof item === 'object') {
        return item[props.name] ?? item;
      }

      return item;
    };

    const valueList = computed(() => {
      if (Array.isArray(props.value)) {
        return props.value.map(item => (props.list ?? []).find(item2 => getListItemId(item2) === item) ?? item);
      }

      return [props.value].map(item => (props.list ?? []).find(item2 => getListItemId(item2) === item) ?? item);
    });

    const valueWithInputList = computed(() => {
      if (
        typeof tagInputIndex.value === 'number'
        && tagInputIndex.value >= 0
        && tagInputIndex.value < valueList.value.length
      ) {
        return [
          ...valueList.value.slice(0, tagInputIndex.value),
          { __tag_input__: true },
          ...valueList.value.slice(tagInputIndex.value),
        ];
      }

      return [...valueList.value, { __tag_input__: true }];
    });

    const optionList = computed(() => {
      return (props.list ?? [])
        .filter(({ selected }) => !selected)
        .map((item) => {
          return {
            item,
            selected: valueList.value.some(v => getListItemId(v) === getListItemId(item)),
          };
        });
    });

    const placeholderText = computed(() => {
      if (!isInputFocused.value && valueList.value.length === 0) {
        return props.placeholder;
      }

      return '';
    });

    const handleInputValueChange = (e: any) => {
      const input = e.target;
      inputTagValue.value = input.value;
      emit('input', input.value);
    };

    /**
     * 获取抛出事件
     * @param value
     */
    const emitValue = (value) => {
      const itemId = getListItemId(value);
      // 避免重复添加
      if (valueList.value.some(item => getListItemId(item) === itemId)) {
        return;
      }

      const targetValue: any[] = [];
      for (const v of valueList.value) {
        targetValue.push(getListItemId(v));
      }

      targetValue.push(getListItemId(value));

      emit('change', targetValue);
    };

    /**
     * 鼠标点击空白位置执行当前focused的 edit input blur行为
     */
    const handleEditInputBlur = (editIndexOverride: number | null = null) => {
      return new Promise((resolve) => {
        // 如果传入了索引覆盖，优先使用；否则使用 editItemOption.value.index；如果都是 null，尝试从 DOM 获取
        const currentEditIndex = editIndexOverride !== null ? editIndexOverride : editItemOption.value.index;

        if (currentEditIndex !== null) {
          let isUpdate = false;

          const targetValue: any[] = [];
          valueList.value.forEach((v, index) => {
            if (index !== currentEditIndex) {
              targetValue.push(getListItemId(v));
            } else {
              const oldValue = getListItemId(v);
              const newValue = inputTagValue.value;
              isUpdate = oldValue !== newValue;
              if (newValue !== '') {
                targetValue.push(newValue);
              }
            }
          });

          if (isUpdate) {
            emit('change', targetValue);
          }

          editItemOption.value.index = null;
          editItemOption.value.width = 12;
          inputTagValue.value = '';

          resolve(true);
        }

        editItemOption.value.width = 12;
        inputTagValue.value = '';
        resolve(false);
      });
    };

    /**
     * 当绑定的数据改变时，销毁当前弹出内容，根据Vue渲染出来的结果进行弹出内容的更新
     */
    const updateFiexedInstanceContent = () => {
      return new Promise((resolve) => {
        nextTick(() => {
          setFixedValueContent();
          fixedInstance.setContent(focusFixedElement);
          fixedInstance.setProps({
            content: focusFixedElement,
          });
          fixedInstance.repositionTippyInstance();

          resolve(true);
        });
      });
    };

    const emitDeleteItem = (val) => {
      const targetValue: any[] = [];
      for (const v of valueList.value) {
        if (v !== val) {
          targetValue.push(getListItemId(v));
        }
      }

      emit('change', targetValue);
    };

    const handleDeleteItemClick = (e, val) => {
      stopDefaultPrevented(e);
      emitDeleteItem(val);
      refTagInputElement.value?.focus();
    };

    const handleOptionItemClick = (val) => {
      emitValue(getListItemId(val));
      if (props.foucsFixed) {
        updateFiexedInstanceContent();
      }
    };

    /**
     * 自动 focus 输入框
     * @returns
     */
    const autoFocusInput = () => {
      if (!focusFixedElement) {
        refTagInputElement.value?.focus();
        return;
      }

      const editInput = focusFixedElement.querySelector('[data-bklog-choice-value-edit-input]') as HTMLInputElement;
      if (editInput) {
        editInput.focus();
        return;
      }

      const input = focusFixedElement.querySelector('[data-bklog-choice-text-input]') as HTMLInputElement;
      input?.focus();
    };

    const getDelTargetElement = (index: number) => {
      const selector = `[data-bklog-choice-value-delete-${index}]`;
      return refTagInputContainer.value?.querySelector(selector);
    };

    let isEmptyInput = false;

    const handleInputKeydown = (e: KeyboardEvent) => {
      const input = e.target as HTMLInputElement;
      isEmptyInput = input.value.length === 0;
    };

    /**
     * Enter 当前键入值
     * @param e
     */
    const handleInputKeyup = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        if (inputTagValue.value.length) {
          stopDefaultPrevented(e);

          emitValue(inputTagValue.value);
          clearInputTag();
          emit('custom-tag-enter');
        }
        emit('enter');
      }

      if (e.key === 'Backspace' && !props.foucsFixed) {
        const input = e.target as HTMLInputElement;
        if (input.value.length === 0 && isEmptyInput) {
          const target = getDelTargetElement(valueList.value.length - 1);
          handleDeleteItemClick({ target }, valueList.value.at(-1));
        }
      }
    };

    const handleDeleteAllClick = (e) => {
      stopDefaultPrevented(e);
      emit('change', []);
    };

    const setFixedOverflowY = () => {
      isFixedOverflowY.value = refTagInputContainer.value?.offsetHeight > 32;

      if (focusFixedElement?.children?.[0]) {
        const target = focusFixedElement.children[0];

        if (isFixedOverflowY.value) {
          target.classList.add('is-ellipsis');
          return;
        }

        target.classList.remove('is-ellipsis');
      }
    };

    /**
     * 处理编辑输入框的input事件
     * @param e
     */
    const handleEditInputChange = (e: InputEvent) => {
      const input = e.target as HTMLInputElement;
      inputTagValue.value = input.value;
    };

    /**
     * 处理编辑输入框的blur事件（非 fixed 模式使用，Vue 直接绑定）
     * @param e
     */
    const handleEditInputBlurEvent = (e: FocusEvent) => {
      const target = e.target as HTMLElement;
      // 只在编辑输入框失焦时处理
      if (!target || !target.hasAttribute('data-bklog-choice-value-edit-input')) {
        return;
      }

      // 确保目标元素属于当前组件（非 fixed 模式，Vue 绑定已经确保这一点，但为了安全起见仍然检查）
      if (!refTagInputContainer.value?.contains(target)) {
        return;
      }

      handleEditInputBlur().then((update: boolean) => {
        if (update) {
          calcItemEllipsis().then(() => {
            setFixedOverflowY();
          });
        }
      });
    };

    /**
     * 处理编辑输入框的keyup事件
     * @param e
     */
    const handleEditInputKeyup = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        stopDefaultPrevented(e);
        handleEditInputBlur().then((update: boolean) => {
          if (props.foucsFixed) {
            setFixedOverflowY();
            if (update) {
              updateFiexedInstanceContent().then(() => {
                autoFocusInput();
              });
            } else {
              autoFocusInput();
            }
          } else {
            if (update) {
              calcItemEllipsis().then(() => {
                setFixedOverflowY();
                autoFocusInput();
              });
            } else {
              autoFocusInput();
            }
          }
        });
      }
    };

    /**
     * Fixed 模式Input事件添加监听
     * @param e
     */
    const handleCloneFixedInputChange = (e: InputEvent) => {
      if ((e.target as HTMLElement).hasAttribute('data-bklog-choice-text-input')) {
        handleInputValueChange(e);
        const target = e.target as HTMLInputElement;
        const charLen = Math.max(getCharLength(inputTagValue.value), 1);
        const maxWidth = Math.min(charLen * INPUT_MIN_WIDTH, maxTagWidthNumber.value);

        target.style.setProperty('width', `${maxWidth}px`);
        setFixedOverflowY();
      }
    };

    /**
     * 为克隆节点中的编辑输入框绑定事件
     */
    const bindEditInputEvents = (container: HTMLElement, forceRebind = false) => {
      const editInput = container.querySelector('[data-bklog-choice-value-edit-input]') as HTMLInputElement;
      if (editInput) {
        // 如果强制重新绑定，先清除属性标记（因为 clone 操作会复制属性，需要清除）
        if (forceRebind) {
          editInput.removeAttribute('data-bklog-edit-bound');
        }

        // 检查是否已经绑定过事件（通过检查是否有自定义属性标记）
        // 如果 forceRebind 为 true，则强制重新绑定（用于节点替换后的场景）
        if (!forceRebind && editInput.hasAttribute('data-bklog-edit-bound')) {
          return;
        }

        // 标记已绑定事件
        editInput.setAttribute('data-bklog-edit-bound', 'true');

        // 绑定事件处理器
        const inputHandler = (e: InputEvent) => {
          handleEditInputChange(e);
        };

        const blurHandler = (e: FocusEvent) => {
          // 只处理当前输入框的 blur，确保是编辑输入框
          if (e.target === editInput) {
            // 在 blur 时，确保从实际的 input 元素读取最新值
            const currentValue = (e.target as HTMLInputElement).value;
            // 从 DOM 元素获取编辑索引，而不是依赖可能被重置的 editItemOption.value.index
            const itemElement = editInput.closest('[data-item-index]') as HTMLElement;
            const editIndexFromDOM = itemElement ? Number.parseInt(itemElement.getAttribute('data-item-index') ?? '-1', 10) : -1;

            inputTagValue.value = currentValue;

            // 如果 editIndex 为 null，但从 DOM 中找到了索引，说明是节点替换导致的误重置，需要恢复
            if (editItemOption.value.index === null && editIndexFromDOM >= 0) {
              editItemOption.value.index = editIndexFromDOM;
            }

            // 使用从 DOM 获取的索引（如果有效），否则使用 editItemOption.value.index
            const finalEditIndex = editIndexFromDOM >= 0 ? editIndexFromDOM : editItemOption.value.index;

            handleEditInputBlur(finalEditIndex).then((update: boolean) => {
              setFixedOverflowY();
              if (update) {
                updateFiexedInstanceContent();
              }
            });
          }
        };

        const keyupHandler = (e: KeyboardEvent) => {
          if (e.target === editInput && e.key === 'Enter') {
            stopDefaultPrevented(e);
            // 在 Enter 时，确保从实际的 input 元素读取最新值
            const currentValue = (e.target as HTMLInputElement).value;
            // 从 DOM 元素获取编辑索引，而不是依赖可能被重置的 editItemOption.value.index
            const itemElement = editInput.closest('[data-item-index]') as HTMLElement;
            const editIndexFromDOM = itemElement ? Number.parseInt(itemElement.getAttribute('data-item-index') ?? '-1', 10) : -1;

            inputTagValue.value = currentValue;

            // 如果 editIndex 为 null，但从 DOM 中找到了索引，说明是节点替换导致的误重置，需要恢复
            if (editItemOption.value.index === null && editIndexFromDOM >= 0) {
              editItemOption.value.index = editIndexFromDOM;
            }

            // 使用从 DOM 获取的索引（如果有效），否则使用 editItemOption.value.index
            const finalEditIndex = editIndexFromDOM >= 0 ? editIndexFromDOM : editItemOption.value.index;

            handleEditInputBlur(finalEditIndex).then((update: boolean) => {
              setFixedOverflowY();
              if (update) {
                updateFiexedInstanceContent().then(() => {
                  autoFocusInput();
                });
              } else {
                autoFocusInput();
              }
            });
          }
        };

        const keydownHandler = (e: KeyboardEvent) => {
          // 阻止事件冒泡，避免触发容器的点击事件
          e.stopPropagation();
        };

        editInput.addEventListener('input', inputHandler);
        editInput.addEventListener('blur', blurHandler);
        editInput.addEventListener('keyup', keyupHandler);
        editInput.addEventListener('keydown', keydownHandler);
      }
    };

    const setFocuseFixedPopEvent = () => {
      if (focusFixedElement) {
        focusFixedElement.addEventListener('click', handleFixedValueListClick);
        focusFixedElement.addEventListener('keyup', handleFixedValueInputKeyup);
        focusFixedElement.addEventListener('keydown', handleFixedValueInputKeydown);
        focusFixedElement.addEventListener('input', handleCloneFixedInputChange);
      }
    };

    const setFixedValueContent = () => {
      const copyNode = refTagInputContainer.value.cloneNode(true) as HTMLElement;
      copyNode.style.width = `${refTagInputContainer.value.offsetWidth + 4}px`;

      // 如果正在编辑，确保 clone 的节点中的编辑输入框的 value 与 inputTagValue.value 同步
      if (editItemOption.value.index !== null) {
        const editInput = copyNode.querySelector('[data-bklog-choice-value-edit-input]') as HTMLInputElement;
        if (editInput) {
          editInput.value = inputTagValue.value;
        }
      }

      if (focusFixedElement) {
        // 如果 focusFixedElement 已存在，先替换节点，再绑定事件
        // 这样可以确保事件绑定到已插入 DOM 的节点上
        focusFixedElement.childNodes[0].replaceWith(copyNode);
        // 强制重新绑定事件（因为节点已替换，需要确保事件正确绑定）
        bindEditInputEvents(copyNode, true);
      } else {
        focusFixedElement = document.createElement('div');
        focusFixedElement.classList.add('bklog-choice-fixed-content');

        focusFixedElement.appendChild(copyNode);
        focusFixedElement.appendChild(refChoiceList.value);
        setFocuseFixedPopEvent();
        // 首次创建时绑定事件
        bindEditInputEvents(copyNode);
      }
    };

    const handleCustomTagClick = (e: MouseEvent) => {
      emitValue(inputTagValue.value);
      clearInputTag();
      emit('custom-tag-enter');
      stopDefaultPrevented(e);
    };

    /**
     * fixed 模式弹出内容点击事件监听
     * @param e
     * @returns
     */
    const handleFixedValueListClick = (e: MouseEvent) => {
      stopDefaultPrevented(e);

      const target = e?.target as HTMLElement;
      if (
        target.hasAttribute('data-bklog-choice-text-input')
        || target?.classList.contains('bklog-choice-value-edit-input')
      ) {
        return;
      }

      // 点击进行编辑
      if (target?.classList.contains('bklog-choice-value-span')) {
        const index = target.parentElement.getAttribute('data-item-index');
        const indexNum = Number.parseInt(index, 10);
        const originalText = target.innerText;
        editItemOption.value.index = indexNum;
        editItemOption.value.width = target.parentElement.offsetWidth;
        inputTagValue.value = originalText;
        updateFiexedInstanceContent().then(() => {
          autoFocusInput();
        });
        return;
      }

      // 点击删除单个值
      if (target.hasAttribute('data-bklog-choice-item-del')) {
        const index = Number.parseInt(target.getAttribute('data-bklog-choice-item-del') ?? '-1', 10);
        if (index >= 0) {
          const targetValue: any[] = [];
          valueList.value.forEach((v, idx) => {
            if (idx !== index) {
              targetValue.push(getListItemId(v));
            }
          });

          emit('change', targetValue);

          updateFiexedInstanceContent().then(() => {
            setFixedOverflowY();
          });
        }

        return;
      }

      handleEditInputBlur().then((update: boolean) => {
        setFixedOverflowY();
        if (update) {
          updateFiexedInstanceContent().then(() => {
            autoFocusInput();
          });
          return;
        }

        autoFocusInput();
      });
    };

    /**
     *
     * @param e
     */
    const handleFixedValueInputKeydown = (e: KeyboardEvent) => {
      const input = e.target as HTMLInputElement;
      isEmptyInput = input.value === '';
    };

    /**
     *
     * @param e
     * @returns
     */
    const handleFixedValueInputKeyup = (e: KeyboardEvent) => {
      const target = e.target as HTMLInputElement;
      if (target.hasAttribute('data-bklog-choice-text-input')) {
        handleInputKeyup(e);
        if (e.key === 'Enter') {
          updateFiexedInstanceContent().then(() => {
            setFixedOverflowY();
            setTimeout(autoFocusInput);
          });
        }

        if (e.key === 'Backspace' && target.value === '' && isEmptyInput) {
          emitDeleteItem(valueList.value.at(-1));
          target.closest('.bklog-choice-value-item')?.remove();
          setFixedOverflowY();
          setTimeout(autoFocusInput);
        }
      } else if (target.hasAttribute('data-bklog-choice-value-edit-input')) {
        handleEditInputKeyup(e);
      }
    };

    const handleOptionItemMouseenter = (index: number) => {
      activeItemIndex.value = index;
    };

    const handleOptionItemMouseleave = () => {
      activeItemIndex.value = undefined;
    };

    const lastTagWidth = 40;
    const closeTagWidth = 30;
    const inputWidth = 12;
    const hiddenItemCount = ref(0);
    const hiddenItemIndex = ref([]);
    const getMaxWidth = () => {
      if (props.maxWidth) {
        return Number.parseFloat(props.maxWidth.replace('px', ''));
      }

      return refRootElement.value?.offsetWidth ?? 0;
    };

    const calcItemEllipsis = () => {
      if (isInputFocused.value) {
        return Promise.resolve(true);
      }

      hiddenItemCount.value = 0;
      hiddenItemIndex.value.length = 0;
      hiddenItemIndex.value = [];

      return new Promise((resolve) => {
        nextTick(() => {
          const maxWidth = getMaxWidth();
          const { offsetHeight, scrollHeight } = (refRootElement.value ?? {}) as HTMLElement;
          if (offsetHeight < scrollHeight) {
            const childList = Array.from(refTagInputContainer.value.children ?? []);
            let width = 0;
            const avalibleWidth = maxWidth - closeTagWidth - inputWidth;

            childList.forEach((item: HTMLElement, index) => {
              if (!item.hasAttribute('data-ignore-element')) {
                const itemWidth = item.offsetWidth;
                width += itemWidth;

                if (avalibleWidth - width < lastTagWidth + inputWidth) {
                  hiddenItemIndex.value.push(index);
                  hiddenItemCount.value += 1;
                }
              }
            });

            resolve(true);
          }
        });
      });
    };

    if (props.foucsFixed) {
      fixedInstance = new PopInstanceUtil({
        refContent: () => {
          setFixedValueContent();
          return focusFixedElement;
        },
        arrow: false,
        tippyOptions: {
          appendTo: document.body,
          hideOnClick: true,
          placement: 'bottom-start',
          theme: 'log-pure-choice',
          offset: [0, -1],
          zIndex: props.zIndex,
          onShow: () => {
            isInputFocused.value = true;
            emit('toggle', true);
          },
          onShown: () => {
            fixedInstance.setIsShowing(false);

            nextTick(() => {
              autoFocusInput();
              setFixedOverflowY();
            });
          },

          onHide: () => {
            isInputFocused.value = false;
            emit('toggle', false);
          },
          onHidden: () => {
            fixedInstance.setIsShowing(false);
            handleEditInputBlur();
            nextTick(() => {
              calcItemEllipsis().then(() => {
                setFixedOverflowY();
              });
            });
          },
        },
      });

      const { addEvent } = useRetrieveEvent();
      addEvent(RetrieveEvent.GLOBAL_SCROLL, () => {
        if (isInputFocused.value && fixedInstance.isShown()) {
          fixedInstance.hide();
        }
      });
    }

    const cloneFixedItem = () => {
      updateFiexedInstanceContent().then(() => {
        if (!fixedInstance.isShown()) {
          fixedInstance.show(refFixedPointerElement.value, true, true);
        }
      });
    };

    const execContainerClick = () => {
      isInputFocused.value = true;

      if (hiddenItemCount.value > 0) {
        calcItemEllipsis().then(() => {
          if (props.foucsFixed) {
            cloneFixedItem();
            return;
          }

          popInstance.show(refRootElement.value);
          refTagInputElement.value?.focus();
        });

        return;
      }

      if (props.foucsFixed) {
        cloneFixedItem();
        return;
      }

      popInstance.show(refRootElement.value);
      refTagInputElement.value?.focus();
    };

    const handleSelectedValueItemclick = (e: MouseEvent, item, index) => {
      if (!item.__tag_input__) {
        const target = e.target as HTMLElement;
        editItemOption.value.index = index;
        editItemOption.value.width = target.parentElement.offsetWidth;
        inputTagValue.value = getListItemId(item);

        nextTick(execContainerClick);
      }
    };

    const clearInputTag = () => {
      (refTagInputElement.value as HTMLInputElement).value = '';
      inputTagValue.value = '';
    };

    const handleContainerClick = (e: MouseEvent) => {
      stopDefaultPrevented(e);
      execContainerClick();
    };

    watch(
      () => [props.value],
      () => {
        if (isInputFocused.value && props.foucsFixed) {
          updateFiexedInstanceContent();
          autoFocusInput();
          return;
        }

        calcItemEllipsis().then(() => {
          autoFocusInput();
        });
      },
    );

    watch(
      () => [isInputFocused.value],
      () => {
        if (isInputFocused.value) {
          emit('focus', isInputFocused.value);
          return;
        }

        emit('blur', isInputFocused.value);
      },
    );

    onMounted(() => {
      containerWidth.value = refRootElement.value.offsetWidth;
      calcItemEllipsis();
    });

    onUnmounted(() => {
      popInstance?.uninstallInstance();
      fixedInstance?.uninstallInstance();
      fixedInstance = null;
    });

    const rootStyle = computed(() => {
      return {
        '--bklog-choice-min-width': props.minWidth ?? '120px',
        '--bklog-choice-max-width': props.maxWidth ?? '120px',
        '--bklog-choice-max-height': props.maxHeight ?? '100%',
        '--bklog-choice-min-height': props.minHeight,
        '--bklog-choice-focus-border-color': props.focusBorderColor,
        '--bklog-choice-border-color': props.borderColor,
      };
    });

    const valueTagStyle = computed(() => {
      return {
        maxWidth: props.valueTagMaxWidth,
      };
    });

    const renderInputTag = () => {
      return (
        <div
          class={[
            'bklog-choice-list-item',
            'custom-tag',
            {
              'is-hidden': inputTagValue.value.length === 0 || editItemOption.value.index !== null,
              'is-active': activeItemIndex.value === null,
            },
          ]}
          onClick={handleCustomTagClick}
          onMouseenter={() => handleOptionItemMouseenter(null)}
          onMouseleave={() => handleOptionItemMouseleave()}
        >
          {t('生成“{n}”标签', { n: inputTagValue.value })}
        </div>
      );
    };

    const renderOptionList = () => {
      if (props.template === 'tag-input') {
        return;
      }

      if (!optionList.value.length) {
        return <div class='empty-row'>{t('暂无数据')}</div>;
      }

      return optionList.value.map(({ item, selected }, index) => {
        const name = getListItemName(item);
        return (
          <div
            key={`${index}-${item}`}
            class={['bklog-choice-list-item', { 'is-selected': selected }]}
            title={name}
            onClick={() => handleOptionItemClick(item)}
            onMouseenter={() => handleOptionItemMouseenter(index)}
            onMouseleave={() => handleOptionItemMouseleave()}
          >
            {slots.item?.(item) ?? getListItemName(item)}
          </div>
        );
      });
    };

    const getValueContext = (item, index) => {
      if (editItemOption.value.index === index) {
        return (
          <input
            style={{ width: `${editItemOption.value.width}px` }}
            class='bklog-choice-value-edit-input'
            value={inputTagValue.value}
            data-bklog-choice-value-edit-input
            onInput={handleEditInputChange}
            onBlur={handleEditInputBlurEvent}
            onKeyup={handleEditInputKeyup}
            onKeydown={(e) => {
              // 阻止事件冒泡，避免触发容器的点击事件
              e.stopPropagation();
            }}
          />
        );
      }

      const name = getListItemName(item);
      return [
        <bdi
          key={`${index}-${name}`}
          class='bklog-choice-value-span'
          title={name}
          onClick={e => handleSelectedValueItemclick(e, item, index)}
        >
          {name}
        </bdi>,
        <i
          key={`${index}-${name}-close`}
          class='bklog-icon bklog-close'
          data-bklog-choice-item-del={index}
          onClick={e => handleDeleteItemClick(e, item)}
        />,
      ];
    };

    const renderValueList = () => {
      return valueWithInputList.value.map((item: any, index) => {
        if (item?.__tag_input__) {
          return (
            <li
              key='__tag_input__'
              class={[
                'bklog-choice-value-item tag-input',
                {
                  'is-hidden':
                    editItemOption.value.index !== null || (hiddenItemCount.value > 0 && !isInputFocused.value),
                },
              ]}
              data-ignore-element='true'
              data-item-index={index}
              data-w-hidden='false'
            >
              <input
                ref={refTagInputElement}
                style={tagInputStyle.value}
                type='text'
                data-bklog-choice-text-input
                onInput={handleInputValueChange}
                onKeydown={handleInputKeydown}
                onKeyup={handleInputKeyup}
              />
            </li>
          );
        }

        const tagAttrs = props.onTagRender?.(item, index) ?? {};

        tagAttrs.style = { ...tagAttrs.style, ...valueTagStyle.value };
        tagAttrs.class = [
          ...(tagAttrs.class ?? []),
          'bklog-choice-value-item',
          {
            'is-edit-item': editItemOption.value.index === index,
          },
        ];

        return (
          <li
            key={getItemKey(item, index)}
            data-item-index={index}
            data-w-hidden={hiddenItemIndex.value.includes(index) && !isInputFocused.value}
            dir={props.bdiDir}
            {...tagAttrs}
          >
            {getValueContext(item, index)}
          </li>
        );
      });
    };

    const getTagOptionsRender = () => {
      if (props.template === 'tag-input') {
        return null;
      }

      return [
        renderInputTag(),
        <div
          key='bklog-choice-value'
          class='bklog-choice-value-container'
          v-bkloading={{ isLoading: props.loading, size: 'small' }}
        >
          {renderOptionList()}
        </div>,
      ];
    };

    const getDropdownRender = () => {
      if (props.template === 'tag-choice') {
        return <span class={[dropdownIconName.value, 'bklog-choice-dropdown-icon']} />;
      }

      return null;
    };

    return () => (
      <div
        ref={refRootElement}
        style={rootStyle.value}
        class={[
          'bklog-tag-choice-container',
          {
            'is-focus': isInputFocused.value,
            'is-choice-active': isInputFocused.value,
            'has-hidden-item': hiddenItemCount.value > 0,
            'is-focus-fixed': props.foucsFixed,
            'is-ellipsis': isFixedOverflowY.value,
            template: props.template,
          },
        ]}
        onClick={handleContainerClick}
      >
        <span
          ref={refFixedPointerElement}
          class='hidden-fixed-pointer'
        />
        <ul
          ref={refTagInputContainer}
          style={rootStyle.value}
          class={[
            'bklog-tag-choice-input',
            props.template,
            { 'is-focus': isInputFocused.value, 'is-ellipsis': isFixedOverflowY.value },
          ]}
          data-placeholder={placeholderText.value}
        >
          {renderValueList()}
          <li
            class={['bklog-choice-value-item', { 'is-hidden': hiddenItemCount.value === 0 || isInputFocused.value }]}
            data-ignore-element
          >
            +{hiddenItemCount.value}
          </li>
        </ul>
        {getDropdownRender()}
        <span
          class='bk-icon icon-close-circle-shape delete-all-tags'
          onClick={handleDeleteAllClick}
        />
        <div v-show={false}>
          <div
            ref={refChoiceList}
            style={containerStyle.value}
            class='bklog-tag-choice-list'
          >
            {getTagOptionsRender()}
          </div>
        </div>
      </div>
    );
  },
});
