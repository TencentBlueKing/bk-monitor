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

import { defineComponent, computed, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

// import InfoTips from '../../../common-comp/info-tips';
import LineRuleConfig from '../line-rule-config';
import LogFilter from '../log-filter';
import LogPathConfig from '../log-path-config';
import ConfigClusterBox from './config-cluster-box';

import type { IContainerConfigItem } from '../../../../type';

import './configuration-item-list.scss';

/**
 * ConfigurationItem 组件
 * 用于展示一个可折叠的配置项界面
 */

export default defineComponent({
  name: 'ConfigurationItemList', // 组件名称

  props: {
    data: {
      type: Array as PropType<IContainerConfigItem[]>,
      default: () => [],
    },
    scenarioId: {
      type: String,
      default: '',
    },
    bcsClusterId: {
      type: String,
      default: '',
    },
    clusterList: {
      type: Array,
      default: () => [],
    },
    logType: {
      type: String,
      default: 'row',
    },
    collectorType: {
      type: String,
      default: '',
    },
  },

  emits: ['change'], // 组件触发的事件，当宽度改变时触发

  setup(props, { emit }) {
    // 使用国际化翻译函数
    const { t } = useLocale();
    const store = useStore();
    // 获取全局数据
    const globalsData = computed(() => store.getters['globals/globalsData']);
    // 添加索引转字母的函数
    const indexToLetter = (index: number): string => {
      // 65 是 'A' 的 ASCII 码
      const asciiCode = 65;
      return String.fromCharCode(asciiCode + index);
    };

    const handleDataChange = (item: IContainerConfigItem, ind: number) => {
      const nextData = [...props.data];
      nextData[ind] = item;
      emit('change', nextData);
    };

    // 创建默认配置项
    const createDefaultConfigItem = () => {
      return {
        collector_type: 'container_log_config',
        namespaces: [],
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
          exclude_files: [{ value: '' }],
          conditions: {
            type: 'none',
            match_type: 'include',
            match_content: '',
            separator: '|',
            separator_filters: [{ fieldindex: '', word: '', op: '=', logic_op: 'and' }],
          },
          multiline_pattern: '',
          multiline_max_lines: '50',
          multiline_timeout: '2',
          winlog_name: [],
          winlog_level: [],
          winlog_event_id: [],
        },
      };
    };

    // 添加配置项
    const handleAddConfigItem = () => {
      const newConfigItem = createDefaultConfigItem();
      const nextData = [...props.data, newConfigItem];
      emit('change', nextData);
    };

    // 删除配置项
    const handleDeleteConfigItem = (index: number) => {
      const nextData = [...props.data];
      nextData.splice(index, 1);
      emit('change', nextData);
    };
    const renderItem = (item: IContainerConfigItem, ind: number) => (
      <div class='item-box'>
        <div class='item-header'>
          <span>{indexToLetter(ind)}</span>
          {props.data.length > 1 && (
            <i
              class='bk-icon icon-delete del-icons'
              on-Click={() => handleDeleteConfigItem(ind)}
            />
          )}
        </div>
        <div class='item-content'>
          <div class='item-content-child-bg'>
            <ConfigClusterBox
              bcsClusterId={props.bcsClusterId}
              clusterList={props.clusterList}
              config={item}
              isNode={props.collectorType === 'node_log_config'}
              scenarioId={props.scenarioId}
              on-change={data => {
                item = data;
                handleDataChange(item, ind);
              }}
            />
          </div>
          {/* 行首正则 */}
          {props.logType === 'section' && (
            <div class='item-content-child-bg'>
              <LineRuleConfig
                class='line-rule-tmp small-width'
                data={item.params}
                on-update={val => {
                  item.params = val;
                  handleDataChange(item, ind);
                }}
              />
            </div>
          )}
          {/* 日志路径 */}
          <div class='item-content-child small-width'>
            <LogPathConfig
              excludeFiles={item.params.exclude_files}
              paths={item.params.paths}
              on-update={(key, val) => {
                item.params[key] = val;
                handleDataChange(item, ind);
              }}
            />
          </div>
          <div class='item-content-child small-width'>
            <div class='item-content-title'>{t('字符集')}</div>
            <bk-select
              class='encoding-select'
              clearable={false}
              value={item.data_encoding}
              searchable
              on-selected={val => {
                item.data_encoding = val;
                handleDataChange(item, ind);
              }}
            >
              {(globalsData.value.data_encoding || []).map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
          </div>
          <div class='item-content-child'>
            <div class='item-content-title'>{t('日志过滤')}</div>
            <LogFilter
              conditions={item.params.conditions}
              // isCloneOrUpdate={isCloneOrUpdate.value}
              on-conditions-change={val => {
                item.params.conditions = val;
                handleDataChange(item, ind);
              }}
            />
          </div>
        </div>
      </div>
    );
    // 组件渲染函数
    return () => (
      <div class='configuration-item-list-main'>
        {props.data.map((item, ind) => renderItem(item, ind))}
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
