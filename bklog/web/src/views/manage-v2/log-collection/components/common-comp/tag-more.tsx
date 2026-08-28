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
/** biome-ignore-all lint/style/useForOf: 需要使用索引进行精确控制 */
import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch, type Ref, type VNode } from 'vue';

import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import $http from '@/api';
import useStore from '@/hooks/use-store';
import { showMessage } from '../../utils';

import './tag-more.scss';
import { t } from '@/hooks/use-locale';

/**
 * 标签项数据结构
 */
export type ITagItem = {
  id?: number | string;
  name: string;
  tag_id?: number;
  color?: string;
  is_built_in?: boolean;
  [key: string]: unknown;
};

export type ITagMoreContentBounds = {
  height: number;
  left: number;
  top: number;
  width: number;
};

export type ITagMoreTriggerSlotData = {
  content: VNode[];
  contentBounds: ITagMoreContentBounds | null;
  disabled: boolean;
  isEmpty: boolean;
  isOpen: boolean;
  triggerRef: Ref<HTMLDivElement | undefined>;
};

/**
 * 标签组件属性定义
 */
export type ITagMoreProps = {
  /** 自定义class */
  className?: string;
  /** tag之间的间距，默认8px */
  gap?: number;
  /** 每个tag的最大宽度，默认128px */
  maxTagWidth: number;
  /** 最大展示行数，默认1行 */
  maxRows?: number;
  /** 模式：index-set（所属索引集）| label（标签） */
  mode?: 'index-set' | 'label';
  /** 行数据，标签模式下需要 index_set_id 和 status */
  rowData?: Record<string, unknown>;
  /** 全量标签列表，标签模式下使用 */
  selectLabelList?: ITagItem[];
  /** 是否显示tooltip，默认true */
  showTooltip?: boolean;
  /** 标签列表 */
  tags: ITagItem[];
  /** tooltip标题 */
  title?: string;
  /** tooltip位置 */
  tooltipPlacement?: 'bottom' | 'left' | 'right' | 'top';
};

/**
 * 防抖延迟时间（毫秒）
 */
const DEBOUNCE_DELAY = 50;

