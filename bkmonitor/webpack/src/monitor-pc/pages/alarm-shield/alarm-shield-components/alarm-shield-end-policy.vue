<template>
  <div class="shield-end-policy">
    <div class="policy-label">{{ $t('屏蔽期间产生的告警') }}</div>
    <div>
      <template v-if="readonly">
        {{ $t(value === 'close' ? '屏蔽结束时关闭告警，不再通知' : '屏蔽结束后发送一次通知') }}
      </template>
      <bk-radio-group
        v-else
        :value="value"
        @change="$emit('input', $event)"
      >
        <bk-radio value="notify_once">{{ $t('屏蔽结束后发送一次通知') }}</bk-radio>
        <bk-radio value="close">{{ $t('屏蔽结束时关闭告警，不再通知') }}</bk-radio>
      </bk-radio-group>
      <p>
        {{
          $t(
            value === 'close'
              ? '屏蔽期间产生的告警不通知、不执行处理套餐；屏蔽结束时关闭，不补发通知、不补执行处理。屏蔽开始前的告警不受影响。'
              : '屏蔽结束时，仍未恢复的告警将各发送一次通知，可能集中产生多条通知。'
          )
        }}
      </p>
      <p>{{ $t('结束处理方式创建后不可修改。如需使用另一种方式，请新建屏蔽规则。') }}</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AlarmShieldEndPolicy',
  props: {
    value: { type: String, default: 'notify_once' },
    readonly: { type: Boolean, default: false },
  },
};
</script>

<style lang="scss" scoped>
.shield-end-policy {
  display: flex;
  margin-bottom: 20px;
  line-height: 32px;

  .policy-label {
    flex: 0 0 120px;
    padding-right: 24px;
    text-align: right;
  }

  p {
    margin: 4px 0;
    line-height: 20px;
    color: #979ba5;
  }
}
</style>
