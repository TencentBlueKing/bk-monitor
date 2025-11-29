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

import { computed, defineComponent, ref } from 'vue';

import { t } from '@/hooks/use-locale';
import { FormData, MatchType, ActionType, RelatedResource } from './types';
import useStore from '@/hooks/use-store';
import { bkColorPicker } from 'bk-magic-vue';

import './log-keyword-setting.scss';

export default defineComponent({
  name: 'LogKeywordSetting',
  components: {
    bkColorPicker,
  },
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  setup(props) {
    const store = useStore();

    // 匹配类型选项
    const matchTypeOptions = [
      { label: t('字段匹配'), value: MatchType.FIELD },
      { label: t('正则匹配'), value: MatchType.REGEX },
    ];

    // 执行动作选项
    const actionTypeOptions = [
      { label: t('标记'), value: ActionType.MARK },
      { label: t('跳转'), value: ActionType.JUMP },
      { label: t('关联'), value: ActionType.RELATED },
    ];

    // 关联资源选项
    const relatedResourceOptions = [
      { label: t('主机'), value: RelatedResource.HOST },
      { label: t('容器'), value: RelatedResource.CONTAINER },
      { label: 'APM', value: RelatedResource.APM },
      { label: 'Trace', value: RelatedResource.TRACE },
      { label: 'Code', value: RelatedResource.CODE },
    ];

    const dialogVisible = ref(false); // Dialog 显示状态
    const labelWidth = ref(store.state.isEnLanguage ? 130 : 70); // 标签宽度
    const formRef = ref(null);
    const formData = ref<FormData>({
      taskName: '', // 任务名称
      matchType: MatchType.FIELD, // 匹配类型
      selectField: '', // 选择字段
      regex: '', // 正则表达式
      actionType: ActionType.MARK, // 执行动作
      tagName: '', // tag名称
      color: '', // 颜色
      jumpLink: '', // 跳转链接
      relatedResource: RelatedResource.HOST, // 关联资源
      relatedConfig: {
        appInstance: '', // 应用实例
        serviceInstance: '', // 服务实例
      },
    });

    // 通用表单验证规则
    const basicRules = {
      required: true,
      trigger: 'blur',
    };

    const formRules = computed(() => {
      return {
        taskName: [basicRules],
        matchType: [basicRules],
        selectField: [basicRules],
        regex: [basicRules],
        actionType: [basicRules],
        tagName: [
          {
            required: formData.value.actionType === ActionType.MARK,
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

    const handleValueChange = (value: boolean) => {
      dialogVisible.value = value;
      if (!value) {
        handleReset();
        formRef.value?.clearError();
      }
    };

    // 重置表单
    const handleReset = () => {
      formData.value = {
        taskName: '',
        matchType: MatchType.FIELD,
        selectField: '',
        regex: '',
        actionType: ActionType.MARK,
        tagName: '',
        color: '',
        jumpLink: '',
        relatedResource: RelatedResource.HOST,
        relatedConfig: {
          appInstance: '',
          serviceInstance: '',
        },
      };
    };

    // 新建关键字
    const handleConfirm = async () => {
      console.log('新建关键字', formData.value);
      // 先进行表单验证
      const isValid = await formRef.value.validate();
      if (!isValid) {
        return;
      }
      dialogVisible.value = false;
    };

    // label宽度计算属性
    const labelWidthValue = computed(() => {
      if (formData.value.matchType === MatchType.FIELD) {
        return labelWidth.value;
      }
      return labelWidth.value + 12;
    });

    // 任务名称插槽
    const taskNameSlot = {
      default: ({ row }) => (
        <bk-button
          text
          theme='primary'
          class='name-button'
        >
          {row.taskName}
        </bk-button>
      ),
    };

    // 创建人插槽
    const creatorSlot = {
      default: ({ row }) => <bk-user-display-name user-id={row.creator}></bk-user-display-name>,
    };

    // 跳转链接插槽
    const jumpLinkSlot = {
      default: () => (
        <bk-button
          text
          theme='primary'
        >
          {t('前往')}
        </bk-button>
      ),
    };

    return () => (
      <div class='log-keyword-setting'>
        {/* 新建按钮 */}
        <bk-button
          theme='primary'
          class='new-button'
          title={t('新建')}
          on-click={() => (dialogVisible.value = true)}
        >
          {t('新建')}
        </bk-button>
        {/* 表格部分 */}
        <bk-table data={props.data}>
          <bk-table-column
            label={t('任务名称')}
            prop='taskName'
            min-width='120'
            scopedSlots={taskNameSlot}
          />
          <bk-table-column
            label={t('正则表达式')}
            prop='regex'
            min-width='200'
          />
          <bk-table-column
            label={t('类型')}
            prop='type'
            width='120'
          />
          <bk-table-column
            label={t('创建人')}
            prop='creator'
            min-width='120'
            scopedSlots={creatorSlot}
          />
          <bk-table-column
            label={t('跳转链接')}
            prop='jumpLink'
            width='120'
            scopedSlots={jumpLinkSlot}
          />
          <bk-table-column
            label={t('操作')}
            width='150'
          >
            <bk-button
              text
              theme='primary'
              class='mr16'
            >
              {t('编辑')}
            </bk-button>
            <bk-button
              text
              theme='primary'
            >
              {t('删除')}
            </bk-button>
          </bk-table-column>
        </bk-table>
        {/* 新建日志关键字表单 */}
        <bk-dialog
          value={dialogVisible.value}
          on-value-change={handleValueChange}
          on-confirm={handleConfirm}
          mask-close={false}
          auto-close={false}
          title={t('日志关键字')}
          header-position='left'
          width='532'
          ext-cls='log-keyword-setting-dialog'
        >
          <bk-form
            ref={formRef}
            label-width={labelWidthValue.value}
            {...{
              props: {
                model: formData.value,
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
                value={formData.value.taskName}
                on-change={(value: string) => (formData.value.taskName = value)}
              />
            </bk-form-item>
            <bk-form-item
              label={t('匹配类型')}
              required
              property='matchType'
            >
              <bk-radio-group
                value={formData.value.matchType}
                on-change={(value: MatchType) => (formData.value.matchType = value)}
              >
                {matchTypeOptions.map(option => (
                  <bk-radio value={option.value}>{option.label}</bk-radio>
                ))}
              </bk-radio-group>
            </bk-form-item>
            {/* 根据匹配类型条件显示字段 */}
            {formData.value.matchType === MatchType.FIELD && (
              <bk-form-item
                label={t('选择字段')}
                required
                property='selectField'
              >
                <bk-select></bk-select>
              </bk-form-item>
            )}
            {formData.value.matchType === MatchType.REGEX && (
              <bk-form-item
                label={t('正则表达式')}
                required
                property='regex'
              >
                <bk-input
                  value={formData.value.regex}
                  on-change={(value: string) => (formData.value.regex = value)}
                  type='textarea'
                  input-style={{ height: '118px' }}
                />
              </bk-form-item>
            )}
            <bk-form-item
              label={t('执行动作')}
              required
              property='actionType'
            >
              <bk-radio-group
                value={formData.value.actionType}
                on-change={(value: ActionType) => (formData.value.actionType = value)}
              >
                {actionTypeOptions.map(option => (
                  <bk-radio value={option.value}>{option.label}</bk-radio>
                ))}
              </bk-radio-group>
            </bk-form-item>
            {/* 根据执行动作条件显示不同配置 */}
            {formData.value.actionType === ActionType.MARK && (
              <div class='mt22'>
                <bk-form-item
                  label={t('配置')}
                  required
                  property='tagName'
                >
                  <bk-input
                    value={formData.value.tagName}
                    on-change={(value: string) => (formData.value.tagName = value)}
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
                      value={formData.value.color}
                      on-change={(value: string) => (formData.value.color = value)}
                    ></bk-color-picker>
                  </div>
                </bk-form-item>
              </div>
            )}
            {(formData.value.actionType === ActionType.JUMP || formData.value.actionType === ActionType.RELATED) && (
              <bk-form-item
                label={t('tag 名称')}
                property='tagName'
              >
                <bk-input
                  value={formData.value.tagName}
                  on-change={(value: string) => (formData.value.tagName = value)}
                  placeholder={t('请输入tag名称，不得超出8个字母、数字、_')}
                />
              </bk-form-item>
            )}
            {formData.value.actionType === ActionType.JUMP && (
              <bk-form-item
                label={t('跳转链接')}
                required
                property='jumpLink'
              >
                <bk-input
                  value={formData.value.jumpLink}
                  on-change={(value: string) => (formData.value.jumpLink = value)}
                />
              </bk-form-item>
            )}
            {formData.value.actionType === ActionType.RELATED && (
              <div class='mt22'>
                <bk-form-item
                  label={t('关联资源')}
                  required
                  property='relatedResource'
                >
                  <bk-radio-group
                    value={formData.value.relatedResource}
                    on-change={(value: RelatedResource) => (formData.value.relatedResource = value)}
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
                  <bk-select placeholder={t('请选择应用实例')}></bk-select>
                </bk-form-item>
                <bk-form-item
                  required
                  property='relatedConfig.serviceInstance'
                >
                  <bk-select placeholder={t('请选择服务实例')}></bk-select>
                </bk-form-item>
              </div>
            )}
          </bk-form>
        </bk-dialog>
      </div>
    );
  },
});
