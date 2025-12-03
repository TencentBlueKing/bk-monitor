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
import { uniqueId } from 'lodash-es';
import useStore from '@/hooks/use-store';

import './log-keyword-form-dialog.scss';

// 默认表单数据
const getDefaultFormData = (): FormData => ({
  taskId: '',
  taskName: '',
  creator: '',
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
});

export default defineComponent({
  name: 'LogKeywordFormDialog',
  components: {
    bkColorPicker,
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

    // 表单验证规则
    const formRules = computed(() => {
      return {
        taskName: [basicRules],
        matchType: [basicRules],
        selectField: [basicRules],
        regex: [basicRules],
        actionType: [basicRules],
        tagName: [
          {
            required: localFormData.value.actionType === ActionType.MARK,
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

    // 模拟应用实例数据
    const mockAppInstanceList = [
      { id: 'app-001', name: '支付网关服务' },
      { id: 'app-002', name: '用户认证中心' },
      { id: 'app-003', name: '订单处理系统' },
      { id: 'app-004', name: '数据报表服务' },
      { id: 'app-005', name: '消息通知服务' },
    ];

    // 模拟服务实例数据
    const mockServiceInstanceList = [
      { id: 'srv-mysql-primary', name: '主交易数据库 (MySQL)' },
      { id: 'srv-redis-session', name: '用户会话缓存 (Redis)' },
      { id: 'srv-kafka-log', name: '日志消息队列 (Kafka)' },
      { id: 'srv-es-search', name: '全文检索引擎 (Elasticsearch)' },
      { id: 'srv-consul-registry', name: '服务注册中心 (Consul)' },
    ];

    // 处理对话框显示状态变化
    const handleDialogValueChange = (value: boolean) => {
      if (!value) {
        handleReset();
        handleCancel();
      }
    };

    // 处理取消
    const handleCancel = () => {
      emit('cancel');
    };

    // 根据匹配类型和执行动作组装表单数据
    const assembleFormData = (): FormData => {
      // 创建默认表单数据结构
      const defaultData = getDefaultFormData();

      // 根据操作类型决定 taskId
      if (props.type === 'create') {
        defaultData.taskId = uniqueId();
      } else if (props.type === 'edit') {
        defaultData.taskId = localFormData.value.taskId;
      }

      // 基础字段始终赋值
      defaultData.taskName = localFormData.value.taskName;
      defaultData.creator = store.state.userMeta?.username;
      defaultData.matchType = localFormData.value.matchType;
      defaultData.actionType = localFormData.value.actionType;
      defaultData.tagName = localFormData.value.tagName;

      // 根据匹配类型赋值相应字段
      if (localFormData.value.matchType === MatchType.FIELD) {
        defaultData.selectField = localFormData.value.selectField;
        // regex 保持默认空值
      } else if (localFormData.value.matchType === MatchType.REGEX) {
        defaultData.regex = localFormData.value.regex;
        // selectField 保持默认空值
      }

      // 根据执行动作赋值相应字段
      if (localFormData.value.actionType === ActionType.MARK) {
        defaultData.color = localFormData.value.color;
        // jumpLink 和 relatedConfig 保持默认值
      } else if (localFormData.value.actionType === ActionType.JUMP) {
        defaultData.jumpLink = localFormData.value.jumpLink;
        // color 和 relatedConfig 保持默认值
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
    };

    // 监听匹配类型和执行动作变化，变化时清除错误提示
    watch(
      () => localFormData.value.matchType,
      () => {
        handleClearError();
      },
    );

    watch(
      () => localFormData.value.actionType,
      () => {
        handleClearError();
      },
    );

    watch(
      () => props.formData,
      (newFormData: FormData) => {
        if (newFormData) {
          localFormData.value = { ...newFormData };
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
            <bk-form-item
              label={t('正则表达式')}
              required
              property='regex'
            >
              <bk-input
                value={localFormData.value.regex}
                on-change={(value: string) => (localFormData.value.regex = value)}
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
              <bk-input
                value={localFormData.value.jumpLink}
                on-change={(value: string) => (localFormData.value.jumpLink = value)}
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
