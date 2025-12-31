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

import { computed, defineComponent, ref, watch } from 'vue';
import { t } from '@/hooks/use-locale';
import { bkColorPicker } from 'bk-magic-vue';
import { FormData, MatchType, ActionType, RelatedResource } from './types';
import useStore from '@/hooks/use-store';
import JumpLinkEditor from './jump-link-editor';

import './log-keyword-form-dialog.scss';

// 组件内部使用的表单数据类型（包含 originalText）
type LocalFormData = FormData & { originalText: string };

// 默认表单数据（包含originalText用于表单验证）
const getDefaultFormData = (): LocalFormData => ({
  taskName: '',
  creator: '',
  matchType: MatchType.FIELD,
  selectField: '',
  regex: '',
  originalText: '', // 仅用于正则测试，不提交后端
  actionType: ActionType.MARK,
  tagName: '',
  color: '#FF4500',
  jumpLink: '',
  relatedResource: RelatedResource.HOST,
  relatedConfig: {
    appInstance: '',
    serviceInstance: '',
  },
});

export default defineComponent({
  name: 'LogKeywordFormDialog',
  components: {
    bkColorPicker,
    JumpLinkEditor,
  },
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    formData: {
      type: Object,
      default: null,
    },
    type: {
      type: String,
      default: 'create', // create | edit | view
      validator: (value: string) => ['create', 'edit', 'view'].includes(value),
    },
  },
  emits: ['confirm', 'cancel'],
  setup(props, { emit }) {
    const store = useStore();
    const formRef = ref(null);
    const localFormData = ref(getDefaultFormData());
    const labelWidth = ref(store.state.isEnLanguage ? 130 : 70);

    // 正则测试相关状态
    const regexTestResult = ref(''); // 测试匹配结果
    const hasTestedRegex = ref(false); // 是否已进行正则测试
    const showTestResult = ref(false); // 是否显示测试结果区域

    // 匹配类型选项
    const matchTypeOptions = [
      { label: t('字段匹配'), value: MatchType.FIELD },
      { label: t('正则匹配'), value: MatchType.REGEX },
    ];

    // 执行动作选项
    const actionTypeOptions = [
      { label: t('标记'), value: ActionType.MARK },
      { label: t('跳转'), value: ActionType.JUMP },
      // { label: t('关联'), value: ActionType.RELATED },
    ];

    // 关联资源选项
    const relatedResourceOptions = [
      { label: t('主机'), value: RelatedResource.HOST },
      { label: t('容器'), value: RelatedResource.CONTAINER },
      { label: 'APM', value: RelatedResource.APM },
      { label: 'Trace', value: RelatedResource.TRACE },
      { label: 'Code', value: RelatedResource.CODE },
    ];

    // 通用表单验证规则
    const basicRules = {
      required: true,
      trigger: 'blur',
    };

    // tagName 校验函数
    const validateTagName = (value: string): boolean => {
      // 去除首尾空格
      const trimmedValue = value?.trim() || '';

      // 如果是标记动作，tagName 为必填
      if (localFormData.value.actionType === ActionType.MARK && !trimmedValue) {
        return false;
      }

      // 如果有值，则进行格式校验
      if (trimmedValue) {
        // 检查长度（最多8个字符）
        if (trimmedValue.length > 8) {
          return false;
        }

        // 检查字符格式（只允许字母、数字、下划线）
        const regex = /^[a-zA-Z0-9_]+$/;
        return regex.test(trimmedValue);
      }

      return true;
    };

    // 表单验证规则
    const formRules = computed(() => {
      return {
        taskName: [basicRules],
        matchType: [basicRules],
        selectField: [basicRules],
        regex: [basicRules],
        actionType: [basicRules],
        originalText: [basicRules],
        tagName: [
          {
            required: localFormData.value.actionType === ActionType.MARK,
            trigger: 'blur',
          },
          {
            validator: validateTagName,
            message: t('tag名称不得超出8个字母、数字、_'),
            trigger: 'blur',
          },
        ],
        color: [basicRules],
        jumpLink: [basicRules],
        relatedResource: [basicRules],
        'relatedConfig.appInstance': [basicRules],
        'relatedConfig.serviceInstance': [basicRules],
      };
    });

    // 选择字段列表
    const selectFieldList = computed(() => {
      return (store.state.indexFieldInfo.fields ?? []).filter(f => f.es_doc_values && f.field_type === 'keyword');
    });

    // 应用实例数据
    const mockAppInstanceList = [];

    // 服务实例数据
    const mockServiceInstanceList = [];

    // 处理对话框显示状态变化
    const handleDialogValueChange = (value: boolean) => {
      if (!value) {
        handleReset();
        handleClearError();
        handleCancel();
      }
    };

    // 处理取消
    const handleCancel = () => {
      emit('cancel');
    };

    // 根据匹配类型和执行动作组装表单数据
    const assembleFormData = (): FormData => {
      // 使用解构排除originalText字段
      const { originalText, ...defaultData } = getDefaultFormData();
      const { bk_tenant_id: bkTenantId, username } = store.state.userMeta;

      // 基础字段始终赋值
      defaultData.taskName = localFormData.value.taskName.trim();
      defaultData.creator = bkTenantId ?? username;
      defaultData.matchType = localFormData.value.matchType;
      defaultData.actionType = localFormData.value.actionType;
      defaultData.tagName = localFormData.value.tagName.trim();

      // 根据匹配类型赋值相应字段
      if (localFormData.value.matchType === MatchType.FIELD) {
        defaultData.selectField = localFormData.value.selectField;
      } else if (localFormData.value.matchType === MatchType.REGEX) {
        defaultData.regex = localFormData.value.regex.trim();
      }

      // 根据执行动作赋值相应字段
      if (localFormData.value.actionType === ActionType.MARK) {
        defaultData.color = localFormData.value.color;
      } else if (localFormData.value.actionType === ActionType.JUMP) {
        defaultData.jumpLink = localFormData.value.jumpLink.trim();
      } else if (localFormData.value.actionType === ActionType.RELATED) {
        defaultData.relatedResource = localFormData.value.relatedResource;
        defaultData.relatedConfig = {
          appInstance: localFormData.value.relatedConfig.appInstance,
          serviceInstance: localFormData.value.relatedConfig.serviceInstance,
        };
        // color 和 jumpLink 保持默认值
      }

      return defaultData;
    };

    // 处理确认
    const handleConfirm = async () => {
      const isValid = await formRef.value.validate();
      if (!isValid) {
        return;
      }

      const submitData = assembleFormData();
      emit('confirm', submitData);
    };

    // 清除错误提示
    const handleClearError = () => {
      formRef.value?.clearError();
    };

    // 重置表单
    const handleReset = () => {
      localFormData.value = getDefaultFormData();
      // 重置正则测试相关状态
      regexTestResult.value = '';
      hasTestedRegex.value = false;
      showTestResult.value = false;
    };

    // 正则表达式测试匹配
    const handleTestRegex = () => {
      const { originalText, regex } = localFormData.value;

      if (!originalText.trim() || !regex.trim()) {
        regexTestResult.value = '请先输入原文和正则表达式';
        showTestResult.value = true; // 显示结果区域
        return;
      }

      showTestResult.value = true; // 显示结果区域

      try {
        const regexObj = new RegExp(regex, 'g');
        const matches = originalText.match(regexObj);

        if (matches && matches.length > 0) {
          regexTestResult.value = `${t('匹配成功！找到 {0} 个匹配项：', [matches.length])}\n${matches.map((match, index) => `${index + 1}. ${match}`).join('\n')}`;
        } else {
          regexTestResult.value = t('未找到匹配项');
        }

        hasTestedRegex.value = true;
      } catch (error) {
        regexTestResult.value = `${t('正则表达式语法错误：')}${error.message}`;
        hasTestedRegex.value = false;
      }
    };

    // 判断确认按钮是否应该禁用
    const isConfirmDisabled = computed(() => {
      return localFormData.value.matchType === MatchType.REGEX && !hasTestedRegex.value;
    });

    // 监听匹配类型和执行动作变化，变化时清除错误提示
    watch(
      () => [localFormData.value.matchType, localFormData.value.actionType],
      () => {
        handleClearError();
      },
    );

    // 监听匹配类型变化，重置正则测试状态
    watch(
      () => localFormData.value.matchType,
      (newMatchType) => {
        if (newMatchType !== MatchType.REGEX) {
          showTestResult.value = false;
          regexTestResult.value = '';
          hasTestedRegex.value = false;
        }
      },
    );

    // 监听原文和正则表达式变化，重置测试状态
    watch(
      () => [localFormData.value.originalText, localFormData.value.regex],
      () => {
        if (localFormData.value.matchType === MatchType.REGEX) {
          hasTestedRegex.value = false;
          regexTestResult.value = '';
        }
      },
    );

    watch(
      () => props.formData,
      (newFormData: FormData) => {
        if (newFormData) {
          localFormData.value = { ...newFormData, originalText: '' };
        } else {
          localFormData.value = getDefaultFormData();
        }
      },
      { immediate: true },
    );

    // label宽度计算属性
    const labelWidthValue = computed(() => {
      if (localFormData.value.matchType === MatchType.FIELD) {
        return labelWidth.value;
      }
      return labelWidth.value + 12;
    });

    return () => (
      <bk-dialog
        value={props.visible}
        on-value-change={handleDialogValueChange}
        mask-close={false}
        auto-close={false}
        title={t('日志关键字')}
        header-position='left'
        width='532'
        ext-cls='log-keyword-setting-dialog'
        transfer
        scopedSlots={{
          footer: () => (
            <div class='dialog-footer'>
              <span
                v-bk-tooltips={{
                  content: t('正则表达式未测试匹配'),
                  disabled: !isConfirmDisabled.value,
                }}
              >
                <bk-button
                  theme='primary'
                  disabled={isConfirmDisabled.value}
                  on-click={handleConfirm}
                >
                  {t('确认')}
                </bk-button>
              </span>
              <bk-button on-click={handleCancel}>{t('取消')}</bk-button>
            </div>
          ),
        }}
      >
        <bk-form
          ref={formRef}
          label-width={labelWidthValue.value}
          {...{
            props: {
              model: localFormData.value,
              rules: formRules.value,
            },
          }}
        >
          <bk-form-item
            label={t('任务名称')}
            required
            property='taskName'
          >
            <bk-input
              value={localFormData.value.taskName}
              on-change={(value: string) => (localFormData.value.taskName = value)}
            />
          </bk-form-item>
          <bk-form-item
            label={t('匹配类型')}
            required
            property='matchType'
          >
            <bk-radio-group
              value={localFormData.value.matchType}
              on-change={(value: MatchType) => (localFormData.value.matchType = value)}
            >
              {matchTypeOptions.map(option => (
                <bk-radio value={option.value}>{option.label}</bk-radio>
              ))}
            </bk-radio-group>
          </bk-form-item>
          {/* 根据匹配类型条件显示字段 */}
          {localFormData.value.matchType === MatchType.FIELD && (
            <bk-form-item
              label={t('选择字段')}
              required
              property='selectField'
            >
              <bk-select
                value={localFormData.value.selectField}
                on-change={(value: string) => (localFormData.value.selectField = value)}
                searchable
              >
                {selectFieldList.value.map(option => (
                  <bk-option
                    id={option.field_name}
                    key={option.field_name}
                    name={`${option.field_name}(${option.field_alias || option.field_name})`}
                  />
                ))}
              </bk-select>
            </bk-form-item>
          )}
          {localFormData.value.matchType === MatchType.REGEX && (
            <div class='mt22'>
              <bk-form-item
                label={t('原文')}
                required
                property='originalText'
              >
                <bk-input
                  value={localFormData.value.originalText}
                  on-change={(value: string) => (localFormData.value.originalText = value)}
                  type='textarea'
                  input-style={{ height: '80px' }}
                />
              </bk-form-item>
              <bk-form-item
                label={t('正则表达式')}
                required
                property='regex'
              >
                <bk-input
                  value={localFormData.value.regex}
                  on-change={(value: string) => (localFormData.value.regex = value)}
                  type='textarea'
                  input-style={{ height: '80px' }}
                />
              </bk-form-item>
              <bk-form-item>
                <bk-button
                  theme='primary'
                  outline
                  on-click={handleTestRegex}
                >
                  {t('测试匹配')}
                </bk-button>
              </bk-form-item>
              {showTestResult.value && (
                <bk-form-item label={t('匹配结果')}>
                  <bk-input
                    value={regexTestResult.value}
                    type='textarea'
                    input-style={{ height: '80px' }}
                    readonly
                    placeholder={t('点击"测试匹配"按钮查看结果')}
                  />
                </bk-form-item>
              )}
            </div>
          )}
          <bk-form-item
            label={t('执行动作')}
            required
            property='actionType'
            class='mt22'
          >
            <bk-radio-group
              value={localFormData.value.actionType}
              on-change={(value: ActionType) => (localFormData.value.actionType = value)}
            >
              {actionTypeOptions.map(option => (
                <bk-radio value={option.value}>{option.label}</bk-radio>
              ))}
            </bk-radio-group>
          </bk-form-item>
          {/* 根据执行动作条件显示不同配置 */}
          {localFormData.value.actionType === ActionType.MARK && (
            <div class='mt22'>
              <bk-form-item
                label={t('配置')}
                required
                property='tagName'
              >
                <bk-input
                  value={localFormData.value.tagName}
                  on-change={(value: string) => (localFormData.value.tagName = value)}
                  placeholder={t('请输入tag名称，不得超出8个字母、数字、_')}
                >
                  <template slot='prepend'>
                    <div class='prepend-text'>{t('tag名称')}</div>
                  </template>
                </bk-input>
              </bk-form-item>
              <bk-form-item
                required
                property='color'
              >
                <div class='color-item'>
                  <div class='prepend-text'>{t('颜色')}</div>
                  <bk-color-picker
                    value={localFormData.value.color}
                    on-change={(value: string) => (localFormData.value.color = value)}
                  ></bk-color-picker>
                </div>
              </bk-form-item>
            </div>
          )}
          {(localFormData.value.actionType === ActionType.JUMP
            || localFormData.value.actionType === ActionType.RELATED) && (
            <bk-form-item
              label={t('tag 名称')}
              property='tagName'
            >
              <bk-input
                value={localFormData.value.tagName}
                on-change={(value: string) => (localFormData.value.tagName = value)}
                placeholder={t('请输入tag名称，不得超出8个字母、数字、_')}
              />
            </bk-form-item>
          )}
          {localFormData.value.actionType === ActionType.JUMP && (
            <bk-form-item
              label={t('跳转链接')}
              required
              property='jumpLink'
            >
              <JumpLinkEditor
                value={localFormData.value.jumpLink}
                on-change={(value: string) => (localFormData.value.jumpLink = value)}
                placeholder={t('请输入跳转链接，支持 {变量名} 格式')}
              />
            </bk-form-item>
          )}
          {localFormData.value.actionType === ActionType.RELATED && (
            <div class='mt22'>
              <bk-form-item
                label={t('关联资源')}
                required
                property='relatedResource'
              >
                <bk-radio-group
                  value={localFormData.value.relatedResource}
                  on-change={(value: RelatedResource) => (localFormData.value.relatedResource = value)}
                >
                  {relatedResourceOptions.map(option => (
                    <bk-radio value={option.value}>{option.label}</bk-radio>
                  ))}
                </bk-radio-group>
              </bk-form-item>
              <bk-form-item
                label={t('关联配置')}
                required
                property='relatedConfig.appInstance'
              >
                <bk-select
                  placeholder={t('请选择应用实例')}
                  value={localFormData.value.relatedConfig.appInstance}
                  on-change={(value: string) => (localFormData.value.relatedConfig.appInstance = value)}
                  searchable
                >
                  {mockAppInstanceList.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    />
                  ))}
                </bk-select>
              </bk-form-item>
              <bk-form-item
                required
                property='relatedConfig.serviceInstance'
              >
                <bk-select
                  placeholder={t('请选择服务实例')}
                  value={localFormData.value.relatedConfig.serviceInstance}
                  on-change={(value: string) => (localFormData.value.relatedConfig.serviceInstance = value)}
                  searchable
                >
                  {mockServiceInstanceList.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    />
                  ))}
                </bk-select>
              </bk-form-item>
            </div>
          )}
        </bk-form>
      </bk-dialog>
    );
  },
});
