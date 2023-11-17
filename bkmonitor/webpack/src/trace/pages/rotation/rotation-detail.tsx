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
import { defineComponent, inject, PropType, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { Button, Loading, Sideslider } from 'bkui-vue';

import { retrieveDutyRule } from '../../../monitor-api/modules/model';
import { previewDutyRulePlan } from '../../../monitor-api/modules/user_groups';
import HistoryDialog from '../../components/history-dialog/history-dialog';
import { IAuthority } from '../../typings/authority';

import { getCalendar, setPreviewDataOfServer } from './components/calendar-preview';
import FormItem from './components/form-item';
import RotationCalendarPreview from './components/rotation-calendar-preview';
import { RotationSelectTextMap, RotationSelectTypeEnum, RotationTabTypeEnum } from './typings/common';
import { randomColor, transformDetailTimer, transformDetailUsers } from './utils';

import './rotation-detail.scss';

export default defineComponent({
  name: 'RotationDetail',
  props: {
    show: {
      type: Boolean,
      default: false
    },
    id: {
      type: [Number, String],
      default: ''
    },
    onShowChange: {
      type: Function as PropType<(v: boolean) => void>,
      default: _v => {}
    }
  },
  setup(props) {
    const { t } = useI18n();
    const router = useRouter();
    const authority = inject<IAuthority>('authority');

    const loading = ref(false);

    const historyList = ref([]);

    const previewData = ref([]);

    const previewLoading = ref(false);

    watch(
      () => props.show,
      (v: boolean) => {
        if (v) {
          getData();
          getPreviewData();
        }
      }
    );

    const type = ref<RotationTabTypeEnum>(RotationTabTypeEnum.REGULAR);
    const detailData = ref();
    const rotationType = ref<RotationSelectTypeEnum>(RotationSelectTypeEnum.Weekly);
    const users = ref([]);
    const timeList = ref([]);

    function getData() {
      loading.value = true;
      retrieveDutyRule(props.id)
        .then(res => {
          detailData.value = res;
          type.value = res.category;
          rotationType.value = res.duty_arranges?.[0]?.duty_time?.[0].work_type || RotationSelectTypeEnum.Weekly;
          users.value = transformDetailUsers(detailData.value.duty_arranges, type.value);
          timeList.value = transformDetailTimer(detailData.value.duty_arranges, type.value);
          historyList.value = [
            { label: t('创建人'), value: res.create_user || '--' },
            { label: t('创建时间'), value: res.create_time || '--' },
            { label: t('最近更新人'), value: res.update_user || '--' },
            { label: t('修改时间'), value: res.update_time || '--' }
          ];
        })
        .finally(() => {
          loading.value = false;
        });
    }
    /**
     * @description 获取轮值预览
     */
    function getPreviewData() {
      previewLoading.value = true;
      const startDate = getCalendar()[0][0];
      const beginTime = `${startDate.year}-${startDate.month + 1}-${startDate.day} 00:00:00`;
      const params = {
        source_type: 'DB',
        id: props.id,
        begin_time: beginTime,
        days: 42
      };
      previewDutyRulePlan(params)
        .then(data => {
          previewData.value = setPreviewDataOfServer(data);
        })
        .finally(() => {
          previewLoading.value = false;
        });
      // previewData.value = setPreviewDataOfServer(data);
    }

    function renderUserLogo(user) {
      if (user.logo) return <img src={user.logo}></img>;
      if (user.type === 'group') return <span class='icon-monitor icon-mc-user-group no-img'></span>;
      return <span class='icon-monitor icon-mc-user-one no-img'></span>;
    }
    /**
     * @description 关闭侧栏
     */
    function handleClosed() {
      props.onShowChange(false);
    }
    /**
     * @description 跳转到编辑页
     */
    function handleToEdit() {
      router.push({
        name: 'rotation-edit',
        params: {
          id: props.id
        }
      });
    }
    return {
      loading,
      type,
      detailData,
      rotationType,
      users,
      timeList,
      historyList,
      previewData,
      authority,
      previewLoading,
      renderUserLogo,
      handleClosed,
      t,
      handleToEdit
    };
  },
  render() {
    return (
      <Sideslider
        extCls={'rotation-detail-side'}
        isShow={this.show}
        quickClose={true}
        width={960}
        onClosed={this.handleClosed}
      >
        {{
          header: () => (
            <div class='rotation-detail-side-header'>
              <span class='header-left'>{this.t('轮值详情')}</span>
              <span class='header-right'>
                <Button
                  class='mr-8'
                  theme='primary'
                  outline
                  onClick={() =>
                    this.authority.auth.MANAGE_AUTH
                      ? this.handleToEdit()
                      : this.authority.showDetail([this.authority.map.MANAGE_AUTH])
                  }
                  v-authority={{ active: !this.authority.auth.MANAGE_AUTH }}
                >
                  {this.t('编辑')}
                </Button>
                <HistoryDialog list={this.historyList}></HistoryDialog>
              </span>
            </div>
          ),
          default: () => (
            <Loading loading={this.loading}>
              <div class='rotation-detail-side-content'>
                <FormItem
                  label={this.t('规则名称')}
                  hasColon={true}
                >
                  <span class='detail-text'>{this.detailData?.name || '--'}</span>
                </FormItem>
                <FormItem
                  label={this.t('标签')}
                  hasColon={true}
                >
                  <span class='detail-text'>{this.detailData?.labels?.join(', ') || '--'}</span>
                </FormItem>
                <FormItem
                  label={this.t('启/停')}
                  hasColon={true}
                >
                  <span class='detail-text'>{this.detailData?.enabled ? this.t('开启') : this.t('停用')}</span>
                </FormItem>
                <FormItem
                  label={this.t('轮值类型')}
                  hasColon={true}
                >
                  <span class='detail-text'>
                    {this.type === RotationTabTypeEnum.REGULAR ? this.t('日常值班') : this.t('交替轮值')}
                  </span>
                </FormItem>
                {this.type === RotationTabTypeEnum.REGULAR
                  ? [
                      <FormItem
                        label={this.t('值班人员')}
                        hasColon={true}
                      >
                        <span class='notice-user'>
                          {this.users.map(user => (
                            <div class='personnel-choice'>
                              {this.renderUserLogo(user)}
                              <span>{user.display_name}</span>
                            </div>
                          ))}
                        </span>
                      </FormItem>,
                      <FormItem
                        label={this.t('工作时间范围')}
                        hasColon={true}
                      >
                        <div class='regular-form-item-wrap'>
                          {this.timeList.map(item => (
                            <span class='detail-text'>{item.dateRange}</span>
                          ))}
                        </div>
                      </FormItem>,
                      <FormItem
                        label={this.t('工作时间')}
                        hasColon={true}
                      >
                        <div class='regular-form-item-wrap'>
                          {this.timeList.map(item => (
                            <span class='detail-text'>{item.time}</span>
                          ))}
                        </div>
                      </FormItem>
                    ]
                  : [
                      <FormItem
                        label={this.t('值班用户组')}
                        hasColon={true}
                      >
                        <div class='notice-user-list'>
                          {this.users.map((item, ind) => (
                            <span class='notice-user pl-16'>
                              <div
                                class='has-color'
                                style={{ background: randomColor(ind) }}
                              ></div>
                              {item.map(user => (
                                <div class='personnel-choice'>
                                  {this.renderUserLogo(user)}
                                  <span>{user.display_name}</span>
                                </div>
                              ))}
                            </span>
                          ))}
                        </div>
                      </FormItem>,
                      <FormItem
                        label={this.t('轮值类型')}
                        hasColon={true}
                      >
                        <span class='detail-text'>{RotationSelectTextMap[this.rotationType]}</span>
                      </FormItem>,
                      <FormItem
                        label={this.t('单班时间')}
                        hasColon={true}
                      >
                        {this.timeList.map(time => (
                          <div class='muti-text'>{time}</div>
                        ))}
                      </FormItem>
                    ]}
                <FormItem
                  label={this.t('生效时间')}
                  hasColon={true}
                >
                  <span class='detail-text'>{`${this.detailData?.effective_time} - ${
                    this.detailData?.end_time || this.t('永久')
                  }`}</span>
                </FormItem>
                <FormItem
                  label={this.t('轮值预览')}
                  hasColon={true}
                >
                  <Loading loading={this.previewLoading}>
                    <RotationCalendarPreview
                      class='width-806'
                      value={this.previewData}
                    ></RotationCalendarPreview>
                  </Loading>
                </FormItem>
              </div>
            </Loading>
          )
        }}
      </Sideslider>
    );
  }
});
