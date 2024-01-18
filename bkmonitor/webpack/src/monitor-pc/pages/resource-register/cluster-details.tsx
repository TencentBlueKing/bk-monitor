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

import HistoryDialog from '../../components/history-dialog/history-dialog';

import './cluster-details.scss';

interface IProps {
  show?: boolean;
  data?: any;
  onShowChange?: (v: boolean) => void;
  onEdit?: (id: string) => void;
}
@Component
export default class ClusterDetails extends tsc<IProps> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ default: () => null, type: Object }) data: any;

  contents = [];
  clusterName = '';
  historyList = [];

  @Watch('show')
  handleWatchShow(v: boolean) {
    if (v) {
      this.init();
    }
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  init() {
    if (!!this.data) {
      this.clusterName = this.data.cluster_name;
      this.contents = [
        {
          name: this.$tc('资源类别'),
          content: this.data.cluster_type
        },
        {
          name: this.$t('集群名称'),
          content: this.data.cluster_name
        },
        {
          name: this.$tc('用途'),
          content: !!this.data.label ? (
            <div class='used-tags'>
              {this.data.lable.split(',').map(label => (
                <div class='tags-item'>{label}</div>
              ))}
            </div>
          ) : (
            '--'
          )
        },
        {
          name: this.$tc('集群域名'),
          content: this.data.domain_name
        },
        {
          name: this.$t('端口'),
          content: this.data.port
        },
        {
          name: this.$t('访问协议'),
          content: this.data.schema
        },
        {
          name: this.$tc('用户名'),
          content: this.data.username
        },
        {
          name: this.$t('密码'),
          content: this.data.password
        },
        {
          name: this.$t('ges注册配置'),
          content: this.data.gse_stream_to_id === -1 ? this.$t('否') : this.$t('是')
        },
        {
          name: this.$t('负责人'),
          content: this.data.creator
        },
        {
          name: this.$t('描述'),
          content: this.data.description
        }
      ];
      this.historyList = [
        { label: this.$t('创建人'), value: this.data.creator || '--' },
        { label: this.$t('创建时间'), value: this.data.create_time || '--' },
        { label: this.$t('最近更新人'), value: this.data.last_modify_user || '--' },
        { label: this.$t('修改时间'), value: this.data.last_modify_time || '--' }
      ];
    }
  }

  handleEdit() {
    this.$emit('edit', this.data.cluster_id);
  }

  detailsItem(item: { name: string; content: any }, key) {
    return (
      <div
        class='content-item'
        key={key}
      >
        <span class='lable'>{item.name}: </span>
        <span class='content'>{item.content || '--'}</span>
      </div>
    );
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='resource-register-cluster-details-sides'
        isShow={this.show}
        quick-close={true}
        transfer={true}
        width={400}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
      >
        <div
          slot='header'
          class='header-wrap'
        >
          <span class='header-title'>{this.clusterName}</span>
          <bk-button
            class='edit-btn'
            theme='primary'
            outline
            onClick={this.handleEdit}
          >
            {this.$t('编辑')}
          </bk-button>
          <HistoryDialog
            class='mr24'
            list={this.historyList}
          />
        </div>
        <div slot='content'>
          <div class='content-wrap'>{this.contents.map((item, index) => this.detailsItem(item, index))}</div>
        </div>
      </bk-sideslider>
    );
  }
}
