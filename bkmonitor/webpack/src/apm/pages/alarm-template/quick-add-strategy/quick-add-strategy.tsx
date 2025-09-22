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

import { applyStrategyTemplate, listUserGroup, searchStrategyTemplate } from 'monitor-api/modules/model';
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

  templateListLoading = false;

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

  /**
   * 处理光标选择变化
   * 根据传入的模板ID更新当前选中的模板项
   * @param {number} id - 选中的模板ID
   */
  handleCursorChange(id: number) {
    this.cursorId = id;
    this.cursorItem = this.templateList.find(item => item.id === id);
  }

  handleCheckedChange(checked) {
    this.checkedList = checked;
  }

  /**
   * 应用策略模板
   * 异步方法，用于批量应用选中的策略模板
   * 构建请求参数并调用后端接口，处理成功和失败情况
   * @returns {Promise<boolean>} 返回Promise，true表示应用成功，false表示失败
   */
  async applyStrategyTemplate() {
    const params = {
      app_name: this.params?.app_name,
      service_names: [this.params?.service_name],
      strategy_template_ids: this.checkedList,
      extra: [],
      global: this.globalParams || undefined,
    };
    const res = await applyStrategyTemplate(params)
      .then(() => {
        return true;
      })
      .catch(() => {
        return false;
      });
    if (res) {
      this.$bkMessage({
        message: this.$t('生成成功'),
        theme: 'success',
      });
      return true;
    }
    return false;
  }

  /**
   * 处理表单提交
   * 异步方法，用于处理一键生成策略的提交操作
   * 1. 首先调用应用策略模板方法
   * 2. 检查是否有已应用的模板需要警告用户
   * 3. 显示成功信息弹窗，提供用户操作选项
   * @returns {Promise<void>} 无返回值
   */
  async handleSubmit() {
    const h = this.$createElement;

    const isSuccess = await this.applyStrategyTemplate();
    if (!isSuccess) {
      return;
    }

    const hasBeenApplied = this.checkedList.some(id => {
      const templateItem = this.templateList.find(item => item.id === id);
      return !!templateItem?.has_been_applied;
    });

    this.$bkInfo({
      type: 'success',
      title: this.$t('批量创建策略成功'),
      okText: this.$t('留在当前页'),
      width: 480,
      cancelFn: () => {
        window.open(location.href.replace(location.hash, '#/strategy-config'));
        return true;
      },
      subHeader: hasBeenApplied
        ? h(
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
          )
        : undefined,
      cancelText: this.$t('前往策略列表'),
    });
  }

  getTemplateList() {
    this.templateListLoading = true;
    searchStrategyTemplate({
      app_name: this.params?.app_name,
      conditions: [],
      simple: true,
    })
      .then(data => {
        this.templateList = data?.list || [];
        if (this.templateList.length) {
          this.handleCursorChange(this.templateList[0].id);
        }
      })
      .finally(() => {
        this.templateListLoading = false;
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
            {this.templateListLoading ? (
              <div class='template-list-loading'>
                {new Array(10).fill(0).map((_, index) => (
                  <div
                    key={index}
                    class='template-list-loading-item skeleton-element'
                  />
                ))}
              </div>
            ) : (
              <TemplateList
                checked={this.checkedList}
                cursorId={this.cursorId}
                templateList={this.templateList}
                onCheckedChange={this.handleCheckedChange}
                onCursorChange={this.handleCursorChange}
              />
            )}
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
            disabled={!this.checkedList.length}
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
