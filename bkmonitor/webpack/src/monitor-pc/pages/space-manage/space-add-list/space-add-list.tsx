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

import { fetchBusinessInfo, listSpaces } from 'monitor-api/modules/commons';
import { skipToDocsLink } from 'monitor-common/utils/docs';

import ResearchForm from '../research-form/research-form';
import SpaceAddItem from '../space-add-item/space-add-item';

import './space-add-list.scss';

const { i18n } = window;
enum SpaceAddType {
  business = 2 /** 业务 */,
  container = 1 /** 容器项目 */,
  other = 3 /** 其他 */,
  research = 0 /** 研发项目 */,
}
export interface IAddItemData {
  id: SpaceAddType;
  name: string;
  icon: string;
  desc: string;
}

interface IProps {
  show: boolean;
  onSaveSuccess?: () => void;
  onShowChange?: (v: boolean) => void;
}

@Component
export default class SpaceAddList extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  /** 选中的id */
  acitveType: SpaceAddType = null;

  addListData: IAddItemData[] = [
    {
      id: SpaceAddType.research,
      name: i18n.tc('研发项目'),
      icon: 'icon-mc-space-paas',
      desc: window.i18n.tc(
        '研发项目主要是满足日常的研发代码提交和构建， 在研发项目中提供了构建机监控、APM、自定义指标上报等功能。 研发项目与蓝盾项目直接建立绑定关系，新建研发项目会同步到蓝盾项目。'
      ),
    },
    {
      id: SpaceAddType.container,
      name: i18n.tc('容器项目'),
      icon: 'icon-mc-space-bcs',
      desc: window.i18n.tc(
        '容器项目当前主要指 kubernetes，基于容器管理平台(TKEx-IEG), 接入容器项目后能够满足容器相关的监控和日志采集等。同时蓝盾的研发项目，可以直接开启容器项目能力。'
      ),
    },
    {
      id: SpaceAddType.business,
      name: i18n.tc('业务'),
      icon: 'icon-mc-space-biz',
      desc: window.i18n.tc(
        '业务是最终服务的对象，业务可以理解是对外提供的一个站点、游戏、平台服务等。包含了各种资源，物理主机、容器集群、服务模块、业务程序、运营数据等等。所以也包含了不同的角色和不同的研发项目，站在业务的整体视角可以观测到方方面面。'
      ),
    },
    {
      id: SpaceAddType.other,
      name: i18n.tc('其他'),
      icon: 'icon-mc-space-others',
      desc: `${
        window.i18n.tc('蓝鲸监控也支持其他平台的主动对接方式，具体请联系平台管理员') +
        (window.monitor_managers?.length ? ':' : '') +
        (window.monitor_managers || []).join(',')
      }。`,
    },
  ];

  hasSaveSuccess = false;
  newBusinessUrl = '';
  bkciSpaceList = [];
  async created() {
    const data = await fetchBusinessInfo().catch(() => false);
    this.newBusinessUrl = data?.new_biz_apply;
  }
  @Watch('show')
  handleShow(v: boolean) {
    if (v) {
      this.hasSaveSuccess = false;
      this.handleGetSpaceList();
    }
  }

  async handleGetSpaceList() {
    const list = await listSpaces({ show_all: true, show_detail: false }).catch(() => []);
    this.bkciSpaceList = list.filter(item => item.space_type_id === 'bkci');
  }

  handleCancel() {
    this.$emit('showChange', false);
    if (this.hasSaveSuccess) {
      this.$emit('saveSuccess');
    }
  }

  handleChecked(id: SpaceAddType) {
    if (id === SpaceAddType.other) return;
    this.acitveType = this.acitveType === id ? null : id;
  }

  /* 保存成功 */
  handleResearchFormSuccess() {
    this.hasSaveSuccess = true;
    this.handleGetSpaceList();
    this.handleResearchFormCancel();
    this.$emit('saveSuccess');
  }
  handleResearchFormCancel() {
    this.acitveType = null;
  }
  handleGotoLink(urlOrName: string) {
    if (urlOrName.match(/^http/)) {
      window.open(urlOrName, '_blank');
      return;
    }
    skipToDocsLink(urlOrName);
  }
  render() {
    /** 容器项目、业务 */
    const commonTpl = (type: SpaceAddType) => {
      const map: Record<string, any> = {
        [SpaceAddType.container]: {
          title: this.$tc('新建容器项目'),
          doc: 'addClusterMd',
          href: window.cluster_setup_url,
        },
        [SpaceAddType.business]: {
          title: this.$tc('新建业务'),
          doc: this.newBusinessUrl,
          // href: window.agent_setup_url
        },
      };
      const data = map[type];
      return (
        <div class='common-link-guide'>
          <div class='common-link-title'>{data.title}</div>
          <div class='common-link'>
            <a
              class='common-link-item doc'
              onClick={() => this.handleGotoLink(data.doc)}
            >
              <i class='icon-monitor icon-mc-detail' />
              {this.$tc('文档说明')}
            </a>
            {data.href && (
              <a
                class='common-link-item href'
                href={data.href}
                rel='noopener noreferrer'
                target='_blank'
              >
                <i class='icon-monitor icon-mc-link' />
                {this.$tc('去新建')}
              </a>
            )}
          </div>
        </div>
      );
    };
    const contentTpl = (type: SpaceAddType) => {
      switch (type) {
        case SpaceAddType.research:
          return (
            <ResearchForm
              spaceList={this.bkciSpaceList}
              onCancel={this.handleResearchFormCancel}
              onSuccess={this.handleResearchFormSuccess}
            />
          );
        case SpaceAddType.container:
        case SpaceAddType.business:
          return commonTpl(type);
        default:
          return;
      }
    };
    return (
      <bk-dialog
        width={640}
        ext-cls='space-dialog'
        header-position='left'
        show-footer={false}
        title={this.$tc('新增')}
        value={this.show}
        onCancel={this.handleCancel}
      >
        <div class='space-add-list'>
          {this.addListData.map(item => (
            <SpaceAddItem
              key={item.id}
              checked={item.id === this.acitveType}
              data={item}
              disabled={item.id === SpaceAddType.other}
              onChecked={() => this.handleChecked(item.id)}
            >
              {contentTpl(this.acitveType)}
            </SpaceAddItem>
          ))}
        </div>
      </bk-dialog>
    );
  }
}
