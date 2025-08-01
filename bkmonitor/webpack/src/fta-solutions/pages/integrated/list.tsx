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

import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';

import type { IPluginDetail, OperateType } from './content-group-item';
import type { IGroupData } from './group';
import type { EmptyStatusOperationType, EmptyStatusType } from 'monitor-pc/components/empty-status/types';

import './list.scss';

interface IListEvents {
  onEmptyOperate?: (type: EmptyStatusOperationType) => void;
  onOperate: (data: IOperateData) => void;
}

interface IListProps {
  data: IGroupData;
  emptyType?: EmptyStatusType;
}
interface IOperateData {
  item: IPluginDetail;
  type: OperateType;
}
/**
 * 列表视图
 */
@Component({ name: 'List' })
export default class List extends tsc<IListProps, IListEvents> {
  // 当前分组数据
  @Prop({ type: Object, default: () => ({}) }) readonly data: IGroupData;
  @Prop({ type: String, default: 'empty' }) readonly emptyType: EmptyStatusType;

  get tableData() {
    return this.data.data.reduce<IPluginDetail[]>((pre, item) => {
      pre.push(...item.data.filter(set => set.show));
      return pre;
    }, []);
  }

  statusMap = {
    ENABLED: this.$t('已启用'),
    UPDATABLE: this.$t('有更新'),
    NO_DATA: this.$t('无数据'),
    REMOVE_SOON: this.$t('将下架'),
    REMOVED: this.$t('已下架'),
    DISABLED: this.$t('已停用'),
  };

  @Emit('emptyOperate')
  handleOperation(type: EmptyStatusOperationType) {
    return type;
  }

  render() {
    return (
      <bk-table
        class='list-view'
        data={this.tableData}
        row-class-name={this.getRowClassName}
        size='medium'
      >
        <div slot='empty'>
          <EmptyStatus
            type={this.emptyType}
            onOperation={this.handleOperation}
          />
        </div>
        <bk-table-column
          scopedSlots={{
            default: ({ row }: { row: IPluginDetail }) => (
              <div class='col-name'>
                {row.logo ? (
                  <img
                    class='img-logo'
                    alt=''
                    src={`data:image/png;base64,${row.logo}`}
                  />
                ) : (
                  <span class='text-logo'>
                    {(row.plugin_display_name || row.plugin_id).slice(0, 1).toLocaleUpperCase()}
                  </span>
                )}
                <div class='col-name-detail'>
                  <span
                    class='name'
                    onClick={() => this.handleGotoDetail(row)}
                  >
                    {row.plugin_display_name}
                  </span>
                  <span class='author'>
                    {row.author}
                    {row.is_official ? <i class='icon-monitor icon-mc-official' /> : null}
                  </span>
                </div>
              </div>
            ),
          }}
          label={this.$t('名称')}
          min-width={200}
        />
        <bk-table-column
          label={this.$t('方式')}
          prop='main_type_display'
        />
        <bk-table-column
          width={100}
          label={this.$t('类型')}
          prop='category_display'
        />
        <bk-table-column
          label={this.$t('分类')}
          prop='scenario_display'
        />
        <bk-table-column
          scopedSlots={{
            default: ({ row }: { row: IPluginDetail }) => (
              <div class='col-tag'>{row?.tags?.map(tag => <span class='tag'>{tag}</span>) || '--'}</div>
            ),
          }}
          label={this.$t('标签')}
        />
        <bk-table-column
          width={100}
          scopedSlots={{
            default: ({ row }: { row: IPluginDetail }) => (
              <span class={`col-status ${row.status.toLocaleLowerCase()}`}>{this.statusMap[row.status]}</span>
            ),
          }}
          label={this.$t('状态')}
        />
        <bk-table-column
          width={80}
          scopedSlots={{
            default: ({ row }: { row: IPluginDetail }) => (
              <span class='col-popularity'>
                {row.popularity ? (
                  <span>
                    <i class='icon-monitor icon-mc-check-fill' />
                    {row.popularity}
                  </span>
                ) : (
                  '--'
                )}
              </span>
            ),
          }}
          align='center'
          label={this.$t('热度')}
        />
        <bk-table-column
          scopedSlots={{
            default: ({ row }: { row: IPluginDetail }) => (
              <div>
                <div>
                  <bk-user-display-name user-id={row.create_user} />
                </div>
                <div>{row.create_time}</div>
              </div>
            ),
          }}
          label={this.$t('创建记录')}
        />
        <bk-table-column
          scopedSlots={{
            default: ({ row }: { row: IPluginDetail }) => (
              <div>
                <div>
                  <bk-user-display-name user-id={row.update_user} />
                </div>
                <div>{row.update_time}</div>
              </div>
            ),
          }}
          label={this.$t('更新记录')}
        />
        <bk-table-column
          width={100}
          scopedSlots={{
            default: ({ row }: { row: IPluginDetail }) => (
              <bk-button
                v-en-style='width: 72px;'
                text
                onClick={() => this.handleConfig(row)}
              >
                {this.$t('配置')}
              </bk-button>
            ),
          }}
          label={this.$t('操作')}
        />
      </bk-table>
    );
  }

  getRowClassName({ row }: { row: IPluginDetail }) {
    return row.status === 'REMOVED' ? 'row-removed' : '';
  }

  @Emit('operate')
  handleGotoDetail(row: IPluginDetail): IOperateData {
    return {
      type: 'detail',
      item: row,
    };
  }

  @Emit('operate')
  handleConfig(row: IPluginDetail): IOperateData {
    return {
      type: 'config',
      item: row,
    };
  }
}
