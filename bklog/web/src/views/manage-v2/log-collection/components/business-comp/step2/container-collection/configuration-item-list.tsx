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

import { defineComponent, computed, type PropType, ref, type ComponentPublicInstance } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import LineRuleConfig from '../line-rule-config';
import LogFilter from '../log-filter';
import LogPathConfig from '../log-path-config';
import ConfigClusterBox from './config-cluster-box';

import type { IContainerConfigItem, IClusterItem, IConditions } from '../../../../type';

import './configuration-item-list.scss';

/**
 * 子组件实例类型定义
 */
interface ILineRuleRef extends ComponentPublicInstance {
  validate: () => boolean;
}

interface ILogPathRef extends ComponentPublicInstance {
  validate: () => boolean;
}

interface ILogFilterRef extends ComponentPublicInstance {
  validateInputs: () => boolean;
}

/**
 * 组件 Props 类型定义
 */
interface IConfigurationItemListProps {
  /** 配置项数据列表 */
  data: IContainerConfigItem[];
  /** 场景ID */
  scenarioId: string;
  /** BCS集群ID */
  bcsClusterId: string;
  /** 集群列表 */
  clusterList: IClusterItem[];
  /** 日志类型：'row' 行日志 | 'section' 段日志 */
  logType: 'row' | 'section';
  /** 采集器类型 */
  collectorType: string;
}

/**
 * ConfigurationItemList 组件
 *
 * 功能说明：
 * - 用于展示和管理多个容器日志采集配置项
 * - 支持添加、删除配置项
 * - 每个配置项包含：集群配置、行首正则（条件显示）、日志路径、字符集、日志过滤
 * - 提供统一的校验方法，校验所有子组件的输入
 */
