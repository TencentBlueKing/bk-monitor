/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, defineComponent, shallowRef, watchEffect } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { fieldTypeMap } from 'trace/components/retrieval-filter/utils';
import { useI18n } from 'vue-i18n';
import JsonPretty from 'vue-json-pretty';

import LogCell from './log-cell';
import { parseTableRowData } from './utils/utils';

import type { EClickMenuType, IFieldInfo } from './typing';

import './expand-content.scss';
import 'vue-json-pretty/lib/styles.css';

export default defineComponent({
  name: 'ExpandContent',
  props: {
    row: {
      type: Object,
      default: () => null,
    },
    originLog: {
      type: Object,
      default: () => null,
    },
    fields: {
      type: Array as PropType<IFieldInfo[]>,
      default: () => [],
    },
    displayFields: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {
    clickMenu: (_opt: { field: IFieldInfo; type: EClickMenuType; value: string }) => true,
    removeField: (_fieldName: string) => true,
    addField: (_fieldName: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const activeExpandView = shallowRef('kv');

    const kvList = shallowRef([]);
    const jsonData = shallowRef({});

    watchEffect(() => {
      const tempJsonData = props.fields.reduce((pre, cur) => {
        const fieldName = cur.query_alias || cur.field_name;
        pre[fieldName] = parseTableRowData(props.originLog ?? props.row, cur.field_name, cur.field_type) ?? '';
        return pre;
      }, {});
      const tempKvList = props.fields.filter(item => {
        return !['--', '{}', '[]'].includes(parseTableRowData(props.row, item.field_name));
      });
      jsonData.value = tempJsonData;
      kvList.value = tempKvList;
    });

    const handleCopy = (value: Record<string, any>) => {
      copyText(JSON.stringify(value), msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    };

    const headerWrapper = () => {
      return (
        <div class='view-tab'>
          <div class='tab-left'>
            <span
              class={{ activeKv: activeExpandView.value === 'kv' }}
              onClick={() => {
                activeExpandView.value = 'kv';
              }}
            >
              KV
            </span>
            <span
              class={{ activeJson: activeExpandView.value === 'json' }}
              onClick={() => {
                activeExpandView.value = 'json';
              }}
            >
              JSON
            </span>
          </div>
          <div class='tab-right'>
            <span
              class='icon-monitor icon-mc-copy'
              onClick={() => handleCopy(jsonData.value)}
            />
          </div>
        </div>
      );
    };
    const kvListWrapper = () => {
      return (
        <div class='kv-list-wrap'>
          {kvList.value.map((item, index) => {
            const fieldIcon = fieldTypeMap[item.field_type] || fieldTypeMap.text;
            const isDisplay = props.displayFields.includes(item.field_name);
            return (
              <div
                key={index}
                class='log-item'
              >
                <div class='field-label'>
                  <span
                    class='field-eye-btn'
                    v-bk-tooltips={{
                      content: t(isDisplay ? '隐藏' : '展示'),
                    }}
                  >
                    <span
                      class={['icon-monitor', isDisplay ? 'icon-mc-invisible' : 'icon-mc-visual']}
                      onClick={() => {
                        if (isDisplay) {
                          emit('removeField', item.field_name);
                        } else {
                          emit('addField', item.field_name);
                        }
                      }}
                    />
                  </span>
                  <span
                    style={{
                      backgroundColor: fieldIcon.bgColor,
                      color: fieldIcon.color,
                      marginRight: '5px',
                      marginTop: '2px',
                    }}
                    class={[fieldIcon.icon, 'col-title-field-icon']}
                    v-bk-tooltips={{
                      content: fieldIcon.name,
                    }}
                  />
                  <span class='field-text'>{item.query_alias || item.field_name}</span>
                </div>
                <div class='field-value'>
                  <LogCell
                    options={{
                      onClickMenu: (opt: { type: EClickMenuType; value: string }) => {
                        emit('clickMenu', {
                          ...opt,
                          field: item,
                        });
                      },
                    }}
                    field={item}
                    row={props.originLog ?? props.row}
                  />
                </div>
              </div>
            );
          })}
        </div>
      );
    };

    const jsonViewWrapper = () => {
      return (
        <div class='json-view-wrap'>
          <JsonPretty data={jsonData.value} />
        </div>
      );
    };

    return {
      activeExpandView,
      kvList,
      kvListWrapper,
      jsonViewWrapper,
      headerWrapper,
    };
  },
  render() {
    return (
      <div class='log-table-new-expand-content'>
        {this.headerWrapper()}
        {this.activeExpandView === 'kv' ? this.kvListWrapper() : this.jsonViewWrapper()}
      </div>
    );
  },
});
