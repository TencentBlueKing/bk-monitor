<!--
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
-->
<template>
  <div
    v-show="!taskDetail.show && hasGroupList"
    class="group-task"
  >
    <div class="group-task-header">
      <span class="header-name"> {{ $t('拨测任务组') }} </span>
    </div>
    <div
      ref="cardWrap"
      class="group-task-wrap"
      :style="{ height: wrapHeight + 'px' }"
    >
      <div
        ref="cardWrapList"
        class="group-task-wrap-list"
      >
        <div
          v-for="(item, index) in group"
          v-show="item.name.includes(keyword)"
          :key="index"
          :ref="'task-item-' + index"
          class="group-task-wrap-list-item"
          :class="{ 'drag-active': index === drag.active }"
          @click.stop="handleItemClick(item)"
          @dragover="handleDragOver(index, item, $event)"
          @dragleave="handleDragLeave(index, item, $event)"
          @dragenter="handleDragEnter(index, item, $event)"
          @drop="handleDragDrop(index, item, $event)"
          @mouseenter="handleGroupMouseEnter(index)"
          @mouseleave="handleGroupMouseLeave(item, index)"
        >
          <div class="item-desc">
            <span
              class="desc-icon"
              :style="{
                'background-image': item.logo ? `url(${item.logo})` : 'none',
                'background-color': item.logo ? '' : '#B6CAEC',
                'border-radius': item.logo ? '0' : '100%',
              }"
            >
              {{ !item.logo ? item.name.slice(0, 1).toLocaleUpperCase() : '' }}
            </span>
            <div class="desc-right">
              <div class="desc-right-title">
                {{ item.name
                }}<span
                  v-if="item.alarm_num"
                  class="alarm-label"
                  >{{ item.alarm_num }}</span
                >
              </div>
              <div class="desc-right-label">
                <span
                  v-for="(set, name) in item.protocol_num"
                  :key="name"
                  class="right-label"
                  >{{ `${set.name}(${set.val})` }}</span
                >
                <span
                  v-if="!item.protocol_num || !item.protocol_num.length"
                  class="right-label"
                >
                  {{ $t('空任务组') }}
                </span>
              </div>
              <span
                v-if="hoverActive === index"
                :ref="'popover-' + index"
                v-authority="{ active: !authority.MANAGE_AUTH }"
                class="desc-right-icon"
                :class="{ 'hover-active': popover.hover }"
                @click.stop="
                  authority.MANAGE_AUTH ? handlePopoverShow(item, index, $event) : handleShowAuthorityDetail()
                "
                @mouseleave="handleGroupPopoverLeave"
                @mouseover="popover.hover = true"
              >
                <i class="bk-icon icon-more" />
              </span>
            </div>
          </div>
          <div
            v-if="item.top_three_tasks.length"
            class="item-list"
          >
            <div
              v-for="(pro, i) in item.top_three_tasks"
              :key="i"
              class="item-list-progress"
            >
              <div class="progress-desc">
                <span class="desc-name">{{ pro.name }}</span>
                <span class="desc-percent">{{ pro.available !== null ? pro.available + '%' : '--' }}</span>
              </div>
              <bk-progress
                class="progress-item"
                :percent="+(pro.available * 0.01).toFixed(2) || 0"
                :show-text="false"
                :color="pro.available | filterProcess"
              />
            </div>
          </div>
          <div
            v-else
            class="item-empty"
          >
            <div class="item-empty-item">
              {{ $t('暂无拨测任务') }}
            </div>
            <div class="item-empty-item">
              {{ $t('可以拖动拨测任务至此') }}
            </div>
          </div>
        </div>
      </div>
    </div>
    <div
      v-if="needExpand && !expand"
      class="more-btn-wrap"
      @click="handleExpand"
    >
      <span class="more-btn">{{ $t('显示全部') }}<i class="icon-monitor icon-double-down" /></span>
    </div>
    <div v-show="false">
      <div
        ref="popoverContent"
        class="popover-desc"
      >
        <div
          class="popover-desc-btn"
          @click.stop="handleEditGroup"
        >
          {{ $t('编辑') }}
        </div>
        <div
          class="popover-desc-btn"
          @click.stop="handleDeleteGroup"
        >
          {{ $t('解散任务组') }}
        </div>
      </div>
    </div>
    <bk-dialog
      v-model="dialog.edit.show"
      class="bk-dialog-edit"
      :title="dialog.edit.add ? $t('新建拨测任务组') : $t('编辑拨测任务组')"
      header-position="left"
      width="480"
      @after-leave="fixStyle"
    >
      <div class="dialog-edit">
        <div class="dialog-edit-content">
          <div>
            <div class="dialog-edit-label">
              {{ $t('任务组名称') }}
            </div>
            <bk-input
              v-model="dialog.edit.name"
              :class="{ 'dialog-edit-input': dialog.edit.validate }"
              :placeholder="$t('输入拨测任务组名称')"
              @blur="dialog.edit.validate = !dialog.edit.name.length"
              @change="dialog.edit.validate = !dialog.edit.name.length"
            />
            <div
              v-show="dialog.edit.validate"
              class="dialog-edit-validate"
            >
              {{ dialog.edit.message || '输入拨测任务组名称' }}
            </div>
          </div>
          <div v-if="false">
            <div class="dialog-edit-label">
              {{ $t('所属') }}
            </div>
            <bk-select
              v-model="dialog.edit.bizId"
              :placeholder="$t('选择所属空间')"
              :disabled="bizId !== 0"
            >
              <bk-option
                v-for="item in bizList"
                :id="item.id"
                :key="item.id"
                class="dialog-edit-option"
                :name="item.text"
              />
            </bk-select>
          </div>
          <div>
            <div class="dialog-edit-label">
              {{ $t('选择拨测任务') }}
            </div>
            <bk-select
              v-model="dialog.edit.select"
              class="dialog-edit-select"
              multiple
              :placeholder="$t('选择拨测任务')"
            >
              <bk-option
                v-for="item in taskList"
                :id="item.id"
                :key="item.id"
                class="dialog-edit-option"
                :name="item.name"
              />
            </bk-select>
          </div>
        </div>
        <div class="dialog-edit-upload">
          <div
            class="dialog-edit-logo"
            :style="{ 'background-image': dialog.edit.logo ? `url(${dialog.edit.logo})` : 'none' }"
            @mouseover="dialog.edit.close = true"
            @mouseleave="dialog.edit.close = false"
          >
            {{ !dialog.edit.logo ? 'LOGO' : '' }}
            <div
              v-show="dialog.edit.close"
              class="logo-mask"
            >
              {{ !!dialog.edit.logo ? $t('点击更换') : $t('点击上传') }}
            </div>
            <i
              v-show="dialog.edit.close && !!dialog.edit.logo"
              class="bk-icon icon-close"
              @click.stop.prevent="handleDeleteLogo"
            />
            <input
              type="file"
              class="edit-logo"
              title=""
              accept="image/png"
              @change="handleUploadChange"
            />
          </div>
        </div>
      </div>
      <div slot="footer">
        <bk-button
          theme="primary"
          :disabled="dialog.edit.validate"
          @click="handleSubmitEdit"
        >
          {{ $t('确定') }}
        </bk-button>
        <bk-button @click="handleCancel">
          {{ $t('取消') }}
        </bk-button>
      </div>
    </bk-dialog>
  </div>
