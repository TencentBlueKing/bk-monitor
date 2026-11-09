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
import { bkMessage } from 'bk-magic-vue';
import useLocale from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  name: 'TimeCompare',
  props: {
    fingerOperateData: {
      type: Object,
      require: true,
    },
    requestData: {
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
    const patternSize = ref(0);
    const yearOnYearHour = ref(1);
    const isNear24 = ref(false);
    const isShowPopoverInstance = ref(false);
    const yearSwitch = ref(false);
    const tippyOptions = ref({
      theme: 'light',
      trigger: 'manual',
      hideOnClick: false,
      offset: '16',
      interactive: true,
    });

    watch(
      () => [props.fingerOperateData, props.requestData.show_new_pattern],
      () => {
        const finger = props.fingerOperateData;
        isNear24.value = props.requestData.show_new_pattern;
        patternSize.value = finger.patternSize;
        yearSwitch.value = finger.yearSwitch;
        yearOnYearHour.value = finger.yearOnYearHour;
      },
      {
        immediate: true,
        deep: true,
      },
    );

    const changeCustomizeState = val => {
      emit('handle-finger-operate', 'fingerOperateData', { isShowCustomize: val });
    };

    const cancelPopover = () => {
      isShowPopoverInstance.value = false;
      popoverRef.value.instance.hide();
    };

    const handleConfirm = () => {
      emit('handle-finger-operate', 'fingerOperateData', {
        yearSwitch: yearSwitch.value,
        yearOnYearHour: yearOnYearHour.value,
      });
      emit(
        'handle-finger-operate',
        'requestData',
        {
          year_on_year_hour: yearSwitch.value ? yearOnYearHour.value : 0,
        },
        true,
      );
      cancelPopover();
    };

    // 同比自定义输入
    const handleEnterCompared = val => {
      const matchVal = val.match(/^(\d+)h$/);
      if (!matchVal) {
        bkMessage({
          theme: 'warning',
          message: t('请按照提示输入'),
        });
        return;
      }
      changeCustomizeState(true);
      const { comparedList: propComparedList } = props.fingerOperateData;
      const isRepeat = propComparedList.some(el => el.id === Number(matchVal[1]));
      if (isRepeat) {
        yearOnYearHour.value = Number(matchVal[1]);
        return;
      }
      propComparedList.push({
        id: Number(matchVal[1]),
        name: t('{n} 小时前', { n: matchVal[1] }),
      });
      emit('handle-finger-operate', 'fingerOperateData', {
        comparedList: propComparedList,
      });
      yearOnYearHour.value = Number(matchVal[1]);
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

    const toggleYearSelect = (isSelect: boolean) => {
      if (!isSelect) {
        changeCustomizeState(true);
      }
    };

    expose({
      getValue: () => ({
        year_on_year_hour: yearSwitch.value ? yearOnYearHour.value : 0,
      }),
      hide: () => {
        popoverRef.value.instance.hide();
        isShowPopoverInstance.value = false;
      },
    });

    return () => (
      <bk-popover
        ref={popoverRef}
        width={400}
        disabled={!props.clusterSwitch}
        tippy-options={tippyOptions.value}
        placement='bottom-start'
      >
        <div
          class='quick-filter-trigger-main'
          on-click={handleShowPopover}
        >
          <log-icon
            type='shijian'
            class='trigger-icon'
          />
          <span>{t('时间对比')}</span>
        </div>
        <div slot='content'>
          <div class='time-compare-popover'>
            <div class='title-main'>{t('时间对比')}</div>
            <div class='piece-item'>
              <span class='title'>{t('同比')}</span>
              <div class='year-on-year'>
                <bk-switcher
                  value={yearSwitch.value}
                  theme='primary'
                  on-change={val => (yearSwitch.value = val)}
                />
                <bk-select
                  ext-cls='compared-select'
                  value={yearOnYearHour.value}
                  clearable={false}
                  disabled={!yearSwitch.value}
                  ext-popover-cls='compared-select-option'
                  on-toggle={toggleYearSelect}
                  on-change={val => (yearOnYearHour.value = val)}
                >
                  {props.fingerOperateData.comparedList.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.name}
                    />
                  ))}
                  <div slot='extension'>
                    <div class='compared-customize'>
                      {props.fingerOperateData.isShowCustomize ? (
                        <div
                          class='customize-option'
                          on-click={() => changeCustomizeState(false)}
                        >
                          <span>{t('自定义')}</span>
                        </div>
                      ) : (
                        <div>
                          <bk-input
                            placeholder={t('输入自定义同比，按 Enter 确认')}
                            on-enter={handleEnterCompared}
                          />
                          <div class='compared-select-icon'>
                            <span
                              class='top-end'
                              v-bk-tooltips={t('自定义输入格式: 如 1h 代表一小时 h小时')}
                            >
                              <i class='bklog-icon bklog-help'></i>
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </bk-select>
              </div>
            </div>
            <div class='popover-button'>
              <bk-button
                style='margin-right: 8px'
                size='small'
                theme='primary'
                on-click={handleConfirm}
              >
                {t('确定')}
              </bk-button>
              <bk-button
                size='small'
                theme='default'
                on-click={cancelPopover}
              >
                {t('取消')}
              </bk-button>
            </div>
          </div>
        </div>
      </bk-popover>
    );
  },
});
