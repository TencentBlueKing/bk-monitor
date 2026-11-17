/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import './form-skeleton.scss';

type Control = 'input' | 'textarea' | 'choice' | 'switch' | 'sample' | 'hint';

function formCard(controls: Control[]) {
  return (
    <div class='info-card'>
      <div class='collection-form-skeleton__title' />
      {controls.map(control => (
        <div class='collection-form-skeleton__row'>
          <span class='collection-form-skeleton__label' />
          <span class={['collection-form-skeleton__control', control]} />
        </div>
      ))}
    </div>
  );
}

function formSkeleton(cleaning: boolean) {
  return (
    <div class={['collection-form-skeleton', { 'is-cleaning': cleaning }]} aria-hidden='true'>
      <div class='classify-main-box'>
        {cleaning ? formCard(['hint', 'sample', 'switch']) : formCard(['input', 'input', 'input', 'textarea'])}
        {cleaning ? formCard(['choice', 'input', 'choice', 'switch']) : formCard(['choice', 'choice', 'input', 'input'])}
      </div>
      <div class='collection-form-skeleton__footer'><span /><span /></div>
    </div>
  );
}

export const renderCollectionFormSkeleton = () => formSkeleton(false);
export const renderCleaningFormSkeleton = () => formSkeleton(true);
