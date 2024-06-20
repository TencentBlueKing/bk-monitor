export {};

declare global {
  interface Window {
    mainComponent: any;
    timezone: string;
    MONITOR_URL: string;
    BK_SHARED_RES_URL: string;
    VERSION: string;
  }
}

declare module 'vue/types/vue' {
  interface Vue {
    $bkMessage?: (p: Partial<{}>) => void;
    $bkPopover?: (...Object) => void;
  }
}
