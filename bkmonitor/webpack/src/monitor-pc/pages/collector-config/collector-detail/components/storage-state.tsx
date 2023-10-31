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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Divider, Input, Table, TableColumn } from 'bk-magic-vue';

import './storage-state.scss';

enum InfoFieldEnum {
  StorageIndexName = 'storageIndexName',
  StorageCluster = 'storageCluster',
  ExpiredTime = 'expiredTime',
  CopyNumber = 'copyNumber'
}
interface InfoField {
  label: string;
  /** 是否需要编辑功能 */
  hasEdit?: boolean;
  /** 是否处于编辑态 */
  isEdit?: boolean;
  /** 编辑值 */
  editValue?: string | number;
  /** 是否需要下划线 */
  hasUnderline?: boolean;
}

type InfoFields = {
  [key in InfoFieldEnum]: InfoField;
};

interface StorageStateProps {
  collectId: number;
}

@Component
export default class StorageState extends tsc<StorageStateProps, {}> {
  @Prop({ type: Number, required: true }) collectId: number;

  infoData = {
    [InfoFieldEnum.StorageIndexName]: 'trace_agg_scene',
    [InfoFieldEnum.StorageCluster]: '默认集群',
    [InfoFieldEnum.ExpiredTime]: 7,
    [InfoFieldEnum.CopyNumber]: 1
  };

  infoFields: InfoFields = {
    [InfoFieldEnum.StorageIndexName]: {
      label: this.$tc('存储索引名')
    },
    [InfoFieldEnum.StorageCluster]: {
      label: this.$tc('存储集群'),
      hasEdit: true,
      isEdit: false,
      editValue: ''
    },
    [InfoFieldEnum.ExpiredTime]: {
      label: this.$tc('过期时间'),
      hasEdit: true,
      isEdit: false,
      editValue: 1,
      hasUnderline: true
    },
    [InfoFieldEnum.CopyNumber]: {
      label: this.$tc('副本数'),
      hasEdit: true,
      isEdit: false,
      editValue: 1,
      hasUnderline: true
    }
  };

  clusterTableList = [];
  clusterTableLoading = false;

  indexTableList = [];
  indexTableLoading = false;

  handleInfoEdit(type: InfoFieldEnum) {
    this.infoFields[type].isEdit = true;
    this.infoFields[type].editValue = this.infoData[type];
  }

  handleEditConfirm(field: InfoField) {
    console.log(field);
  }

  /**
   * 根据表单字段类型渲染不同的内容
   * @param type 字段类型
   */
  renderInfoField(type: InfoFieldEnum) {
    const field = this.infoFields[type];

    const renderEditComp = () => {
      switch (type) {
        case InfoFieldEnum.StorageCluster:
          return <Input v-model={this.infoFields[type].editValue} />;
        case InfoFieldEnum.ExpiredTime:
        case InfoFieldEnum.CopyNumber:
          return (
            <Input
              type='number'
              min={1}
              v-model={field.editValue}
            />
          );
      }
    };

    return (
      <div class='info-item'>
        <div class='info-label'>
          <span class={{ label: true, underline: field.hasUnderline }}>{field.label}</span>
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
                onClick={() => (field.isEdit = false)}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          ) : (
            <div class='default'>
              {this.infoData[type]}
              {field.hasEdit && (
                <i
                  class='icon-monitor icon-bianji'
                  onClick={() => this.handleInfoEdit(type)}
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
      <div class='storage-state-component'>
        <div class='storage-info'>
          <div class='title'>{this.$t('存储信息')}</div>
          <div class='info-form'>
            <div class='info-row'>
              {this.renderInfoField(InfoFieldEnum.StorageIndexName)}
              {this.renderInfoField(InfoFieldEnum.StorageCluster)}
            </div>
            <div class='info-row'>
              {this.renderInfoField(InfoFieldEnum.ExpiredTime)}
              {this.renderInfoField(InfoFieldEnum.CopyNumber)}
            </div>
          </div>
        </div>
        <Divider class='divider' />
        <div class='cluster-status'>
          <div class='title'>{this.$t('集群状态')}</div>
          <div class='table-content'>
            <Table
              class='data-table'
              data={this.clusterTableList}
              outer-border={false}
              header-border={false}
              v-bkloading={{ isLoading: this.clusterTableLoading }}
            >
              <TableColumn label={this.$t('索引')} />
              <TableColumn label={this.$t('运行状态')} />
              <TableColumn
                label={this.$t('主分片')}
                sortable
              />
              <TableColumn
                label={this.$t('副本分片')}
                sortable
              />
              <TableColumn
                label={this.$t('文档计数')}
                sortable
              />
              <TableColumn
                label={this.$t('存储大小')}
                sortable
              />
            </Table>
          </div>
        </div>
        <Divider class='divider' />
        <div class='index-status'>
          <div class='title'>{this.$t('索引状态')}</div>
          <div class='table-content'>
            <Table
              class='data-table'
              data={this.indexTableList}
              outer-border={false}
              header-border={false}
              v-bkloading={{ isLoading: this.indexTableLoading }}
            >
              <TableColumn label={this.$t('索引')} />
              <TableColumn label={this.$t('运行状态')} />
              <TableColumn
                label={this.$t('主分片')}
                sortable
              />
              <TableColumn
                label={this.$t('副本分片')}
                sortable
              />
              <TableColumn
                label={this.$t('文档计数')}
                sortable
              />
              <TableColumn
                label={this.$t('存储大小')}
                sortable
              />
            </Table>
          </div>
        </div>
      </div>
    );
  }
}
