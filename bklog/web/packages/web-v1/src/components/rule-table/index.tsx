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
import { defineComponent, ref, watch } from 'vue';

import { copyMessage, base64Encode } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import VueDraggable from 'vuedraggable';

import AddRule from './add-rule';
import Regexopover from './regex-popover';

import './index.scss';

export default defineComponent({
  name: 'RuleTable',
  components: {
    EmptyStatus,
    VueDraggable,
    Regexopover,
    AddRule,
  },
  props: {
    ruleList: {
      type: Array,
      default: () => [],
    },
    readonly: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const tableLoading = ref(false);
    const isShowAddRule = ref(false);
    const isEditRow = ref(false);
    const ruleList = ref<any[]>([]);
    const currentRowData = ref({});
    const searchValue = ref('');

    let currentRowIndex = 0;
    let localRuleList: any[] = [];

    const initTableList = () => {
      ruleList.value = structuredClone(props.ruleList);
      localRuleList = structuredClone(props.ruleList);
    };

    watch(
      () => props.ruleList,
      () => {
        initTableList();
      },
      { immediate: true },
    );

    const handleDragChange = (data: {
      moved: {
        oldIndex: number;
        newIndex: number;
        element: any;
      };
    }) => {
      const tmpList = structuredClone(ruleList.value);
      const { oldIndex, newIndex } = data.moved;
      const oldItem = tmpList[oldIndex];
      tmpList.splice(oldIndex, 1);
      tmpList.splice(newIndex, 0, oldItem);
      ruleList.value = tmpList;
      localRuleList = structuredClone(ruleList.value);
      emit('rule-list-change', ruleList.value);
    };

    const handleMenuClick = item => {
      copyMessage(Object.values(item)[0]);
    };

    const handleClickEditRule = (item: any, index: number, isAdd = false) => {
      isShowAddRule.value = true;
      isEditRow.value = !isAdd;
      currentRowData.value = isAdd ? {} : item;
      currentRowIndex = index;
    };

    const handleAddRule = (item: any) => {
      ruleList.value.splice(currentRowIndex + 1, 0, item);
      localRuleList = structuredClone(ruleList.value);
      emit('rule-list-change', ruleList.value);
    };

    const handleEditRule = (item: any) => {
      ruleList.value[currentRowIndex] = item;
      localRuleList = structuredClone(ruleList.value);
      emit('rule-list-change', ruleList.value);
    };

    const handleClickRemoveRule = (index: number) => {
      ruleList.value.splice(index, 1);
      localRuleList = structuredClone(ruleList.value);
      emit('rule-list-change', ruleList.value);
    };

    const ruleArrToBase64 = () => {
      try {
        const ruleNewList = ruleList.value.reduce((pre, cur) => {
          const key = Object.keys(cur)[0];
          const val = Object.values(cur)[0];
          const rulesStr = JSON.stringify(`${key}:${val}`);
          pre.push(rulesStr);
          return pre;
        }, []);
        const ruleArrStr = `[${ruleNewList.join(' ,')}]`;
        return base64Encode(ruleArrStr);
      } catch {
        return '';
      }
    };

    const handleSearch = (keyword: string) => {
      searchValue.value = keyword;
      if (!keyword) {
        ruleList.value = structuredClone(localRuleList);
        return;
      }

      const searchRegExp = new RegExp(keyword, 'i');
      ruleList.value = localRuleList.filter(item => searchRegExp.test(Object.keys(item)[0] as string));
    };

    expose({
      getRuleList: () => ruleList.value,
      getRuleListBase64: ruleArrToBase64,
      init: initTableList,
      search: handleSearch,
    });

    return () => (
      <div class='rule-table-main'>
        <div class={['table-row-header', { 'is-readonly': props.readonly }]}>
          <div class='index-column'>{t('生效顺序')}</div>
          <div class='regular-column'>{t('正则表达式')}</div>
          <div class='placement-column'>{t('占位符')}</div>
          {!props.readonly && <div class='operate-column'>{t('操作')}</div>}
        </div>

        {ruleList.value.length > 0 ? (
          <div v-bkloading={{ isLoading: tableLoading.value }}>
            <vue-draggable
              disabled={props.readonly}
              {...{
                animation: 150,
                tag: 'ul',
                handle: '.bklog-drag-dots',
                'ghost-class': 'sortable-ghost-class',
              }}
              value={ruleList.value}
              on-change={handleDragChange}
            >
              <transition-group>
                {ruleList.value.map((item, index) => (
                  <li
                    key={item.__Index__}
                    class={['table-row-content', { 'is-readonly': props.readonly }]}
                  >
                    <div class='index-column'>
                      {!props.readonly && (
                        <log-icon
                          class='icon'
                          type='drag-dots'
                        />
                      )}
                      <span>{index + 1}</span>
                    </div>
                    <div class='regular-column'>
                      <Regexopover
                        is-cluster={false}
                        placement='top'
                        on-event-click={() => handleMenuClick(item)}
                      >
                        <span class='row-left-regular'> {Object.values(item)[0]}</span>
                      </Regexopover>
                    </div>
                    <div class='placement-column'>{Object.keys(item)[0]}</div>
                    {!props.readonly && (
                      <div class='operate-column'>
                        <bk-button
                          text
                          on-click={() => handleClickEditRule(item, index)}
                        >
                          <log-icon
                            class='opt-icon'
                            type='edit'
                          />
                        </bk-button>
                        <bk-button
                          text
                          on-click={() => handleClickEditRule(item, index, true)}
                        >
                          <log-icon
                            class='opt-icon'
                            type='plus-circle'
                            common
                          />
                        </bk-button>
                        <bk-popconfirm
                          width={280}
                          content={t('删除操作无法撤回，请谨慎操作！')}
                          placement='bottom'
                          title={t('确认删除该规则？')}
                          trigger='click'
                          on-confirm={() => handleClickRemoveRule(index)}
                        >
                          <bk-button text>
                            <log-icon
                              class='opt-icon'
                              type='minus-circle'
                              common
                            />
                          </bk-button>
                        </bk-popconfirm>
                      </div>
                    )}
                  </li>
                ))}
              </transition-group>
            </vue-draggable>
          </div>
        ) : (
          <div class='no-cluster-rule'>
            {searchValue.value ? (
              <bk-exception
                scene='part'
                type='search-empty'
              >
                <span style='font-size:12px;'>{t('搜索为空')}</span>
              </bk-exception>
            ) : (
              <bk-exception
                scene='part'
                type='empty'
              >
                <span style='font-size:12px;'>{t('暂无聚类规则')}，</span>
                <bk-button
                  style='padding:0;'
                  size='small'
                  theme='primary'
                  text
                  on-click={() => handleClickEditRule(null, -1, true)}
                >
                  {t('立即新建')}
                </bk-button>
              </bk-exception>
            )}
          </div>
        )}
        <add-rule
          data={currentRowData.value}
          isEdit={isEditRow.value}
          isShow={isShowAddRule.value}
          ruleList={props.ruleList}
          on-add={handleAddRule}
          on-edit={handleEditRule}
          on-show-change={val => {
            isShowAddRule.value = val;
          }}
        />
      </div>
    );
  },
});
