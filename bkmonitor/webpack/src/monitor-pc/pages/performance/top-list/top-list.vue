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
  <transition name="top-list">
    <ul
      v-if="list && list.length"
      v-show="show"
      class="top-list"
    >
      <li
        v-for="(item, index) in list"
        :key="index"
        class="top-list-item"
      >
        <span class="top-list-item-order">{{ index + 1 }}</span>
        <span class="top-list-item-name">{{ item.name }}</span>
        <span class="top-list-item-status">{{ item.percent }}</span>
      </li>
    </ul>
  </transition>
</template>

<script>
export default {
  name: 'TopList',
  props: {
    show: Boolean,
  },
  data() {
    return {
      list: [
        {
          name: 'hell1',
          percent: '12%',
        },
        {
          name: 'hell2',
          percent: '12%',
        },
        {
          name: 'hell3',
          percent: '12%',
        },
        {
          name: 'hell4',
          percent: '12%',
        },
        {
          name: 'hell5',
          percent: '12%',
        },
        {
          name: 'hell6',
          percent: '12%',
        },
        {
          name: 'hell7',
          percent: '12%',
        },
        {
          name: 'hell8',
          percent: '12%',
        },
        {
          name: 'hell9',
          percent: '12%',
        },
        {
          name: 'hell10',
          percent: '12%',
        },
      ],
    };
  },
};
</script>

<style scoped lang="scss">
.top-list {
  padding: 6px 16px 4px;
  background: #fff;
  margin: 0;
  display: flex;
  flex-direction: column;
  width: 240px;
  border: 1px solid #dcdee5;
  border-top: 0;
  border-bottom: 0;
  &-item {
    flex: 1 1 24px;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    font-size: 12px;
    &-order {
      color: #979ba5;
      flex: 0 0 20px;
      text-align: left;
    }
    &-name {
      color: #63656e;
      flex: 1 1 auto;
    }
    &-status {
      color: #2dcb56;
      flex: 0 0 30px;
      text-align: right;
    }
  }
  .top-list-enter-active {
    transition: all 0.33s cubic-bezier(0.23, 1, 0.32, 1);
  }
  .top-list-enter {
    transform: translate(240px, 0);
  }
  .top-list-leave-active {
    transition: all 0.33s cubic-bezier(0.23, 1, 0.32, 1);
  }
  .top-list-leave-to {
    transform: translate(250px, 0);
  }
}
</style>
