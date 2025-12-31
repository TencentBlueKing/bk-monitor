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

import { defineComponent, computed, ref, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import LabelChooseDialog from './label-choose-dialog';
import LabelItemChoose from './label-item-choose';
import type { IContainerConfigItem, IValueItem, IClusterItem } from '../../../../type';

import './config-log-set-edit-item.scss';

/**
 * ConfigLogSetEditItem 组件
 * 用于配置日志设置中的编辑项，支持标签选择和注解选择
 */
export default defineComponent({
  name: 'ConfigLogSetEditItem',
  props: {
    // 编辑类型，必填
    editType: {
      type: String,
      required: true,
    },
    // 配置对象，必填
    config: {
      type: Object as PropType<IContainerConfigItem>,
      required: true,
    },
    // 是否为节点类型，必填
    isNode: {
      type: Boolean,
      required: true,
    },
    bcsClusterId: {
      type: String,
      default: '',
    },
    clusterList: {
      type: Array as PropType<IClusterItem[]>,
      default: () => [],
    },
  },
  // 定义组件可触发的事件
  emits: ['change', 'show-dialog', 'delete-config-params-item'],
  setup(props, { emit }) {
    // 使用国际化翻译函数
    const { t } = useLocale();

    const store = useStore();

    // 控制编辑状态
    const handleEdit = ref(false);

    const isShowDialog = ref(false);

    /**
     * 去重函数：基于 key、operator 和 value 进行去重
     * @param items 需要去重的数组
     * @returns 去重后的数组
     */
    const deduplicateItems = (items: IValueItem[]): IValueItem[] => {
      const seen = new Set<string>();
      return items.filter(item => {
        const key = `${item.key}|${item.operator}|${item.value || ''}`;
        if (seen.has(key)) {
          return false;
        }
        seen.add(key);
        return true;
      });
    };

    // 规范化选择器：将 match_labels 合并进 match_expressions 并移除 match_labels
    const normalizeSelector = (selector: Record<string, any>) => {
      if (!selector) {
        return {};
      }
      if (props.editType === 'label_selector' && Array.isArray(selector.match_labels) && selector.match_labels.length) {
        const matchExpressions = (selector.match_expressions as IValueItem[]) || [];
        const matchLabels = (selector.match_labels as IValueItem[]).map(item => ({
          ...item,
          operator: item.operator === '=' ? 'In' : item.operator,
        }));
        const merged = deduplicateItems([...matchExpressions, ...matchLabels]);
        const { match_labels: _omit, ...rest } = selector;
        return { ...rest, match_expressions: merged } satisfies Record<string, any>;
      }
      return { ...selector } satisfies Record<string, any>;
    };

    // 缓存配置数据（初始化时即进行规范化处理）
    const cacheConfig = ref(normalizeSelector({ ...props.config[props.editType] }) || {});

    // 计算属性：是否为标签编辑
    const isLabelEdit = computed(() => props.editType === 'label_selector');
    const bkBizId = computed(() => store.getters.bkBizId);

    // 计算属性：获取对应的键名（match_expressions 或 match_annotations）
    const typeKeys = computed(() => (isLabelEdit.value ? 'match_expressions' : 'match_annotations'));

    const currentSelector = computed(() => ({
      bk_biz_id: bkBizId.value,
      bcs_cluster_id: props.bcsClusterId,
      type: props.isNode ? 'node' : 'pod',
      namespaceStr: Array.isArray(props.config?.namespaces) ? (props.config.namespaces as string[]).join(',') : '',
      labelSelector: props.config?.label_selector || {},
    }));

    /**
     * 删除配置参数项
     */
    const handleDeleteConfigParamsItem = () => {
      const type = isLabelEdit.value ? 'label' : 'annotation';
      emit('delete-config-params-item', type);
    };

    /**
     * 显示对话框
     */
    const handelShowDialog = () => {
      isShowDialog.value = true;
    };
    /**
     * 修改内容
     * @param index
     * @param newValue
     * @param isMatchLabels
     */
    const handleItemChange = (index: number, newValue: IValueItem, isMatchLabels = false) => {
      const keys = isMatchLabels ? 'match_labels' : typeKeys.value;
      if (cacheConfig.value[keys]) {
        // 创建新数组以确保响应式更新
        const newArray = [...cacheConfig.value[keys]];
        newArray[index] = { ...newValue };
        cacheConfig.value = {
          ...cacheConfig.value,
          [keys]: newArray,
        };
        emit('change', { [props.editType]: cacheConfig.value });
      }
    };
    /**
     * 删除
     * @param index
     * @param isMatchLabels
     */
    const handleItemDelete = (index: number, isMatchLabels = false) => {
      const keys = isMatchLabels ? 'match_labels' : typeKeys.value;
      if (cacheConfig.value[keys]) {
        // 创建新数组以确保响应式更新
        const newArray = [...cacheConfig.value[keys]];
        newArray.splice(index, 1);
        cacheConfig.value = {
          ...cacheConfig.value,
          [keys]: newArray,
        };
        emit('change', { [props.editType]: cacheConfig.value });
      }
    };

    /**
     * 关闭选择标签弹窗
     */
    const handleCancel = () => {
      isShowDialog.value = false;
    };

    /**
     * 确认选择标签
     * @param data 选择的标签数据
     */
    const handleSelect = data => {
      const existingItems = cacheConfig.value[typeKeys.value] || [];
      const newItems = [...existingItems, ...data];
      // 创建新对象以确保响应式更新
      cacheConfig.value = {
        ...cacheConfig.value,
        [typeKeys.value]: deduplicateItems(newItems),
      };
      emit('change', { [props.editType]: cacheConfig.value });
    };

    return () => {
      const list = cacheConfig.value?.[typeKeys.value] || [];
      return (
        <div class='config-log-set-edit-item config-item'>
          <div class='config-item-title'>
            <span>
              {t(isLabelEdit.value ? '按标签选择{n}' : '按注解选择{n}', { n: props.isNode ? 'Node' : 'Container' })}
            </span>
            {!props.isNode && (
              <span
                class='bk-icon icon-delete'
                on-Click={handleDeleteConfigParamsItem}
              />
            )}
          </div>
          <div class='select-label-box'>
            <div
              class='manually'
              on-Click={() => {
                handleEdit.value = true;
                const newItem = {
                  key: '',
                  operator: 'In',
                  value: '',
                };
                const currentKey = typeKeys.value;
                const currentArray = cacheConfig.value[currentKey] || [];
                // 创建新对象以确保响应式更新
                cacheConfig.value = {
                  ...cacheConfig.value,
                  [currentKey]: [...currentArray, newItem],
                };
                emit('change', { [props.editType]: cacheConfig.value });
              }}
            >
              <i class='bk-icon icon-plus-circle' />
              {isLabelEdit.value ? <span>{t('手动输入标签')}</span> : <span>{t('手动输入annotation')}</span>}
            </div>

            {isLabelEdit.value && (
              <div
                class='select'
                on-Click={handelShowDialog}
              >
                <i class='bk-icon icon-plus-circle' />
                <span>{t('选择已有标签')}</span>
              </div>
            )}
          </div>
          <div class='specify-domain'>
            {/* 手动输入标签 */}
            {list.map((item, ind) => (
              <LabelItemChoose
                key={`${props.editType}_${ind}`}
                matchItem={item}
                on-change={val => handleItemChange(ind, val)}
                on-delete={_item => handleItemDelete(ind)}
              />
            ))}
          </div>
          {isLabelEdit.value && (
            <LabelChooseDialog
              clusterList={props.clusterList}
              isShowDialog={isShowDialog.value}
              labelParams={currentSelector.value}
              on-cancel={handleCancel}
              on-change={handleSelect}
            />
          )}
        </div>
      );
    };
  },
});