</template>
<script>
import { createNamespacedHelpers } from 'vuex';

import { uptimeCheckMixin } from '../../../../common/mixins';

const { mapGetters } = createNamespacedHelpers('uptime-check-task');
export default {
  name: 'GroupCards',
  mixins: [uptimeCheckMixin],
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    group: {
      type: Array,
      default() {
        return [];
      },
    },
    taskDetail: {
      type: Object,
      required: true,
    },
    itemWidth: Number,
  },
  data() {
    const defaultEdit = this.getDefaultEditDialog();
    return {
      expand: false,
      needExpand: false,
      wrapHeight: 240,
      hoverActive: -1,
      popoverOptions: {
        appendTo: this.handleAppendTo,
      },
      dialog: {
        edit: defaultEdit,
        delete: {
          id: '',
        },
      },
      drag: {
        active: -1,
      },
      popover: {
        hover: false,
        instance: null,
        active: -1,
      },
    };
  },
  computed: {
    ...mapGetters(['keyword', 'taskList']),
    bizList() {
      return this.$store.getters.bizList;
    },
    bizId() {
      return this.$store.getters.bizId;
    },
    hasGroupList() {
      return !!(this.group.filter(item => item.name.includes(this.keyword)) || []).length;
    },
  },
  watch: {
    expand(v) {
      this.wrapHeight = v && this.needExpand ? this.$refs.cardWrapList.getBoundingClientRect().height : 240;
    },
    itemWidth: {
      handler: 'handleWindowResize',
    },
    group: {
      handler: 'handleGroupChange',
      deep: true,
    },
  },
  mounted() {
    this.handleGroupChange();
    this.$bus.$on('handle-create-task-group', this.handleAddGroup);
  },
  destroyed() {
    this.$bus.$off('handle-create-task-group');
  },
  methods: {
    handleDeleteLogo() {
      const { edit } = this.dialog;
      edit.logo = '';
      edit.close = false;
    },
    handleUploadChange(eve) {
      const e = eve;
      const file = e.target.files[0];
      const fileReader = new FileReader();
      fileReader.onloadend = event => {
        this.dialog.edit.logo = event.target.result;
        e.target.value = '';
      };
      fileReader.readAsDataURL(file);
    },
    handleGroupChange() {
      setTimeout(() => {
        this.needExpand = this.$refs.cardWrapList.getBoundingClientRect().height > 240;
        this.expand = this.expand && this.needExpand;
        this.$nextTick().then(() => {
          this.handleWindowResize();
        });
      }, 16);
    },
    refreshItemWidth() {
      this.handleWindowResize();
    },
    handleWindowResize() {
      const len = this.group.length;
      const width = this.$refs['task-item-0']?.length
        ? this.$refs['task-item-0'][0].getBoundingClientRect().width
        : 400;
      if (len > 0) {
        let i = 0;
        while (i < len) {
          const ref = this.$refs[`task-item-${i}`][0];
          if (ref && ref.getBoundingClientRect().width !== width) {
            ref.style.maxWidth = `${width || 400}px`;
          }
          i += 1;
        }
      }
      const { height } = this.$refs.cardWrapList.getBoundingClientRect();
      if (this.expand) {
        this.wrapHeight = height || this.wrapHeight;
      }
      this.needExpand = (height || this.wrapHeight) > 240;
    },
    getDefaultEditDialog() {
      return {
        add: true,
        id: '',
        show: false,
        name: '',
        bizId: +this.$store.getters.bizId,
        select: [],
        validate: false,
        logo: '',
        close: false,
        message: '',
        active: -1,
      };
    },
    handleItemClick(item) {
      if (item.all_tasks?.length) {
        this.$emit('update:taskDetail', {
          show: true,
          tasks: item.all_tasks.map(task => task.task_id),
          name: item.name,
          id: item.id,
        });
      }
    },
    handleGroupMouseEnter(index) {
      this.hoverActive = index;
      this.dialog.edit.active = index;
    },
    handleGroupMouseLeave() {
      this.hoverActive = -1;
      this.popover.hover = false;
    },
    handlePopoverShow(item, index, e) {
      this.popover.instance = this.$bkPopover(e.target, {
        content: this.$refs.popoverContent,
        arrow: false,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light group-card',
        maxWidth: 520,
        duration: [275, 0],
        offset: '-6',
        appendTo: () => this.$refs[`popover-${index}`][0],
        onHidden: () => {
          this.popover.hover = false;
        },
      });
      // .instances[0]
      this.popover.active = index;
      this.popover.instance?.show(100);
    },
    handleGroupPopoverLeave() {
      this.popover.hover = this.popover.active >= 0;
      !this.popover.hover && this.handlePopoverHide();
    },
    handlePopoverHide() {
      this.popover.instance?.hide(100);
      this.popover.instance?.destroy();
      this.popover.instance = null;
    },
    handleExpand() {
      this.expand = !this.expand;
    },
    handleAppendTo() {
      return this.$refs[`popover-${this.hoverActive}`][0];
    },
    handleEditGroup() {
      const item = this.group[this.hoverActive > -1 ? this.hoverActive : this.dialog.edit.active];
      this.dialog.edit.name = item.name;
      this.dialog.edit.id = item.id;
      this.dialog.edit.bizId = item.bk_biz_id;
      this.dialog.edit.add = false;
      this.dialog.edit.show = true;
      this.dialog.edit.logo = item.logo;
      this.dialog.edit.close = false;
      this.dialog.edit.validate = false;
      this.dialog.edit.select = item.all_tasks.map(task => task.task_id);
      this.dialog.edit.oriName = item.name;
    },
    handleAddGroup() {
      this.dialog.edit = this.getDefaultEditDialog();
      this.dialog.edit.show = true;
    },
    handleDeleteGroup() {
      const item = this.group[this.hoverActive > -1 ? this.hoverActive : this.dialog.edit.active];
      this.dialog.delete.id = item.id;
      this.$bkInfo({
        title: this.$t('确定解散任务组'),
        subTitle: this.$t('该操作仅删除任务组，不会影响组内拨测任务'),
        confirmFn: () => this.handleSubmitDelete(),
      });
    },
    handleSubmitDelete() {
      this.$emit('group-delete', this.dialog.delete.id);
    },
    async handleSubmitEdit() {
      const { edit } = this.dialog;
      edit.name = `${edit.name}`.trim();
      const item = this.group[this.hoverActive > -1 ? this.hoverActive : this.dialog.edit.active];
      if (!edit.name.length) {
        edit.validate = true;
        return;
      }
      if (/["/[\]':;|=,+*?<>{}.\\]+/g.test(edit.name)) {
        edit.validate = true;
        edit.message = `${this.$t('不允许包含如下特殊字符：')} " / \\ [ ]' : ; | = , + * ? < > { } ${this.$t('空格')}`;
        return;
      }
      if (this.validateStrLength(edit.name, 20)) {
        edit.validate = true;
        edit.message = this.$t('注意：最大值为50个字符(10个汉字)');
        return;
      }
      if (
        (edit.add && this.group.find(item => item.name.toLowerCase() === edit.name.toLowerCase())) ||
        (!edit.add &&
          edit.name.toLowerCase() !== edit.oriName.toLowerCase() &&
          this.group.find(set => set.name.toLowerCase() === edit.name.toLowerCase()))
      ) {
        edit.validate = true;
        edit.message = this.$t('注意: 名字冲突');
        return;
      }
      let { logo } = this.dialog.edit;
      if (logo) {
        logo = await this.handleImg2Base64(logo);
      }
      if (
        edit.add ||
        !(
          edit.name === item.name &&
          edit.logo === item.logo &&
          edit.select.sort().join(',') ===
            item.all_tasks
              .map(i => i.task_id)
              .sort()
              .join(',')
        )
      ) {
        this.$emit('group-edit', {
          add: this.dialog.edit.add,
          id: this.dialog.edit.id,
          name: this.dialog.edit.name,
          logo,
          task_id_list: this.dialog.edit.select,
          bk_biz_id: this.bizId,
        });
      }
      this.dialog.edit.show = false;
    },
    handleCancel() {
      this.dialog.edit.show = false;
      this.dialog.edit.active = -1;
    },
    handleImg2Base64(logo) {
      return new Promise(resolve => {
        try {
          const img = new Image();
          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d');
          img.src = logo;
          img.onload = () => {
            const width = Math.min(88, img.width);
            const height = Math.min(88, img.height);
            canvas.width = width;
            canvas.height = height;
            context.clearRect(0, 0, width, height);
            context.drawImage(img, 0, 0, width, height);
            resolve(canvas.toDataURL());
          };
        } catch {
          resolve('');
        }
      });
    },
    handleDragOver(index, item, e) {
      const event = e;
      this.drag.active = index;
      event.dataTransfer.dropEffect = 'move';
      event.preventDefault();
    },
    handleDragLeave() {
      this.drag.active = -1;
    },
    handleDragEnter(index) {
      this.drag.active = index;
    },
    handleDragDrop(index, item, e) {
      e.preventDefault();
      const data = e.dataTransfer.getData('text');
      this.$emit('drag-drop', data, item);
      this.drag.active = -1;
    },
    /**
     * @desc 临时处理bk-dialog关闭后覆盖overflow的样式问题
     */
    fixStyle() {
      const t = setTimeout(() => {
        document.querySelector('body').style.overflowY = 'auto';
        clearTimeout(t);
      }, 300);
    },
    validateStrLength(str, length = 50) {
      const cnLength = (str.match(/[\u4e00-\u9fa5]/g) || []).length;
      const enLength = (str || '').length - cnLength;
      const res = cnLength * 2;
      return res + enLength > length;
    },
  },
};
</script>
<style lang="scss" scoped>
.group-task {
  margin-bottom: 30px;

  &-header {
    display: flex;
    align-items: center;
    margin-bottom: 14px;
    font-size: 14px;

    .header-name {
      flex: 1;
      font-weight: bold;
      color: #313238;
    }

    .header-expand {
      color: #3a84ff;
      cursor: pointer;
    }
  }

  &-wrap {
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.23, 1, 0.23, 1);

    &-list {
      display: flex;
      flex-wrap: wrap;
      margin-right: -20px;

      &-item {
        position: relative;
        flex: 1;
        min-width: 300px;
        max-width: 400px;
        height: 220px;
        padding: 24px;
        margin-right: 20px;
        margin-bottom: 20px;
        background: #fff;
        border: 1px solid #dcdee5;
        border-radius: 2px;

        &:hover {
          cursor: pointer;
          box-shadow: 0px 3px 6px 0px rgba(58, 132, 255, 0.1);
        }

        &.drag-active {
          border: 1px dashed #3a84ff;
        }

        .item-desc {
          display: flex;
          align-items: center;
          margin-bottom: 22px;

          .desc-icon {
            display: flex;
            flex: 0 0 44px;
            align-items: center;
            justify-content: center;
            height: 44px;
            margin-right: 10px;
            font-size: 16px;
            font-weight: bold;
            color: #fff;
            background-size: cover;
          }

          .desc-right {
            display: flex;
            flex-direction: column;
            justify-content: center;

            &-title {
              display: flex;
              align-items: center;
              margin-bottom: 8px;
              font-size: 14px;
              font-weight: bold;
              color: #313238;

              .alarm-label {
                display: inline-block;
                padding: 0 9px;
                margin-left: 10px;
                font-size: 12px;
                color: #fff;
                background: #ea3636;
                border-radius: 15px;
              }
            }

            &-label {
              display: flex;
              align-items: center;
              font-size: 12px;
              color: #979ba5;

              .right-label {
                padding: 1px 6px;
                margin-right: 6px;
                background: #f0f1f5;
                border-radius: 2px;
              }
            }

            &-icon {
              position: absolute;
              top: 14px;
              right: 14px;
              display: flex;
              align-items: center;
              justify-content: center;
              width: 32px;
              height: 32px;
              font-size: 18px;
              color: #63656e;
              cursor: pointer;
              transition: background-clor 0.2s ease-in-out;

              &.hover-active {
                color: #3a84ff;
                background-color: #f0f1f5;
                border-radius: 50%;
              }
            }
          }
        }

        .item-list {
          font-size: 12px;
          color: #63656e;

          &-progress {
            display: flex;
            flex-direction: column;
            margin-bottom: 16px;

            .progress-desc {
              display: flex;
              margin-bottom: 6px;

              .desc-name {
                flex: 1;
              }

              .desc-percent {
                color: #979ba5;
              }
            }

            .progress-item {
              :deep(.progress-bar) {
                box-shadow: none;
              }
            }
          }
        }

        .item-empty {
          overflow: hidden;
          font-size: 12px;
          color: #979ba5;
          text-align: center;

          :first-child {
            margin-top: 16px;
          }
        }
      }

      .item-add-new {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #63656e;
        cursor: pointer;
        background: #fafbfd;
        border: 1px dashed #c4c6cc;

        div {
          display: flex;
          align-items: center;
          font-size: 14px;
          cursor: pointer;
        }

        i {
          margin-right: 9px;
          font-size: 14px;
          font-weight: bold;
          color: #c4c6cc;
        }
      }
    }

    .empty-search-data {
      height: 60px;
      font-size: 18px;
      line-height: 60px;
      color: #979ba5;
      text-align: center;
      background: rgb(251, 252, 253);
      border: 1px solid #dcdee5;
    }
  }

  .popover-desc {
    display: flex;
    flex-direction: column;
    min-width: 75px;
    padding: 6px 0;
    font-size: 12px;
    color: #63656e;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    &-btn {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      height: 32px;
      padding-left: 10px;
      background: #fff;
      // &:first-child {
      //     border-bottom: 1px solid #DCDEE5;
      // }
      &:hover {
        color: #3a84ff;
        cursor: pointer;
        background: #f0f1f5;
      }
    }
  }

  .more-btn-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 24px;
    margin-top: -8px;
    font-size: 12;
    color: #0083ff;
    cursor: pointer;
    transition: all 0.2s ease-in-out;

    .icon-double-down {
      font-size: 16px;
      vertical-align: middle;
    }

    &:hover {
      background-color: #fff;
    }
  }
}

