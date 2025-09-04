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

import { defineComponent, ref, computed, watch } from 'vue';
import { getRegExp } from '@/common/util';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';
import { BK_LOG_STORAGE } from '@/store/store.type';
import RuleTrigger from './rule-trigger';
import ControlOperate from './control-operate';

import './index.scss';

export default defineComponent({
  name: 'ConfigRule',
  components: {
    RuleTrigger,
    ControlOperate,
  },
  props: {
    data: {
      type: Object,
      default: () => undefined,
    },
    isCreate: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const popoverRef = ref(null);
    const formRef = ref(null);
    const controlOperateRef = ref(null);
    const formData = ref({
      op: '',
      values: [],
    });
    const localFormData = ref({
      field_alias: '',
      field_name: '',
      op: '',
      values: [],
    });

    const searchValue = ref('');
    const activeIndex = ref(0);
    const hoverIndex = ref(0);

    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
    const isFieldListEmpty = computed(() => !indexFieldInfo.value.fields.length);
    const isSearchEmpty = computed(() => !isFieldListEmpty.value && !filterFieldList.value.length);
    const exceptionType = computed(() => (isFieldListEmpty.value ? 'empty' : 'search-empty'));
    const textDir = computed(() => {
      const textEllipsisDir = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
      return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
    });
    const filterFieldList = computed(() => {
      const regExp = getRegExp(searchValue.value.trim());
      const filterFn = field =>
        !/^__dist/.test(field.field_name) &&
        field.field_type !== '__virtual__' &&
        (regExp.test(field.field_alias) || regExp.test(field.field_name) || regExp.test(field.query_alias));
      return indexFieldInfo.value.fields.filter(filterFn);
    });
    const isConfirmEnable = computed(() => formData.value.op && formData.value.values.length);
    const currentFieldInfo = computed(() => filterFieldList.value[activeIndex.value]);

    const conditionList = [
      { id: '=', name: '=' },
      { id: '!=', name: '!=' },
      { id: 'contains', name: t('包含') },
      { id: 'not contains', name: t('不包含') },
    ];

    const formRules = {
      op: [
        {
          validator: (value: string) => !!value,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
      values: [
        {
          validator: (values: string[]) => !!values.length,
          message: t('必填项'),
          trigger: 'blur',
        },
        // {
        //   validator: (values: string[]) => {
        //     if (['NOT LIKE', 'LIKE'].includes(formData.value.op)) {
        //       return values.every(item => /%/.test(item));
        //     }

        //     return true;
        //   },
        //   message: t('使用LIKE、NOT LINK操作符时请在过滤值前后增加%'),
        //   trigger: 'blur',
        // },
      ],
    };

    watch(
      () => [props.data, filterFieldList.value],
      () => {
        if (props.data && filterFieldList.value.length) {
          activeIndex.value =
            filterFieldList.value.findIndex(
              item => item.field_name === props.data.field_name || item.field_name === props.data.fields_name,
            ) || 0;
          hoverIndex.value = activeIndex.value;
          formData.value = {
            op: props.data.op,
            values: props.data.value,
          };

          const fieldInfo = filterFieldList.value[activeIndex.value];
          localFormData.value = {
            op: props.data.op,
            values: props.data.value,
            field_name: fieldInfo.field_name,
            field_alias: fieldInfo.field_alias,
          };
        }
      },
      { immediate: true },
    );

    const getFieldIcon = (type: string) => {
      return fieldTypeMap.value[type] ? fieldTypeMap.value[type]?.icon : 'bklog-icon bklog-unkown';
    };

    const getFieldIconColor = (type: string) => {
      return fieldTypeMap.value[type] ? fieldTypeMap.value[type]?.color : '#EAEBF0';
    };

    const getFieldIconTextColor = (type: string) => {
      return fieldTypeMap.value[type].textColor;
    };

    const handleFieldItemClick = (fieldInfo: any, index: number) => {
      activeIndex.value = index;
      hoverIndex.value = index;
    };

    const handelClickConfirm = () => {
      formRef.value
        .validate()
        .then(() => {
          localFormData.value = {
            op: formData.value.op,
            values: formData.value.values,
            field_name: currentFieldInfo.value.field_name,
            field_alias: currentFieldInfo.value.field_alias,
          };

          const result = {
            field_name: currentFieldInfo.value.field_name,
            op: formData.value.op,
            value: formData.value.values,
          };
          emit('confirm', result);
          handleClickCancel();
        })
        .catch(e => {
          console.error('error = ', e);
        });
    };

    const handleClickKeyUp = () => {
      if (hoverIndex.value > 0) {
        hoverIndex.value = hoverIndex.value - 1;
      }
    };

    const handleClickKeyDown = () => {
      if (hoverIndex.value < filterFieldList.value.length - 1) {
        hoverIndex.value = hoverIndex.value + 1;
      }
    };

    const handelClickEnter = () => {
      if (activeIndex.value !== hoverIndex.value) {
        activeIndex.value = hoverIndex.value;
      }
    };

    const handleClickTrigger = () => {
      emit('click-trigger');
      popoverRef.value.showHandler();
    };

    const handleClickCancel = () => {
      popoverRef.value.hideHandler();
    };

    const handleClickDelete = () => {
      emit('delete');
    };

    const handlePopoverShow = () => {
      formRef.value?.clearError();
      controlOperateRef.value.bindKeyEvent();
    };

    const handlePopoverHide = () => {
      // formData.value = { op: '', values: [] };
      controlOperateRef.value.unbindKeyEvent();
    };

    expose({
      hide: handleClickCancel,
    });

    return () => (
      <bk-popover
        ref={popoverRef}
        placement='bottom'
        ext-cls='config-rule-popover'
        width={720}
        tippy-options={{
          theme: 'light',
          trigger: 'click',
          hideOnClick: false,
        }}
        on-show={handlePopoverShow}
        on-hide={handlePopoverHide}
      >
        <RuleTrigger
          isCreate={props.isCreate}
          data={localFormData.value}
          on-click={handleClickTrigger}
          on-delete={handleClickDelete}
        />
        <div slot='content'>
          <div class='config-rule-content'>
            <div class='filter-main'>
              <div class='field-list'>
                <div class='search-input'>
                  <bk-input
                    style='width: 100%'
                    value={searchValue.value}
                    clearable
                    placeholder={t('请输入关键字')}
                    behavior='simplicity'
                    left-icon='bk-icon icon-search'
                    on-change={value => (searchValue.value = value)}
                  />
                </div>
                <div class='field-list-main'>
                  {filterFieldList.value.map((item, index) => (
                    <div
                      class={[
                        'config-rule-field-row',
                        {
                          'is-active': activeIndex.value === index,
                          'is-locate': hoverIndex.value === index,
                        },
                      ]}
                      data-tab-index={index}
                      key={item.field_name}
                      on-click={() => handleFieldItemClick(item, index)}
                      on-mouseenter={() => (hoverIndex.value = activeIndex.value)}
                    >
                      <span
                        style={{
                          backgroundColor: getFieldIconColor(item.field_type),
                          color: getFieldIconTextColor(item.field_type),
                        }}
                        class={[getFieldIcon(item.field_type), 'field-type-icon']}
                      ></span>
                      <div
                        class='display-container rtl-text'
                        dir={textDir.value}
                      >
                        <bdi>
                          <span class='field-alias'>{item.field_alias}</span>
                          <span class='field-name'>({item.field_name})</span>
                        </bdi>
                      </div>
                    </div>
                  ))}
                  {(isFieldListEmpty.value || isSearchEmpty.value) && (
                    <bk-exception
                      style='justify-content: center; height: 260px'
                      type={exceptionType.value}
                      scene='part'
                    />
                  )}
                </div>
              </div>
              <div class='value-list'>
                <bk-form
                  ref={formRef}
                  form-type='vertical'
                  {...{
                    props: {
                      model: formData.value,
                      rules: formRules,
                    },
                  }}
                >
                  <bk-form-item
                    label={t('条件')}
                    property='op'
                    error-display-type='normal'
                    required
                  >
                    <div class='setting-item'>
                      <bk-select
                        style='width: 314px'
                        value={formData.value.op}
                        clearable={false}
                        on-change={value => (formData.value.op = value)}
                      >
                        {conditionList.map(option => (
                          <bk-option
                            key={option.id}
                            id={option.id}
                            name={option.name}
                          />
                        ))}
                      </bk-select>
                    </div>
                  </bk-form-item>
                  <bk-form-item
                    label={t('检索值')}
                    property='values'
                    error-display-type='normal'
                    required
                  >
                    <bk-tag-input
                      value={formData.value.values}
                      content-width={232}
                      placeholder={t('请输入')}
                      trigger='focus'
                      allow-auto-match
                      allow-create
                      on-change={value => (formData.value.values = value)}
                    />
                  </bk-form-item>
                </bk-form>
              </div>
            </div>
            <control-operate
              ref={controlOperateRef}
              confrim-enable={isConfirmEnable.value}
              on-up={handleClickKeyUp}
              on-down={handleClickKeyDown}
              on-ctrlenter={handelClickConfirm}
              on-enter={handelClickEnter}
              on-esc={handleClickCancel}
              on-confirm={handelClickConfirm}
              on-cancel={handleClickCancel}
            />
          </div>
        </div>
      </bk-popover>
    );
  },
});
