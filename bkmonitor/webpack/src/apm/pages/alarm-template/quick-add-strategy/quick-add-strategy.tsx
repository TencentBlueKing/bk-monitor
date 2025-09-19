/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Component, Mixins, Prop, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { listUserGroup, searchStrategyTemplate } from 'monitor-api/modules/model';
import authorityMixinCreate from 'monitor-pc/mixins/authorityMixin';
import { MANAGE_AUTH as MANAGE } from 'monitor-pc/pages/alarm-group/authority-map';

import JudgmentConditions from './judgment-conditions';
import TemplateList from './template-list';

import type { IAlarmGroupList, ITempLateItem } from './typing';

import './quick-add-strategy.scss';

interface IProps {
  params?: Record<string, any>;
  show?: boolean;
  onShowChange?: (v: boolean) => void;
}

@Component
class QuickAddStrategy extends Mixins(
  authorityMixinCreate({
    ALARM_GROUP_MANAGE_AUTH: MANAGE,
  })
) {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) params: Record<string, any>;

  templateList = [];
  alarmGroupList: IAlarmGroupList[] = [];
  alarmGroupLoading = false;
  cursorId = '';
  cursorItem: ITempLateItem = null;
  checkedList = [];

  globalParams = null;

  @Watch('show')
  handleWatchShowChange(v: boolean) {
    if (v) {
      this.getTemplateList();
    }
  }

  created() {
    this.getAlarmGroupList();
  }

  handleShowTemplateDetails() {
    // todo
  }

  handleShowChange(v: boolean) {
    this.$emit('showChange', v);
  }

  getAlarmGroupList() {
    this.alarmGroupLoading = true;
    return listUserGroup({ exclude_detail_info: 1 })
      .then(data => {
        this.alarmGroupList = data.map(item => ({
          id: item.id,
          name: item.name,
          needDuty: item.need_duty,
          receiver:
            item?.users?.map(rec => rec.display_name).filter((item, index, arr) => arr.indexOf(item) === index) || [],
        }));
      })
      .finally(() => {
        this.alarmGroupLoading = false;
      });
  }

  handleCursorChange(id) {
    this.cursorId = id;
    this.cursorItem = this.templateList.find(item => item.id === id);
  }

  handleCheckedChange(checked) {
    this.checkedList = checked;
  }

  handleSubmit() {
    const h = this.$createElement;
    this.$bkInfo({
      type: 'success',
      title: this.$t('批量创建策略成功'),
      okText: this.$t('留在当前页'),
      width: 480,
      confirmFn: () => {
        const params = {
          app_name: this.params?.app_name,
          service_names: [this.params?.service_name],
          strategy_template_ids: this.checkedList,
          extra: [],
          global: this.globalParams,
        };
        console.log('confirmFn', params);
      },
      cancelFn: () => {
        console.log('cancelFn');
      },
      subHeader: h(
        'div',
        {
          style: {
            height: '46px',
            background: '#F5F7FA',
            display: 'flex',
            alignItems: 'center',
            color: '#4D4F56',
            justifyContent: 'center',
          },
        },
        this.$t('已配置策略重新下发会被覆盖') as string
      ),
      cancelText: '前往策略列表',
    });
  }

  getTemplateList() {
    searchStrategyTemplate({
      ...this.params,
    }).then(data => {
      this.templateList = data?.list || [];
    });
  }

  handleJudgmentConditionsChange(params) {
    this.globalParams = params;
  }

  render() {
    return (
      <bk-sideslider
        width={1024}
        ext-cls={'quick-add-strategy-side-component'}
        before-close={() => {
          this.handleShowChange(false);
        }}
        isShow={this.show}
        quick-close
      >
        <div slot='header'>{this.$t('一键添加策略')}</div>
        <div
          class='quick-add-strategy-content'
          slot='content'
        >
          <div class='template-list'>
            <TemplateList
              checked={this.checkedList}
              cursorId={this.cursorId}
              templateList={this.templateList}
              onCheckedChange={this.handleCheckedChange}
              onCursorChange={this.handleCursorChange}
            />
            <JudgmentConditions
              userList={this.alarmGroupList}
              onChange={this.handleJudgmentConditionsChange}
            />
          </div>

          <div class='template-preview'>
            {!!this.cursorId && (
              <div class='template-preview-header'>
                <span class='header-title'>{this.$t('预览')}</span>
                <span class='split-line' />
                <span class='header-desc'>{this.cursorItem?.name || '--'}</span>
                <span
                  class='header-right-link'
                  onClick={this.handleShowTemplateDetails}
                >
                  <span>{this.$t('模板详情')}</span>
                  <span class='icon-monitor icon-fenxiang' />
                </span>
              </div>
            )}
          </div>
        </div>
        <div
          class='quick-add-strategy-footer'
          slot='footer'
        >
          <bk-button
            class='mr-8 ml-24'
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.$t('一键生成')}
          </bk-button>
          <bk-button>{this.$t('取消')}</bk-button>
        </div>
      </bk-sideslider>
    );
  }
}

export default ofType<IProps>().convert(QuickAddStrategy);
