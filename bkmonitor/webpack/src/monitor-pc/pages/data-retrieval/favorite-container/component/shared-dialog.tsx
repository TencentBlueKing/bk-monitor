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

import { Component, Emit, Model, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { shareFavorite } from '../../../../../monitor-api/modules/model';
import { Debounce } from '../../../../../monitor-common/utils/utils';
import { ISpaceItem } from '../../../../types';
import { IFavList } from '../../typings';

import List, { IListItem } from './checkbox-list';

import './shared-dialog.scss';

interface IProps {
  value?: boolean;
  favoriteConfig: IFavList.favList;
  favoriteSearchType: string;
}

@Component
export default class SharedDialog extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ type: Object, default: () => ({}) }) favoriteConfig: IFavList.favList; // 共享的参数
  @Prop({ type: String, default: 'metric' }) favoriteSearchType: string; // 共享的参数

  positionTop = 0; // 定位
  resetNameRule = 'skip'; // 重命名规则
  keyword = ''; // 检索keyword
  searchTypeId = '';
  isQuest = false; // 正在请求中
  spaceTypeIdList: { id: string; name: string; styles: any }[] = [];

  @Ref('list') private readonly listRef: HTMLDivElement; // select实例

  created() {
    const spaceTypeMap: Record<string, any> = {};
    this.bizList.forEach(item => {
      spaceTypeMap[item.space_type_id] = 1;
      if (item.space_type_id === 'bkci' && item.space_code) {
        spaceTypeMap.bcs = 1;
      }
    });
    // this.spaceTypeIdList = Object.keys(spaceTypeMap).map(key => ({
    //   id: key,
    //   name: SPACE_TYPE_MAP[key]?.name || this.$t('未知'),
    //   styles: SPACE_TYPE_MAP[key]?.light || {},
    // }));
  }

  /** 业务列表 */
  get bizList(): ISpaceItem[] {
    return this.$store.getters.bizList;
  }

  get bizId(): string {
    return this.$store.getters.bizId;
  }

  /** 业务过滤后的列表 */
  get bizListFilter() {
    const list: IListItem = {
      id: null,
      name: '' /** 普通列表 */,
      children: []
    };
    const keyword = this.keyword.trim().toLocaleLowerCase();
    this.bizList.forEach(item => {
      let show = false;
      if (this.searchTypeId) {
        show =
          this.searchTypeId === 'bcs'
            ? item.space_type_id === 'bkci' && !!item.space_code
            : item.space_type_id === this.searchTypeId;
      }
      if ((show && keyword) || (!this.searchTypeId && !show)) {
        show =
          item.space_name.toLocaleLowerCase().indexOf(keyword) > -1 ||
          item.py_text.toLocaleLowerCase().indexOf(keyword) > -1 ||
          `${item.id}`.includes(keyword) ||
          `${item.space_id}`.toLocaleLowerCase().includes(keyword);
      }
      if (show) {
        const tags = [{ id: item.space_type_id, name: item.type_name, type: item.space_type_id }];
        if (item.space_type_id === 'bkci' && item.space_code) {
          tags.push({ id: 'bcs', name: this.$tc('容器项目'), type: 'bcs' });
        }
        const newItem = {
          ...item,
          name: item.space_name.replace(/\[.*?\]/, ''),
          tags
        };
        list.children.push(newItem as IListItem);
      }
    });
    const allList: IListItem[] = [];
    if (!!list.children.length) {
      list.children = list.children.slice(0, 500);
      allList.push(list);
    }
    return allList;
  }

  mounted() {
    this.positionTop = Math.floor(document.body.clientHeight * 0.1);
  }

  /** 搜索操作 */
  @Debounce(300)
  handleBizSearch(keyword?: string) {
    this.keyword = keyword;
  }

  @Emit('change')
  handleShowChange(value = false) {
    return value;
  }

  handleValueChange(value: boolean) {
    if (!value) {
      this.handleShowChange();
      (this.listRef as any).clearSelectList();
      this.resetNameRule = 'skip';
    }
  }

  async handleSubmitFormData() {
    let selectIDList = (this.listRef as any).selectList;

    if (!selectIDList.length) {
      // 没选空间
      this.$bkMessage({
        message: this.$t('请选择空间'),
        theme: 'warning'
      });
      return;
    }

    if (selectIDList.length === 1 && selectIDList[0] === '*') {
      // 全选空间
      selectIDList = this.bizListFilter[0].children.map(item => item.bk_biz_id);
    }

    try {
      this.isQuest = true;
      const { name, config } = this.favoriteConfig;
      const data = {
        bk_biz_id: this.bizId,
        type: this.favoriteSearchType,
        share_bk_biz_ids: selectIDList,
        duplicate_mode: this.resetNameRule,
        name,
        config
      };
      await shareFavorite(data);
      this.$bkMessage({
        message: this.$t('共享成功'),
        theme: 'success'
      });
      this.handleShowChange();
    } catch (err) {
      console.warn(err);
    } finally {
      this.isQuest = false;
    }
  }

  // handleSearchType(typeId: string) {
  //   this.searchTypeId = typeId === this.searchTypeId ? '' : typeId;
  // }

  render() {
    return (
      <bk-dialog
        value={this.value}
        title={this.$t('共享')}
        header-position='left'
        width={480}
        position={{ top: this.positionTop }}
        mask-close={false}
        auto-close={false}
        loading={this.isQuest}
        on-value-change={this.handleValueChange}
        on-confirm={this.handleSubmitFormData}
      >
        <div class='biz-list-wrap-01'>
          <div class='biz-list-main'>
            <div class='biz-search-wrap'>
              <bk-input
                class='biz-search'
                clearable={false}
                right-icon='bk-icon icon-search'
                placeholder={this.$t('搜索空间')}
                value={this.keyword}
                on-clear={() => this.handleBizSearch('')}
                on-change={this.handleBizSearch}
                on-blur={this.handleBizSearch}
              />
            </div>
            {/* {
              this.spaceTypeIdList.length > 1 && <ul class='space-type-list'>
                {
                  this.spaceTypeIdList.map(item => <li class='space-type-item'
                    style={{
                      ...item.styles,
                      borderColor: item.id === this.searchTypeId ? item.styles.color : 'transparent',
                    }}
                    key={item.id}
                    onClick={() => this.handleSearchType(item.id)}>{item.name}</li>)
                }
              </ul>
            } */}
            <ul class='biz-list'>
              <List
                ref='list'
                list={this.bizListFilter}
              ></List>
            </ul>
          </div>
        </div>
        <div class='reset-name'>
          <span v-bk-tooltips={{ content: this.$t('该规则仅针对重名内容生效') }}>
            <div class='reset-name-title'>{this.$t('重名规则')}</div>
          </span>
          <bk-radio-group vModel={this.resetNameRule}>
            <bk-radio value='skip'>{this.$t('不共享')}</bk-radio>
            <bk-radio value='copy'>{this.$t('创建副本')}</bk-radio>
            <bk-radio value='overwrite'>{this.$t('覆盖')}</bk-radio>
          </bk-radio-group>
        </div>
      </bk-dialog>
    );
  }
}
