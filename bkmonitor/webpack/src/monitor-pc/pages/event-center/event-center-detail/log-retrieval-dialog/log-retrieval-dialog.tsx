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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';

import { isEn } from '../../../../i18n/lang';

import './log-retrieval-dialog.scss';

interface indexItem {
  index_set_id: number;
  index_set_name: string;
  status: number;
  status_name: string;
}
interface LogRetrievalDialogEvent {
  onShowChange: boolean;
}
interface LogRetrievalDialogProps {
  bizId?: number;
  indexList: Array<indexItem>;
  ip: string;
  show: boolean;
  showTips: boolean;
}

@Component({
  name: 'LogRetrievalDialog',
})
export default class LogRetrievalDialog extends tsc<LogRetrievalDialogProps, LogRetrievalDialogEvent> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Boolean, default: false }) showTips: boolean;
  @Prop({ type: Array, default: () => [] }) indexList: Array<indexItem>;
  @Prop({ type: String, default: '' }) ip: string;
  @Prop({ type: Number, default: 0 }) bizId: number;
  @Ref('logForm') refForm;

  public dialog = {
    headerPosition: 'left',
    okText: window.i18n.t('确定'),
    cancelText: window.i18n.t('取消'),
    width: 571,
    title: window.i18n.t('route-日志检索'),
    autoClose: false,
  };
  public data = {
    indexSet: '',
    time: ['', ''],
    sql: '',
  };
  public indexSetList = [];
  public rules = {
    indexSet: [
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
    time: [
      {
        validator: () => this.data.time[0] !== '',
        message: window.i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
    sql: [
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
  };

  @Watch('show')
  handleShow(v) {
    if (v) {
      this.refForm.clearError();
      this.indexSetList = this.indexList.map(item => ({ id: item.index_set_id, name: item.index_set_name }));
      if (this.indexSetList.length) {
        this.data.indexSet = this.indexSetList[0].id;
      }
    }
  }

  @Emit('showChange')
  showChange(v) {
    return v;
  }

  confirm() {
    this.refForm.validate().then(
      () => {
        // 验证成功
        const startTime = encodeURIComponent(dayjs.tz(this.data.time[0]).format('YYYY-MM-DD HH:mm:ss'));
        const endTime = encodeURIComponent(dayjs.tz(this.data.time[1]).format('YYYY-MM-DD HH:mm:ss'));
        const host = window.bk_log_search_url || window.bklogsearch_host;
        const url = `${host}#/retrieve/${this.data.indexSet}?bizId=${
          this.bizId || this.$store.getters.bizId
        }&keyword=${encodeURIComponent(this.data.sql)}&start_time=${startTime}&end_time=${endTime}`;
        window.open(url);
        this.showChange(false);
      },
      () => {
        // 验证失败
      }
    );
  }
  handleClose(v: boolean) {
    if (v) return;
    this.showChange(v);
  }

  render() {
    return (
      <div>
        <bk-dialog
          width={this.dialog.width}
          class='log-retrieval-dialog'
          auto-close={this.dialog.autoClose}
          cancel-text={this.dialog.cancelText}
          header-position={this.dialog.headerPosition}
          ok-text={this.dialog.okText}
          title={this.dialog.title}
          value={this.show}
          on-confirm={this.confirm}
          {...{ on: { 'value-change': this.handleClose } }}
        >
          {this.showTips ? (
            <div class='log-retrieval-tips'>
              <div class='tips-top'>
                <span class='icon-monitor icon-hint' />
                <span>{this.$t('提示：通过 {0} 未找到对应的索引集。如果要采集日志可以前往日志平台。', [this.ip])}</span>
              </div>
              <div class='tips-bottom'>{this.$t('注意：ip查找索引集依赖节点管理版本>=2.1')}</div>
            </div>
          ) : undefined}
          <bk-form
            ref='logForm'
            label-width={isEn ? 110 : 70}
            {...{
              props: {
                model: this.data,
                rules: this.rules,
              },
            }}
          >
            <bk-form-item
              error-display-type={'normal'}
              label={this.$t('索引集')}
              property='indexSet'
              required={true}
            >
              <bk-select
                v-model={this.data.indexSet}
                searchable
              >
                {this.indexSetList.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  />
                ))}
              </bk-select>
            </bk-form-item>
            <bk-form-item
              error-display-type={'normal'}
              label={this.$t('时间范围')}
              property={'time'}
              required={true}
            >
              <bk-date-picker
                v-model={this.data.time}
                placeholder={this.$t('选择日期时间范围')}
                type={'datetimerange'}
              />
            </bk-form-item>
            <bk-form-item
              error-display-type={'normal'}
              label={this.$t('查询语句')}
              property={'sql'}
              required={true}
            >
              <bk-input
                v-model={this.data.sql}
                maxlength={255}
                placeholder={''}
                rows={3}
                type={'textarea'}
              />
            </bk-form-item>
          </bk-form>
          <template slot='footer'>
            <bk-button
              style='margin-right: 10px'
              disabled={this.showTips}
              theme='primary'
              on-click={this.confirm}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button on-click={() => this.handleClose(false)}>{this.$t('取消')}</bk-button>
          </template>
        </bk-dialog>
      </div>
    );
  }
}
