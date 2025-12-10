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

import { defineComponent, ref, onMounted, nextTick, type PropType, watch } from 'vue';

import useLocale from '@/hooks/use-locale';

import InfoTips from '../../common-comp/info-tips';
import $http from '@/api';

import './device-metadata.scss';

type IExtraLabel = {
  key: string;
  value: string;
  duplicateKey: boolean;
};

type IGroupItem = {
  field: string;
  name: string;
  group_name: string;
  key: string;
};
type IMetaItem = {
  key: string;
  value: string;
};
/**
 * 设备元数据
 */
export default defineComponent({
  name: 'DeviceMetadata',
  props: {
    metadata: {
      type: Array as PropType<IMetaItem[]>,
      default: () => [],
    },
  },

  emits: ['extra-labels-change'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    // 自定义标签列表
    const extraLabelList = ref<IExtraLabel[]>([]);
    // 元数据分组列表
    const groupList = ref<IGroupItem[]>([]);
    // 选中的元数据字段
    const selectValue = ref<string[]>([]);
    // 开关状态
    const switcherValue = ref(false);
    // 自定义标签验证错误状态
    const isExtraError = ref(false);
    // 标记是否已经初始化过回填，避免后续编辑时重复回填
    const hasInitialized = ref(false);

    onMounted(() => {
      getDeviceMetaData();
      // 如果已有元数据，则开启开关
      if (props.metadata.filter(item => item.key).length) {
        switcherValue.value = true;
      }
    });
    /**
     * 是否打开switcher
     * @param val
     */
    const switcherChange = (val: boolean) => {
      switcherValue.value = val;
      if (!val) {
        // 关闭开关时清空数据
        emit('extra-labels-change', []);
      }
    };

    /**
     * 回填元数据
     * 将 metadata 中的 key 去掉 'host.' 前缀后回填到 selectValue
     * 将不在 groupList 中的项作为自定义标签回填到 extraLabelList
     */
    const fillMetadataData = () => {
      if (!props.metadata || props.metadata.length === 0 || groupList.value.length === 0) {
        return;
      }

      // 回填选中的元数据字段（去掉 'host.' 前缀）
      const selectedFields: string[] = [];
      props.metadata.forEach((item: IMetaItem) => {
        if (item.key?.startsWith('host.')) {
          const field = item.key.slice(5); // 去掉 'host.' 前缀
          // 检查该字段是否在 groupList 中
          if (groupList.value.some(groupItem => groupItem.field === field)) {
            selectedFields.push(field);
          }
        }
      });
      selectValue.value = selectedFields;

      // 回填自定义标签（不在 groupList 中的 metadata 项）
      extraLabelList.value = props.metadata
        .filter((metadataItem: IMetaItem) => {
          // 如果不是以 'host.' 开头，是自定义标签
          if (!metadataItem.key.startsWith('host.')) {
            return true;
          }
          // 如果以 'host.' 开头，但不在 groupList 中，也是自定义标签
          const field = metadataItem.key.slice(5);
          const isInGroupList = groupList.value.some(groupItem => groupItem.field === field);
          return !isInGroupList;
        })
        .map((item: IMetaItem) => {
          return {
            key: item.key,
            value: item.value,
            duplicateKey: false,
          };
        });

      // 标记已初始化
      hasInitialized.value = true;
    };

    // 获取元数据
    const getDeviceMetaData = async () => {
      try {
        const res = await $http.request('linkConfiguration/getSearchObjectAttribute');
        const { scope = [], host = [] } = res.data;
        groupList.value.push(
          ...scope.map((item: IGroupItem) => {
            item.key = 'scope';
            return item;
          }),
        );
        groupList.value.push(
          ...host.map(item => {
            item.key = 'host';
            return item;
          }),
        );
        // groupList 加载完成后，如果 metadata 有值且未初始化过，则回填
        if (props.metadata && props.metadata.length > 0 && !hasInitialized.value) {
          fillMetadataData();
        }
      } catch (e) {
        console.warn(e);
      }
    };

    /**
     * 处理自定义标签变化并提交
     */
    const handleExtraLabelsChange = () => {
      if (!switcherValue.value) {
        return;
      }

      const result = [
        // 选中的元数据
        ...groupList.value
          .filter((item: IGroupItem) => selectValue.value.includes(item.field))
          .map((item: IGroupItem) => ({
            key: `host.${item.field}`,
            value: item.name,
          })),
        // 自定义标签
        ...extraLabelList.value
          .filter(item => item.key && item.value) // 只包含有效数据
          .map(item => ({
            key: item.key,
            value: item.value,
          })),
      ];

      emit('extra-labels-change', result);
    };
    /**
     * 添加自定义标签
     */
    const handleAddExtraLabel = () => {
      extraLabelList.value.push({
        key: '',
        value: '',
        duplicateKey: false,
      });
    };
    /**
     * 删除自定义标签
     * @param index - 要删除的索引
     */
    const handleDeleteExtraLabel = (index: number) => {
      extraLabelList.value.splice(index, 1);
      // 删除后重新验证并提交数据
      nextTick(() => {
        handleExtraLabelsChange();
      });
    };
    /**
     * 自定义标签输入变化处理
     * @param index - 标签索引
     * @param field - 字段名 ('key' | 'value')
     * @param value - 输入值
     */
    const handleExtraLabelChange = (index: number, field: string, value: string) => {
      extraLabelList.value[index][field] = value;

      // 实时检查key是否重复
      if (field === 'key') {
        const isDuplicate = groupList.value.some(groupItem => groupItem.field === value);
        extraLabelList.value[index].duplicateKey = isDuplicate;
      }

      // 延迟提交变化，避免频繁触发
      nextTick(() => {
        handleExtraLabelsChange();
      });
    };
    /**
     * 向上传递元数据变化
     */
    const emitExtraLabels = () => {
      // 合并选中的元数据和自定义标签
      const result = groupList.value.reduce((accumulator: IMetaItem[], item) => {
        if (selectValue.value.includes(item.field)) {
          accumulator.push({
            key: `host.${item.field}`,
            value: item.name,
          });
        }
        return accumulator;
      }, []);
      emit('extra-labels-change', result);
    };
    /**
     * 下拉框选择的时候
     * @param value
     */
    const handleSelect = (value: string[]) => {
      selectValue.value = value;
      emitExtraLabels();
    };

    /**
     * 自定义标签验证
     * @returns 验证是否通过
     */
    const extraLabelsValidate = (): boolean => {
      if (!switcherValue.value) {
        return true;
      }

      isExtraError.value = false;

      // 检查自定义标签
      if (extraLabelList.value.length) {
        for (const item of extraLabelList.value) {
          // 检查必填项
          if (item.key === '' || item.value === '') {
            isExtraError.value = true;
          }
          // 检查key是否重复
          if (groupList.value.find(group => group.field === item.key)) {
            item.duplicateKey = true;
            isExtraError.value = true;
          }
        }
      }

      if (isExtraError.value) {
        return false;
      }

      // 验证通过时提交数据
      handleExtraLabelsChange();
      return true;
    };

    watch(
      () => props.metadata,
      (newVal, oldVal) => {
        // 深度比较，避免相同引用时重复初始化
        if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) {
          // 更新开关状态
          switcherValue.value = newVal && newVal.length > 0;

          // 只在第一次进入页面且 groupList 已加载时回填
          // 后续编辑时不再回填，避免覆盖用户的操作
          if (!hasInitialized.value && groupList.value.length > 0 && newVal && newVal.length > 0) {
            fillMetadataData();
          }
        }
      },
      { deep: true },
    );

    // 暴露方法给父组件
    expose({
      extraLabelsValidate,
    });
    const renderInputItem = (item: IExtraLabel, index) => (
      <div class='device-metadata-input-item'>
        <div class='item-left'>
          <bk-input
            class={{ 'extra-error': item.key === '' && isExtraError.value }}
            value={item.key}
            on-Blur={() => {
              isExtraError.value = false;
              item.duplicateKey = false;
            }}
            on-Input={(val: string) => handleExtraLabelChange(index, 'key', val)}
          />
          {item.duplicateKey && (
            <i
              class='bk-icon icon-exclamation-circle-shape tooltips-icon'
              v-bk-tooltips={{ content: t('自定义标签key与元数据key重复'), placement: 'top' }}
            />
          )}
        </div>
        <span class='symbol'>=</span>
        <bk-input
          class={{ 'extra-error': item.value === '' && isExtraError.value }}
          value={item.value}
          on-Blur={() => {
            isExtraError.value = false;
          }}
          on-Input={(val: string) => handleExtraLabelChange(index, 'value', val)}
        />
        <span
          class='bk-icon icon-plus-circle-shape icons'
          on-Click={handleAddExtraLabel}
        />
        <span
          class={{ 'bk-icon icon-minus-circle-shape icons': true, disabled: extraLabelList.value.length === 1 }}
          on-Click={handleDeleteExtraLabel}
        />
      </div>
    );
    return () => (
      <div class='device-metadata-main'>
        <div class='switcher-container'>
          <bk-switcher
            size='large'
            theme='primary'
            value={switcherValue.value}
            onChange={switcherChange}
          />
          <InfoTips tips={t('该设置可以将采集设备的元数据信息补充至日志中')} />
        </div>
        {switcherValue.value && (
          <div class='device-metadata-input-container'>
            <bk-select
              value={selectValue.value}
              display-tag
              multiple
              searchable
              on-selected={handleSelect}
            >
              {groupList.value.map(item => (
                <bk-option
                  id={item.field}
                  key={item.field}
                  class='device-metadata-option'
                  name={`${item.field}(${item.name})`}
                >
                  <bk-checkbox
                    class='mr-5'
                    value={selectValue.value.includes(item.field)}
                  />
                  {`${item.field}(${item.name})`}
                </bk-option>
              ))}
            </bk-select>
            <div class='device-metadata-tips-box'>
              <span
                class='form-link'
                on-click={handleAddExtraLabel}
              >
                {t('添加自定义标签')}
              </span>
              <InfoTips tips={t('如果CMDB的元数据无法满足您的需求，可以自行定义匹配想要的结果')} />
            </div>
            <div class='device-metadata-input-list'>
              {extraLabelList.value.map((item: IExtraLabel, index: number) => renderInputItem(item, index))}
            </div>
          </div>
        )}
      </div>
    );
  },
});
