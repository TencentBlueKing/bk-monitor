import type { Button, Checkbox, CheckboxGroup, Radio, RadioButton, RadioGroup, Switch, Loading, Alert, Tag, Progress, Badge, Input } from 'tdesign-vue-next';
export {};
declare module 'vue' {
  interface GlobalComponents {
    TButton: typeof Button;
    TCheckbox: typeof Checkbox;
    TCheckboxGroup: typeof CheckboxGroup;
    TRadio: typeof Radio;
    TRadioButton: typeof RadioButton;
    TRadioGroup: typeof RadioGroup;
    TSwitch: typeof Switch;
    TLoading: typeof Loading;
    TAlert: typeof Alert;
    TTag: typeof Tag;
    TProgress: typeof Progress;
    TBadge: typeof Badge;
    TInput: typeof Input;
  }
}
