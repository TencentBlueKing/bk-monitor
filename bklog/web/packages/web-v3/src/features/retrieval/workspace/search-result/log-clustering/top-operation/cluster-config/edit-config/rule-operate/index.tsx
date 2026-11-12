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

import { RadioGroup as TRadioGroup, Radio as TRadio } from 'tdesign-vue-next';

import { MessagePlugin as TDesignMessage, Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

import { defineComponent, ref, computed, onMounted, watch, type PropType, nextTick } from 'vue';

import OtherImport from '@/features/index-sets/import-from-other/index';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';

import dayjs from 'dayjs';
import { useRouter } from 'vue-router';

import { base64ToRuleArr } from './util';


import type { ConfigInfo, RuleTemplate } from '@/features/retrieval/services/log-clustering';
import type { IResponseData } from '@/platform/services/type';

import './index.scss';

export default defineComponent({
  emits: ["rule-type-change","ruleTypeChange","rule-list-change","ruleListChange","search","unbind-template","unbindTemplate"],

  name: 'RuleOperate',
  components: {
    OtherImport,
  },
  props: {
    defaultValue: {
      type: Object as PropType<ConfigInfo>,
      default: () => {},
    },
    ruleList: {
      type: Array<any>,
      default: () => [],
    },
    templateSpaceUid: {
      type: String,
      default: '',
    },
    isExternal: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const router = useRouter();

    const ruleType = ref('template');
    const isShowOtherImport = ref(false);
    const searchValue = ref('');
    const templateRuleId = ref(0);
    const templateList = ref<
      {
        id: number;
        name: string;
        predefined_varibles: string;
      }[]
    >([]);

    const isCustomize = computed(() => ruleType.value === 'customize');
    const spaceUid = computed(() => store.state.spaceUid);
    const templateSpaceUid = computed(() => props.templateSpaceUid || spaceUid.value);
    const currentTemplate = computed(() => {
      if (!templateRuleId.value) {
        return null;
      }

      return templateList.value.find(item => item.id === templateRuleId.value) || null;
    });
    const hasMatchedTemplate = computed(() => Boolean(currentTemplate.value));
    const isOriginTemplateConfig = computed(() => props.defaultValue.regex_rule_type === 'template');
    const isSameTemplateId = computed(() => props.defaultValue.regex_template_id === templateRuleId.value);
    /** 快速导入的dom */
    let inputDocument: HTMLInputElement;
    let localRuleType = 'template';
    let isShowSwitchPopConfirm = false;

    const handleRuleTypeChange = (value: string, onlyState = false) => {
      ruleType.value = value;
      emit('rule-type-change', value);

      if (onlyState) {
        return;
      }

      if (value === 'customize') {
        if (!isOriginTemplateConfig.value) {
          emit('rule-list-change', base64ToRuleArr(props.defaultValue.predefined_varibles));
        } else {
          emit('rule-list-change', []);
        }
        return;
      }
      if (!templateRuleId.value) {
        emit('rule-list-change', []);
      }
    };

    const handleBeforeRuleTypeChange = (value: string) => {
      isShowSwitchPopConfirm = true;
      ruleType.value = value;
      localRuleType = value;
      nextTick(() => {
        ruleType.value = value === 'customize' ? 'template' : 'customize';
      });
    };

    const handleRuleTypeChangeConfirm = () => {
      isShowSwitchPopConfirm = false;
      handleRuleTypeChange(localRuleType);
    };

    const initDefaultConfig = (updateType = true) => {
      if (!isOriginTemplateConfig.value) {
        if (updateType) {
          handleRuleTypeChange('customize');
        }
        emit('rule-list-change', base64ToRuleArr(props.defaultValue.predefined_varibles));
      } else {
        if (updateType) {
          handleRuleTypeChange('template');
        } else {
          handleSelectTemplate(props.defaultValue.regex_template_id);
        }
      }
    };

    watch(
      () => props.defaultValue.regex_rule_type,
      () => {
        initDefaultConfig();
      },
      { immediate: true },
    );

    watch(
      () => [props.defaultValue, templateList.value, isCustomize.value],
      () => {
        if (isShowSwitchPopConfirm || isCustomize.value) {
          return;
        }

        if (!templateRuleId.value) {
          const templateId = props.defaultValue.regex_template_id;
          if (templateId !== undefined && templateList.value.length) {
            handleSelectTemplate(templateId);
          }
        } else {
          handleSelectTemplate(templateRuleId.value);
        }
      },
      {
        immediate: true,
        deep: true,
      },
    );

    // 初始化模板列表
    const initTemplateList = async () => {
      const res = (await ServicesInstance.logClustering.ruleTemplate({
        params: {
          space_uid: templateSpaceUid.value,
        },
      })) as IResponseData<RuleTemplate[]>;
      templateList.value = res.data.map((item, index) => ({
        ...item,
        name: item.template_name,
        index,
      }));
    };

    const handleSearch = () => {
      emit('search', searchValue.value);
    };

    function handleSelectTemplate(value?: number) {
      const matchedTemplate = templateList.value.find(item => item.id === value);
      templateRuleId.value = matchedTemplate?.id || 0;
      const selectTemplateStr = matchedTemplate?.predefined_varibles || '';
      emit('rule-list-change', selectTemplateStr ? base64ToRuleArr(selectTemplateStr) : []);
    }

    const handleRefresh = async () => {
      await initTemplateList();
      handleSelectTemplate(templateRuleId.value);
    };

    const inputFileEvent = () => {
      // 检查文件是否选择:
      if (!inputDocument.value) return;
      const file = inputDocument.files![0];
      // 读取文件:
      const reader = new FileReader();
      reader.onload = (e: any) => {
        try {
          const list = Object.values(JSON.parse(e.target.result)).map((item: any, index: number) => {
            if (!item.placeholder || !String(item.rule)) throw new Error('无效的json');
            return {
              [item.placeholder]: String([item.rule]),
              __Index__: index,
            };
          });
          emit('rule-list-change', list);
        } catch {
          TDesignMessage("error", { content: t('不是有效的json文件') });
        }
      };
      // 以Text的形式读取文件:
      reader.readAsText(file);
    };

    const initInputType = () => {
      const uploadEl = document.createElement('input');
      uploadEl.type = 'file';
      uploadEl.style.display = 'none';
      uploadEl.addEventListener('change', inputFileEvent);
      inputDocument = uploadEl;
    };

    /** 导出规则 */
    const handleExportRule = () => {
      if (!props.ruleList.length) {
        TDesignMessage("error", { content: t('聚类规则为空，无法导出规则') });
        return;
      }
      const eleLink = document.createElement('a');
      const time = `${dayjs().format('YYYYMMDDHHmmss')}`;
      eleLink.download = `bk_log_search_download_${time}.json`;
      eleLink.style.display = 'none';
      const jsonStr = props.ruleList.reduce<Record<string, any>>((pre, cur, index) => {
        const entriesArr = Object.entries(cur);
        pre[index] = {
          placeholder: entriesArr[0][0],
          rule: entriesArr[0][1],
        };
        return pre;
      }, {});
      // 字符内容转变成blob地址
      const blob = new Blob([JSON.stringify(jsonStr, null, 4)]);
      eleLink.href = URL.createObjectURL(blob);
      // 触发点击
      document.body.appendChild(eleLink);
      eleLink.click();
      document.body.removeChild(eleLink);
    };

    const handleConfirmUnbindTemplate = () => {
      handleRuleTypeChange('customize', true);
      handleSelectTemplate(templateRuleId.value);
      emit('unbind-template');
    };

    const handleGoTemplateManage = (templateId?: number) => {
      const query = {
        collectorConfigId: store.state.indexSetFieldConfig.clean_config.extra.collector_config_id,
      };
      if (templateId) {
        Object.assign(query, { templateId });
      }
      const href = router.resolve({
        name: 'templateManage',
        query,
      });
      window.open(href.href, '_blank', 'noopener,noreferrer');
    };

    initTemplateList();

    onMounted(() => {
      initInputType();
    });

    expose({
      getRuleInfo: () => ({
        type: ruleType.value,
        id: isCustomize.value ? 0 : templateRuleId.value,
      }),
      reset: () => handleSelectTemplate(props.defaultValue.regex_template_id),
    });

    return () => (
      <div class='rule-operate-main'>
        <bk-popconfirm
          width='288'
          confirm-text={t('确认切换')}
          content={t('切换后，已有的相关配置将会丢失，请确认。')}
          placement='bottom'
          title={t('确认切换配置模式？')}
          trigger='click'
          onCancel={() => {
            isShowSwitchPopConfirm = false;
          }}
          onConfirm={handleRuleTypeChangeConfirm}
        >
          <TRadioGroup
            class='type-choose-main'
            value={ruleType.value}
            onChange={(value) => { if (typeof value === 'string') (handleBeforeRuleTypeChange)(value); }}
          >
            <TRadio value='customize'>{t('自定义')}</TRadio>
            <TRadio value='template'>{t('模板')}</TRadio>
          </TRadioGroup>
        </bk-popconfirm>
        <div class='right-oprate-main'>
          {isCustomize.value ? (
            <div class='custom-operate-main'>
              <bk-input
                style='width: 240px'
                placeholder={t('搜索 占位符')}
                right-icon='bk-icon icon-search'
                value={searchValue.value}
                clearable
                onChange={(value: string) => {
                  searchValue.value = value;
                }}
                onClear={handleSearch}
                onEnter={handleSearch}
                onRightIconClick={handleSearch}
              />
              <bk-dropdown-menu
                v-slots={{
                  'dropdown-trigger': () => (
                    <div>
                      <TButton theme='default' variant='outline'
                        class='operate-btn'
                        data-test-id='LogCluster_button_addNewRules'
                      >
                        {t('导入')}
                      </TButton>
                    </div>
                  ),
                  'dropdown-content': () => (
                    <ul class='bk-dropdown-list'>
                      <li>
                        <a
                          href='javascript:;'
                          onClick={() => inputDocument.click()}
                        >
                          {t('本地导入')}
                        </a>
                      </li>
                      <li>
                        <a
                          href='javascript:;'
                          onClick={() => {
                            isShowOtherImport.value = true;
                          }}
                        >
                          {t('其他索引集导入')}
                        </a>
                      </li>
                    </ul>
                  ),
                }}
              ></bk-dropdown-menu>
              <TButton theme='default' variant='outline'
                class='operate-btn'
                onClick={handleExportRule}
              >
                {t('导出')}
              </TButton>
              {!isOriginTemplateConfig.value && (
                <TButton theme='default' variant='outline'
                  style='min-width: 72px'
                  class='operate-btn'
                  onClick={() => initDefaultConfig(false)}
                >
                  {t('恢复默认')}
                </TButton>
              )}
            </div>
          ) : (
            <div class='template-operate-main'>
              <bk-select
                ref='templateListRef'
                ext-cls='template-select'
                clearable={false}
                ext-popover-cls='template-select-popover'
                value={templateRuleId.value}
                searchable
                onChange={handleSelectTemplate}
              >
                {templateList.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
                {!props.isExternal && (
                  <div
                    class='template-manage-extension'
                    slot='extension'
                    onClick={() => handleGoTemplateManage()}
                  >
                    <log-icon type='shezhi' />
                    {t('模板管理')}
                  </div>
                )}
              </bk-select>
              {!props.isExternal && templateRuleId.value > 0 && hasMatchedTemplate.value && (
                <TButton
                  size='small'
                  theme='primary'
                  
                  onClick={() => handleGoTemplateManage(templateRuleId.value)} variant={(true) ? 'text' : ('base')}
                >
                  <log-icon type='edit' />
                  <span style='margin-left: 5px'>{t('编辑模板')}</span>
                </TButton>
              )}
              <bk-popconfirm
                v-slots={{
                  content: () => (
                    <div>
                      <div class='rule-template-unbind-main'>
                        <div class='warn-title'>{t('确认与模板解绑？')}</div>
                        <div class='template-name'>
                          {t('模板名称')}：{currentTemplate.value?.name}
                        </div>
                        <div class='tip-display'>
                          <div>{t('与模板解除绑定后，不再跟随模板变更')}；</div>
                          <div>
                            <i18n path='相关规则配置将落地到  {0}，可在 {0} 继续调整'>
                              <span style='font-weight: 700'>{t('自定义')}</span>
                            </i18n>
                            。
                          </div>
                        </div>
                      </div>
                    </div>
                  ),
                }}
                width={380}
                confirm-text={t('解绑')}
                trigger='click'
                onConfirm={handleConfirmUnbindTemplate}
              >
                {isOriginTemplateConfig.value && isSameTemplateId.value && hasMatchedTemplate.value && (
                  <TButton
                    size='small'
                    theme='primary'
                     variant={(true) ? 'text' : ('base')}
                  >
                    <log-icon type='jiebang' />
                    <span style='margin-left: 5px'>{t('解绑')}</span>
                  </TButton>
                )}
              </bk-popconfirm>

              <TButton
                size='small'
                theme='primary'
                
                onClick={handleRefresh} variant={(true) ? 'text' : ('base')}
              >
                <log-icon type='refresh-icon' />
                <span style='margin-left: 5px'>{t('刷新')}</span>
              </TButton>
            </div>
          )}
        </div>
        <other-import
          isShow={isShowOtherImport.value}
          onShowChange={(value: boolean) => {
            isShowOtherImport.value = value;
          }}
          onSuccess={(list: unknown) => emit('rule-list-change', list)}
        />
      </div>
    );
  },
});
