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
import Component from 'vue-class-component';
import { Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getStrategyListV2 } from 'monitor-api/modules/strategies';

import { EStatusType } from '../utils';

import './add-alarm-chart-dialog.scss';

interface IAddAlarmChartDialogProps {
  showAddTaskDialog: boolean;
  handleMenuMode: string;
  currentBizId: number;
  editStrategyConfig?: IStrategyConfig;
}

interface IStrategyConfig {
  name: string;
  strategy_ids: number[];
  status: {
    name: string;
    strategy_id: number;
  }[];
}

type IAddAlarmChartDialogEvent = {
  onConfirm: (strategyIds: number[], name: string, delStrategyIdSet: Set<number>) => void;
  onCancel: () => void;
  onAfterDialogLeave: () => void;
};

@Component({
  name: 'AddAlarmChartDialog',
})
export default class AddAlarmChartDialog extends tsc<IAddAlarmChartDialogProps, IAddAlarmChartDialogEvent> {
  @Prop({ default: false, type: Boolean }) showAddTaskDialog: boolean;
  @Prop({ default: '', type: String }) handleMenuMode: string;
  @Prop({ default: null, type: Number }) currentBizId: number;
  @Prop({ default: {}, type: Object }) editStrategyConfig: IStrategyConfig;

  @Ref() taskFormRef; // 新增图表表单ref

  strategyList = []; // 策略列表

  filterStrategyIdSet = new Set(); // 修改时回显的策略id列表

  delStrategyIdSet: Set<number> = new Set(); // 已删除的策略id列表

