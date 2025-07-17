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

import { defineComponent, ref, computed, onMounted } from 'vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { base64Decode } from '@/common/util';
import $http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'RuleOperate',
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const ruleType = ref('template');
    const searchValue = ref('');
    const templateRule = ref('');
    const templateList = ref<
      {
        id: string;
        name: string;
        predefined_varibles: string;
      }[]
    >([]);

    const isCustomize = computed(() => ruleType.value === 'customize');
    const spaceUid = computed(() => store.state.spaceUid);

    /** 初始化模板列表 */
    const initTemplateList = async () => {
      const res = await $http.request('logClustering/ruleTemplate', {
        params: {
          space_uid: spaceUid.value,
        },
      });
      templateList.value = res.data.map((item, index) => ({
        ...item,
        isShowEdit: false,
        name: item.template_name,
        editStr: item.template_name,
        index,
      }));
    };

    const base64ToRuleArr = (str: string) => {
      if (!str) return [];
      try {
        const ruleList = JSON.parse(base64Decode(str));
        const ruleNewList = ruleList.reduce((pre, cur, index) => {
          const itemObj = {} as any;
          const matchVal = cur.match(/:(.*)/);
          const key = cur.substring(0, matchVal.index);
          itemObj[key] = matchVal[1];
          itemObj.__Index__ = index;
          pre.push(itemObj);
          return pre;
        }, []);
        return ruleNewList;
      } catch (e) {
        return [];
      }
    };

    const handleSelectTemplate = value => {
      console.log(value);
      templateRule.value = value;
      const selectTemplateStr = templateList.value.find(item => item.id === value).predefined_varibles;
      emit('rule-list-change', base64ToRuleArr(selectTemplateStr));
      // emit('show-table-loading');
    };

    onMounted(() => {
      initTemplateList();
    });

    return () => (
      <div class='rule-operate-main'>
        <bk-radio-group
          class='type-choose-main'
          value={ruleType.value}
          on-change={value => (ruleType.value = value)}
        >
          <bk-radio value='customize'>{t('自定义')}</bk-radio>
          <bk-radio value='template'>{t('模板')}</bk-radio>
        </bk-radio-group>
        <div class='right-oprate-main'>
          {isCustomize.value ? (
            <div class='custom-operate-main'>
              <bk-input
                clearable
                style='width: 240px'
                placeholder={t('搜索 占位符')}
                right-icon='bk-icon icon-search'
                value={searchValue.value}
                on-change={value => (searchValue.value = value)}
              ></bk-input>
              <bk-dropdown-menu>
                <div slot='dropdown-trigger'>
                  <bk-button
                    style='min-width: 48px'
                    class='btn-hover'
                    data-test-id='LogCluster_button_addNewRules'
                  >
                    {t('导入')}
                  </bk-button>
                </div>
                <ul
                  class='bk-dropdown-list'
                  slot='dropdown-content'
                >
                  <li>
                    <a
                      href='javascript:;'
                      on-click='handleFastAddRule'
                    >
                      {t('本地导入')}
                    </a>
                  </li>
                  <li>
                    <a
                      href='javascript:;'
                      on-click='handleAddRuleToIndex'
                    >
                      {t('其他索引集导入')}
                    </a>
                  </li>
                </ul>
              </bk-dropdown-menu>
              <bk-button
                style='min-width: 48px'
                class='btn-hover'
                on-click='() => handleExportRule()'
              >
                {t('导出')}
              </bk-button>
              <bk-button
                style='min-width: 72px'
                class='btn-hover'
                data-test-id='LogCluster_button_reductionRules'
                on-click='reductionRule'
              >
                {t('恢复默认')}
              </bk-button>
            </div>
          ) : (
            <div class='template-operate-main'>
              <bk-select
                ref='templateListRef'
                ext-cls='template-select'
                value={templateRule.value}
                searchable
                clearable={false}
                on-change={handleSelectTemplate}
              >
                {templateList.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
              <bk-button
                text
                theme='primary'
                size='small'
              >
                <log-icon type='edit' />
                <span style='margin-left: 5px'>{t('编辑模板')}</span>
              </bk-button>
              <bk-button
                text
                theme='primary'
                size='small'
              >
                <log-icon type='help' />
                <span style='margin-left: 5px'>{t('解绑')}</span>
              </bk-button>
              <bk-button
                text
                theme='primary'
                size='small'
              >
                <log-icon type='refresh-icon' />
                <span style='margin-left: 5px'>{t('刷新')}</span>
              </bk-button>
            </div>
          )}
        </div>
      </div>
    );
  },
});
