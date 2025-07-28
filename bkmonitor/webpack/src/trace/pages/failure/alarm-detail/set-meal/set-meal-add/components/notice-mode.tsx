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
import { type PropType, computed, defineComponent, ref, watch } from 'vue';

import { Checkbox, Input, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useAppStore } from '../../../../../../store/modules/app';

import './notice-mode.scss';

export const robot = {
  chatid: 'chatid',
  wxworkBot: 'wxwork-bot',
};

export interface INoticeWayValue {
  chatid?: string; // 可选
  level?: number;
  notice_ways?: INoticeWays[];
  phase?: number;
  type?: string[];
}
interface IBkchat {
  [x: string]: any;
  id: string;
  name: string;
}
interface INoticeWay {
  channel?: string;
  icon?: string;
  label: string;
  tip?: string;
  type: string;
  width?: number;
}
interface INoticeWays {
  name: string;
  receivers?: string | string[];
}

export default defineComponent({
  name: 'NoticeModeNew',
  props: {
    noticeWay: {
      type: Array as PropType<INoticeWay[]>,
      default: () => [],
    },
    notifyConfig: {
      type: Array as PropType<INoticeWayValue[]>,
      default: () => [
        { level: 1, notice_ways: [] },
        { level: 2, notice_ways: [] },
        { level: 3, notice_ways: [] },
      ],
    },
    // 0 提醒 1 执行前
    type: {
      type: Number,
      default: 0,
    },
    // 是否显示级别前的颜色
    showlevelMark: {
      type: Boolean,
      default: false,
    },
    // 只读模式
    readonly: {
      type: Boolean,
      default: false,
    },
    showHeader: {
      type: Boolean,
      default: true,
    },
    channels: {
      type: Array as PropType<string[]>,
      default: () => ['user'],
    },
    // 用于更新表格数据
    refreshKey: {
      type: Boolean,
      default: false,
    },
    bkchatList: {
      type: Array as PropType<IBkchat[]>,
      default: () => [],
    },
  },
  setup(props, { emit }) {
    const newNoticeWay = ref<INoticeWay[]>([]);
    const noticeData = ref<any[]>([]);
    const errMsg = ref('');
    // 3-执行前，2-成功时，1-失败时
    // 3-提醒，2-预警 1-致命
    const tableTitle = [window.i18n.t('告警级别'), window.i18n.t('执行阶段')];
    const titleMap = [
      [window.i18n.t('致命'), window.i18n.t('预警'), window.i18n.t('提醒')],
      [window.i18n.t('失败时'), window.i18n.t('成功时'), window.i18n.t('执行前')],
    ];
    const store = useAppStore();
    const { t } = useI18n();

    const levelMap = computed(() => titleMap[props.type]);

    watch(
      () => props.refreshKey,
      v => {
        if (v) handleRenderNoticeWay();
      },
      { immediate: true }
    );

    // 渲染初始表格
    const handleRenderNoticeWay = async () => {
      newNoticeWay.value = [];
      const tableData = [];
      const config: any = {};
      props.notifyConfig.forEach(item => {
        config[item.level] = {
          notice_ways: item.notice_ways.map(ways => {
            const obj = {
              ...ways,
            };
            if (ways?.receivers?.length) {
              if (ways.name === robot.wxworkBot) {
                obj.receivers = ways.receivers.toString();
              } else {
                // bkchat的情况还要判断数据里的值是否已过期
                // 根据值是否存在bkchatlist里来判断过期
                const newReceivers = [];
                (ways.receivers as string[]).forEach(receiver => {
                  const filter = props.bkchatList.find(bkchat => bkchat.id === receiver);
                  if (filter) newReceivers.push(filter.id);
                });
                obj.receivers = newReceivers;
              }
            }
            return obj;
          }),
        };
      });
      props.noticeWay.forEach(set => {
        // 通知类型勾选群机器人后才显示群机器人列
        if (set.type === robot.wxworkBot && !props.channels.includes('wxwork-bot')) return;
        if (set.type === 'bkchat' && !props.channels.includes('bkchat')) return;
        // 通知类型勾选内部通知对象，表格才显示[邮件,短信,语音,微信,企微]列
        if (![robot.wxworkBot, 'bkchat'].includes(set.type) && !props.channels.includes('user')) return;
        newNoticeWay.value.push(set);
      });
      levelMap.value.forEach((item, index) => {
        const key = index + 1;
        const list = newNoticeWay.value.map(set => {
          if ([robot.wxworkBot, 'bkchat'].includes(set.type)) {
            return {
              name: set.type,
              receivers:
                config[key].notice_ways?.find(item => item.name === set.type)?.receivers ||
                (set.type === robot.wxworkBot ? '' : []),
              checked: (config[key].notice_ways?.map(item => item.name) || []).includes(set.type),
            };
          }
          return {
            name: set.type,
            checked: config[key].notice_ways.map(item => item.name).includes(set.type),
          };
        });
        tableData.push({
          list,
          level: key,
          title: levelMap.value[key - 1],
        });
      });
      noticeData.value = tableData.reverse();
      handleRefreshKeyChange();
    };

    // 返回参数
    const handleParams = () => {
      errMsg.value = '';
      return noticeData.value.map(item => {
        const noticeWay: INoticeWayValue = {
          level: item.level,
          notice_ways: item.list
            .filter(set => set.checked)
            .map(set => {
              const obj = {
                name: set.name,
              };
              set.receivers &&
                Object.assign(obj, {
                  // 替换空格
                  receivers: set.receivers,
                });
              return obj;
            }),
        };
        return noticeWay;
      });
    };

    const handleRefreshKeyChange = () => {
      return false;
    };

    const validator = (isStrict = true) => {
      const msg = [
        window.i18n.t('每个告警级别至少选择一种通知方式'),
        window.i18n.t('每个执行阶段至少选择一种通知方式'),
      ];
      const res = handleParams();
      const isPass = res.every(item => {
        if (!item.notice_ways?.length) {
          errMsg.value = msg[props.type];
          return !isStrict;
        }
        return true;
      });
      return isPass;
    };

    const handleJumpAddGroup = () => {
      window.open(`${window.bkchat_manage_url}?bizId=${store.bizId}`);
    };

    return {
      newNoticeWay,
      noticeData,
      errMsg,
      tableTitle,
      handleRenderNoticeWay,
      handleParams,
      validator,
      handleJumpAddGroup,
      t,
    };
  },
  render() {
    return (
      <div class={['meal-notice-mode']}>
        {this.type !== 1 && !this.readonly && this.showHeader && (
          <div class='title'>
            <span class='main'>{this.t('通知方式')}</span>
            <span class='tip'>({this.t('每个告警级别至少选择一种通知方式')})</span>
          </div>
        )}
        <div class='content-table'>
          <table
            class='notice-table'
            cellspacing='0'
          >
            <thead>
              <tr>
                <th class='first-col'>{this.tableTitle[this.type]}</th>
                {this.newNoticeWay.length
                  ? this.newNoticeWay.map(item => (
                      <th key={item.type}>
                        <div class='th-title'>
                          {item.icon ? (
                            <img
                              class='title-icon'
                              alt=''
                              src={`data:image/png;base64,${item.icon}`}
                            />
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
                              }}
                            />
                          ) : undefined}
                        </div>
                      </th>
                    ))
                  : undefined}
              </tr>
            </thead>
            <tbody>
              {this.noticeData.map((item, index) => (
                <tr key={item.tiele + index}>
                  <td class='first-col'>
                    <div
                      key={item.title}
                      class='cell'
                    >
                      {this.showlevelMark && <span class={`level-mark level-mark-${item.level}`} />}
                      <span class={[this.showlevelMark ? `level-title-${item.level}` : undefined]}>{item.title}</span>
                    </div>
                  </td>
                  {item.list.map(notice => (
                    <td
                      key={notice.name}
                      class={[
                        this.channels.length === 3 && 'limit-width',
                        [robot.wxworkBot, 'bkchat'].includes(notice.name) && 'custom-td',
                      ]}
                    >
                      <div
                        key={notice.type}
                        class={['cell', { 'wxwork-bot': notice.name === robot.wxworkBot }]}
                      >
                        {this.readonly ? (
                          <i class={['icon-monitor', notice.checked ? 'icon-mc-check-small' : undefined]} />
                        ) : ['bkchat', 'wxwork-bot'].includes(notice.name) ? undefined : (
                          <Checkbox
                            v-model={notice.checked}
                            v-bk-tooltips={{
                              content: `${this.t('电话按通知对象顺序依次拨打,用户组里无法保证顺序')}`,
                              placements: ['top'],
                              boundary: 'window',
                              disabled: notice.type !== 'voice',
                            }}
                            size={'small'}
                            on-change={this.handleParams}
                          />
                        )}
                        {notice.name === robot.wxworkBot && (
                          <div class='work-group'>
                            {this.readonly ? (
                              <span>{notice.receivers}</span>
                            ) : (
                              <Input
                                v-model={notice.receivers}
                                placeholder={this.t('输入群ID')}
                                type='textarea'
                                on-change={v => {
                                  notice.checked = !!v;
                                  this.handleParams();
                                }}
                              />
                            )}
                          </div>
                        )}
                        {notice.name === 'bkchat' && (
                          <div
                            style={{ textAlign: 'start' }}
                            class='chat-group'
                          >
                            <Select
                              v-model={notice.receivers}
                              disabled={this.readonly}
                              display-tag={true}
                              multiple={true}
                              placeholder='请选择通知方式'
                              onChange={v => {
                                notice.checked = !!v?.length;
                                this.handleParams();
                              }}
                            >
                              {this.bkchatList.map(bkchat => (
                                <Select.Option
                                  id={bkchat.id}
                                  key={bkchat.id + bkchat.name}
                                  name={bkchat.name}
                                />
                              ))}
                              <div
                                style='cursor: pointer;'
                                slot='extension'
                                onClick={this.handleJumpAddGroup}
                              >
                                <i
                                  style={{ marginRight: '5px' }}
                                  class='bk-icon icon-plus-circle'
                                />
                                {this.t('新增群组')}
                              </div>
                            </Select>
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
  },
});
