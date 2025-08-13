import { defineComponent } from 'vue';
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
import { type PropType, computed, reactive } from 'vue';

import { Message, overflowTitle, Progress } from 'bkui-vue';
import dayjs from 'dayjs';
import { copyText, random } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import CollapseItem from '../collapse-item/collapse-item';
import ContentCollapse from '../content-collapse/content-collapse';
import CommonStatus from './common-status/common-status';
import CommonTagList from './common-tag-list/common-tag-list';

import type { ITableItem } from '../../typings/table';
import type { IDetailItem, IDetailValItem, IStatusData, IStatusDataSubValue } from './typing';

import './host-detail-view.scss';

export default defineComponent({
  name: 'HostDetailView',
  directives: {
    overflowTitle,
  },
  props: {
    data: { type: Array as PropType<IDetailItem[]>, default: () => [] },
    width: { type: [Number, String] },
    readonly: { type: Boolean, default: false },
  },
  setup(props) {
    const { t } = useI18n();
    const router = useRouter();
    const route = useRoute();
    const activeCollapseName = reactive([]);
    const targetStatusName = [t('运营状态'), t('采集状态')];
    const targetListName = [t('所属模块')];

    /** 用作显示顶层的 状态一栏 */
    const statusData = computed<{ [key: string]: IStatusData }>(() => {
      return props.data.reduce((pre, cur) => {
        if (targetStatusName.includes(cur.name)) {
          pre[cur.name] = cur;
        }
        return pre;
      }, {});
    });

    /** 中间纯文本的表格 */
    const labelListData = computed<IDetailItem[]>(() => {
      return props.data.filter(item => {
        return !(targetStatusName.includes(item.name) || targetListName.includes(item.name));
      });
    });

    /** 所属模块 的信息 */
    const moduleData = computed(() => {
      const result = props.data.find(item => item.name === t('所属模块'));
      if (result) return [result];
      return [];
    });

    const maintainStatusIcon = computed(() => {
      const statusType = (statusData.value[targetStatusName[0]]?.value as IStatusDataSubValue)?.type;
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
      if (statusData.value[targetStatusName[0]]?.type === 'string' && !statusData.value[targetStatusName[0]]?.value) {
        iconClass = 'icon-inform-circle';
      }
      return iconClass;
    });

    const maintainStatusText = computed(() => {
      const statusType = statusData.value[targetStatusName[0]]?.type;
      if (statusType === 'string') {
        return statusData.value[targetStatusName[0]]?.value || '--';
      }
      if (statusType === 'monitor_status') {
        return (statusData.value[targetStatusName[0]]?.value as IStatusDataSubValue)?.text || '--';
      }
      return '--';
    });

    function handleTransformVal(item: IDetailItem) {
      if (item.type === undefined || item.type === null) return <div>--</div>;
      const { value } = item;
      switch (item.type) {
        case 'time':
          return timeFormatter(value as ITableItem<'time'>);
        case 'list':
          return listFormatter(item);
        case 'tag':
          return tagFormatter(value as ITableItem<'tag'>);
        case 'kv':
          return kvFormatter(value as ITableItem<'kv'>);
        case 'link':
          return linkFormatter(value as ITableItem<'link'>, item);
        case 'status':
          return statusFormatter(value as ITableItem<'status'>);
        case 'progress':
          return progressFormatter(value as ITableItem<'progress'>);
        default:
          return commonFormatter(value as IDetailValItem<'string'>, item);
      }
    }

    // 时间格式化
    function timeFormatter(time: ITableItem<'time'>) {
      if (!time) return '--';
      if (typeof time !== 'number') return time;
      if (time.toString().length < 13) return dayjs.tz(time * 1000, window.timezone).format('YYYY-MM-DD HH:mm:ss');
      return dayjs.tz(time, window.timezone).format('YYYY-MM-DD HH:mm:ss');
    }
    // list类型格式化
    function listFormatter(item: IDetailItem) {
      const val = item.value as ITableItem<'list'>;
      const key = random(10);
      return (
        <div id={key}>
          <ContentCollapse
            defaultHeight={110} // 超过五条显示展开按钮
            expand={item.isExpand}
            maxHeight={300}
            needCloseButton={false}
            onExpandChange={val => {
              item.isExpand = val;
            }}
            onOverflow={val => {
              item.isOverflow = val;
            }}
          >
            <div class='list-type-wrap'>
              {val.length
                ? val.map((item, index) => [
                    <div
                      key={index}
                      class='list-type-item'
                      v-overflow-tips
                    >
                      {item}
                    </div>,
                  ])
                : '--'}
            </div>
          </ContentCollapse>
          {item.isOverflow ? (
            <span
              class='expand-btn'
              onClick={() => {
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
    function tagFormatter(val: ITableItem<'tag'>) {
      return <CommonTagList value={val} />;
    }
    // key-value数据
    function kvFormatter(val: ITableItem<'kv'>) {
      const key = random(10);
      return (
        <div
          id={key}
          class='tag-column'
        >
          {val?.length
            ? val.map((item, index) => (
                <div
                  key={index}
                  class='tag-item set-item'
                  v-overflow-tips
                >
                  <span
                    key={`key__${index}`}
                    class='tag-item-key'
                  >
                    {item.key}
                  </span>
                  &nbsp;:&nbsp;
                  <span
                    key={`val__${index}`}
                    class='tag-item-val'
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
    function linkFormatter(val: ITableItem<'link'>, item: IDetailItem) {
      return (
        <div class='common-link-text'>
          <a
            class='link-col'
            v-overflow-tips
            onClick={e => {
              // 该元素处于 BkCollapse 组件里，为避免该点击事件触发冒泡导致组件异常的 开启/关闭 ，这里手动禁止冒泡。
              e.stopPropagation();
              handleLinkClick(val);
            }}
          >
            {val.value}
          </a>
          {item.need_copy && !!val.value && (
            <i
              class='text-copy icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: t('复制'), delay: 200, boundary: 'window' }}
              onClick={e => {
                // 该元素处于 BkCollapse 组件里，为避免该点击事件触发冒泡导致组件异常的 开启/关闭 ，这里手动禁止冒泡。
                e.stopPropagation();
                handleCopyText(val.value);
              }}
            />
          )}
        </div>
      );
    }
    // link点击事件
    function handleLinkClick(item: ITableItem<'link'>) {
      if (!item.url || props.readonly) return;
      if (item.target === 'self') {
        const resolveRoute = router.resolve({
          path: item.url,
        });
        if (resolveRoute.name === route.name) {
          location.href = resolveRoute.href;
          location.reload();
        } else {
          router.push({
            path: item.url,
          });
        }
        return;
      }
      if (item.target === 'event') {
        handleLinkToDetail(item);
      } else {
        window.open(item.url, random(10));
      }
    }

    // status格式化
    function statusFormatter(val: ITableItem<'status'>) {
      return (
        <CommonStatus
          text={val.text}
          type={val.type}
        />
      );
    }
    // 进度条
    function progressFormatter(val: ITableItem<'progress'>) {
      return (
        <div>
          {<div>{val.label}</div>}
          <Progress
            class={['common-progress-color', `color-${val.status}`]}
            percent={Number((val.value * 0.01).toFixed(2)) || 0}
            showText={false}
            size='small'
          />
        </div>
      );
    }
    // 常用值格式化
    function commonFormatter(val: IDetailValItem<'number'> | IDetailValItem<'string'>, item: IDetailItem) {
      const text = `${val ?? ''}`;
      return (
        <div class='common-detail-text'>
          <span
            class='text'
            v-overflow-tips
          >
            {text || '--'}
          </span>
          {item.need_copy && !!text && (
            <i
              class='text-copy icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: t('复制'), delay: 200, boundary: 'window' }}
              onClick={e => {
                // 该元素处于 BkCollapse 组件里，为避免该点击事件触发冒泡导致组件异常的 开启/关闭 ，这里手动禁止冒泡。
                e.stopPropagation();
                handleCopyText(text);
              }}
            />
          )}
        </div>
      );
    }
    /** 文本复制 */
    function handleCopyText(text: string) {
      let msgStr = t('复制成功');
      copyText(text, errMsg => {
        msgStr = errMsg as string;
      });
      Message({ theme: 'success', message: msgStr });
    }

    function handleLinkToDetail(data: ITableItem<'link'>) {
      return data;
    }

    return {
      activeCollapseName,
      statusData,
      targetStatusName,
      maintainStatusIcon,
      maintainStatusText,
      labelListData,
      moduleData,
      handleTransformVal,
      targetListName,
      t,
    };
  },
  render() {
    return (
      <div class='host-detail-view'>
        {/* 状态展示相关 */}
        <div class='status-container'>
          {/* 运营状态 */}
          {this.statusData[this.targetStatusName[0]] && (
            <div
              class={['status-item', 'bg-failed']}
              v-bk-tooltips={{
                content: this.t('主机当前状态'),
                delay: 200,
                boundary: 'window',
              }}
            >
              <i class={`icon-monitor ${this.maintainStatusIcon}`} />
              <span class='text'>{this.maintainStatusText}</span>
            </div>
          )}

          {this.statusData[this.targetStatusName[1]] && (
            <div
              class={[
                'status-item',
                `bg-${(this.statusData[this.targetStatusName[1]]?.value as IStatusDataSubValue)?.type}`,
              ]}
              v-bk-tooltips={{
                content: this.t('采集状态'),
                delay: 200,
                boundary: 'window',
              }}
            >
              <span class={['common-status-wrap', 'status-wrap-flex']}>
                <span
                  class={[
                    'status-icon',
                    `status-${
                      (this.statusData[this.targetStatusName[1]]?.value as IStatusDataSubValue)?.type || 'disabled'
                    }`,
                  ]}
                />
                <span class='common-status-name'>
                  {(this.statusData[this.targetStatusName[1]]?.value as IStatusDataSubValue)?.text}
                </span>
              </span>
            </div>
          )}
        </div>
        <div class='detail-collapse-panel'>
          {this.labelListData.map(item => (
            <CollapseItem
              key={item.name}
              v-slots={{
                header: () => (
                  <div
                    key={item.name}
                    style={{ maxWidth: `${this.width}px` }}
                    class='panel-item'
                  >
                    <span class={['item-title', { 'title-middle': ['progress'].includes(item.type) }]}>
                      {item.name}
                    </span>
                    <span class='item-value'>{this.handleTransformVal(item)}</span>
                    {item?.count > 0 && (
                      <div>
                        <span class='item-collapse-data-length'>{item?.children?.length}</span>
                      </div>
                    )}
                  </div>
                ),
                content: () => {
                  return (
                    <div class='detail-collapse-content'>
                      {item?.children?.map?.(child => (
                        <div
                          key={child.name}
                          class='row'
                        >
                          <div class='label-container'>
                            <span class='label'>{child.name}</span>
                            <span>&nbsp;:</span>
                          </div>
                          <div class='value-container'>
                            {child.type === 'string' && <div class='value'>{child.value}</div>}
                            {child.type === 'list' &&
                              Array.isArray(child?.value) &&
                              child?.value?.map?.(s => (
                                <div
                                  key={s}
                                  class='value'
                                >
                                  {s}
                                </div>
                              ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                },
              }}
              showContent={item.count > 0}
            />
          ))}

          {/* 所属模块 */}
          {(this.moduleData as IDetailItem[]).map(item => (
            <div key={item.name}>
              {this.targetListName.includes(item.name) && <div class='divider' />}
              <div class='module-data-panel-item'>
                <div class={['module-data-item-title']}>{item.name}</div>
                <div class='module-data-item-value'>{this.handleTransformVal(item)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  },
});
