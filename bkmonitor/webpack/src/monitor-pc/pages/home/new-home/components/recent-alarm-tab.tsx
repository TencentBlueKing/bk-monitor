import { Emit, Mixins, Prop } from 'vue-property-decorator';

import { saveAlarmGraphBizIndex } from 'monitor-api/modules/overview';
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

import { shortcuts } from '../../../../components/time-range/utils';
import UserConfigMixin from '../../../../mixins/userStoreConfig';
import { RECENT_ALARM_TIME_RANGE_KEY } from '../utils';
import HomeBizSelect from './home-biz-list';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IRecentAlarmTab } from '../type';

import './recent-alarm-tab.scss';

interface IRecentAlarmTabProps {
  activeTabId: number;
  bizLimit: number;
  showTabLoading: boolean;
  tabs: IRecentAlarmTab[];
}
@Component({
  name: 'RecentAlarmTab',
})
export default class RecentAlarmTab extends Mixins(UserConfigMixin) {
  /** 业务列表 */
  @Prop({ default: () => [], type: Array }) tabs: IRecentAlarmTabProps['tabs'];
  /** 当前业务ID */
  @Prop({ default: 0, type: Number }) activeTabId: IRecentAlarmTabProps['activeTabId'];
  /** 当前业务ID */
  @Prop({ default: 5, type: Number }) bizLimit: IRecentAlarmTabProps['bizLimit'];
  /** loading */
  @Prop({ default: false, type: Boolean }) showTabLoading: IRecentAlarmTabProps['showTabLoading'];

  /** 当前拖拽id */
  dragId = '';
  dragoverId = '';

  /** 删除业务ID */
  currentDelId = null;

  /** 选择器text */
  selectedText: string;
  /** 时间选择器 */
  timeRange = JSON.stringify(shortcuts[5].value as TimeRangeType);

  // 可以添加业务flag
  get canAddBusiness() {
    // 仅支持添加 n 个业务
    return this.tabs.length < this.bizLimit;
  }

  /** 业务列表 */
  get bizIdList() {
    return this.$store.getters.bizList.filter(
      ({ bk_biz_id }) => !this.tabs.map(item => item.bk_biz_id).includes(bk_biz_id)
    );
  }

  async created() {
    const timeRange = await this.handleGetUserConfig<string>(RECENT_ALARM_TIME_RANGE_KEY, {
      reject403: true,
    });
    this.timeRange = JSON.stringify(timeRange || (shortcuts[5].value as TimeRangeType));
    const selectedOption = shortcuts.find(option => JSON.stringify(option.value) === this.timeRange);
    if (selectedOption) {
      this.selectedText = selectedOption.text as string;
    }
  }

  // 设置存储的首页时间选择器并同步到用户配置
  setStoreSelectedTimeRange() {
    this.handleSetUserConfig(RECENT_ALARM_TIME_RANGE_KEY, this.timeRange);
  }

  // 拖拽 start
  // 拖拽开始，记录当前拖拽的ID
  handleDragstart(index: number) {
    this.dragId = index.toString();
  }

  // 拖拽经过事件，设置当前拖拽ID
  handleDragover(index: number, e: DragEvent) {
    e.preventDefault();
    this.dragoverId = index.toString();
  }

  // 拖拽离开事件，清除当前拖拽的ID
  handleDragleave() {
    this.dragoverId = '';
  }

  // 拖拽完成时逻辑
  handleDrop() {
    if (this.dragId !== this.dragoverId) {
      const tab = Object.assign([], this.tabs);
      const dragIndex = Number.parseInt(this.dragId, 10);
      const dragoverIndex = Number.parseInt(this.dragoverId, 10);

      const draggedTab = this.tabs[dragIndex];
      tab.splice(dragIndex, 1);
      tab.splice(dragoverIndex, 0, draggedTab);
      this.dragId = '';
      this.dragoverId = '';
      // 保存排序
      saveAlarmGraphBizIndex({
        bk_biz_ids: tab.map(tab => tab.bk_biz_id),
      });
      this.$emit('handleDropTab', tab);
    }
    this.dragoverId = '';
  }
  // 拖拽 end

  // 选择标签
  @Emit('changeTab')
  selectTab(tabId: number) {
    return tabId;
  }

  // 处理删除业务逻辑
  @Emit('handleDelTask')
  handleDelTask(id: number) {
    return id;
  }

  // 添加业务
  @Emit('handleSelectBiz')
  handleSelectBiz(id: number) {
    return id;
  }

  // 改变时间选择器
  @Emit('changeTime')
  handleChangeTime(value) {
    // 基于选择的值更新显示文本
    const selectedOption = shortcuts.find(option => JSON.stringify(option.value) === value);
    if (selectedOption) {
      this.selectedText = selectedOption.text;
    }
    return JSON.parse(this.timeRange);
  }

  render() {
    return (
      <div class='recent-alarm-tab'>
        {
          <div class='tabs'>
            {this.tabs.map(({ bk_biz_name: name, bk_biz_id: id }, index) => (
              <div
                key={id}
                class='tab'
                v-bkloading={{ isLoading: this.showTabLoading, zIndex: 10, size: 'mini' }}
                draggable={true}
                onDragleave={this.handleDragleave}
                onDragover={e => this.handleDragover(index, e)}
                onDragstart={() => this.handleDragstart(index)}
                onDrop={this.handleDrop}
              >
                <span class='icon-monitor icon-mc-tuozhuai item-drag' />
                <span
                  class={[
                    'tab-title',
                    this.activeTabId === id ? 'active' : '',
                    this.dragoverId === index.toString() ? 'is-dragover' : '',
                  ]}
                  onClick={() => this.selectTab(id)}
                >
                  {name}
                </span>
                <div>
                  <span
                    class='icon-monitor item-close icon-mc-delete-line'
                    v-bk-tooltips={{
                      content: this.$t('删除该业务'),
                      trigger: 'mouseenter',
                      zIndex: 9999,
                      boundary: document.body,
                      allowHTML: false,
                    }}
                    onClick={() => this.handleDelTask(id)}
                  />
                </div>
              </div>
            ))}
            {!this.canAddBusiness ? (
              <span
                class='add-task task-disabled'
                v-bk-tooltips={{
                  content: this.$t('仅支持添加 {0} 个业务', {
                    0: this.bizLimit,
                  }),
                  trigger: 'mouseenter',
                  zIndex: 9999,
                  boundary: document.body,
                  allowHTML: false,
                }}
              >
                <i class='bk-icon icon-plus-circle' />
                {this.$t('添加业务')}
              </span>
            ) : (
              <HomeBizSelect
                ref='homeBizSelect'
                bizList={this.bizIdList}
                minWidth={380}
                stickyList={[]}
                theme='light'
                onChange={this.handleSelectBiz}
              />
            )}
          </div>
        }
        {/* 时间选择器 */}
        <div class='alarm-time-filter'>
          <bk-select
            ext-cls='alarm-time'
            v-model={this.timeRange}
            clearable={false}
            ext-popover-cls='alarm-time-popover'
            popover-width={70}
            onChange={this.handleChangeTime}
            onSelected={this.setStoreSelectedTimeRange}
          >
            <div
              class='select-trigger'
              slot='trigger'
            >
              <span>
                <span class='item-name-text'>{this.selectedText}</span>
              </span>
              <div class='arrow-wrap'>
                <i class='icon-monitor icon-mc-arrow-down' />
              </div>
            </div>
            {shortcuts.map(option => (
              <bk-option
                id={JSON.stringify(option.value)}
                key={option.text}
                name={option.text}
              />
            ))}
          </bk-select>
        </div>
      </div>
    );
  }
}
