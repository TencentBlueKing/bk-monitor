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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AutoHeightTextarea from './auto-height-textarea';

import './notice-mode.scss';

export const robot = {
  chatid: 'chatid',
  wxworkBot: 'wxwork-bot'
};

interface INoticeModeProps {
  noticeWay?: INoticeWay[];
  notifyConfig?: INoticeWayValue[];
  type?: number;
  readonly?: boolean;
  showlevelMark?: boolean;
  showHeader?: boolean;
}
interface INoticeWay {
  type: string;
  label: string;
  icon?: string;
  tip?: string;
  width?: number;
  channel?: string;
}
export interface INoticeWayValue {
  phase?: number;
  level?: number;
  notice_ways?: INoticeWays[];
  chatid?: string; // 可选
}
interface INoticeWays {
  name: string;
  receivers?: string[] | string;
}
interface INoticeModeEvent {
  onChange?: INoticeWayValue[];
}

@Component({
  name: 'NoticeModeNew'
})
export default class NoticeModeNew extends tsc<INoticeModeProps, INoticeModeEvent> {
  @Prop({ type: Array, default: () => [] }) noticeWay!: INoticeWay[];
  @Prop({
    type: Array,
    default: () => [
      { level: 1, notice_ways: [] },
      { level: 2, notice_ways: [] },
      { level: 3, notice_ways: [] }
    ]
  })
  notifyConfig: INoticeWayValue[];
  @Prop({ type: Number, default: 0 }) type: number; // 0 提醒 1 执行前
  @Prop({ default: false, type: Boolean }) showlevelMark: boolean; // 是否显示级别前的颜色
  @Prop({ default: false, type: Boolean }) readonly: boolean; // 只读模式
  @Prop({ default: true, type: Boolean }) showHeader: boolean;
  @Prop({ default: () => ['user'], type: Array }) channels;
  @Prop({ default: false, type: Boolean }) refreshKey: boolean; // 用于更新表格数据
  @Prop({ default: () => [], type: Array }) bkchatList;
  // 3-执行前，2-成功时，1-失败时
  // 3-提醒，2-预警 1-致命
  tableTitle = [window.i18n.t('告警级别'), window.i18n.t('执行阶段')];
  titleMap = [
    [window.i18n.t('致命'), window.i18n.t('预警'), window.i18n.t('提醒')],
    [window.i18n.t('失败时'), window.i18n.t('成功时'), window.i18n.t('执行前')]
  ];
  newNoticeWay = [];

  noticeData = [];

  errMsg = '';

  get levelMap() {
    return this.titleMap[this.type];
  }

  // @Watch('noticeWay', { immediate: true, deep: true })
  // @Watch('notifyConfig', { deep: true })
  // @Watch('channels', { deep: true })
  // handleNotifyConfig() {
  //   this.handleRenderNoticeWay();
  // }

  @Watch('refreshKey', { immediate: true })
  handleConfigUpdate(v) {
    v && this.handleRenderNoticeWay();
  }

  // 渲染初始表格
  async handleRenderNoticeWay() {
    this.newNoticeWay = [];
    const tableData = [];
    const config = {};
    this.notifyConfig.forEach(item => {
      config[item.level] = {
        notice_ways: item.notice_ways.map(ways => {
          const obj = {
            ...ways
          };
          if (ways?.receivers?.length) {
            if (ways.name === robot.wxworkBot) {
              obj.receivers = ways.receivers.toString();
            } else {
              // bkchat的情况还要判断数据里的值是否已过期
              // 根据值是否存在bkchatlist里来判断过期
              const newReceivers = [];
              ways.receivers?.forEach(receiver => {
                const filter = this.bkchatList.find(bkchat => bkchat.id === receiver);
                filter && newReceivers.push(filter.id);
              });
              obj.receivers = newReceivers;
            }
          }
          return obj;
        })
      };
    });
    this.noticeWay.forEach(set => {
      // 通知类型勾选群机器人后才显示群机器人列
      if (set.type === robot.wxworkBot && !this.channels.includes('wxwork-bot')) return;
      if (set.type === 'bkchat' && !this.channels.includes('bkchat')) return;
      // 通知类型勾选内部通知对象，表格才显示[邮件,短信,语音,微信,企微]列
      if (![robot.wxworkBot, 'bkchat'].includes(set.type) && !this.channels.includes('user')) return;
      this.newNoticeWay.push(set);
    });
    this.levelMap.forEach((item, index) => {
      const key = index + 1;
      const list = this.newNoticeWay.map(set => {
        if ([robot.wxworkBot, 'bkchat'].includes(set.type)) {
          return {
            name: set.type,
            receivers:
              config[key].notice_ways?.find(item => item.name === set.type)?.receivers ||
              (set.type === robot.wxworkBot ? '' : []),
            checked: (config[key].notice_ways?.map(item => item.name) || []).includes(set.type)
          };
        }
        return {
          name: set.type,
          checked: !!config[key]?.notice_ways?.map(item => item.name).includes(set.type)
        };
      });
      tableData.push({
        list,
        level: key,
        title: this.levelMap[key - 1]
      });
    });
    this.noticeData = tableData.reverse();
    this.handleRefreshKeyChange();
  }
  // 返回参数
  @Emit('change')
  handleParams() {
    this.errMsg = '';
    return this.noticeData.map(item => {
      const noticeWay: INoticeWayValue = {
        level: item.level,
        notice_ways: item.list
          .filter(set => set.checked)
          .map(set => {
            const obj = {
              name: set.name
            };
            set.receivers &&
              Object.assign(obj, {
                // 替换空格
                receivers: set.receivers
              });
            return obj;
          })
      };
      return noticeWay;
    });
  }
  @Emit('refreshKeyChange')
  handleRefreshKeyChange() {
    return false;
  }

