<script setup>
import { computed } from 'vue';

import useLocale from '@/hooks/use-locale';

const props = defineProps({
  aiQueryResult: {
    type: Object,
    default: () => ({}),
  },
  showBorder: {
    type: Boolean,
    default: false,
  },
});

const { $t } = useLocale();

const isSuccess = computed(() => props.aiQueryResult?.parseResult === 'SUCCESS');
const isFailed = computed(() => props.aiQueryResult?.parseResult && props.aiQueryResult?.parseResult !== 'SUCCESS');

/**
 * 关闭解析结果提示
 */
const handleClose = () => {
  if (props.aiQueryResult) {
    props.aiQueryResult.parseResult = undefined;
    props.aiQueryResult.explain = undefined;
  }
};
</script>

<template>
  <div
    v-if="aiQueryResult?.parseResult"
    :class="['ai-parse-result-banner', {
      'is-success': isSuccess,
      'is-failed': isFailed,
      'show-border': showBorder,
    }]"
  >
    <div class="ai-parse-result-content">
      <span
        v-if="isSuccess"
        class="ai-parse-text"
      >
        <i class="bklog-icon bklog-circle-correct-filled ai-parse-icon" />
        <span class="ai-parse-success-label">{{ $t('解析成功') }}:</span>
        <span class="ai-parse-success-text">{{ $t('AI 小鲸解析生成语句') }}: {{ aiQueryResult.queryString }}</span>
      </span>
      <span
        v-else
        class="ai-parse-text"
      >
        <i class="bklog-icon bklog-circle-alert-filled ai-parse-icon" />
        <span class="ai-parse-failed-label">{{ $t('解析失败') }}:</span>
        <span class="ai-parse-failed-reason">{{ aiQueryResult.explain }}</span>
      </span>
    </div>
    <i
      class="bklog-icon bklog-close ai-parse-close"
      @click="handleClose"
    />
  </div>
</template>

<style lang="scss" scoped>
.ai-parse-result-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  padding: 0 16px;
  font-size: 12px;
  line-height: 32px;

  &.is-success {
    background: #ebfaf0;
  }

  &.is-failed {
    background: #fff0f0;
  }

  &.show-border {
    border-style: solid;
    border-width: 1px;

    &.is-success {
      border-color: #A1E3BA;
    }

    &.is-failed {
      border-color: #F8B4B4;
    }
  }

  .ai-parse-result-content {
    display: flex;
    align-items: center;
    flex: 1;
    overflow: hidden;

    .ai-parse-text {
      display: flex;
      align-items: center;
      flex: 1;
      overflow: hidden;
      min-width: 0;

      .ai-parse-icon {
        margin-right: 8px;
        font-size: 16px;
        flex-shrink: 0;
      }
    }
  }

  &.is-success {
    .ai-parse-text {
      .ai-parse-icon {
        color: #299e56;
      }

      .ai-parse-success-label {
        color: #299e56;
        margin-right: 4px;
      }

      .ai-parse-success-text {
        color: #299e56;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }

  &.is-failed {
    .ai-parse-text {
      .ai-parse-icon {
        color: #e71818;
      }

      .ai-parse-failed-label {
        color: #e71818;
        margin-right: 4px;
      }

      .ai-parse-failed-reason {
        color: #313238;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }

  .ai-parse-close {
    margin-left: 16px;
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;
    flex-shrink: 0;

    &:hover {
      color: #63656e;
    }
  }
}
</style>
