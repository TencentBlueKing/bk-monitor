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

import { importEventPlugin } from 'monitor-api/modules/event_plugin';

import type { TranslateResult } from 'vue-i18n';

export type ViewType = 'card' | 'list';
interface ContentHeaderEvents {
  onImportSuccess: () => void;
  onSearchValueChange: (value: string) => void;
  onViewChange: (type: ViewType) => void;
}
interface ITypeData {
  icon: string;
  id: ViewType;
  tips: TranslateResult;
}

interface IViewTypes {
  active: ViewType;
  list: ITypeData[];
}

/**
 * 集成模块顶部操作组件
 */
@Component({ name: 'ContentHeader' })
export default class ContentHeader extends tsc<{ filterWidth: number; searchValue: string }, ContentHeaderEvents> {
  @Prop({ default: '' }) searchValue: string;
  @Prop({ required: true }) filterWidth: number;
  viewTypes: IViewTypes = {
    list: [
      {
        id: 'card',
        icon: 'icon-monitor icon-card',
        tips: this.$t('卡片视图'),
      },
      {
        id: 'list',
        icon: 'icon-monitor icon-biaoge',
        tips: this.$t('列表视图'),
      },
    ],
    active: 'card',
  };

  fileLoading = false;

  handleImport() {
    this.$refs?.upload?.click?.();
  }
  async fileChange(e): void {
    this.fileLoading = true;
    if (e.target.files[0]) {
      const file = e.target.files[0];
      const isTarGz = /^[\u4E00-\u9FA5A-Za-z0-9_]+(.tar.gz)$/g.test(file.name);
      if (isTarGz) {
        const data = await importEventPlugin({
          file_data: file,
          force_update: true,
        }).catch(() => null);
        if (data) {
          this.$bkMessage({
            theme: 'success',
            message: this.$t('导入成功'),
          });
          this.$emit('importSuccess');
        }
      } else {
        this.$bkMessage({
          theme: 'warning',
          message: this.$t('上传tar.gz文件'),
        });
      }
    }
    this.fileLoading = false;
  }

  render() {
    return (
      <header class='header'>
        <div class='header-left'>
          <bk-button
            loading={this.fileLoading}
            onClick={() => this.handleImport()}
          >
            <span class='import-btn'>
              <span class='icon-monitor icon-xiazai1' />
              <span>{this.$t('导入')}</span>
              <input
                ref='upload'
                class='file-input'
                accept='.gz,.tar.gz'
                type='file'
                on-change={this.fileChange}
                onClick={e => {
                  e.stopPropagation();
                }}
              />
            </span>
          </bk-button>
        </div>
        <div class='header-right'>
          <i
            style={{ display: this.filterWidth > 200 ? 'none' : 'flex' }}
            class='icon-monitor icon-double-up set-filter'
            on-click={() => this.$emit('set-filter')}
          />
          <div class='type-switch'>
            {this.viewTypes.list.map(item => (
              <span
                class={['type-switch-icon', { active: item.id === this.viewTypes.active }]}
                v-bk-tooltips={{
                  placement: 'top',
                  content: item.tips,
                  allowHTML: false,
                }}
                onClick={() => this.handleChangeViewType(item)}
              >
                <i class={item.icon} />
              </span>
            ))}
          </div>
          <bk-input
            class='search'
            placeholder={this.$t('搜索事件源名称、ID、分类、方式、作者、创建人、更新人')}
            right-icon='bk-icon icon-search'
            value={this.searchValue}
            onChange={this.handleSearchValueChange}
          />
        </div>
      </header>
    );
  }

  /**
   * 视图类型切换事件
   * @param item
   * @returns
   */
  @Emit('viewChange')
  handleChangeViewType(item: ITypeData) {
    this.viewTypes.active = item.id;
    return this.viewTypes.active;
  }

  /**
   * 搜索事件
   * @param value
   * @returns
   */
  @Emit('searchValueChange')
  handleSearchValueChange(value: string) {
    return value;
  }
}
