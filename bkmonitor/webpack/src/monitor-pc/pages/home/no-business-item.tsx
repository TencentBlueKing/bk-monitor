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
import { throttle } from 'throttle-debounce';

// 20231205 代码还原，先保留原有部分
// import { showAccessRequest } from '../../components/access-request-dialog';
import { spaceTypeTexts } from '../../../fta-solutions/pages/home/business-item';
import { getAuthorityDetail } from '../../../monitor-api/modules/iam';

import './no-business-item.scss';

interface IData {
  id: string | number;
  name: string;
  space_info?: {
    space_type_id?: string;
    space_code?: any;
    space_id?: string;
  };
}

interface IProps {
  data: IData;
}

@Component
export default class NoBusinessItem extends tsc<IProps> {
  @Prop({
    type: Object,
    default: () => ({
      name: '',
      id: ''
    })
  })
  data: IData;

  url = '';
  loading = false;

  /* 暂无权限标签位置 */
  tagPosition = {
    top: 0,
    left: 0
  };
  tagActive = false;
  mousemoveFn = () => {};

  // 判断当前业务，并返回tag
  // get getCurrentBizTag() {
  //   if (this.$store.getters.bizId === this.data.id) {
  //     return <bk-tag theme='success'> { this.$t('当前空间')} </bk-tag>;
  //   }
  // }

  async created() {
    this.mousemoveFn = throttle(50, false, this.handleMousemove);
    if (this.data.id) {
      this.loading = true;
      this.url = await getAuthorityDetail({
        action_ids: ['view_business_v2'],
        bk_biz_id: this.data.id
      })
        .then(res => res.apply_url)
        .catch(() => false);
      this.loading = false;
    }
  }

  handleClick() {
    // 20231205 代码还原，先保留原有部分
    // showAccessRequest(this.url);
    window.open(this.url);
  }

  // 项目类型tag
  typeLabelTag(item) {
    const tags = spaceTypeTexts(item);
    return tags.map(tag => (
      <div
        class='type-tag'
        style={{
          color: tag.light.color,
          backgroundColor: tag.light.backgroundColor
        }}
      >
        {tag.name}
      </div>
    ));
  }

  // 判断当前业务，并返回tag
  getCurrentBizTag() {
    if (this.$store.getters.bizId === this.data.id) {
      return (
        <div class='current-tag-wrap'>
          <div class='slope-tag'>
            <span class='slope-tag-text'>{window.i18n.tc('当前')}</span>
          </div>
        </div>
      );
    }
  }

  handleMousemove(event: MouseEvent) {
    this.tagPosition = {
      top: event.pageY,
      left: event.pageX
    };
  }
  handleMouseenter() {
    document.addEventListener('mousemove', this.mousemoveFn);
    this.tagActive = true;
  }
  handleMouseleave() {
    document.removeEventListener('mousemove', this.mousemoveFn);
    this.tagActive = false;
  }

  // id显示逻辑
  getIdStr() {
    if (this.data?.space_info?.space_type_id === 'bkcc') {
      return `#${this.data.id}`;
    }
    return this.data?.space_info?.space_id || `#${this.data.id}`;
  }

  render() {
    return (
      <div class='no-business-item-component'>
        <div
          class='left'
          onMouseenter={this.handleMouseenter}
          onMouseleave={this.handleMouseleave}
        >
          {this.tagActive && (
            <span
              class='err-tag'
              style={{
                top: `${this.tagPosition.top + 5}px`,
                left: `${this.tagPosition.left + 5}px`
              }}
            >
              {window.i18n.tc('暂无权限')}
            </span>
          )}
          {this.getCurrentBizTag()}
          <div class='head'>
            <div class='title'>
              <span class='title-wrap'>
                <span
                  class='name'
                  v-bk-overflow-tips
                >
                  {this.data.name}
                </span>
                <span class='subtitle'>({this.getIdStr()})</span>
              </span>
              {this.typeLabelTag(this.data.space_info)}
            </div>
          </div>
          <div class='skeleton'>
            {/* eslint-disable-next-line @typescript-eslint/no-require-imports */}
            <img
              src={require('../../static/images/svg/business-skeleton.svg')}
              alt=''
            ></img>
          </div>
        </div>
        <div class='line'></div>
        <div
          class='right'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='content'>
            <bk-exception
              class='content-exception'
              type={403}
            >
              <span class='msg'>{window.i18n.tc('您没有业务权限，请先申请！')}</span>
            </bk-exception>
          </div>
          <bk-button
            theme='primary'
            class='btn'
            onClick={this.handleClick}
          >
            {window.i18n.tc('申请权限')}
          </bk-button>
        </div>
      </div>
    );
  }
}
