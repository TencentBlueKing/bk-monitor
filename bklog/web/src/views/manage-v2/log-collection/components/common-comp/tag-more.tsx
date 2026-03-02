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
import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch, computed } from 'vue';

import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import $http from '@/api';
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

  setup(props: ITagMoreProps, { emit }) {
    // DOM引用
    const containerRef = ref<HTMLDivElement>(); // 主容器引用
    const measureRef = ref<HTMLDivElement>(); // 隐藏的测量容器引用
    const tipsPanelRef = ref<HTMLDivElement>(); // tooltip内容面板引用

    // 状态管理
    const visibleTags = ref<ITagItem[]>([]); // 当前可见的标签列表
    const hiddenCount = ref(0); // 隐藏的标签数量
    let resizeObserver: ResizeObserver | undefined; // 容器尺寸监听器

    // 标签模式相关状态
    const isHover = ref(false); // 鼠标是否悬停在容器上
    const isSelectOpen = ref(false); // select弹窗是否打开
    const isShowNewGroupInput = ref(false); // 是否显示新增标签输入框
    const verifyData = ref({ labelEditName: '' }); // 新增标签表单数据
    const tagSelectRef = ref(null); // Select组件引用
    const checkInputFormRef = ref(null); // Form组件引用
    const labelEditInputRef = ref(null); // 新增标签输入框引用

    /** 是否为标签模式 */
    const isLabelMode = computed(() => props.mode === 'label');

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
                data: { name: verifyData.value.labelEditName.trim() },
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

    /**
     * 计算可见标签数量和隐藏标签数量
     * 使用贪心算法：尽可能多地显示标签，同时确保指示器能够放下
     *
     * 算法流程：
     * 1. 快速路径：如果所有标签的最小宽度总和小于容器宽度，全部显示
     * 2. 测量每个标签的实际宽度
     * 3. 贪心算法：尽可能多地放置标签
     * 4. 调整：如果放不下指示器，减少可见标签数量
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

      // 标签模式下需要预留添加按钮的空间（按钮24px + select margin-left 4px）
      // 以及删除按钮空间（icon 18px + margin-left 2px）
      const addBtnReserved = isLabelMode.value ? 28 : 0;
      const closeBtnWidth = isLabelMode.value ? 20 : 0;
      const containerWidth = containerRef.value.offsetWidth - addBtnReserved - closeBtnWidth;
      const gap = props.gap;

      // 快速路径：计算所有标签的最小宽度总和（使用maxTagWidth）
      // 如果这个总和小于容器宽度，说明所有标签都能放下
      const totalMinWidth = tagList.length * props.maxTagWidth + (tagList.length - 1) * gap;
      if (totalMinWidth <= containerWidth) {
        visibleTags.value = tagList;
        hiddenCount.value = 0;
        return;
      }

      // 预先测量每个标签的实际宽度（受maxTagWidth限制）
      const tagWidths = tagList.map(tag => measureItemWidth(tag.name));

      // 贪心算法：尽可能多地放置标签
      let usedWidth = 0; // 已使用的宽度
      let visibleCount = 0; // 可见标签数量

      for (let i = 0; i < tagWidths.length; i++) {
        // 计算放置当前标签所需的总宽度（包括间距）
        const spacing = visibleCount > 0 ? gap : 0; // 第一个标签不需要左边距
        const requiredWidth = usedWidth + spacing + tagWidths[i];

        if (requiredWidth <= containerWidth) {
          usedWidth = requiredWidth;
          visibleCount += 1;
        } else {
          // 当前标签放不下，停止循环
          break;
        }
      }

      // 如果所有标签都能放下，直接返回
      if (visibleCount >= tagList.length) {
        visibleTags.value = tagList;
        hiddenCount.value = 0;
        return;
      }

      // 确保至少显示1个标签
      visibleCount = Math.max(1, visibleCount);
      let remainingCount = tagList.length - visibleCount;
      let indicatorWidth = measureIndicatorWidth(remainingCount);

      // 计算放置指示器所需的总宽度
      let totalRequired = usedWidth + gap + indicatorWidth;

      // 如果放不下指示器，需要减少可见标签数量
      // 循环调整直到能够放下指示器，或只剩下1个可见标签
      while (visibleCount > 1 && totalRequired > containerWidth) {
        visibleCount -= 1;
        remainingCount = tagList.length - visibleCount;

        // 重新计算已使用宽度（基于实际可见的标签）
        usedWidth = tagWidths
          .slice(0, visibleCount)
          .reduce((sum, width, index) => sum + width + (index > 0 ? gap : 0), 0);

        // 重新测量指示器宽度（因为隐藏数量变化了）
        indicatorWidth = measureIndicatorWidth(remainingCount);
        totalRequired = usedWidth + gap + indicatorWidth;
      }

      // 最终赋值
      visibleTags.value = tagList.slice(0, visibleCount);
      hiddenCount.value = remainingCount;
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
          calculateVisibleTags();
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
      if (!(props.showTooltip && containerRef.value)) {
        return;
      }

      tippyInstance = tippy(containerRef.value as SingleTarget, {
        content: tipsPanelRef.value as HTMLElement,
        placement: props.tooltipPlacement,
        interactive: true, // 允许用户与tooltip交互
        hideOnClick: true, // 点击后隐藏
        appendTo: () => document.body, // 挂载到body，避免被父容器裁剪
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
        calculateVisibleTags();

        // 使用ResizeObserver监听容器尺寸变化，自动重新计算可见标签
        if (window.ResizeObserver) {
          resizeObserver = new ResizeObserver(debouncedCalculate);
          if (containerRef.value) {
            resizeObserver.observe(containerRef.value);
          }
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
     * gap和maxTagWidth的变化会影响标签布局，需要重新计算
     */
    watch([() => props.gap, () => props.maxTagWidth], () => {
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
          calculateVisibleTags();
          if (window.ResizeObserver && resizeObserver && newVal) {
            resizeObserver.observe(newVal);
          }
        });
      }
    });

    /**
     * 监听标签模式下展示标签列表变化
     * 有标签 → 无标签时，销毁 tippy 并清理状态
     */
    watch(showLabelList, (newList) => {
      if (isLabelMode.value && newList.length === 0) {
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
    const renderLabelSelect = () => {
      if (!isLabelMode.value) return null;
      return (
        <bk-select
          ref={tagSelectRef}
          scopedSlots={{
            trigger: () => (
              <div
                class={[
                  'tag-more-add-btn',
                  { disabled: isDisabledAddNewTag.value },
                ]}
                v-bk-tooltips={{
                  disabled: !isDisabledAddNewTag.value,
                  content: t('停用状态下无法添加标签'),
                  delay: 300,
                }}
              >
                <i class='bk-icon icon-plus-line' />
              </div>
            ),
          }}
          disabled={isDisabledAddNewTag.value}
          popover-min-width={240}
          popover-options={{ boundary: 'window', distance: 30 }}
          searchable
          on-selected={addLabelToIndexSet}
          on-toggle={toggleSelect}
        >
          <div class='new-label-container' slot='extension'>
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
    const renderMeasureBox = () => <div ref={measureRef} class='measure-box' />;

    /** 渲染可见标签列表 */
    const renderTagList = () => visibleTags.value.map((tag, index) => (
        <span
          key={tag.tag_id || tag.id || index}
          style={{
            maxWidth: `${props.maxTagWidth}px`,
            marginRight: index < visibleTags.value.length - 1 ? `${props.gap}px` : '0',
          }}
          class={['tag-item', { 'tag-item-label': isLabelMode.value }]}
        >
          {isLabelMode.value
            ? [
                <span class='tag-item-name'>{tag.name}</span>,
                <i
                  class='bk-icon icon-close tag-item-close'
                  onClick={() => tag.tag_id && handleDeleteTag(tag.tag_id)}
                />,
            ]
            : tag.name}
        </span>
    ));

    /** 渲染隐藏标签数量指示器 */
    const renderIndicator = () => hiddenCount.value > 0 && (
        <span
          style={{ marginLeft: visibleTags.value.length > 0 ? `${props.gap}px` : '0' }}
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
            <span class={['tag-more-add-wrap', { 'is-visible': showAdd }]}>
              {renderLabelSelect()}
            </span>
          </div>
        );
      }

      // 标签模式下：有标签数据
      if (isLabelMode.value) {
        return (
          <div
            key='label-has-tags'
            ref={containerRef}
            class={['tag-more-container tag-more-label-mode', props.className]}
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
          class={['tag-more-container', props.className]}
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
