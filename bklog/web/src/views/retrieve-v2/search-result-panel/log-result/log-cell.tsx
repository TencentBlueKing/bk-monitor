import { computed, defineComponent, onMounted, ref, nextTick } from 'vue';
import interactjs from 'interactjs';

export default defineComponent({
  props: {
    width: {
      type: [String, Number],
      default: 120,
    },
    minWidth: {
      type: [String, Number],
      default: 'atuo',
    },
    resize: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { slots, emit }) {
    const cellStyle = computed(() => {
      if (props.width === 'default') {
        return {
          width: '100%',
        };
      }
      return {
        width: `${props.width}px`,
        minWidth: typeof props.minWidth === 'number' ? `${props.minWidth}px` : `${props.width}px`,
      };
    });

    const refRoot = ref();

    const renderVNode = () => {
      return (
        <div
          style={cellStyle.value}
          ref={refRoot}
        >
          {slots.default?.()}
        </div>
      );
    };

    onMounted(() => {
      if (props.resize) {
        nextTick(() => {
          const container = refRoot.value?.closest('.bklog-result-container') as HTMLElement;
          const guideLineElement = container.querySelector('.resize-guide-line') as HTMLElement;

          const setGuidLeft = event => {
            const client = event.client;
            const containerRect = container.getBoundingClientRect();

            guideLineElement.style.left = `${client.x - containerRect.x}px`;
          };

          interactjs(refRoot.value).resizable({
            edges: { top: false, left: false, bottom: false, right: true },
            listeners: {
              start(event) {
                // Show the guide line when resizing starts
                guideLineElement.style.display = 'block';
                document.body.classList.add('no-user-select');
                setGuidLeft(event);
              },
              move(event) {
                let { x, y } = event.target.dataset;

                x = (parseFloat(x) || 0) + event.deltaRect.left;
                y = (parseFloat(y) || 0) + event.deltaRect.top;

                Object.assign(event.target.style, {
                  width: `${event.rect.width}px`,
                  height: `${event.rect.height}px`,
                  transform: `translate(${x}px, ${y}px)`,
                });

                Object.assign(event.target.dataset, { x, y });
                if (event.rect.width > 30) {
                  setGuidLeft(event);
                }
              },
              end(event) {
                // Hide the guide line when resizing ends
                guideLineElement.style.display = 'none';
                document.body.classList.remove('no-user-select');
                emit('resize-width', event.rect.width);
              },
            },
          });
        });
      }
    });

    return { renderVNode };
  },
  render() {
    return this.renderVNode();
  },
});