.bk-dialog-edit {
  :deep(.bk-dialog-footer) {
    padding: 9px 24px;
  }
}

.dialog-edit {
  display: flex;
  height: 134px;
  margin-top: -7px;

  &-content {
    display: flex;
    flex: 1;
    flex-direction: column;
    justify-content: space-between;
    margin-right: 24px;
  }

  &-label {
    margin-bottom: 8px;
  }

  &-select {
    width: 320px;
  }

  &-input {
    :deep(input) {
      border: 1px solid #ea3636;
    }
  }

  &-validate {
    font-size: 12px;
    color: #ea3636;
  }

  &-upload {
    width: 86px;
    text-align: center;
  }

  &-logo {
    position: relative;
    width: 86px;
    height: 86px;
    margin-top: 29px;
    margin-bottom: 10px;
    font-size: 12px;
    line-height: 86px;
    color: #979ba5;
    text-align: center;
    background: #fafbfd;
    background-size: cover;
    border: 1px dashed #dcdee5;
    border-radius: 2px;

    &:hover {
      border-color: #3a84ff;
    }

    .edit-logo {
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      left: 0;
      z-index: 1;
      width: 84px;
      cursor: pointer;
      opacity: 0;
    }

    .icon-close {
      position: absolute;
      top: 2px;
      right: 2px;
      z-index: 2;
      color: #fff;
      cursor: pointer;
    }

    .logo-mask {
      position: absolute;
      top: 0;
      left: 0;
      z-index: 0;
      width: 84px;
      height: 84px;
      font-size: 14px;
      color: #fff;
      background: #000;
      opacity: 0.5;
    }
  }

  &-option {
    width: 320px;
  }
}

.dialog-delete {
  font-size: 14px;
  line-height: 19px;
  color: #63656e;
}
</style>
