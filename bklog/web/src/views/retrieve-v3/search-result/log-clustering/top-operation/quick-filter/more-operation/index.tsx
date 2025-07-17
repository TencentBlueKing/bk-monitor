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

import { computed, defineComponent, onMounted, ref, watch } from 'vue';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';
import { debounce } from 'throttle-debounce';
import $http from '@/api';
import { bkMessage, bkInfoBox } from 'bk-magic-vue';
import useLocale from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  name: 'MoreOperation',
  props: {
    fingerOperateData: {
      type: Object,
      require: true,
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    requestData: {
      type: Object,
      require: true,
    },
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit }) {
    const store = useStore();
    const route = useRoute();
    const { t } = useLocale();

    const groupPopover = ref(null);
    const dimension = ref([]); // 当前维度字段的值
    const group = ref([]); // 当前分组选中的值
    const isToggle = ref(false); // 当前是否显示分组下拉框
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
    const isCurrentIndexSetIdCreateSubscription = ref(false);
    /** 打开设置弹窗时的维度 */
    const catchDimension = ref([]);

    const bkBizId = computed(() => store.state.bkBizId);
    const dimensionList = computed(() =>
      props.fingerOperateData.groupList.filter(item => !group.value.includes(item.id)),
    );
    const groupList = computed(() =>
      props.fingerOperateData.groupList.filter(item => !dimension.value.includes(item.id)),
    );
    watch(
      group,
      () => {
        // 分组列表未展开时数组变化则发送请求
        if (!isToggle.value) {
          emit('handle-finger-operate', 'group', group.value);
        }
      },
      {
        deep: true,
      },
    );

    const changeCustomizeState = val => {
      emit('handle-finger-operate', 'fingerOperateData', { isShowCustomize: val });
    };

    /**
     * @desc: 是否默认展示分组接口
     */
    const updateInitGroup = async () => {
      await $http.request('/logClustering/updateInitGroup', {
        params: {
          index_set_id: window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId,
        },
        data: {
          group_fields: dimension.value,
        },
      });
    };

    const cancelPopover = () => {
      isShowPopoverInstance.value = false;
      groupPopover.value.instance.hide();
    };

    const finishEmit = () => {
      emit('handle-finger-operate', 'fingerOperateData', {
        dimensionList: dimension.value,
        selectGroupList: group.value,
        yearSwitch: yearSwitch.value,
        yearOnYearHour: yearOnYearHour.value,
      });
      emit(
        'handle-finger-operate',
        'requestData',
        {
          group_by: [...group.value, ...dimension.value],
          year_on_year_hour: yearSwitch.value ? yearOnYearHour.value : 0,
        },
        true,
      );
      cancelPopover();
    };

    const submitPopover = async () => {
      // 设置过维度 进行二次确认弹窗判断
      if (catchDimension.value.length) {
        const dimensionSortStr = dimension.value.sort().join(',');
        const catchDimensionSortStr = catchDimension.value.sort().join(',');
        const isShowInfo = dimensionSortStr !== catchDimensionSortStr;
        if (isShowInfo) {
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
      } else {
        // 没设置过维度 直接提交
        if (dimension.value.length) {
          await updateInitGroup();
        }
        finishEmit();
      }
    };

    /**
     * @desc: 同比自定义输入
     * @param { String } val
     */
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

    /**
     * 检查当前 索引集 是否创建过订阅。
     */
    const checkReportIsExisted = () => {
      $http
        .request('newReport/getExistReports/', {
          query: {
            scenario: 'clustering',
            bk_biz_id: bkBizId.value,
            index_set_id: window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId,
          },
        })
        .then(response => {
          isCurrentIndexSetIdCreateSubscription.value = !!response.data.length;
        })
        .catch(console.log);
    };

    const handleShowMorePopover = () => {
      const finger = props.fingerOperateData;
      isNear24.value = props.requestData.show_new_pattern;
      patternSize.value = finger.patternSize;
      dimension.value = finger.dimensionList;
      catchDimension.value = finger.dimensionList;
      group.value = finger.selectGroupList;
      yearSwitch.value = finger.yearSwitch;
      yearOnYearHour.value = finger.yearOnYearHour;
    };

    const handleClickGroupPopover = () => {
      !isShowPopoverInstance.value ? groupPopover.value.instance.show() : groupPopover.value.instance.hide();
      isShowPopoverInstance.value = !isShowPopoverInstance.value;
    };

    const toggleYearSelect = val => {
      !val && changeCustomizeState(true);
    };

    const checkReportIsExistedDebounce = debounce(1000, checkReportIsExisted);

    onMounted(() => {
      if (!props.isClusterActive) {
        return;
      }
      handleShowMorePopover();
      checkReportIsExistedDebounce();
    });

    return () => (
      <bk-popover
        ref={groupPopover}
        width={400}
        ext-cls='popover-content'
        disabled={!props.clusterSwitch}
        on-show={handleShowMorePopover}
        tippy-options={tippyOptions.value}
        placement='bottom-start'
      >
        <div
          v-bk-tooltips={t('更多')}
          class={{ 'operation-icon': true, 'disabled-icon': !props.clusterSwitch }}
          on-click={handleClickGroupPopover}
        >
          <span class='bk-icon icon-more'></span>
        </div>
        <div slot='content'>
          <div class='group-popover'>
            <div class='piece'>
              <span>
                <span class='title'>{t('维度')}</span>
                <i
                  class='notice bklog-icon bklog-help'
                  v-bk-tooltips={{ content: t('修改字段会影响当前聚类结果，请勿随意修改'), placement: 'top' }}
                />
              </span>
              <bk-select
                value={dimension.value}
                scroll-height={140}
                ext-popover-cls='selected-ext'
                display-tag
                multiple
                searchable
                on-change={val => (dimension.value = val)}
              >
                {dimensionList.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  >
                    <bk-checkbox
                      checked={dimension.value.includes(option.id)}
                      title={option.name}
                    >
                      {option.name}
                    </bk-checkbox>
                  </bk-option>
                ))}
              </bk-select>
              <div class='group-alert'>
                <i class='bk-icon icon-info'></i>
                <span>{t('如需根据某些维度拆分聚类结果，可将字段设置为维度。')}</span>
              </div>
            </div>
            <div class='piece'>
              <span class='title'>{t('分组')}</span>
              <bk-select
                value={group.value}
                scroll-height={140}
                ext-popover-cls='selected-ext'
                display-tag
                multiple
                searchable
                on-change={val => (group.value = val)}
              >
                {groupList.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  >
                    <bk-checkbox
                      checked={group.value.includes(option.id)}
                      title={option.name}
                    >
                      {option.name}
                    </bk-checkbox>
                  </bk-option>
                ))}
              </bk-select>
            </div>
            <div class='piece'>
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
                  disabled={!yearSwitch}
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
                  {{
                    extension: () => (
                      <div class='compared-customize'>
                        {props.fingerOperateData.isShowCustomize && (
                          <div
                            class='customize-option'
                            on-click={() => changeCustomizeState(false)}
                          >
                            <span>{t('自定义')}</span>
                          </div>
                        )}
                        <div v-else>
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
                      </div>
                    ),
                  }}
                </bk-select>
              </div>
            </div>
            <div class='popover-button'>
              <bk-button
                style='margin-right: 8px'
                size='small'
                theme='primary'
                on-click={submitPopover}
              >
                {t('保存')}
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
