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
  <div class="manage-container">
    <div
      v-if="!pageLoading"
      class="manage-main"
    >
      <sub-nav></sub-nav>
      <router-view
        class="manage-content"
        :key="routerKey"
      ></router-view>
    </div>
  </div>
</template>

<script>
import SubNav from '@/components/nav/manage-nav';
import { mapState, mapGetters } from 'vuex';

export default {
  name: 'ManageIndex',
  components: {
    SubNav,
  },
  data() {
    return {
      navThemeColor: '#2c354d',
      routerKey: 0,
      isExpand: true,
    };
  },

  computed: {
    ...mapState(['topMenu', 'activeManageNav']),
    ...mapState('globals', ['globalsData']),
    ...mapGetters({
      pageLoading: 'pageLoading',
    }),
    manageNavList() {
      return this.topMenu.find(item => item.id === 'manage')?.children || [];
    },
  },
  methods: {
    getMenuIcon(item) {
      if (item.icon) {
        return `bklog-icon bklog-${item.icon}`;
      }

      return 'bk-icon icon-home-shape';
    },
    handleClickNavItem(id) {
      this.$router.push({
        name: id,
        query: {
          spaceUid: this.$store.state.spaceUid,
        },
      });
      if (this.activeManageNav.id === id) {
        // this.routerKey += 1;
      }
    },
    handleToggle(data) {
      this.isExpand = data;
    },
  },
  mounted() {
    const bkBizId = this.$store.state.bkBizId;
    const spaceUid = this.$store.state.spaceUid;

    this.$router.replace({
      query: {
        bizId: bkBizId,
        spaceUid: spaceUid,
        ...this.$route.query,
      },
    });
  },
};
</script>

<style lang="scss" scoped>
  @import '../../scss/mixins/scroller.scss';

  .manage-container {
    height: 100%;

    .manage-content {
      // height: 100%;
      position: relative;
      top: 48px;
      height: calc(100% - 52px);
      overflow: auto;

      @include scroller($backgroundColor: #c4c6cc, $width: 4px);
    }

    .manage-main {
      height: 100%;
    }

    :deep(.bk-table) {
      background: #fff;

      .cell {
        display: block;
      }

      .bk-table-pagination-wrapper {
        background: #fafbfd;
      }
    }
  }
</style>
