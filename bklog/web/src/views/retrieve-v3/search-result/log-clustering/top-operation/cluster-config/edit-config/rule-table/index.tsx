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
import useLocale from '@/hooks/use-locale';
import EmptyStatus from '@/components/empty-status/index.vue';
import VueDraggable from 'vuedraggable';
import RegisterColumn from '@/views/retrieve/result-comp/register-column.vue';
import ClusterEventPopover from '@/views/retrieve/result-table-panel/log-clustering/components/cluster-event-popover.vue';

import './index.scss';

export default defineComponent({
  name: 'RuleTable',
  components: {
    EmptyStatus,
    VueDraggable,
    ClusterEventPopover,
    RegisterColumn,
  },
  props: {
    ruleList: {
      type: Array,
      default: () => [],
    },
    globalEditable: {
      type: Boolean,
      default: true,
    },
  },
  setup(props) {
    const { t } = useLocale();

    const tableLoading = ref(false);

    const rulesList = ref([]);
    watch(
      () => props.ruleList,
      () => {
        console.log('???', props.ruleList);
        rulesList.value = props.ruleList;
      },
      { immediate: true },
    );

    return () => (
      <div
        class='cluster-table'
        data-test-id='LogCluster_div_rulesTable'
      >
        <div class='table-row flbc'>
          <div class='row-left'>
            <div class='row-left-index'>{t('生效顺序')}</div>
            <div class='row-left-regular'>{t('正则表达式')}</div>
          </div>
          <div class='row-right flbc'>
            <div>{t('占位符')}</div>
            <div>{t('操作')}</div>
          </div>
        </div>

        {rulesList.value.length > 0 ? (
          <div v-bkloading={{ isLoading: tableLoading.value }}>
            <vue-draggable
              v-bind='dragOptions'
              value={rulesList.value}
            >
              <transition-group>
                {rulesList.value.map((item, index) => (
                  <li
                    class='table-row table-row-li flbc'
                    key={item.__Index__}
                  >
                    <div class='row-left'>
                      <div class='row-left-index'>
                        <span class='icon bklog-icon bklog-drag-dots'></span>
                        <span>{index}</span>
                      </div>
                      <div class='regular-container'>
                        <register-column
                          context={Object.values(item)[0]}
                          root-margin='-180px 0px 0px 0px'
                        >
                          <cluster-event-popover
                            is-cluster={false}
                            placement='top'
                            on-event-click='() => handleMenuClick(item)'
                          >
                            <span class='row-left-regular'> {Object.values(item)[0]}</span>
                          </cluster-event-popover>
                        </register-column>
                      </div>
                    </div>
                    <div class='row-right flbc'>
                      <div>
                        <span
                          class='row-right-item'
                          ref='`placeholder-${index}`'
                        >
                          {Object.keys(item)[0]}
                        </span>
                      </div>
                      <div class='rule-btn'>
                        <bk-button
                          style='margin-right: 10px'
                          disabled='!globalEditable'
                          theme='primary'
                          text
                          on-click='clusterAddRule(index)'
                        >
                          {t('添加')}
                        </bk-button>
                        <bk-button
                          style='margin-right: 10px'
                          disabled='!globalEditable'
                          theme='primary'
                          text
                          on-click='clusterEdit(index)'
                        >
                          {t('编辑')}
                        </bk-button>
                        <bk-popover
                          ref='deletePopoverRef'
                          ext-cls='config-item'
                          tippy-options='tippyOptions'
                        >
                          <bk-button
                            disabled='!globalEditable'
                            theme='primary'
                            text
                          >
                            {t('删除')}
                          </bk-button>
                          <div slot='content'>
                            <div>
                              <div class='popover-slot'>
                                <span>{t('确定要删除当前规则？')}</span>
                                <div class='popover-btn'>
                                  <bk-button
                                    text
                                    on-click='clusterRemove(index)'
                                  >
                                    {t('确定')}
                                  </bk-button>
                                  <bk-button
                                    theme='danger'
                                    text
                                    on-click='handleCancelDelete(index)'
                                  >
                                    {t('取消')}
                                  </bk-button>
                                </div>
                              </div>
                            </div>
                          </div>
                        </bk-popover>
                      </div>
                    </div>
                  </li>
                ))}
              </transition-group>
            </vue-draggable>
          </div>
        ) : (
          <div class='no-cluster-rule'>
            <empty-status
              show-text={false}
              empty-type='empty'
            >
              <div>{t('暂无聚类规则')}</div>
            </empty-status>
          </div>
        )}
      </div>
    );
  },
});
