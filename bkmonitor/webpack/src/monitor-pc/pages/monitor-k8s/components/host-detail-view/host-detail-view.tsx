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
import { Component, Emit, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { copyText, random } from '../../../../../monitor-common/utils/utils';
import Collapse from '../../../../components/collapse/collapse';
import { ITableItem } from '../../typings';
import { IDetailItem, IDetailValItem } from '../../typings/common-detail';
import CommonStatus from '../common-status/common-status';
import CommonTagList from '../common-tag-list/common-tag-list';

interface IProps {
  data: IDetailItem[];
  width: string | number;
}

interface IEvents {
  onLinkToDetail: ITableItem<'link'>;
}

interface IStatusData {
  name: string;
  type: string;
  value: string | IStatusDataSubValue;
}

interface IStatusDataSubValue {
  name: string;
  type: string;
  text: string;
}

// 由于本地的 vue-i18n 库导致无法正常调试，这里做了一个特殊处理去解决后端的文本强制转成中文作为判断。
const textMapping = {
  采集状态: '采集状态',
  'Collection Status': '采集状态',
  运营状态: '运营状态',
  'Operation Status': '运营状态',
  所属模块: '所属模块',
  Modules: '所属模块'
};

@Component
export default class HostDetailView extends tsc<IProps, IEvents> {
  @InjectReactive('readonly') readonly readonly: boolean;
  @Prop({ type: Array, default: () => [] }) data: IDetailItem[];
  @Prop({ type: [String, Number] }) width: string | number;
  activeCollapseName: [] = [];
  targetStatusName = ['运营状态', '采集状态'];
  targetListName = ['所属模块'];

  handleTransformVal(item: IDetailItem) {
    if (item.type === undefined || item.type === null) return <div>--</div>;
    const { value } = item;
    switch (item.type) {
      case 'time':
        return this.timeFormatter(value as ITableItem<'time'>);
      case 'list':
        return this.listFormatter(item);
      case 'tag':
        return this.tagFormatter(value as ITableItem<'tag'>);
      case 'kv':
        return this.kvFormatter(value as ITableItem<'kv'>);
      case 'link':
        return this.linkFormatter(value as ITableItem<'link'>, item);
      case 'status':
        return this.statusFormatter(value as ITableItem<'status'>);
      case 'progress':
        return this.progressFormatter(value as ITableItem<'progress'>);
      default:
        return this.commonFormatter(value as IDetailValItem<'string'>, item);
    }
  }

  // 时间格式化
  timeFormatter(time: ITableItem<'time'>) {
    if (!time) return '--';
    if (typeof time !== 'number') return time;
    if (time.toString().length < 13) return dayjs.tz(time * 1000, window.timezone).format('YYYY-MM-DD HH:mm:ss');
    return dayjs.tz(time, window.timezone).format('YYYY-MM-DD HH:mm:ss');
  }
  // list类型格式化
  listFormatter(item: IDetailItem) {
    const val = item.value as ITableItem<'list'>;
    const key = random(10);
    return (
      <div id={key}>
        <Collapse
          defaultHeight={110} // 超过五条显示展开按钮
          maxHeight={300}
          expand={item.isExpand}
          needCloseButton={false}
          onExpandChange={val => {
            // eslint-disable-next-line no-param-reassign
            item.isExpand = val;
          }}
          onOverflow={val => {
            // eslint-disable-next-line no-param-reassign
            item.isOverflow = val;
          }}
        >
          <div class='list-type-wrap'>
            {val.length
              ? val.map((item, index) => [
                  <div
                    v-bk-overflow-tips
                    key={index}
                    class='list-type-item'
                  >
                    {item}
                  </div>
                ])
              : '--'}
          </div>
        </Collapse>
        {item.isOverflow ? (
          <span
            class='expand-btn'
            onClick={() => {
              // eslint-disable-next-line no-param-reassign
              item.isExpand = !item.isExpand;
            }}
          >
            {item.isExpand ? '收起' : '展开'}
          </span>
        ) : undefined}
      </div>
    );
  }
  // tag类型格式化
  tagFormatter(val: ITableItem<'tag'>) {
    return <CommonTagList value={val}></CommonTagList>;
  }
  // key-value数据
  kvFormatter(val: ITableItem<'kv'>) {
    const key = random(10);
    return (
      <div
        class='tag-column'
        id={key}
      >
        {val?.length
          ? val.map((item, index) => (
              <div
                key={index}
                class='tag-item set-item'
                v-bk-overflow-tips
              >
                <span
                  class='tag-item-key'
                  key={`key__${index}`}
                >
                  {item.key}
                </span>
                &nbsp;:&nbsp;
                <span
                  class='tag-item-val'
                  key={`val__${index}`}
                >
                  {item.value}
                </span>
              </div>
            ))
          : '--'}
      </div>
    );
  }
  // link格式化
  linkFormatter(val: ITableItem<'link'>, item: IDetailItem) {
    return (
      <div class='common-link-text'>
        <a
          class='link-col'
          v-bk-overflow-tips
          onClick={e => {
            // 该元素处于 BkCollapse 组件里，为避免该点击事件触发冒泡导致组件异常的 开启/关闭 ，这里手动禁止冒泡。
            e.stopPropagation();
            this.handleLinkClick(val);
          }}
        >
          {val.value}
        </a>
        {item.need_copy && !!val.value && (
          <i
            class='text-copy icon-monitor icon-mc-copy'
            v-bk-tooltips={{ content: this.$t('复制'), delay: 200, boundary: 'window' }}
            onClick={e => {
              // 该元素处于 BkCollapse 组件里，为避免该点击事件触发冒泡导致组件异常的 开启/关闭 ，这里手动禁止冒泡。
              e.stopPropagation();
              this.handleCopyText(val.value);
            }}
          ></i>
        )}
      </div>
    );
  }
  // link点击事件
  handleLinkClick(item: ITableItem<'link'>) {
    if (!item.url || this.readonly) return;
    if (item.target === 'self') {
      const route = this.$router.resolve({
        path: item.url
      });
      if (route.resolved.name === this.$route.name) {
        location.href = route.href;
        location.reload();
      } else {
        this.$router.push({
          path: item.url
        });
      }
      return;
    }
    if (item.target === 'event') {
      this.handleLinkToDetail(item);
    } else {
      window.open(item.url, random(10));
    }
  }
  @Emit('linkToDetail')
  handleLinkToDetail(data: ITableItem<'link'>) {
    return data;
  }
  // status格式化
  statusFormatter(val: ITableItem<'status'>) {
    return (
      <CommonStatus
        type={val.type}
        text={val.text}
      />
    );
  }
  // 进度条
  progressFormatter(val: ITableItem<'progress'>) {
    return (
      <div>
        {<div>{val.label}</div>}
        <bk-progress
          class={['common-progress-color', `color-${val.status}`]}
          showText={false}
          percent={Number((val.value * 0.01).toFixed(2)) || 0}
        ></bk-progress>
      </div>
    );
  }
  // 常用值格式化
  commonFormatter(val: IDetailValItem<'string'> | IDetailValItem<'number'>, item: IDetailItem) {
    const text = `${val ?? ''}`;
    return (
      <div class='common-detail-text'>
        <span
          class='text'
          v-bk-overflow-tips
        >
          {text || '--'}
        </span>
        {item.need_copy && !!text && (
          <i
            class='text-copy icon-monitor icon-mc-copy'
            v-bk-tooltips={{ content: this.$t('复制'), delay: 200, boundary: 'window' }}
            onClick={e => {
              // 该元素处于 BkCollapse 组件里，为避免该点击事件触发冒泡导致组件异常的 开启/关闭 ，这里手动禁止冒泡。
              e.stopPropagation();
              this.handleCopyText(text);
            }}
          ></i>
        )}
      </div>
    );
  }
  /** 文本复制 */
  handleCopyText(text: string) {
    let msgStr = this.$tc('复制成功');
    copyText(text, errMsg => {
      msgStr = errMsg as string;
    });
    this.$bkMessage({ theme: 'success', message: msgStr });
  }
  /** 用作显示顶层的 状态一栏 */
  get statusData(): { [key: string]: IStatusData } {
    const o = {};
    this.data.forEach(item => {
      if (this.targetStatusName.includes(textMapping[item.name])) {
        o[textMapping[item.name]] = item;
      }
    });
    return o;
  }
  /** 中间纯文本的表格 */
  get labelListData(): IDetailItem[] {
    return this.data.filter(item => {
      return !(
        this.targetStatusName.includes(textMapping[item.name]) || this.targetListName.includes(textMapping[item.name])
      );
    });
  }
  /** 所属模块 的信息 */
  get moduleData(): { name: string; type: string; value: any | string[] }[] {
    const result = this.data.find(item => textMapping[item.name] === '所属模块');
    if (result) return [result];
    return [];
  }
  /** 不确定是否要保留，因为后端返回的文本貌似不太靠谱的样子 */
  get collectionStatusMessage() {
    switch ((this.statusData[this.targetStatusName[1]]?.value as IStatusDataSubValue)?.type) {
      case 'normal':
        return this.$tc('采集正常');
      case 'disabled':
        return this.$tc('采集失败');
      case 'failed':
        return this.$tc('无数据');
      default:
        return this.$tc('加载中');
    }
  }
  get maintainStatusIcon() {
    const statusType = (this.statusData[this.targetStatusName[0]]?.value as IStatusDataSubValue)?.type;
    let iconClass = '';

    switch (statusType) {
      // 不告警 状态
      case 'is_shielding':
        iconClass = 'icon-menu-shield';
        break;
      // 不监控 状态
      case 'ignore_monitoring':
        iconClass = 'icon-celvepingbi';
        break;
      // 正常监控 状态
      case 'normal':
        iconClass = 'icon-inform-circle';
        break;
    }
    // 特殊情况： 当 type 为 string 且 value 的文本为空时 即为：没有配置。
    if (
      this.statusData[this.targetStatusName[0]]?.type === 'string' &&
      !this.statusData[this.targetStatusName[0]]?.value
    ) {
      iconClass = 'icon-inform-circle';
    }
    return iconClass;
  }
  get maintainStatusText() {
    const statusType = this.statusData[this.targetStatusName[0]]?.type;
    if (statusType === 'string') {
      return this.statusData[this.targetStatusName[0]]?.value || '--';
    }
    if (statusType === 'monitor_status') {
      return (this.statusData[this.targetStatusName[0]]?.value as IStatusDataSubValue)?.text || '--';
    }
    return '--';
  }
  render() {
    return (
      <div>
        {/* 状态展示相关 */}
        <div class='status-container'>
          {/* 运营状态 */}
          {this.statusData[this.targetStatusName[0]] && (
            <div
              class={['status-item', `bg-failed`]}
              v-bk-tooltips={{
                content: this.$t('主机当前状态'),
                delay: 200,
                boundary: 'window'
              }}
            >
              <i class={`icon-monitor ${this.maintainStatusIcon}`}></i>
              <span class='text'>{this.maintainStatusText}</span>
            </div>
          )}

          {this.statusData[this.targetStatusName[1]] && (
            <div
              class={[
                'status-item',
                `bg-${(this.statusData[this.targetStatusName[1]]?.value as IStatusDataSubValue)?.type}`
              ]}
              v-bk-tooltips={{
                content: this.$t('tips-采集状态'),
                delay: 200,
                boundary: 'window'
              }}
            >
              <span class={['common-status-wrap', 'status-wrap-flex']}>
                <span
                  class={[
                    'status-icon',
                    `status-${
                      (this.statusData[this.targetStatusName[1]]?.value as IStatusDataSubValue)?.type || 'disabled'
                    }`
                  ]}
                ></span>
                <span class='common-status-name'>
                  {(this.statusData[this.targetStatusName[1]]?.value as IStatusDataSubValue)?.text}
                </span>
              </span>
            </div>
          )}
        </div>
        <bk-collapse
          v-model={this.activeCollapseName}
          class='detail-collapse-title'
        >
          {this.labelListData.map(item => (
            <div>
              <bk-collapse-item
                name={item.name}
                hide-arrow={!item?.children?.length}
              >
                <div
                  class='panel-item'
                  style={{ maxWidth: `${this.width}px` }}
                  key={item.name}
                >
                  <span class={['item-title', { 'title-middle': ['progress'].includes(item.type) }]}>{item.name}</span>
                  <span class='item-value'>{this.handleTransformVal(item)}</span>
                  {item?.count > 0 && (
                    <div>
                      <span class='item-collapse-data-length'>{item?.children?.length}</span>
                    </div>
                  )}
                </div>
                {item?.count > 0 && (
                  <div
                    slot='content'
                    class='detail-collapse-content'
                  >
                    {item?.children?.map?.(child => (
                      <div class='row'>
                        <div class='label-container'>
                          <span class='label'>{child.name}</span>
                          <span>&nbsp;:</span>
                        </div>
                        <div class='value-container'>
                          {child.type === 'string' && <div class='value'>{child.value}</div>}
                          {child.type === 'list' &&
                            Array.isArray(child?.value) &&
                            child?.value?.map?.(s => <div class='value'>{s}</div>)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </bk-collapse-item>
            </div>
          ))}

          {/* 所属模块 */}
          {(this.moduleData as IDetailItem[]).map(item => (
            <div key={item.name}>
              {this.targetListName.includes(textMapping[item.name]) && <div class='divider'></div>}
              <div class='module-data-panel-item'>
                <div class={['module-data-item-title']}>{item.name}</div>
                <div class='module-data-item-value'>{this.handleTransformVal(item)}</div>
              </div>
            </div>
          ))}
        </bk-collapse>
      </div>
    );
  }
}
