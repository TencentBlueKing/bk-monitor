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
import { Component, Emit, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { saveCalendar } from 'monitor-api/modules/calendar';

import './calendar-add-input.scss';
/** 日历颜色组 [[深色, 浅色]] */
const COLORS_LIST: Array<[string, string]> = [
  ['#3A84FF', '#E1ECFF'],
  ['#2DCB56', '#DCFFE2'],
  ['#FFB848', '#FFE8C3'],
  ['#FF5656', '#FFDDDD'],
  ['#31EBE7', '#D5FBFA'],
  ['#754DE3', '#E3DBF9'],
  ['#85CCA8', '#E7F5EE'],
  ['#D66F6B', '#F7E2E1'],
  ['#FFEC50', '#FFF9CA'],
  ['#D85FEB', '#F7DFFB'],
];
interface IEvents {
  onCancel: void;
  onConfirm: void;
}
/**
 * 新建日历输入框
 */
@Component
export default class CalendarAddInput extends tsc<object, IEvents> {
  @Ref() inputRef: any;
  /** 日历名称 */
  inputText = '';

  loading = false;

  isShowInput = true;

  created() {
    this.isShowInput = !this.$slots.default;
  }

  @Emit('cancel')
  handleCancel() {
    this.handleShowInput(false);
    this.inputText = '';
  }

  /** 确认添加 */
  @Emit('confirm')
  handleConfirm() {
    this.inputText = '';
    this.handleShowInput(false);
  }
  /**
   * 隐藏输入框操作
   */
  handleShowInput(val: boolean) {
    if (this.$slots.default) {
      this.isShowInput = val;
      val && this.focus();
    }
  }

  /** 输入框获取焦点 */
  focus() {
    this.$nextTick(() => {
      this.inputRef?.focus?.();
    });
  }

  /**
   * 添加日历接口
   */
  async handleAddCalendar() {
    const colors = this.randomColor();
    const params = {
      name: this.inputText,
      deep_color: colors[0],
      light_color: colors[1],
    };
    this.loading = true;
    const res = await saveCalendar(params)
      .then(() => true)
      .catch(() => false);
    this.loading = false;
    if (res) this.handleConfirm();
  }
  /** 随机颜色 */
  randomColor(): [string, string] {
    const leng = COLORS_LIST.length;
    const i = Math.floor(Math.random() * leng);
    return COLORS_LIST[i];
  }
  render() {
    return (
      <div
        class='calendar-input-wrapper'
        v-bkloading={{ isLoading: this.loading, zIndex: 1 }}
      >
        {this.$slots.default && !this.isShowInput && (
          <div
            class='calendar-input-trigger'
            onClick={() => this.handleShowInput(true)}
          >
            {this.$slots.default}
          </div>
        )}
        {this.isShowInput && (
          <div class='calendar-input-content'>
            <bk-input
              ref='inputRef'
              class='calendar-input'
              v-model={this.inputText}
              placeholder={this.$t('输入日历名称')}
            />
            <bk-button
              class='btn'
              theme='primary'
              text
              onClick={this.handleAddCalendar}
            >
              {this.$t('确认')}
            </bk-button>
            <bk-button
              class='btn cancel'
              theme='default'
              text
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        )}
      </div>
    );
  }
}
