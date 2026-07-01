import { defineComponent, type PropType } from 'vue';

export default defineComponent({
  name: 'RelatedLogLoading',
  props: {
    title: {
      type: String,
      required: true,
    },
    text: {
      type: String,
      required: true,
    },
    steps: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  setup(props) {
    return () => (
      <div
        class='standalone-related-log-loading-panel'
        role='status'
        aria-live='polite'
      >
        <div class='standalone-related-log-loading-card'>
          <div class='standalone-related-log-loading-spinner' />
          <div class='standalone-related-log-loading-title'>{props.title}</div>
          <div class='standalone-related-log-loading-text'>
            <transition name='standalone-related-log-loading-text-fade' mode='out-in'>
              <span key={props.text}>{props.text}</span>
            </transition>
          </div>
          {props.steps.length > 0 ? (
            <div class='standalone-related-log-loading-steps'>
              {props.steps.map((step, index) => (
                <div
                  key={step}
                  class='standalone-related-log-loading-step'
                >
                  <span class='standalone-related-log-loading-step-index'>{index + 1}</span>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    );
  },
});
