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

import { includesValue } from '@/shared/utils/typed-record';

import { defineComponent, ref, computed, watch, onMounted, onUnmounted } from 'vue';

import { getRegExp } from '@/shared/lib/util';
import useFieldEgges from '@/shared/composables/use-field-egges';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import { storeRuntimeCacheService } from '@/app/state/services/runtime-cache.service.js';
import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';

import ControlOperate from './control-operate/index';
import RuleTrigger from './rule-trigger/index';

import './index.scss';

export default defineComponent({
  emits: ["confirm","click-trigger","clickTrigger","delete"],

  name: 'ConfigRule',
  components: {
    RuleTrigger,
    ControlOperate,
  },
  props: {
    data: {
      type: Object,
      default: () => {},
    },
    isCreate: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const { isRequesting, isValidateItem, requestFieldEgges, setIsRequesting, isValidateEgges } = useFieldEgges();

    const fieldListMainRef = ref(null);
    const popoverRef = ref(null);
    const formRef = ref<import("@/shared/types/legacy-form").LegacyFormInstance | null>(null);
    const controlOperateRef = ref(null);
    const contentInputWrapperRef = ref(null);
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
    const isMatchListShown = ref(true);
    const fieldValueCache = ref<Record<string, string[]>>({});

    const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
    const fieldList = computed(() => store.getters.filteredFieldList ?? []);
    const isFieldListEmpty = computed(() => !store.state.indexFieldInfo.is_loading && !fieldList.value.length);
    const isSearchEmpty = computed(() => !(isFieldListEmpty.value || filterFieldList.value.length));
    const exceptionType = computed(() => (isFieldListEmpty.value ? 'empty' : 'search-empty'));
    const textDir = computed(() => {
      const textEllipsisDir = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
      return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
    });
    const filterFieldList = computed(() => {
      const regExp = getRegExp(searchValue.value.trim());
      const filterFn = (field: { field_name: string; field_type: string; field_alias: string; query_alias: string; }) =>
        !/^__dist/.test(field.field_name) &&
        field.field_type !== '__virtual__' &&
        !['dtEventTimeStamp', 'time', 'iterationIndex', 'gseIndex'].includes(field.field_name) &&
        (regExp.test(field.field_alias) || regExp.test(field.field_name) || regExp.test(field.query_alias));
      return fieldList.value.filter(filterFn);
    });
    const isConfirmEnable = computed(() => formData.value.op && formData.value.values.length);
    const currentFieldInfo = computed(() => filterFieldList.value[activeIndex.value]);
    const fieldAggsItems = computed(() => {
      void store.state.fieldAggsItemsVersion;
      return storeRuntimeCacheService.getFieldAggsItems(store.state.indexId || 'default');
    });

    const activeItemMatchList = computed(() => {
      return (fieldAggsItems.value[currentFieldInfo.value.field_name] ?? []).filter(
(        item: unknown) => !includesValue((formData.value.values ?? []), item),
      );
    });

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
      ],
    };

    const cacheCurrentFieldValues = () => {
      const fieldName = currentFieldInfo.value?.field_name;
      if (!fieldName) {
        return;
      }

      fieldValueCache.value[fieldName] = [...(formData.value.values ?? [])];
    };

    const restoreFieldValues = (fieldName?: string) => {
      formData.value.values = [...(fieldValueCache.value[fieldName] ?? [])];
    };

    const initData = () => {
      if (props.data && filterFieldList.value.length) {
        activeIndex.value =
          filterFieldList.value.findIndex(
(            item: { field_name: any; }) => item.field_name === props.data.field_name || item.field_name === props.data.fields_name,
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
        fieldValueCache.value[fieldInfo.field_name] = [...(props.data.value ?? [])];
      }
    };

    watch(
      () => [props.data, filterFieldList.value],
      () => {
        initData();
      },
      { immediate: true },
    );

    const getFieldIcon = (type: string) => {
      return fieldTypeMap.value[type]?.icon ?? 'bklog-icon bklog-unkown';
    };

    const getFieldIconColor = (type: string) => {
      return fieldTypeMap.value[type]?.color ?? '#EAEBF0';
    };

    const getFieldIconTextColor = (type: string) => {
      return fieldTypeMap.value[type]?.textColor ?? '#000';
    };

    const checkAndRequestEgges = () => {
      if (isValidateEgges(currentFieldInfo.value)) {
        isMatchListShown.value = true;
        setIsRequesting(true);
        requestFieldEgges(currentFieldInfo.value);
      }
    };

    const handleFieldItemClick = (index: number) => {
      if (activeIndex.value !== index) {
        cacheCurrentFieldValues();
        activeIndex.value = index;
        hoverIndex.value = index;
        restoreFieldValues(currentFieldInfo.value?.field_name);
      }

      checkAndRequestEgges();
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
        .catch((e: unknown) => {
          console.error('error = ', e);
        });
    };

    const handleChooseMatchItem = (e: any, item: string) => {
      e.stopPropagation();
      isMatchListShown.value = true;
      formData.value.values.push(item);
      cacheCurrentFieldValues();
    };

    const handleShowMatchList = () => {
      isMatchListShown.value = true;
    };

    const handleClickKeyUp = () => {
      if (hoverIndex.value > 0) {
        hoverIndex.value -= 1;
      }
    };

    const handleClickKeyDown = () => {
      if (hoverIndex.value < filterFieldList.value.length - 1) {
        hoverIndex.value += 1;
      }
    };

    const handelClickEnter = () => {
      if (activeIndex.value !== hoverIndex.value) {
        cacheCurrentFieldValues();
        activeIndex.value = hoverIndex.value;
        restoreFieldValues(currentFieldInfo.value?.field_name);
        checkAndRequestEgges();
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
      isMatchListShown.value = true;
      initData();
      setTimeout(() => {
        const selectItemDom = fieldListMainRef.value.querySelector('.is-active');
        if (selectItemDom) {
          selectItemDom.scrollIntoView();
        }
      });
    };

    const handlePopoverHide = () => {
      controlOperateRef.value.unbindKeyEvent();
    };

    const handleDocumentClick = (e: MouseEvent) => {
      if (!isMatchListShown.value || !contentInputWrapperRef.value) {
        return;
      }

      if (contentInputWrapperRef.value.contains(e.target as HTMLElement)) {
        return;
      }

      isMatchListShown.value = false;
    };

    onMounted(() => {
      handleFieldItemClick(activeIndex.value);
      document.addEventListener('click', handleDocumentClick, true);
    });

    onUnmounted(() => {
      document.removeEventListener('click', handleDocumentClick, true);
    });

    expose({
      hide: handleClickCancel,
    });

    return () => (
      <bk-popover
        v-slots={{
          content: () => (
            <div>
              <div class='config-rule-content'>
                <div class='filter-main'>
                  <div class='field-list'>
                    <div class='search-input'>
                      <bk-input
                        style='width: 100%'
                        behavior='simplicity'
                        left-icon='bk-icon icon-search'
                        placeholder={t('请输入关键字')}
                        value={searchValue.value}
                        clearable
                        onChange={(value: string) => {
                          searchValue.value = value;
                        }}
                      />
                    </div>
                    <div
                      ref={fieldListMainRef}
                      class='field-list-main'
                    >
                      {filterFieldList.value.map((item: { field_name: string|number|symbol|undefined; field_type: string; field_alias: string; }, index: number) => (
                        <div
                          key={item.field_name}
                          class={[
                            'config-rule-field-row',
                            {
                              'is-active': activeIndex.value === index,
                              'is-locate': hoverIndex.value === index,
                            },
                          ]}
                          data-tab-index={index}
                          onClick={() => handleFieldItemClick(index)}
                          onMouseenter={() => {
                            hoverIndex.value = activeIndex.value;
                          }}
                        >
                          <span
                            style={{
                              backgroundColor: getFieldIconColor(item.field_type),
                              color: getFieldIconTextColor(item.field_type),
                            }}
                            class={[getFieldIcon(item.field_type), 'field-type-icon']}
                          />
                          <div
                            class='display-container rtl-text'
                            dir={textDir.value}
                          >
                            {item.field_alias !== '' ? (
                              <bdi>
                                <span class='field-alias'>{item.field_alias}</span>
                                <span class='field-name'>({item.field_name})</span>
                              </bdi>
                            ) : (
                              <bdi>
                                <span class='field-alias'>{item.field_name}</span>
                              </bdi>
                            )}
                          </div>
                        </div>
                      ))}
                      {(isFieldListEmpty.value || isSearchEmpty.value) && (
                        <bk-exception
                          style='justify-content: center; height: 260px'
                          scene='part'
                          type={exceptionType.value}
                        />
                      )}
                    </div>
                  </div>
                  <div class='value-list'>
                    <bk-form
                      ref={formRef}
                      form-type='vertical'
                      {...{
                        ...{
                          model: formData.value,
                          rules: formRules,
                        },
                      }}
                    >
                      <bk-form-item
                        label={t('条件')}
                        property='op'
                        required
                      >
                        <div class='setting-item'>
                          <bk-select
                            style='width: 314px'
                            clearable={false}
                            value={formData.value.op}
                            onChange={(value: string) => {
                              formData.value.op = value;
                            }}
                          >
                            {conditionList.map(option => (
                              <bk-option
                                id={option.id}
                                key={option.id}
                                name={option.name}
                              />
                            ))}
                          </bk-select>
                        </div>
                      </bk-form-item>
                      <bk-form-item
                        label={t('检索值')}
                        property='values'
                        required
                      >
                        <div
                          ref={contentInputWrapperRef}
                          class='content-input-wraper'
                        >
                          <bk-tag-input
                            clearable={false}
                            content-width={232}
                            placeholder={t('请输入')}
                            separator='\n'
                            trigger='focus'
                            value={formData.value.values}
                            allow-auto-match
                            allow-create
                            free-paste
                            onChange={(value: never[]) => {
                              formData.value.values = value;
                              cacheCurrentFieldValues();
                            }}
                            onFocus={handleShowMatchList}
                          />
                          {isValidateItem.value && (
                            <div
                              class='match-list-main'
                              style={{ display: isMatchListShown.value ? 'block' : 'none' }}
                              v-loading={{
                                loading: isRequesting.value,
                                size: 'small',
                              }}
                            >
                              {activeItemMatchList.value.length > 0 ? (
                                activeItemMatchList.value.map((item: string|number|symbol|undefined) => (
                                  <div
                                    key={item}
                                    class='match-item'
                                    v-log-overflow-tips
                                    onClick={e => handleChooseMatchItem(e, item)}
                                  >
                                    {item}
                                  </div>
                                ))
                              ) : (
                                <span style='padding-left:8px'>{t('暂无数据')}</span>
                              )}
                            </div>
                          )}
                        </div>
                      </bk-form-item>
                    </bk-form>
                  </div>
                </div>
                <control-operate
                  ref={controlOperateRef}
                  confrim-enable={isConfirmEnable.value}
                  onCancel={handleClickCancel}
                  onConfirm={handelClickConfirm}
                  onCtrlenter={handelClickConfirm}
                  onDown={handleClickKeyDown}
                  onEnter={handelClickEnter}
                  onEsc={handleClickCancel}
                  onUp={handleClickKeyUp}
                />
              </div>
            </div>
          ),
        }}
        ref={popoverRef}
        width={720}
        ext-cls='config-rule-popover'
        tippy-options={{
          theme: 'light',
          trigger: 'click',
          hideOnClick: false,
        }}
        placement='bottom'
        onHide={handlePopoverHide}
        onShow={handlePopoverShow}
      >
        <RuleTrigger
          data={localFormData.value}
          isCreate={props.isCreate}
          onClick={handleClickTrigger}
          onDelete={handleClickDelete}
        />
      </bk-popover>
    );
  },
});
