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

import { Alert as TAlert } from 'tdesign-vue-next';

import { Checkbox as TCheckbox } from 'tdesign-vue-next';

import { Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

import { computed, defineComponent, onMounted, ref } from 'vue';

import useLocale from '@/shared/composables/use-locale';
import { bkInfoBox as bkInfoBox } from '@/platform/compat/tdesign/info-box';



import './index.scss';

export default defineComponent({
  emits: ["handle-finger-operate","handleFingerOperate","click-trigger","clickTrigger","open-temp-group","openTempGroup"],

  name: 'DimensionSplit',
  props: {
    fingerOperateData: {
      type: Object,
      require: true,
    },
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const popoverRef = ref(null);
    const dimension = ref<string[]>([]);
    const group = ref<string[]>([]);
    // 打开设置弹窗时的维度
    const catchDimension = ref<string[]>([]);
    const isShowPopoverInstance = ref(false);
    const tippyOptions = ref({
      theme: 'light',
      trigger: 'manual',
      hideOnClick: false,
      offset: '16',
      interactive: true,
    });

    const dimensionList = computed(() =>
      props.fingerOperateData.groupList.filter(
(        item: { id: string; }) =>
          !group.value.includes(item.id) &&
          !['dtEventTimeStamp', 'time', 'iterationIndex', 'gseIndex'].includes(item.id),
      ),
    );

    const handleInitData = () => {
      const finger = props.fingerOperateData;
      dimension.value = finger.dimensionList;
      catchDimension.value = finger.dimensionList;
      group.value = finger.selectGroupList;
    };

    /**
     * 是否默认展示分组接口
     */
    const updateInitGroup = async () => {
      await ServicesInstance.logClustering.updateInitGroup({
        params: {
          index_set_id: props.indexId,
        },
        data: {
          group_fields: dimension.value,
        },
      });
    };

    const closePopover = () => {
      isShowPopoverInstance.value = false;
      popoverRef.value.instance.hide();
    };

    const finishEmit = () => {
      emit('handle-finger-operate', 'fingerOperateData', {
        dimensionList: dimension.value,
        selectGroupList: group.value,
      });
      emit(
        'handle-finger-operate',
        'requestData',
        {
          group_by: [],
        },
        true,
      );
      closePopover();
    };

    const submitPopover = async () => {
      const dimensionSortStr = [...dimension.value].sort().join(',');
      const catchDimensionSortStr = [...catchDimension.value].sort().join(',');
      if (dimensionSortStr !== catchDimensionSortStr) {
        bkInfoBox({
          type: 'warning',
          title: t('修改维度字段会影响已有备注、告警配置，如无必要，请勿随意变动。请确定是否修改？'),
          confirmFn: async () => {
            await updateInitGroup();
            finishEmit();
          },
        });
      } else {
        // 不请求更新维度接口 直接提交
        finishEmit();
      }
    };

    const handleShowPopover = () => {
      emit('click-trigger');
      if (!isShowPopoverInstance.value) {
        popoverRef.value.instance.show();
      } else {
        popoverRef.value.instance.hide();
      }
      isShowPopoverInstance.value = !isShowPopoverInstance.value;
    };

    onMounted(() => {
      handleInitData();
    });

    expose({
      getValue: () => dimension.value,
      hide: () => {
        popoverRef.value.instance.hide();
        isShowPopoverInstance.value = false;
      },
      show: () => {
        popoverRef.value.instance.show();
        isShowPopoverInstance.value = true;
      },
    });

    return () => (
      <bk-popover
        v-slots={{
          content: () => (
            <div>
              <div class='dimension-popover'>
                <div class='title-main'>{t('聚合维度')}</div>
                <TAlert
                  v-slots={{
                    message: () => (
                      <div>
                        <i18n path='如需根据某些维度拆分聚类结果，可将字段设置为维度；维度拆分是比较 {0} 的，根据拆分结果填写责任人和备注，较少改动（临时分组需求请使用“{1}”功能）'>
                          <span style='font-weight: 700'>{t('固化')}</span>
                          <TButton
                            style='font-size: 12px'
                            theme='primary'
                            
                            onClick={() => emit('open-temp-group')} variant={(true) ? 'text' : ('base')}
                          >
                            {t('临时分组')}
                          </TButton>
                        </i18n>
                      </div>
                    ),
                  }}
                  style='color: #4D4F56'
                  theme={'info'} data-v2-display='alert'
                ></TAlert>
                <div class='piece-item'>
                  <span class='title'>{t('维度')}</span>
                  <bk-select
                    ext-popover-cls='quick-filter-selected-ext'
                    scroll-height={140}
                    value={dimension.value}
                    display-tag
                    multiple
                    searchable
                    onChange={(val: string[]) => {
                      dimension.value = val;
                    }}
                  >
                    {dimensionList.value.map((option: { id: string; name: any; }) => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      >
                        <TCheckbox
                          checked={dimension.value.includes(option.id)}
                          title={option.name}
                        >
                          {option.name}
                        </TCheckbox>
                      </bk-option>
                    ))}
                  </bk-select>
                </div>
                <div class='popover-button'>
                  <TButton
                    style='margin-right: 8px'
                    size='small'
                    theme='primary'
                    onClick={submitPopover}
                  >
                    {t('确定')}
                  </TButton>
                  <TButton
                    size='small'
                    theme='default'
                    onClick={closePopover}
                  >
                    {t('取消')}
                  </TButton>
                </div>
              </div>
            </div>
          ),
        }}
        ref={popoverRef}
        width={400}
        disabled={!props.clusterSwitch}
        placement='bottom-start'
        tippy-options={tippyOptions.value}
        onShow={handleInitData}
      >
        <div
          class='quick-filter-trigger-main'
          onClick={handleShowPopover}
        >
          <log-icon
            class='trigger-icon'
            type='dimens'
          />
          <span>{t('聚合维度')}</span>
        </div>
      </bk-popover>
    );
  },
});
