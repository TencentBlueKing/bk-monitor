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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { HandleBtnType, IDataRetrievalView } from '../typings';

@Component
export default class HandleBtn extends tsc<HandleBtnType.IProps, HandleBtnType.IEvent> {
  @Prop({ default: false, type: Boolean }) canQuery: boolean; // 查询按钮是否可用
  @Prop({ default: false, type: Boolean }) autoQuery: boolean; // 是否开启自动查询
  @Prop({ default: false, type: Boolean }) queryLoading: boolean; // 查询时需要loading
  @Prop({ default: false, type: Boolean }) isFavoriteUpdate: boolean; // 收藏参数是否更新
  @Prop({ default: true, type: Boolean }) canFav: boolean; // 判断是否能收藏
  @Prop({ default: () => ({}), type: Object }) favCheckedValue: IDataRetrievalView.IProps['favCheckedValue']; // 当前点击的收藏

  favDescInput = '';
  favLoading = false;
  /** 查询 */
  @Emit('query')
  handleQuery() {}

  /** 清空配置 */
  @Emit('clear')
  handleClearAll() {}

  /**
   * @description: 更新收藏或新增收藏
   * @param {Boolean} isDirectUpdate
   */
  @Emit('addFav')
  handleEmitFavoriteDialog(isDirectUpdate: boolean) {
    return isDirectUpdate;
  }

  @Emit('queryTypeChange')
  handleQueryTypeChange() {
    if (this.queryLoading) return this.autoQuery;
    return !this.autoQuery;
  }

  render() {
    return (
      <div class={['handle-btn-group']}>
        <span
          class='query-type-btn'
          v-bk-tooltips={{ content: this.autoQuery ? this.$t('切换手动查询') : this.$t('切换自动查询'), duration: 400 }}
          onClick={this.handleQueryTypeChange}
        >
          {(() => {
            if (this.queryLoading) {
              /* eslint-disable-next-line @typescript-eslint/no-require-imports */
              return (
                <img
                  src={require('../../../static/images/svg/spinner.svg')}
                  class='status-loading'
                  alt=''
                ></img>
              );
            }
            return this.autoQuery ? (
              <span class='icon-monitor icon-weibiaoti519'></span>
            ) : (
              <span class='icon-monitor icon-kaishi11'></span>
            );
          })()}
        </span>
        <span onMousedown={this.handleQuery}>
          <bk-button
            theme='primary'
            disabled={!this.canQuery}
          >
            {/* { this.autoQuery ? <i class="icon-monitor icon-mc-zidongsousuo"></i> : undefined } */}
            {this.autoQuery ? this.$t('自动查询') : this.$t('查询')}
          </bk-button>
        </span>
        {!!this.favCheckedValue ? (
          <div class='favorite-btn-container'>
            {this.isFavoriteUpdate ? <i class='catching-ball'></i> : undefined}
            <span
              v-bk-tooltips={{ content: this.$t('当前收藏有更新，点击保存当前修改'), disabled: !this.isFavoriteUpdate }}
            >
              <bk-button
                theme='default'
                disabled={!this.isFavoriteUpdate}
                onClick={() => this.handleEmitFavoriteDialog(true)}
              >
                <i class={`icon-monitor ${this.isFavoriteUpdate ? 'icon-mc-mark' : 'icon-mc-collect'}`}></i>
                <span>{this.isFavoriteUpdate ? this.$t('保存') : this.$t('已收藏')}</span>
              </bk-button>
            </span>
          </div>
        ) : (
          <bk-button
            theme='default'
            disabled={!this.canQuery || !this.canFav}
            onClick={() => this.handleEmitFavoriteDialog(false)}
          >
            <i class='icon-monitor icon-mc-uncollect'></i>
            {this.$t('收藏')}
          </bk-button>
        )}

        <bk-popover content={this.$t('清空')}>
          <div
            class='clear-params-btn'
            onClick={this.handleClearAll}
          >
            <i class='icon-monitor icon-mc-clear-query'></i>
            <bk-button theme='default'></bk-button>
          </div>
        </bk-popover>
      </div>
    );
  }
}