  validator(isStrict = true) {
    const msg = [
      window.i18n.tc('每个告警级别至少选择一种通知方式'),
      window.i18n.tc('每个执行阶段至少选择一种通知方式')
    ];
    const res = this.handleParams();
    const isPass = res.every(item => {
      if (!item.notice_ways?.length) {
        this.errMsg = msg[this.type];
        return !isStrict;
      }
      return true;
    });
    return isPass;
  }

  handleJumpAddGroup() {
    window.open(`${window.bkchat_manage_url}?bizId=${this.$store.getters.bizId}`);
  }

  render() {
    return (
      <div class={['meal-notice-mode', { readonly: this.readonly }]}>
        {this.type !== 1 && !this.readonly && this.showHeader && (
          <div class='title'>
            <span class='main'>{this.$t('通知方式')}</span>
            <span class='tip'>({this.$t('每个告警级别至少选择一种通知方式')})</span>
          </div>
        )}
        <div class='content-table'>
          <table
            class='notice-table'
            cellspacing='0'
          >
            <thead>
              <th class='first-col'>{this.tableTitle[this.type]}</th>
              {this.newNoticeWay.length
                ? this.newNoticeWay.map(item => (
                    <th>
                      <div class='th-title'>
                        {item.icon ? (
                          <img
                            alt=''
                            class='title-icon'
                            src={`data:image/png;base64,${item.icon}`}
                          ></img>
                        ) : undefined}
                        {item.label}
                        {item.tip ? (
                          <i
                            class='icon-monitor icon-remind icon-right'
                            v-bk-tooltips={{
                              content: item.tip,
                              boundary: 'window',
                              placements: ['top'],
                              width: item.width,
                              allowHTML: true
                            }}
                          ></i>
                        ) : undefined}
                      </div>
                    </th>
                  ))
                : undefined}
            </thead>
            <tbody>
              {this.noticeData.map(item => (
                <tr>
                  <td class='first-col'>
                    <div
                      class='cell'
                      key={item.title}
                    >
                      {this.showlevelMark && <span class={`level-mark level-mark-${item.level}`}></span>}
                      <span class={[this.showlevelMark ? `level-title-${item.level}` : undefined]}>{item.title}</span>
                    </div>
                  </td>
                  {item.list.map(notice => (
                    <td
                      class={[
                        this.channels.length === 3 && 'limit-width',
                        [robot.wxworkBot, 'bkchat'].includes(notice.name) && 'custom-td'
                      ]}
                    >
                      <div
                        class={['cell', { 'wxwork-bot': notice.name === robot.wxworkBot }]}
                        key={notice.type}
                      >
                        {this.readonly ? (
                          <i class={['icon-monitor', notice.checked ? 'icon-mc-check-small' : undefined]}></i>
                        ) : ['bkchat', 'wxwork-bot'].includes(notice.name) ? undefined : (
                          <bk-checkbox
                            size={'small'}
                            v-model={notice.checked}
                            theme='primary'
                            v-bk-tooltips={{
                              content: `${this.$t('电话按通知对象顺序依次拨打,用户组里无法保证顺序')}`,
                              placements: ['top'],
                              boundary: 'window',
                              disabled: notice.type !== 'voice'
                            }}
                            on-change={() => this.handleParams()}
                          ></bk-checkbox>
                        )}
                        {notice.name === robot.wxworkBot && (
                          <div class='work-group'>
                            {this.readonly ? (
                              <span>{notice.receivers}</span>
                            ) : (
                              <AutoHeightTextarea
                                v-model={notice.receivers}
                                placeholder={this.$tc('输入群ID')}
                                on-change={v => {
                                  notice.checked = !!v;
                                  this.handleParams();
                                }}
                              ></AutoHeightTextarea>
                              // <bk-input
                              //   v-model={notice.receivers}
                              //   placeholder={this.$t('输入群ID')}
                              //   type='textarea'
                              //   on-change={v => {
                              //     notice.checked = !!v;
                              //     this.handleParams();
                              //   }}
                              // ></bk-input>
                            )}
                          </div>
                        )}
                        {notice.name === 'bkchat' && (
                          <div
                            class='chat-group'
                            style={{ textAlign: 'start' }}
                          >
                            <bk-select
                              v-model={notice.receivers}
                              readonly={this.readonly}
                              multiple={true}
                              display-tag={true}
                              placeholder='请选择通知方式'
                              on-change={v => {
                                notice.checked = !!v?.length;
                                this.handleParams();
                              }}
                            >
                              {this.bkchatList.map(bkchat => (
                                <bk-option
                                  id={bkchat.id}
                                  name={bkchat.name}
                                  key={bkchat.id + bkchat.name}
                                />
                              ))}
                              <div
                                slot='extension'
                                style='cursor: pointer;'
                                onClick={this.handleJumpAddGroup}
                              >
                                <i
                                  class='bk-icon icon-plus-circle'
                                  style={{ marginRight: '5px' }}
                                ></i>
                                {this.$tc('新增群组')}
                              </div>
                            </bk-select>
                          </div>
                        )}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {this.errMsg && <div class='err-msg'>{this.errMsg}</div>}
      </div>
    );
  }
}