export default defineComponent({
  name: 'ConfigurationItemList',

  props: {
    /** 配置项数据列表 */
    data: {
      type: Array as PropType<IContainerConfigItem[]>,
      required: true,
      default: () => [],
    },
    /** 场景ID */
    scenarioId: {
      type: String,
      required: false,
      default: '',
    },
    /** BCS集群ID */
    bcsClusterId: {
      type: String,
      required: false,
      default: '',
    },
    /** 集群列表 */
    clusterList: {
      type: Array as PropType<IClusterItem[]>,
      required: false,
      default: () => [],
    },
    /** 日志类型：'row' 行日志 | 'section' 段日志 */
    logType: {
      type: String as PropType<'row' | 'section'>,
      required: false,
      default: 'row',
    },
    /** 采集器类型 */
    collectorType: {
      type: String,
      required: false,
      default: '',
    },
  },

  emits: ['change'],

  setup(props: IConfigurationItemListProps, { emit, expose }) {
    // 使用国际化翻译函数
    const { t } = useLocale();
    const store = useStore();

    /**
     * 子组件引用数组
     * 用于存储每个配置项对应的子组件实例，以便进行校验
     * 使用 any[] 类型避免 TypeScript 类型推断过深的问题
     */
    const lineRuleRefs = ref<any[]>([]);
    const logPathRefs = ref<any[]>([]);
    const logFilterRefs = ref<any[]>([]);

    /** 获取全局数据（字符集选项等） */
    const globalsData = computed(() => store.getters['globals/globalsData']);

    /**
     * 将索引转换为字母标识（A, B, C, ...）
     * @param index - 配置项的索引（从0开始）
     * @returns 对应的字母标识
     */
    const indexToLetter = (index: number): string => {
      // 65 是 'A' 的 ASCII 码
      const asciiCode = 65;
      return String.fromCharCode(asciiCode + index);
    };

    /**
     * 处理配置项数据变更
     * @param item - 更新后的配置项数据
     * @param ind - 配置项的索引
     */
    const handleDataChange = (item: IContainerConfigItem, ind: number): void => {
      const nextData = [...props.data];
      nextData[ind] = item;
      emit('change', nextData);
    };

    /**
     * 创建默认配置项
     * @returns 包含所有默认值的配置项对象
     *
     * 注意：返回的对象包含了一些类型定义中未声明的字段（如 noQuestParams, containerNameList），
     * 这些字段在实际业务逻辑中使用，使用类型断言来兼容类型系统
     */
    const createDefaultConfigItem = (): IContainerConfigItem => {
      return {
        collector_type: 'container_log_config',
        namespaces: [],
        // noQuestParams 和 containerNameList 不在类型定义中，但实际业务中需要使用
        noQuestParams: {
          letterIndex: 0,
          scopeSelectShow: {
            namespace: false,
            label: true,
            load: true,
            containerName: true,
            annotation: true,
          },
          namespaceStr: '',
          namespacesExclude: '=',
          containerExclude: '=',
        },
        container: {
          workload_type: '',
          workload_name: '',
          container_name: '',
        },
        containerNameList: [],
        label_selector: {
          match_labels: [],
          match_expressions: [],
        },
        annotation_selector: {
          match_annotations: [],
        },
        data_encoding: 'UTF-8',
        params: {
          paths: [{ value: '' }],
          exclude_files: [], // 类型定义中是 string[]，但实际使用时需要转换为 { value: string }[]
          conditions: {
            type: 'none' as const,
            match_type: 'include',
            match_content: '',
            separator: '|',
            separator_filters: [{ fieldindex: '', word: '', op: '=', logic_op: 'and' }],
          },
          multiline_pattern: '',
          multiline_max_lines: '50',
          multiline_timeout: '2',
          // winlog 相关字段在 IContainerCollectionParams 中，但 IContainerConfigItem.params 类型是 IHostCollectionParams
          // 这里使用类型断言来兼容实际使用场景
          winlog_name: [],
          winlog_level: [],
          winlog_event_id: [],
        },
      };
    };

    /**
     * 添加新的配置项
     * 在现有配置项列表末尾添加一个默认配置项
     */
    const handleAddConfigItem = (): void => {
      const newConfigItem = createDefaultConfigItem();
      const nextData = [...props.data, newConfigItem];
      emit('change', nextData);
    };

    /**
     * 删除指定索引的配置项
     * @param index - 要删除的配置项索引
     */
    const handleDeleteConfigItem = (index: number): void => {
      const nextData = [...props.data];
      nextData.splice(index, 1);
      // 同步删除对应的 refs，保持索引一致性
      lineRuleRefs.value.splice(index, 1);
      logPathRefs.value.splice(index, 1);
      logFilterRefs.value.splice(index, 1);
      emit('change', nextData);
    };

    /**
     * 校验方法：校验所有配置项的子组件输入
     *
     * 校验规则：
     * 1. 当 logType === 'section' 时，校验行首正则配置
     * 2. 校验日志路径配置（必填）
     * 3. 校验日志过滤配置
     *
     * @returns {boolean} 校验是否通过，true表示所有配置项校验通过，false表示至少有一个配置项校验失败
     */
    const validate = (): boolean => {
      let allValid = true;
      const dataLength = props.data.length;

      // 使用 for...of 循环遍历所有配置项进行校验
      for (let index = 0; index < dataLength; index++) {
        // 校验行首正则（仅在 logType === 'section' 时存在）
        if (props.logType === 'section') {
          const lineRuleRef = lineRuleRefs.value[index] as ILineRuleRef | null | undefined;
          if (lineRuleRef && typeof lineRuleRef.validate === 'function') {
            const lineRuleValid = lineRuleRef.validate();
            if (!lineRuleValid) {
              allValid = false;
            }
          }
        }

        // 校验日志路径
        const logPathRef = logPathRefs.value[index] as ILogPathRef | null | undefined;
        if (logPathRef && typeof logPathRef.validate === 'function') {
          const logPathValid = logPathRef.validate();
          if (!logPathValid) {
            allValid = false;
          }
        }

        // 校验日志过滤
        const logFilterRef = logFilterRefs.value[index] as ILogFilterRef | null | undefined;
        if (logFilterRef && typeof logFilterRef.validateInputs === 'function') {
          const logFilterValid = logFilterRef.validateInputs();
          if (!logFilterValid) {
            allValid = false;
          }
        }
      }

      return allValid;
    };

    /**
     * 渲染单个配置项
     * @param item - 配置项数据
     * @param ind - 配置项的索引
     * @returns JSX 元素
     */
    const renderItem = (item: IContainerConfigItem, ind: number) => {
      // 确保 refs 数组有足够的长度，避免索引越界
      if (lineRuleRefs.value.length <= ind) {
        lineRuleRefs.value.length = ind + 1;
      }
      if (logPathRefs.value.length <= ind) {
        logPathRefs.value.length = ind + 1;
      }
      if (logFilterRefs.value.length <= ind) {
        logFilterRefs.value.length = ind + 1;
      }

      return (
        <div class='item-box'>
          {/* 配置项头部：显示字母标识和删除按钮 */}
          <div class='item-header'>
            <span>{indexToLetter(ind)}</span>
            {/* 当配置项数量大于1时才显示删除按钮 */}
            {props.data.length > 1 && (
              <i
                class='bk-icon icon-delete del-icons'
                on-Click={() => handleDeleteConfigItem(ind)}
              />
            )}
          </div>
          <div class='item-content'>
            {/* 集群配置区域 */}
            <div class='item-content-child-bg'>
              <ConfigClusterBox
                bcsClusterId={props.bcsClusterId}
                clusterList={props.clusterList}
                config={item}
                isNode={props.collectorType === 'node_log_config'}
                scenarioId={props.scenarioId}
                on-change={(data: IContainerConfigItem) => {
                  handleDataChange(data, ind);
                }}
              />
            </div>
            {/* 行首正则配置（仅在段日志模式下显示） */}
            {props.logType === 'section' && (
              <div class='item-content-child-bg'>
                <LineRuleConfig
                  ref={(el: any) => {
                    lineRuleRefs.value[ind] = el;
                  }}
                  class='line-rule-tmp small-width'
                  data={(item.params || {}) as Record<string, any>}
                  on-update={(val: Record<string, any>) => {
                    const updatedItem = { ...item, params: val as IContainerConfigItem['params'] };
                    handleDataChange(updatedItem, ind);
                  }}
                />
              </div>
            )}
            {/* 日志路径配置 */}
            <div class='item-content-child small-width'>
              <LogPathConfig
                ref={(el: any) => {
                  logPathRefs.value[ind] = el;
                }}
                excludeFiles={
                  (item.params?.exclude_files || []).map((file: string | { value: string }) =>
                    typeof file === 'string' ? { value: file } : file,
                  ) as { value: string }[]
                }
                paths={
                  (item.params?.paths || []).map((path: { value?: string }) => ({
                    value: path.value || '',
                  })) as { value: string }[]
                }
                on-update={(key: string, val: any) => {
                  // 如果更新的是 exclude_files，需要转换为 string[] 格式存储
                  const updatedParams = { ...item.params };
                  if (key === 'exclude_files' && Array.isArray(val)) {
                    updatedParams[key] = val.map((item: { value: string }) => item.value);
                  } else {
                    updatedParams[key] = val;
                  }
                  const updatedItem = {
                    ...item,
                    params: updatedParams,
                  };
                  handleDataChange(updatedItem, ind);
                }}
              />
            </div>
            {/* 字符集选择 */}
            <div class='item-content-child small-width'>
              <div class='item-content-title'>{t('字符集')}</div>
              <bk-select
                class='encoding-select'
                clearable={false}
                value={item.data_encoding}
                searchable
                on-selected={(val: string) => {
                  const updatedItem = { ...item, data_encoding: val };
                  handleDataChange(updatedItem, ind);
                }}
              >
                {(globalsData.value?.data_encoding || []).map((option: { id: string; name: string }) => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            </div>
            {/* 日志过滤配置 */}
            <div class='item-content-child'>
              <div class='item-content-title'>{t('日志过滤')}</div>
              <LogFilter
                ref={(el: HTMLElement) => {
                  logFilterRefs.value[ind] = el;
                }}
                conditions={item.params?.conditions || { type: 'none' }}
                on-conditions-change={(val: IConditions) => {
                  const updatedItem = {
                    ...item,
                    params: {
                      ...item.params,
                      conditions: val,
                    },
                  };
                  handleDataChange(updatedItem, ind);
                }}
              />
            </div>
          </div>
        </div>
      );
    };

    /**
     * 暴露给父组件的方法
     * 父组件可以通过 ref 调用 validate 方法进行表单校验
     */
    expose({
      validate,
    });

    /**
     * 组件渲染函数
     * 渲染所有配置项和添加按钮
     */
    return () => (
      <div class='configuration-item-list-main'>
        {/* 渲染所有配置项 */}
        {props.data.map((item: IContainerConfigItem, ind: number) => renderItem(item, ind))}
        {/* 添加配置项按钮 */}
        <div
          class='add-btn'
          on-Click={handleAddConfigItem}
        >
          <i class='bk-icon icon-plus-line icons' />
          {t('添加配置项')}
        </div>
      </div>
    );
  },
});
