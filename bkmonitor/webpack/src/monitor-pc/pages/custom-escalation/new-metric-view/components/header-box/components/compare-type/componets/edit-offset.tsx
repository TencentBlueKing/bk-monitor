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
import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';
import Dayjs from 'dayjs';
import _ from 'lodash';
import { makeMap } from 'monitor-common/utils/make-map';

import './edit-offset.scss';

interface IProps {
  value: string[];
}

interface IEmit {
  onChange: (value: string[]) => void;
}

@Component
export default class CompareWay extends tsc<IProps, IEmit> {
  @Prop({ type: Array, default: () => [] }) readonly value: IProps['value'];

  @Ref('rooRef') rootRef: HTMLElement;
  @Ref('popoverRef') popoverRef: any;
  @Ref('popoverMenuRef') popoverMenuRef: HTMLElement;

  offsetList = Object.freeze([
    {
      id: '1h',
      name: this.$t('1小时前'),
    },
    {
      id: '1d',
      name: this.$t('昨天'),
    },
    {
      id: '7d',
      name: this.$t('上周'),
    },
    {
      id: '30d',
      name: this.$t('1 月前'),
    },
  ]);

  isPopoverShown = true;
  isCustom = false;
  customDate = '';
  tempCustomDate = ''; // 自定义日期编辑状态缓存值
  localValue: string[] = [];
  tempEditValue: string[] = []; // 偏移日期编辑状态缓存值

  get timeRangTimestamp() {
    return customEscalationViewStore.timeRangTimestamp;
  }

  get resultList() {
    const valueMap = makeMap(this.localValue);
    return _.filter(this.offsetList, item => valueMap[item.id]);
  }

  @Watch('value', { immediate: true })
  valueChange() {
    const constValueMap = makeMap(this.offsetList.map(item => item.id));
    this.localValue = _.filter(this.value, item => constValueMap[item]);
    // 解析自定义日期
    const customDay = _.find(this.value, item => !constValueMap[item]);
    if (customDay) {
      this.isCustom = true;
      this.customDate = Dayjs().subtract(Number.parseInt(customDay), 'day').format('YYYY-MM-DD');
    }
  }

  disabledDateMethod(value: any) {
    const [, endTime] = this.timeRangTimestamp;
    if (Dayjs(value).isAfter(Dayjs.unix(endTime))) {
      return true;
    }
    const tempValueMap = makeMap(this.tempEditValue);
    if (tempValueMap['1h'] && Dayjs(value).isSame(Dayjs(), 'day')) {
      return true;
    }

    const compareDay = (day: string) => {
      return Dayjs(value).isSame(Dayjs().subtract(Number.parseInt(day), 'day'), 'day');
    };

    if (tempValueMap['1d'] && compareDay('1d')) {
      return true;
    }
    if (tempValueMap['7d'] && compareDay('7d')) {
      return true;
    }
    if (tempValueMap['30d'] && compareDay('30d')) {
      return true;
    }
    return false;
  }

  calcDateRang(offset: string) {
    const [startTime, endTime] = this.timeRangTimestamp;
    const format = (value: Dayjs.Dayjs) => value.format('YYYY-MM-DD HH:mm:ss');
    if (offset === '1h') {
      return `${format(Dayjs.unix(startTime).subtract(1, 'hour'))} ~ ${format(Dayjs.unix(endTime).subtract(1, 'hour'))}`;
    }
    if (['1d', '7d', '30d'].includes(offset)) {
      const dayOffset = Number.parseInt(offset);
      return `${format(Dayjs.unix(startTime).subtract(dayOffset, 'day'))} ~ ${format(Dayjs.unix(endTime).subtract(dayOffset, 'day'))}`;
    }
    return '';
  }

  triggerChange() {
    const result = [...this.localValue];
    if (this.isCustom && this.customDate) {
      result.push(`${Dayjs().diff(Dayjs(this.customDate), 'day')}d`);
    }
    this.$emit('change', result);
  }

