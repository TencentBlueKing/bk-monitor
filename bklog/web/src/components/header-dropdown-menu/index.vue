<template>
  <bk-dropdown-menu
    align="center"
    @hide="dropdownHide"
    @show="dropdownShow"
  >
    <template #dropdown-trigger>
      <div
        v-if="navIcon"
        class="icon-language-container"
        :class="isShowDropdown && 'active'"
      >
        <div class="icon-circle-container">
          <span
            class="icon bklog-icon"
            :class="navIcon"
            slot="dropdown-trigger"
          ></span>
        </div>
      </div>
      <slot name="dropdown-trigger"></slot>
    </template>
    <template #dropdown-content>
      <ul class="bk-dropdown-list">
        <li
          v-for="(item, index) in dropdownList"
          :key="index"
        >
          <!-- isShow为false时才不显示，没有传isShow或者isShow为true时则显示 -->
          <a
            v-if="!(item.isShow === false)"
            href="javascript:;"
            @click="handleClick(item)"
          >
            <span
              v-if="item.icon"
              :class="['dropdown-item-icon', 'bk-icon', item.icon]"
            />
            {{ $t(item.name) }}
          </a>
        </li>
      </ul>
    </template>
  </bk-dropdown-menu>
</template>

<script>
  import { emit } from 'vue-tsx-support';
  export default {
    name: 'HeaderDropDownMenu',
    props: {
      navIcon: {
        type: String,
        default: '',
      },
      dropdownList: {
        default: () => [],
        type: Array,
        required: true,
      },
    },
    data() {
      return {
        isShowDropdown: true,
      };
    },
    methods: {
      dropdownHide() {
        this.isShowDropdown = false;
        this.$emit('handleDropdown', this.isShowDropdown);
      },
      dropdownShow() {
        this.isShowDropdown = true;
        this.$emit('handleDropdown', this.isShowDropdown);
      },
      handleClick(item) {
        if (item.clickHandler) {
          item.clickHandler();
        }
        this.$emit('handleMenuItemClick', item);
      },
    },
  };
</script>

<style lang="scss">
  @import '../../scss/mixins/flex';

  .icon-language-container {
    height: 50px;
    margin: 4px;
    cursor: pointer;

    @include flex-center;

    .icon-circle-container {
      width: 32px;
      height: 32px;
      border-radius: 16px;
      transition: all 0.2s;

      @include flex-center;

      .bklog-icon {
        font-size: 16px;
        transition: all 0.2s;
      }
    }

    &:hover,
    &.active {
      .icon-circle-container {
        background: linear-gradient(270deg, #253047, #263247);
        transition: all 0.2s;

        .bklog-icon {
          color: #d3d9e4;
          transition: all 0.2s;
        }
      }
    }
  }

  .dropdown-item-icon {
    font-size: 20px;
  }
</style>