export default defineComponent({
  props: {
    className: {
      default: '',
      type: String,
    },
    title: {
      default: '',
      type: String,
    },
    gap: {
      default: 8,
      type: Number,
    },
    maxTagWidth: {
      default: 128,
      type: Number,
    },
    maxRows: {
      default: 1,
      type: Number,
    },
    mode: {
      default: 'index-set',
      type: String as () => 'index-set' | 'label',
    },
    rowData: {
      default: () => ({}),
      type: Object as () => Record<string, unknown>,
    },
    selectLabelList: {
      default: () => [],
      type: Array as () => ITagItem[],
    },
    showTooltip: {
      default: true,
      type: Boolean,
    },
    tags: {
      default: () => [],
      type: Array as () => ITagItem[],
    },
    tooltipPlacement: {
      default: 'bottom',
      type: String as () => 'bottom' | 'left' | 'right' | 'top',
    },
  },

  emits: ['refresh-label-list', 'update-tags'],

  setup(props: ITagMoreProps, { emit, slots }) {
    const store = useStore();

    // DOM引用
    const containerRef = ref<HTMLDivElement>(); // 主容器引用
    const measureRef = ref<HTMLDivElement>(); // 隐藏的测量容器引用
    const tipsPanelRef = ref<HTMLDivElement>(); // tooltip内容面板引用

    // 状态管理
    const visibleTags = ref<ITagItem[]>([]); // 当前可见的标签列表
    const hiddenCount = ref(0); // 隐藏的标签数量
    const contentBounds = ref<ITagMoreContentBounds | null>(null);
    let resizeObserver: ResizeObserver | undefined; // 容器尺寸监听器
    let contentResizeObserver: ResizeObserver | undefined;
    let measureAnimationFrame: number | undefined;
    let shouldRefreshObservedElements = false;

    // 标签模式相关状态
    const isHover = ref(false); // 鼠标是否悬停在容器上
    const isSelectOpen = ref(false); // select弹窗是否打开
    const isShowNewGroupInput = ref(false); // 是否显示新增标签输入框
    const verifyData = ref({ labelEditName: '' }); // 新增标签表单数据
    const selectedLabelId = ref<number | string>(''); // 标签选择器的临时选中值
    const tagSelectRef = ref(null); // Select组件引用
    const checkInputFormRef = ref(null); // Form组件引用
    const labelEditInputRef = ref(null); // 新增标签输入框引用

    /** 是否为标签模式 */
    const isLabelMode = computed(() => props.mode === 'label');
    /** 是否由调用方提供选择器触发者 */
    const hasCustomTrigger = computed(() => !!slots.trigger);

    /** 是否禁用添加标签（terminated 状态） */
    const isDisabledAddNewTag = computed(() => props.rowData?.status === 'terminated');

    /** 过滤掉内置标签的列表 */
    const filterBuiltInList = computed(() => (props.selectLabelList || []).filter(item => !item.is_built_in));

    /** 内置标签的列表 */
    const builtInList = computed(() => (props.selectLabelList || []).filter(item => item.is_built_in));

    /** 索引集展示的标签（过滤掉内置标签） */
    const showLabelList = computed(() => {
      const showIDlist = filterBuiltInList.value.map(item => item.tag_id);
      return (props.tags || []).filter(item => showIDlist.includes(item.tag_id));
    });

    /** 单选框标签下拉列表（已选中的置灰） */
    const showGroupSelectLabelList = computed(() => {
      const propIDlist = (props.tags || []).map(item => item.tag_id);
      return filterBuiltInList.value.map(item => ({
        ...item,
        disabled: propIDlist.includes(item.tag_id),
      }));
    });

    /** 校验标签名是否重复 */
    const checkTagName = () => {
      return !showGroupSelectLabelList.value.some(item => item.name === verifyData.value.labelEditName.trim());
    };

    /** 校验是否为内置标签名 */
    const checkBuiltInTagName = () => {
      return !builtInList.value.some(item => item.name === verifyData.value.labelEditName.trim());
    };

    const rules = {
      labelEditName: [
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
        {
          validator: checkTagName,
          message: t('已有同名标签'),
          trigger: 'blur',
        },
        {
          validator: checkBuiltInTagName,
          message: t('内置标签名，请重新填写'),
          trigger: 'blur',
        },
      ],
    };

    /** 给索引集添加标签 */
    const addLabelToIndexSet = (tagID: number) => {
      if (!tagID) return;
      $http
        .request('unionSearch/unionAddLabel', {
          params: { index_set_id: props.rowData?.index_set_id },
          data: { tag_id: tagID },
        })
        .then(() => {
          const newLabel = (props.selectLabelList || []).find(item => item.tag_id === tagID);
          if (newLabel) {
            const updatedTags = [...(props.tags || []), newLabel];
            emit('update-tags', updatedTags);
          }
          showMessage(t('操作成功'), 'success');
        })
        .finally(() => {
          selectedLabelId.value = '';
        });
    };

    /** 删除采集项的标签 */
    const handleDeleteTag = (tagID: number) => {
      $http
        .request('unionSearch/unionDeleteLabel', {
          params: { index_set_id: props.rowData?.index_set_id },
          data: { tag_id: tagID },
        })
        .then(() => {
          const updatedTags = (props.tags || []).filter(item => item.tag_id !== tagID);
          emit('update-tags', updatedTags);
          selectedLabelId.value = '';
          showMessage(t('操作成功'), 'success');
        });
    };

    /** 新增标签 */
    const handleChangeLabelStatus = (operate: string) => {
      if (operate === 'add') {
        checkInputFormRef.value?.validate().then(
          () => {
            $http
              .request('unionSearch/unionCreateLabel', {
                data: { name: verifyData.value.labelEditName.trim(), space_uid: store.state.spaceUid },
              })
              .then(res => {
                emit('refresh-label-list');
                addLabelToIndexSet(res.data.tag_id);
              })
              .finally(() => {
                verifyData.value.labelEditName = '';
                isShowNewGroupInput.value = false;
                tagSelectRef.value?.close();
              });
          },
          () => {},
        );
      } else {
        isShowNewGroupInput.value = false;
      }
    };

    const handleLabelKeyDown = (val: string) => {
      if (val) handleChangeLabelStatus('add');
    };

    const toggleSelect = (val: boolean) => {
      isSelectOpen.value = val;
      if (!val) {
        isHover.value = false;
        isShowNewGroupInput.value = false;
        verifyData.value.labelEditName = '';
      }
    };

    // Tippy实例
    let tippyInstance: Instance | null = null;

    /**
     * 缓存测量用的DOM元素，避免频繁创建和删除
     * 用于准确测量标签和指示器的实际宽度
     */
    const measureSpans: {
      tag: HTMLSpanElement | null;
      indicator: HTMLSpanElement | null;
    } = {
      tag: null,
      indicator: null,
    };

    /**
     * 初始化测量用的DOM元素
     * 在隐藏容器中创建用于测量的span元素，这些元素不会被用户看到
     */
    const initMeasureElements = () => {
      if (!measureRef.value) {
        return;
      }

      // 创建标签测量元素
      if (!measureSpans.tag) {
        const span = document.createElement('span');
        span.className = 'tag-item';
        span.style.display = 'inline-block';
        measureRef.value.appendChild(span);
        measureSpans.tag = span;
      }

      // 创建指示器测量元素
      if (!measureSpans.indicator) {
        const span = document.createElement('span');
        span.className = 'tag-more-indicator';
        span.style.display = 'inline-block';
        measureRef.value.appendChild(span);
        measureSpans.indicator = span;
      }
    };

    /**
     * 测量标签的实际宽度
     * @param text - 标签文本内容
     * @returns 标签宽度（不超过maxTagWidth）
     */
    const measureItemWidth = (text: string): number => {
      if (!measureSpans.tag) {
        return props.maxTagWidth;
      }

      measureSpans.tag.textContent = text;
      const naturalWidth = measureSpans.tag.offsetWidth;
      return Math.min(naturalWidth, props.maxTagWidth);
    };

    /**
     * 测量指示器的实际宽度
     * @param count - 隐藏标签的数量
     * @returns 指示器宽度
     */
    const measureIndicatorWidth = (count: number): number => {
      if (!measureSpans.indicator) {
        return 0;
      }

      measureSpans.indicator.textContent = `+${count}`;
      return measureSpans.indicator.offsetWidth;
    };

    /** 按顺序模拟 flex 换行，判断所有元素是否能在限定行数内放下 */
    const canFitInRows = (itemWidths: number[], rowWidth: number, maxRows: number) => {
      let currentRowWidth = 0;
      let rowCount = 1;

      for (const itemWidth of itemWidths) {
        if (itemWidth > rowWidth) {
          return false;
        }
        if (currentRowWidth + itemWidth <= rowWidth) {
          currentRowWidth += itemWidth;
          continue;
        }
        rowCount += 1;
        currentRowWidth = itemWidth;
        if (rowCount > maxRows) {
          return false;
        }
      }
      return true;
    };

    /**
     * 计算可见标签数量和隐藏标签数量。
     * 从“全部展示”开始逐步减少标签，直到标签、+N 和标签模式操作按钮能够在限定行数内放下。
     */
    const calculateVisibleTags = () => {
      // 标签模式下使用过滤后的标签列表
      const tagList = isLabelMode.value ? showLabelList.value : props.tags;

      // 边界情况处理
      if (!containerRef.value || tagList.length === 0) {
        visibleTags.value = tagList;
        hiddenCount.value = 0;
        return;
      }

      const containerStyle = window.getComputedStyle(containerRef.value);
      const horizontalPadding =
        Number.parseFloat(containerStyle.paddingLeft) + Number.parseFloat(containerStyle.paddingRight);
      const containerWidth = Math.max(0, containerRef.value.clientWidth - horizontalPadding);
      const maxRows = Math.max(1, Math.floor(props.maxRows || 1));
      const gap = props.gap;
      const tagWidths = tagList.map(tag => measureItemWidth(tag.name));

      for (let visibleCount = tagList.length; visibleCount >= 1; visibleCount -= 1) {
        const remainingCount = tagList.length - visibleCount;
        const itemWidths = tagWidths.slice(0, visibleCount).map((width, index) => {
          const hasNextTagOrIndicator = index < visibleCount - 1 || remainingCount > 0;
          return width + (hasNextTagOrIndicator ? gap : 0);
        });

        if (remainingCount > 0) {
          itemWidths.push(measureIndicatorWidth(remainingCount));
        }
        // 标签模式始终将添加按钮作为最后一个布局项（24px + 4px 左间距）。
        if (isLabelMode.value && !hasCustomTrigger.value) {
          itemWidths.push(28);
        }

        if (canFitInRows(itemWidths, containerWidth, maxRows)) {
          visibleTags.value = tagList.slice(0, visibleCount);
          hiddenCount.value = remainingCount;
          return;
        }
      }

      // 极窄容器下仍保证至少展示第一个标签，与原有行为保持一致。
      visibleTags.value = tagList.slice(0, 1);
      hiddenCount.value = Math.max(0, tagList.length - 1);
    };

    /** 获取参与触发框视觉区域测量的可见内容节点。 */
    const getVisibleContentElements = () => {
      if (!containerRef.value || !hasCustomTrigger.value) {
        return [];
      }
      return Array.from(
        containerRef.value.querySelectorAll<HTMLElement>('.tag-item, .tag-more-indicator, .tag-more-empty'),
      ).filter(element => !element.closest('.measure-box') && element.getClientRects().length > 0);
    };

    /** 根据浏览器实际布局结果更新标签内容区域，不参与可见标签数量计算。 */
    const updateContentBounds = () => {
      const container = containerRef.value;
      const elements = getVisibleContentElements();
      if (!container || elements.length === 0) {
        contentBounds.value = null;
        return;
      }

      const containerRect = container.getBoundingClientRect();
      const elementRects = elements.map(element => element.getBoundingClientRect());
      const left = Math.min(...elementRects.map(rect => rect.left));
      const top = Math.min(...elementRects.map(rect => rect.top));
      const right = Math.max(...elementRects.map(rect => rect.right));
      const bottom = Math.max(...elementRects.map(rect => rect.bottom));
      const nextBounds = {
        height: bottom - top,
        left: left - containerRect.left,
        top: top - containerRect.top,
        width: right - left,
      };
      const currentBounds = contentBounds.value;
      if (
        !currentBounds ||
        Object.keys(nextBounds).some(key => {
          const name = key as keyof ITagMoreContentBounds;
          return Math.abs(nextBounds[name] - currentBounds[name]) > 0.1;
        })
      ) {
        contentBounds.value = nextBounds;
      }
    };

    /** 同步监听标签节点尺寸，覆盖删除图标显示等不改变外层尺寸的场景。 */
    const observeContentElements = () => {
      if (!contentResizeObserver) {
        return;
      }
      contentResizeObserver.disconnect();
      getVisibleContentElements().forEach(element => contentResizeObserver?.observe(element));
    };

    const scheduleContentBoundsMeasure = (refreshObservedElements = false) => {
      if (!hasCustomTrigger.value) {
        return;
      }
      shouldRefreshObservedElements = shouldRefreshObservedElements || refreshObservedElements;
      nextTick(() => {
        if (measureAnimationFrame !== undefined) {
          window.cancelAnimationFrame(measureAnimationFrame);
        }
        measureAnimationFrame = window.requestAnimationFrame(() => {
          updateContentBounds();
          if (shouldRefreshObservedElements) {
            observeContentElements();
            shouldRefreshObservedElements = false;
          }
          measureAnimationFrame = undefined;
        });
      });
    };

    const calculateAndMeasure = () => {
      calculateVisibleTags();
      scheduleContentBoundsMeasure(true);
    };

    /**
     * 防抖函数：避免频繁触发计算
     * 在短时间内多次调用时，只执行最后一次
     * @returns 防抖后的计算函数
     */
    const debouncedCalculate = (() => {
      let timeout: null | number = null;
      const fn = () => {
        if (timeout) {
          window.clearTimeout(timeout);
        }
        timeout = window.setTimeout(() => {
          calculateAndMeasure();
          timeout = null;
        }, DEBOUNCE_DELAY);
      };
      fn.cancel = () => {
        if (timeout) {
          window.clearTimeout(timeout);
          timeout = null;
        }
      };
      return fn;
    })();

    /**
     * 初始化Tooltip弹窗
     * 使用tippy.js创建交互式提示框，显示所有标签列表
     */
    const initActionPop = () => {
      if (
        tippyInstance ||
        !(props.showTooltip && containerRef.value && tipsPanelRef.value) ||
        (hasCustomTrigger.value && isDisabledAddNewTag.value)
      ) {
        return;
      }

      tippyInstance = tippy(containerRef.value as SingleTarget, {
        content: tipsPanelRef.value as HTMLElement,
        placement: props.tooltipPlacement,
        interactive: true, // 允许用户与tooltip交互
        hideOnClick: true, // 点击后隐藏
        appendTo: () => document.body, // 挂载到body，避免被父容器裁剪
        // 定位锚点优先使用调用方渲染的触发框（.tag-more-trigger-frame），使 tooltip
        // 对齐实际内容区域的正下方；frame 不存在或未布局（display:none）时回退到容器。
        getReferenceClientRect: () => {
          const container = containerRef.value as HTMLElement;
          const frameRect = container?.querySelector('.tag-more-trigger-frame')?.getBoundingClientRect();
          if (frameRect && frameRect.width > 0 && frameRect.height > 0) {
            return frameRect;
          }
          return container.getBoundingClientRect();
        },
      });
    };

    /**
     * 组件挂载后的初始化
     * 1. 初始化测量元素
     * 2. 初始化tooltip
     * 3. 计算可见标签
     * 4. 监听容器尺寸变化
     */
    onMounted(() => {
      nextTick(() => {
        initMeasureElements();
        initActionPop();
        calculateAndMeasure();

        // 使用ResizeObserver监听容器尺寸变化，自动重新计算可见标签
        if (window.ResizeObserver) {
          resizeObserver = new ResizeObserver(debouncedCalculate);
          contentResizeObserver = new ResizeObserver(() => scheduleContentBoundsMeasure());
          if (containerRef.value) {
            resizeObserver.observe(containerRef.value);
          }
          observeContentElements();
        }
      });
    });

    /**
     * 组件卸载前的清理工作
     * 释放所有资源，避免内存泄漏
     */
    onBeforeUnmount(() => {
      // 清理防抖定时器
      debouncedCalculate.cancel();

      // 清理ResizeObserver
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = undefined;
      }
      if (contentResizeObserver) {
        contentResizeObserver.disconnect();
        contentResizeObserver = undefined;
      }
      if (measureAnimationFrame !== undefined) {
        window.cancelAnimationFrame(measureAnimationFrame);
        measureAnimationFrame = undefined;
      }

      // 清理tippy实例
      if (tippyInstance) {
        tippyInstance.destroy();
        tippyInstance = null;
      }

      // 清理测量元素
      if (measureRef.value) {
        measureRef.value.innerHTML = '';
      }
    });

    /**
     * 监听标签列表变化
     * 使用深度监听，当标签内容变化时重新计算可见标签
     */
    watch(
      () => props.tags,
      () => {
        nextTick(() => {
          debouncedCalculate();
          // 更新 tippy 内容
          if (tippyInstance && tipsPanelRef.value) {
            tippyInstance.setContent(tipsPanelRef.value);
          }
        });
      },
      { deep: true },
    );

    /**
     * 监听影响布局的属性变化
     * gap、maxTagWidth和maxRows的变化会影响标签布局，需要重新计算
     */
    watch([() => props.gap, () => props.maxTagWidth, () => props.maxRows], () => {
      nextTick(debouncedCalculate);
    });

    /**
     * 监听容器引用变化
     * 无标签切到有标签时 containerRef 从 undefined 变为有值，需要重新初始化
     */
    watch(containerRef, (newVal, oldVal) => {
      if (newVal && !oldVal) {
        nextTick(() => {
          initMeasureElements();
          if (!tippyInstance) {
            initActionPop();
          }
          calculateAndMeasure();
          if (window.ResizeObserver && resizeObserver && newVal) {
            resizeObserver.observe(newVal);
          }
        });
      }
    });

    /** 外置 trigger 时内容面板可能晚于 trigger 挂载，需要在面板就绪后初始化或更新 tooltip */
    watch(tipsPanelRef, newVal => {
      if (!newVal || !containerRef.value) {
        return;
      }
      nextTick(() => {
        if (tippyInstance) {
          tippyInstance.setContent(newVal);
        } else {
          initActionPop();
        }
      });
    });

    /**
     * tooltip 源标签数量：label 模式取过滤后的展示列表，索引集模式取原始 tags。
     * 按数量监听，避免 tags 数组引用变化（内容不变）导致 tippy 被误销毁。
     */
    const tooltipTagCount = computed(() =>
      isLabelMode.value ? showLabelList.value.length : (props.tags || []).length,
    );

    /**
     * 监听 tooltip 源标签数量变化
     * 有标签 → 无标签时，销毁 tippy 并清理状态；无标签 → 有标签时重建
     */
    watch(tooltipTagCount, newCount => {
      if (hasCustomTrigger.value) {
        nextTick(() => {
          if (newCount > 0 && !tippyInstance) {
            initActionPop();
          } else if (newCount === 0 && tippyInstance) {
            tippyInstance.destroy();
            tippyInstance = null;
          }
        });
        return;
      }
      if (isLabelMode.value && newCount === 0) {
        // 销毁 tippy 实例
        if (tippyInstance) {
          tippyInstance.destroy();
          tippyInstance = null;
        }
        // 停止监听旧容器
        if (resizeObserver && containerRef.value) {
          resizeObserver.unobserve(containerRef.value);
        }
      }
    });

    /**
     * 渲染标签模式下的添加按钮（Select 弹出层）
     */
    const renderLabelSelect = (trigger?: () => VNode) => {
      if (!isLabelMode.value) return null;
      return (
        <bk-select
          ref={tagSelectRef}
          class={{ 'tag-more-cell-select': hasCustomTrigger.value }}
          scopedSlots={{
            trigger:
              trigger ||
              (() => (
                <div
                  class={['tag-more-add-btn', { disabled: isDisabledAddNewTag.value }]}
                  v-bk-tooltips={{
                    disabled: !isDisabledAddNewTag.value,
                    content: t('停用状态下无法添加标签'),
                    delay: 300,
                  }}
                >
                  <i class='bk-icon icon-plus-line' />
                </div>
              )),
          }}
          disabled={isDisabledAddNewTag.value}
          popover-min-width={240}
          popover-options={{ boundary: 'window' }}
          searchable
          value={selectedLabelId.value}
          onInput={(value: number | string) => {
            selectedLabelId.value = value;
          }}
          on-selected={addLabelToIndexSet}
          onToggle={toggleSelect}
        >
          <div
            class='new-label-container'
            slot='extension'
          >
            {isShowNewGroupInput.value ? (
              <div class='new-label-input'>
                <bk-form
                  ref={checkInputFormRef}
                  style={{ width: '100%' }}
                  label-width={0}
                  {...{
                    props: {
                      model: verifyData.value,
                      rules,
                    },
                  }}
                >
                  <bk-form-item property='labelEditName'>
                    <bk-input
                      ref={labelEditInputRef}
                      value={verifyData.value.labelEditName}
                      on-change={(val: string) => (verifyData.value.labelEditName = val)}
                      clearable
                      onKeydown={(_: string, e: KeyboardEvent) => {
                        if (e.key === 'Enter') {
                          e.stopPropagation();
                          handleLabelKeyDown(verifyData.value.labelEditName);
                        }
                      }}
                    />
                  </bk-form-item>
                </bk-form>
                <div class='operate-button'>
                  <span
                    class='bk-icon icon-check-line'
                    onClick={() => handleChangeLabelStatus('add')}
                  />
                  <span
                    class='bk-icon icon-close-line-2'
                    onClick={() => handleChangeLabelStatus('cancel')}
                  />
                </div>
              </div>
            ) : (
              <div
                class='add-new-label'
                onClick={() => {
                  isShowNewGroupInput.value = true;
                  nextTick(() => {
                    labelEditInputRef.value?.focus();
                  });
                }}
              >
                <i class='bk-icon icon-plus-circle' />
                <span>{t('新增标签')}</span>
              </div>
            )}
          </div>
          <div class='group-list'>
            {showGroupSelectLabelList.value.map(item => (
              <bk-option
                id={item.tag_id}
                key={item.tag_id}
                class='label-option'
                disabled={item.disabled}
                name={item.name}
              />
            ))}
          </div>
        </bk-select>
      );
    };

    /** 渲染 Tooltip 内容面板 */
    const renderTipsPanel = (tagList: ITagItem[]) => (
      <div
        ref={tipsPanelRef}
        class='more-tips-panel'
      >
        {props.title && <div class='title'>{props.title}:</div>}
        <ul>
          {tagList.map((item, index) => (
            <li key={item.tag_id || item.id || index}>{item.name}</li>
          ))}
        </ul>
      </div>
    );

    /** 渲染隐藏的测量容器 */
    const renderMeasureBox = () => (
      <div
        ref={measureRef}
        class='measure-box'
      />
    );

    /** 渲染可见标签列表 */
    const renderTagList = () =>
      visibleTags.value.map((tag, index) => (
        <span
          key={tag.tag_id || tag.id || index}
          style={{
            maxWidth: `${props.maxTagWidth}px`,
            marginRight: index < visibleTags.value.length - 1 || hiddenCount.value > 0 ? `${props.gap}px` : '0',
          }}
          class={['tag-item', { 'tag-item-label': isLabelMode.value }]}
        >
          {isLabelMode.value
            ? [
                <span class='tag-item-name'>{tag.name}</span>,
                <i
                  class='bk-icon icon-close tag-item-close'
                  onMousedown={(event: MouseEvent) => event.stopPropagation()}
                  onClick={(event: MouseEvent) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (tag.tag_id) {
                      handleDeleteTag(tag.tag_id);
                    }
                  }}
                />,
              ]
            : tag.name}
        </span>
      ));

    /** 渲染隐藏标签数量指示器 */
    const renderIndicator = () =>
      hiddenCount.value > 0 && (
        <span
          style={{ marginLeft: '0' }}
          class='tag-more-indicator'
        >
          +{hiddenCount.value}
        </span>
      );

    /**
     * 渲染函数
     * 返回组件的JSX结构
     */
    return () => {
      const maxRows = Math.max(1, Math.floor(props.maxRows || 1));
      const containerClass = {
        'tag-more-multi-line': maxRows > 1,
      };
      const containerStyle = maxRows > 1 ? { maxHeight: `${maxRows * 22 + (maxRows - 1) * 4}px` } : undefined;

      if (hasCustomTrigger.value) {
        const renderCustomTrigger = () => {
          const tagList = isLabelMode.value ? showLabelList.value : props.tags;
          const content: VNode[] = [];
          if (tagList.length > 0) {
            content.push(renderTipsPanel(tagList));
          }
          content.push(renderMeasureBox());
          if (tagList.length > 0) {
            content.push(...renderTagList());
          } else {
            content.push(<span class='tag-more-empty'>--</span>);
          }
          const indicator = renderIndicator();
          if (indicator) {
            content.push(indicator);
          }

          const triggerNode = slots.trigger?.({
            content,
            contentBounds: contentBounds.value,
            disabled: isDisabledAddNewTag.value,
            isEmpty: tagList.length === 0,
            isOpen: isSelectOpen.value,
            triggerRef: containerRef,
          } as ITagMoreTriggerSlotData);
          return triggerNode?.[0] as VNode;
        };
        return isLabelMode.value ? renderLabelSelect(renderCustomTrigger) : renderCustomTrigger();
      }

      // 标签模式下：无标签数据时显示 -- 和添加按钮（hover切换显示）
      if (isLabelMode.value && showLabelList.value.length === 0) {
        const showAdd = isHover.value || isSelectOpen.value;
        return (
          <div
            key='label-empty'
            class={['tag-more-container tag-more-label-mode tag-more-label-empty', props.className]}
            onMouseenter={() => (isHover.value = true)}
            onMouseleave={() => {
              if (!isSelectOpen.value) {
                isHover.value = false;
              }
            }}
          >
            {!showAdd && <span class='tag-more-empty'>--</span>}
            <span class={['tag-more-add-wrap', { 'is-visible': showAdd }]}>{renderLabelSelect()}</span>
          </div>
        );
      }

      // 标签模式下：有标签数据
      if (isLabelMode.value) {
        return (
          <div
            key='label-has-tags'
            ref={containerRef}
            class={['tag-more-container tag-more-label-mode', containerClass, props.className]}
            style={containerStyle}
          >
            {renderTipsPanel(showLabelList.value)}
            {renderMeasureBox()}
            {renderTagList()}
            {renderIndicator()}
            {renderLabelSelect()}
          </div>
        );
      }

      // 索引集模式（默认）
      return (
        <div
          ref={containerRef}
          class={['tag-more-container', containerClass, props.className]}
          style={containerStyle}
        >
          {renderTipsPanel(props.tags)}
          {renderMeasureBox()}
          {renderTagList()}
          {renderIndicator()}
        </div>
      );
    };
  },
});
