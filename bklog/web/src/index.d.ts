export {};

declare global {
  interface Window {
    mainComponent: any;
    timezone: string;
  }
}

declare module 'vue/types/vue' {
  interface Vue {
    $bkMessage?: (p: Partial<{}>) => void;
    $bkPopover?: (...Object) => void;
  }
}