  /** 表单规则 */
  rules = {
    name: [{ required: true, message: window.i18n.tc('必填项'), trigger: 'blur' }],
    strategy_ids: [
      {
        validator: val => val.length,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
  };

  // 策略配置
  strategyConfig: IStrategyConfig = {
    strategy_ids: [],
    name: '',
    status: [],
  };

  // select 底部加载配置
  bottomLoadingOptions = {
    isLoading: false,
    size: 'mini',
  };

  // 数据分页
  pagination = {
    currentPage: 1,
    limit: 10,
    isLastPage: false,
  };

  loadingStrategyList = false; // 加载策略列表Loading

  @Watch('showAddTaskDialog')
  showDialog(v) {
    if (!v) return;
    if (this.handleMenuMode === 'edit') {
      this.strategyConfig.strategy_ids = this.editStrategyConfig.strategy_ids;
      this.strategyConfig.name = this.editStrategyConfig.name;
      this.strategyConfig.status = this.editStrategyConfig.status;
      this.getStrategyListById();
      return;
    }
    this.getStrategyListByPage();
  }

  @Emit('cancel')
  handleCancel() { }

  /** 表单校验 */
  handleValidate(): Promise<boolean> {
    return this.taskFormRef
      .validate()
      .then(() => true)
      .catch(() => false);
  }

  async getStrategyListByPage() {
    if (!this.currentBizId) return;
    this.loadingStrategyList = true;
    try {
      const { currentPage: page, limit } = this.pagination;
      const data = await getStrategyListV2({
        page,
        limit,
        bk_biz_id: this.currentBizId,
      });
      this.pagination.isLastPage = data.total <= page * limit;
      this.pagination.currentPage++;
      if (this.handleMenuMode === 'edit') {
        this.strategyList.push(
          ...(data.strategy_config_list.filter(item => {
            if (!this.filterStrategyIdSet.has(item.id)) {
              return true; // 保留在 filter 结果中
            }
            this.filterStrategyIdSet.delete(item.id); // 从集合中移除已处理的 ID
          }) || [])
        );
        return;
      }
      this.strategyList.push(...(data.strategy_config_list || []));
      this.strategyList.sort((a, b) => {
        // 根据优先级字段排序，优先级 is_shielded < is_enabled
        // 将 true 视为 0，false 视为 1 进行比较
        if (a.is_enabled !== b.is_enabled) {
          return (b.is_enabled ? 1 : 0) - (a.is_enabled ? 1 : 0);
        }
        if (a.shield_info?.is_shielded !== b.shield_info?.is_shielded) {
          return (a.shield_info?.is_shielded ? 1 : 0) - (b.shield_info?.is_shielded ? 1 : 0);
        }
        return 0;
      });
    } catch (error) {
      console.log('getStrategyListByPage error', error);
    } finally {
      this.loadingStrategyList = false;
    }
  }

  // 根据策略 Id 获取数据
  async getStrategyListById() {
    if (!this.currentBizId) return;
    this.loadingStrategyList = true;

    try {
      const data = await getStrategyListV2({
        limit: 20,
        bk_biz_id: this.currentBizId,
        conditions: [{ key: 'strategy_id', value: this.strategyConfig.strategy_ids }],
      });
      this.filterStrategyIdSet = new Set(data.strategy_config_list.map(({ id }) => id));
      this.strategyList.unshift(
        ...(this.strategyConfig.status.map(item => {
          const strategy = data.strategy_config_list.find(strategy => strategy.id === item.strategy_id);
          if (strategy) return strategy;
          this.delStrategyIdSet.add(item.strategy_id);
          return {
            is_deleted: true,
            name: item.name,
            id: item.strategy_id,
          };
        }) || [])
      );
      // 如果回显值过少，手动触发触底事件
      if (this.strategyList.length < 10) {
        this.handleScrollToBottom();
      }
    } catch (error) {
      console.log('getStrategyListById error', error);
    } finally {
      this.loadingStrategyList = false;
    }
  }

  async handleScrollToBottom() {
    try {
      // 判断是否为最后一页
      if (this.pagination.isLastPage) return;
      this.bottomLoadingOptions.isLoading = true;
      await this.getStrategyListByPage();
      this.bottomLoadingOptions.isLoading = false;
    } catch (error) {
      console.log('error', error);
    }
  }

  isSelected(id) {
    return this.strategyConfig.strategy_ids.includes(id);
  }

  getStrategyStatus(isDeleted = false, isShielded = false, isEnabled = true) {
    let status = ''; // 默认状态

    // 优先级 已删除 > 已屏蔽 > 已停用
    if (isDeleted) {
      status = 'deleted';
    } else if (isShielded) {
      status = 'shielded';
    } else if (!isEnabled) {
      status = 'disabled';
    }
    return EStatusType[status];
  }

  // 确定新增图表
  async handleConfirm() {
    const isPass = await this.handleValidate();
    if (!isPass) return;
    this.$emit('confirm', this.strategyConfig.strategy_ids, this.strategyConfig.name, this.delStrategyIdSet);
  }

  // 清除相关数据
  clearConfig() {
    this.taskFormRef?.clearError?.();
    this.strategyConfig.strategy_ids = [];
    this.strategyConfig.name = '';
    this.pagination = {
      currentPage: 1,
      limit: 10,
      isLastPage: false,
    };
    this.filterStrategyIdSet = new Set();
    this.delStrategyIdSet = new Set();
    this.strategyList = [];
  }

  render() {
    return (
      <bk-dialog
        width={480}
        escClose={false}
        header-position='left'
        mask-close={false}
        title={this.handleMenuMode === 'edit' ? this.$t('修改图表') : this.$t('新增图表')}
        value={this.showAddTaskDialog}
        show-footer
        on-after-leave={() => {
          // 重置编辑索引，关闭对话框，清除策略配置
          this.clearConfig();
          this.$emit('afterDialogLeave');
        }}
        onCancel={this.handleCancel}
      >
        <bk-form
          ref='taskFormRef'
          formType='vertical'
          {...{
            props: {
              model: this.strategyConfig,
              rules: this.rules,
            },
          }}
        >
          {
            <bk-form-item
              ext-cls='add-chart-strategy'
              error-display-type='normal'
              label={this.$t('策略')}
              property='strategy_ids'
              required
            >
              <bk-select
                v-model={this.strategyConfig.strategy_ids}
                // display-key='id'
                // id-Key='id'
                // list={this.strategyList}
                loading={this.loadingStrategyList}
                placeholder={this.$t('请选择策略')}
                scrollLoading={this.bottomLoadingOptions}
                // enable-virtual-scroll
                enable-scroll-load
                multiple
                searchable
                on-scroll-end={this.handleScrollToBottom}
              >
                {this.strategyList.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    class={{ 'add-task-select-ext': true, 'is-deleted': item.is_deleted }}
                    disabled={
                      this.getStrategyStatus(item.is_deleted, item.shield_info?.is_shielded, item.is_enabled) &&
                      (this.handleMenuMode !== 'edit' || item.is_deleted)
                    }
                    name={item.name}
                  >
                    <div
                      class={{
                        'strategy-name': true,
                        'has-tag': this.getStrategyStatus(
                          item.is_deleted,
                          item.shield_info?.is_shielded,
                          item.is_enabled
                        ),
                        selected: this.isSelected(item.id),
                      }}
                      v-bk-tooltips={{
                        content: item.name,
                        trigger: 'mouseenter',
                        zIndex: 9999,
                        boundary: document.body,
                        allowHTML: false,
                        delay: [1000, 0],
                      }}
                    >
                      {item.name}
                    </div>
                    <div class='strategy-status'>
                      <span class='strategy-tag'>
                        {this.$tc(
                          this.getStrategyStatus(item.is_deleted, item.shield_info?.is_shielded, item.is_enabled)
                        )}
                      </span>
                      {this.isSelected(item.id) && <span class='icon-monitor icon-mc-check-small' />}
                    </div>
                  </bk-option>
                ))}
              </bk-select>
            </bk-form-item>
          }
          {
            <bk-form-item
              error-display-type='normal'
              label={this.$t('图表名称')}
              property='name'
              required
            >
              <bk-input
                v-model={this.strategyConfig.name}
                placeholder={this.$t('请输入图表名称，默认为策略名称')}
              />
            </bk-form-item>
          }
        </bk-form>
        <div
          class='task-add-dialog-footer'
          slot='footer'
        >
          <bk-button
            disabled={this.loadingStrategyList || !this.strategyConfig.name || !this.strategyConfig.strategy_ids.length}
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确认')}
          </bk-button>
          <bk-button
            theme='default'
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
