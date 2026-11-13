import i18n from '../src/platform/i18n/i18n';
// Set the legacy translation owner before evaluating collection utilities.
Reflect.set(window, 'mainComponent', { $t: i18n.t });
await import('./collection-create-ui-root');
