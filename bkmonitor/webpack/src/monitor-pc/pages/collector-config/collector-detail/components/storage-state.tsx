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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Divider, Input, Table, TableColumn } from 'bk-magic-vue';

import './storage-state.scss';

interface InfoItem {
  key: string;
  name: string;
  value: string;
  type?: 'number' | 'input';
  hasEdit?: boolean;
  /** 是否需要下划线 */
  hasUnderline?: boolean;
}

interface LocalInfoField extends InfoItem {
  /** 是否处于编辑态 */
  isEdit?: boolean;
  /** 编辑值 */
  editValue?: string | number;
}

interface StatusContentItem {
  key: string;
  name: string;
}

interface StatusValueItem {
  [key: string]: string | number;
}

interface StatusItem {
  name: string;
  content: {
    keys: StatusContentItem[];
    values: StatusValueItem[];
  };
}

interface DataInterface {
  info: InfoItem[];
  status: StatusItem[];
}

interface StorageStateProps {
  collectId: number;
  data: DataInterface;
  loading?: boolean;
}

@Component
export default class StorageState extends tsc<StorageStateProps, {}> {
  @Prop({ type: Number, required: true }) collectId: number;
  @Prop({ type: Object, default: null }) data: DataInterface;
  @Prop({ type: Boolean, default: false }) loading: boolean;

  infoData: LocalInfoField[] = [];

  clusterStatusTable = {
    columns: [],
    data: []
  };

  indexStatusTable = {
    columns: [],
    data: []
  };

  @Watch('data')
  handleDataChange(val: DataInterface) {
    this.infoData = val.info.map(item => {
      // todo 当前版本没有编辑功能，后续版本可能会加上，需要后台返回编辑状态
      if (item.hasEdit) {
        return {
          ...item,
          isEdit: false,
          editValue: ''
        };
      }
      return item;
    });
    this.clusterStatusTable = {
      columns: val.status[0].content.keys,
      data: val.status[0].content.values
    };
    this.indexStatusTable = {
      columns: val.status[1].content.keys,
      data: val.status[1].content.values
    };
  }

  handleInfoEditStatusChange(field: LocalInfoField) {
    field.isEdit = !field.isEdit;
    if (field.isEdit) {
      field.editValue = field.value;
    }
  }

  handleEditConfirm(field: LocalInfoField) {
    console.log(field);
  }

  /**
   * 根据表单字段类型渲染不同的内容
   * @param type 字段类型
   */
  renderInfoField(field: LocalInfoField) {
    const renderEditComp = () => {
      switch (field.type) {
        case 'number':
          return (
            <Input
              type='number'
              min={1}
              v-model={field.editValue}
            />
          );
        case 'input':
          return <Input v-model={field.editValue} />;
      }
    };

    return (
      <div class='info-item'>
        <div class='info-label'>
          <span class={{ label: true, underline: field.hasUnderline }}>{field.name}</span>
        </div>
        <div class='info-value'>
          {field.isEdit ? (
            <div class='edit'>
              <div class='comp'>{renderEditComp()}</div>
              <bk-button
                class='btn'
                text
                onClick={() => this.handleEditConfirm(field)}
              >
                {this.$t('确定')}
              </bk-button>
              <bk-button
                class='btn'
                text
                onClick={() => this.handleInfoEditStatusChange(field)}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          ) : (
            <div class='default'>
              {field.value}
              {field.hasEdit && (
                <i
                  class='icon-monitor icon-bianji'
                  onClick={() => this.handleInfoEditStatusChange(field)}
                />
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  render() {
    return (
      <div
        class='storage-state-component'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='storage-info'>
          <div class='title'>{this.$t('存储信息')}</div>
          <div class='info-form'>{this.infoData.map(field => this.renderInfoField(field))}</div>
        </div>
        <Divider class='divider' />
        <div class='cluster-status'>
          <div class='title'>{this.$t('集群状态')}</div>
          <div class='table-content'>
            <Table
              class='data-table'
              data={this.clusterStatusTable.data}
              outer-border={false}
              header-border={false}
              max-height={350}
            >
              {this.clusterStatusTable.columns.map(column => {
                return (
                  <TableColumn
                    key={column.key}
                    label={column.name}
                    prop={column.key}
                  />
                );
              })}
            </Table>
          </div>
        </div>
        <Divider class='divider' />
        <div class='index-status'>
          <div class='title'>{this.$t('索引状态')}</div>
          <div class='table-content'>
            <Table
              class='data-table'
              data={this.indexStatusTable.data}
              outer-border={false}
              header-border={false}
              max-height={350}
            >
              {this.indexStatusTable.columns.map(column => {
                return (
                  <TableColumn
                    key={column.key}
                    label={column.name}
                    prop={column.key}
                  />
                );
              })}
            </Table>
          </div>
        </div>
      </div>
    );
  }
}