  handleHideEdit(event: Event) {
    if (!this.isPopoverShown) {
      return;
    }
    if (
      _.some(
        event.composedPath(),
        item =>
          [this.rootRef, this.popoverMenuRef].includes(item as HTMLElement) ||
          (item as HTMLElement).classList?.contains('metric-view-custom-date-picker')
      )
    ) {
      return;
    }
    this.popoverRef?.hideHandler();
  }

  handleShowEdit() {
    this.isPopoverShown = true;
    this.tempEditValue = [...this.localValue];
    this.tempCustomDate = this.customDate;
  }

  handleSubmitEdit() {
    this.isPopoverShown = false;
    this.localValue = [...this.tempEditValue];
    this.customDate = this.tempCustomDate;
    this.triggerChange();
  }

  handleRemove(id: string) {
    this.localValue = _.filter(this.localValue, item => item !== id);
    this.triggerChange();
    if (this.localValue.length < 1) {
      this.popoverRef.showHandler();
    }
  }

  handleRemoveCustom() {
    this.isCustom = false;
    this.customDate = '';
    this.triggerChange();
    this.popoverRef.showHandler();
  }

  handleCustomDateChange(day: string) {
    this.tempCustomDate = day;
  }

  mounted() {
    if (this.value.length < 1) {
      this.popoverRef.showHandler();
    }

    // 莫名其妙外部切花对比类型的点击操作会触发下面的click 事件，加个 setTimeout
    setTimeout(() => {
      document.body.addEventListener('click', this.handleHideEdit);
      this.$once('hook:beforeDestroy', () => {
        document.body.removeEventListener('click', this.handleHideEdit);
      });
    });
  }

  render() {
    return (
      <div
        ref='rooRef'
        class='compare-type-time-edit-offset'
      >
        <div class='result-list'>
          {this.resultList.map(item => (
            <div
              key={item.id}
              class='offset-tag'
            >
              {item.name}
              <i
                class='icon-monitor icon-mc-close remove-btn'
                onClick={() => this.handleRemove(item.id)}
              />
            </div>
          ))}
          {this.customDate && (
            <div class='offset-tag'>
              {this.customDate}
              <i
                class='icon-monitor icon-mc-close remove-btn'
                onClick={this.handleRemoveCustom}
              />
            </div>
          )}
        </div>
        <bk-popover
          ref='popoverRef'
          tippy-options={{
            placement: 'bottom-start',
            arrow: false,
            distance: 8,
            hideOnClick: false,
            onHidden: this.handleSubmitEdit,
            onShow: this.handleShowEdit,
          }}
          theme='light compare-type-time-edit-offset'
          trigger='click'
        >
          <div class='append-btn'>
            <i class='icon-monitor icon-a-1jiahao' />
          </div>
          <div
            ref='popoverMenuRef'
            class='wrapper'
            slot='content'
          >
            {this.isPopoverShown && (
              <bk-checkbox-group v-model={this.tempEditValue}>
                {this.offsetList.map(offsetItem => (
                  <div
                    key={offsetItem.id}
                    class='time-item'
                  >
                    <bk-checkbox value={offsetItem.id}>
                      <div
                        class='time-description'
                        v-bk-tooltips={this.calcDateRang(offsetItem.id)}
                      >
                        {offsetItem.name}
                      </div>
                    </bk-checkbox>
                  </div>
                ))}
              </bk-checkbox-group>
            )}
            <div class='time-item'>
              <bk-checkbox v-model={this.isCustom}>{this.$t('自定义')}</bk-checkbox>
              {this.isCustom && (
                <bk-date-picker
                  style='width: 126px; margin-left: 12px;'
                  options={{
                    disabledDate: this.disabledDateMethod,
                  }}
                  ext-popover-cls='metric-view-custom-date-picker'
                  transfer={true}
                  value={this.tempCustomDate}
                  onChange={this.handleCustomDateChange}
                />
              )}
            </div>
          </div>
        </bk-popover>
      </div>
    );
  }
}
