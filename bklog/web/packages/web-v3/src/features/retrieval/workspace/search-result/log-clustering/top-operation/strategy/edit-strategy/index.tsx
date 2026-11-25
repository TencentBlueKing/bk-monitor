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


import { renderDrawerFormSkeleton } from '@/shared/ui/loading/drawer-skeleton';
import { useApplicationStore } from '@/app/state/domains/application-store';
import { Dialog as TDialog, InputNumber as TInputNumber, MessagePlugin as TDesignMessage, Option as TOption, Select as TSelect } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
import { asDictionary } from '@/shared/utils/typed-record';
import { useOverlayZIndex } from '@/shared/global/overlay/index';

import { defineComponent, ref, computed, watch } from 'vue';
import useLocale from '@/shared/composables/use-locale';



import { StrategyType } from '../index';
import { type UserGroupList } from '@/features/retrieval/services/retrieve';
import { type IResponseData } from '@/platform/services/type';

import './index.scss';

export default defineComponent({
  emits: ["success","update:isShow"],

  name: 'EditStrategy',
  props: {
    configData: {
      type: Object,
      require: true,
    },
    indexId: {
      type: String,
      require: true,
    },
    type: {
      type: String,
      default: 'new_cls_strategy',
    },
    isShow: {
      type: Boolean,
      default: false,
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useApplicationStore();

    const rules = {
      interval: [
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
      threshold: [
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
      level: [
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
      user_groups: [
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
    };

    const levelSelectList = [
      { id: 1, name: t('致命') },
      { id: 2, name: t('预警') },
      { id: 3, name: t('提醒') },
    ];

    const levelIconMap = asDictionary({
      1: {
        icon: 'weixian',
        color: 'var(--td-error-color)',
      },
      2: {
        icon: 'circle-alert-filled',
        color: 'var(--td-warning-color)',
      },
      3: {
        icon: 'info-fill',
        color: 'var(--td-brand-color)',
      },
    });

    const strategyFromRef = ref<any>(null);
    const isShowDialog = ref(false);
    const dialogZIndex = useOverlayZIndex(isShowDialog);
    const levelPanelShow = ref(false);
    const levelPanelZIndex = useOverlayZIndex(levelPanelShow, 'DROPDOWN');
    const formLoading = ref(false);
    const groupSelectList = ref<
      {
        id: number;
        name: string;
      }[]
    >([]);
    const formData = ref({} as any);

    const isAlarmType = computed(() => props.type === StrategyType.NEW_CLASS);
    const bkBizId = computed(() => store.bkBizId);

    watch(
      () => [props.configData, isAlarmType.value, isShowDialog.value],
      () => {
        if (!isShowDialog.value) {
          return;
        }

        if (props.configData) {
          formData.value = isAlarmType.value
            ? structuredClone(props.configData[StrategyType.NEW_CLASS])
            : structuredClone(props.configData[StrategyType.SUDDEN_INCREASE]);
        }
      },
      {
        deep: true,
        immediate: true,
      },
    );

    watch(
      () => props.isShow,
      () => {
        isShowDialog.value = props.isShow;
      },
      { immediate: true },
    );

    const handleConfirmSubmit = async () => {
      try {
        await strategyFromRef.value.validate();
        const submitPostStr = (isAlarmType.value ? ServicesInstance.retrieve.newClsStrategy : ServicesInstance.retrieve.normalStrategy);
        const { label_name, ...otherData } = formData.value;
        const res = await submitPostStr({
          params: {
            index_set_id: props.indexId,
          },
          data: otherData,
        });
        if (res.code === 0) {
          TDesignMessage("success", { content: t('操作成功') });
          handleDialogClose();
          emit('success');
        }
      } catch (e) {
        console.error(e);
      }
    };

    /** 给索引集添加标签 */
    const requestGetUserGroup = () => {
      formLoading.value = true;
      ServicesInstance.retrieve.userGroup({
          data: {
            bk_biz_id: bkBizId.value,
          },
        })
        .then((res: IResponseData<UserGroupList>) => {
          groupSelectList.value = res.data.map(item => ({
            id: item.id,
            name: item.name,
          }));
        })
        .finally(() => {
          formLoading.value = false;
        });
    };

    const handleOpenDialog = (isOpen: boolean) => {
      isShowDialog.value = isOpen;
      if (isOpen) {
        requestGetUserGroup();
      } else {
        strategyFromRef.value.clearError();
      }
    };

    const handleCreateUserGroups = () => {
      window.open(`${window.MONITOR_URL}/?bizId=${bkBizId.value}#/alarm-group/add`, '_blank', 'noopener,noreferrer');
    };

    const handleDialogClose = () => {
      levelPanelShow.value = false;
      emit('update:isShow', false);
      isShowDialog.value = false;
    };

    return () => (
      <TDialog
        v-slots={{
          header: () => (
            <div>
              <div class='header-main'>
                <span class='title-main'>{t(props.isEdit ? '编辑策略' : '新建策略')}</span>
                <span class='split-line'></span>
                <span class='title-sub'>{isAlarmType.value ? t('新类告警') : t('数量突增告警')}</span>
              </div>
            </div>
          ),
        }}
        width={480}
        dialogClassName='strategy-dialog'
        attach='body'
        visible={isShowDialog.value}
        zIndex={dialogZIndex.value}
        confirmBtn={t('确定')}
        cancelBtn={t('取消')}
        closeOnOverlayClick={false}
        onConfirm={handleConfirmSubmit}
        onClose={handleDialogClose}
        onOpened={() => handleOpenDialog(true)}
        onClosed={() => handleOpenDialog(false)}
      >
        <bk-form
          ref={strategyFromRef}
          class='strategy-form'
          v-loading={{ loading: formLoading.value, indicator: renderDrawerFormSkeleton }}
          form-type='vertical'
          {...{
            ...{
              model: formData.value,
              rules,
            },
          }}
        >
          <bk-form-item
            v-show={isAlarmType.value}
            label={t('新类告警间隔（天）')}
            tips={t('表示近一段时间内新增日志模式，可自定义判定的时间区间，如：近 30 天内新增')}
            property='interval'
            required
          >
            <TInputNumber
              value={formData.value.interval}
              placeholder={t('每隔 n（整数）天数，再次产生的日志模式将视为新类')}
              theme='normal'
              onChange={(value: unknown) => (formData.value.interval = value)}
            />
          </bk-form-item>
          <bk-form-item
            v-show={isAlarmType.value}
            label={t('新类告警阈值')}
            tips={t('表示某日志模式数量突然异常增长，可能某些模块突发风险')}
            property='threshold'
            required
          >
            <TInputNumber
              value={formData.value.threshold}
              placeholder={t('新类对应日志触发告警的条数')}
              theme='normal'
              onChange={(value: unknown) => (formData.value.threshold = value)}
            />
          </bk-form-item>
          <bk-form-item
            label={t('告警级别')}
            property='level'
            required
          >
            <TSelect
              v-slots={{
                prefixIcon: () => (
                  <log-icon
                    type={levelIconMap[formData.value.level]?.icon || ''}
                    style={{ color: levelIconMap[formData.value.level]?.color, fontSize: '14px' }}
                  />
                ),
              }}
              value={formData.value.level}
              clearable={false}
              popupProps={{ zIndex: levelPanelZIndex.value }}
              onPopupVisibleChange={(visible: boolean) => (levelPanelShow.value = visible)}
              onChange={(value: unknown) => (formData.value.level = value)}
            >
              {levelSelectList.map(item => (
                <TOption
                  key={item.id}
                  value={item.id}
                  label={item.name}
                >
                  <log-icon
                    type={levelIconMap[item.id].icon}
                    style={{
                      color: levelIconMap[item.id].color,
                      fontSize: '14px',
                    }}
                  />
                  <span style='margin-left:4px'>{item.name}</span>
                </TOption>
              ))}
            </TSelect>
          </bk-form-item>
          <bk-form-item
            v-show={!isAlarmType.value}
            label={t('变化敏感度')}
            property='sensitivity'
            required
          >
            <div class='level-box'>
              <bk-slider
                v-slots={{
                  start: () => <span style='margin-right: 10px;'>{t('低')}</span>,
                  end: () => <span style='margin-left: 10px;'>{t('高')}</span>,
                }}
                value={formData.value.sensitivity}
                max-value={10}
                min-value={0}
                onChange={(value: unknown) => (formData.value.sensitivity = value)}
              ></bk-slider>
            </div>
          </bk-form-item>
          <bk-form-item
            label={t('告警组')}
            property='user_groups'
            required
          >
            <bk-select
              v-slots={{
                extension: () => (
                  <div
                    class='groups-btn'
                    onClick={handleCreateUserGroups}
                  >
                    <i class='bk-icon icon-plus-circle'></i>
                    {t('新增告警组')}
                  </div>
                ),
              }}
              value={formData.value.user_groups}
              ext-popover-cls='strategy-create-groups'
              display-tag
              multiple
              searchable
              onChange={(value: unknown) => (formData.value.user_groups = value)}
            >
              {groupSelectList.value.map(item => (
                <bk-option
                  id={item.id}
                  name={item.name}
                ></bk-option>
              ))}
            </bk-select>
          </bk-form-item>
        </bk-form>
      </TDialog>
    );
  },
});
