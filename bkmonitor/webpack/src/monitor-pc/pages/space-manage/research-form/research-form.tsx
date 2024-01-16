/*
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
 */
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { createSpace, listDevopsSpaces } from '../../../../monitor-api/modules/commons';

import OrganizationSelector from './organization-selector';

import './research-form.scss';

enum ResearchStatus {
  edit /** 编辑 */,
  add /** 新建 */
}
interface IFormValue {
  project?: string; // 蓝盾项目
  spaceName: string; //  空间名
  spaceId: string; // 英文名
  desc: string; // 说明
  organizationStr?: string; // 组织
  organization?: string[]; // 组织
  project_type?: number | string;
  bg_id?: number | string;
  dept_id?: number | string;
  center_id?: number | string;
}

interface ISpaceItem {
  space_id: string;
  space_name: string;
  space_type_id: string;
}

const normalRule = {
  required: true,
  message: window.i18n.tc('必填项'),
  trigger: 'blur'
};
const englishNameRule = {
  validator(val) {
    // eslint-disable-next-line no-useless-escape
    return /^[a-z][a-z0-9\-]{1,31}$/.test(val);
  },
  message: window.i18n.t('英文缩写必须由小写字母+数字+中划线组成，以小写字母开头，长度限制32字符！'),
  trigger: 'blur'
};
const spaceNameRule = {
  validator(val) {
    return val.length >= 2 && val.length <= 32;
  },
  message: window.i18n.t('长度限制2-32字符'),
  trigger: 'blur'
};
/* 重复校验 */
const deduplicationRule = (list: string[], type: 'spaceId' | 'spaceName') => {
  if (type === 'spaceName') {
    return {
      validator(val) {
        return !list.includes(val);
      },
      message: `${window.i18n.t('注意: 名字冲突')}。`,
      trigger: 'blur'
    };
  }
  if (type === 'spaceId') {
    return {
      validator(val) {
        return !list.includes(val.toLocaleLowerCase());
      },
      message: `${window.i18n.t('注意: 名字冲突')}。`,
      trigger: 'blur'
    };
  }
  return undefined;
};

const projectTypeList = [
  { id: 0, name: window.i18n.tc('手游') },
  { id: 1, name: window.i18n.tc('端游') },
  { id: 2, name: window.i18n.tc('页游') },
  { id: 3, name: window.i18n.tc('平台产品') },
  { id: 4, name: window.i18n.tc('支撑产品') }
];

interface IProps {
  spaceList?: ISpaceItem[];
  onSuccess?: () => void;
  onCancel?: () => void;
}

/**
 * 研发项目表单
 */
@Component
export default class ResearchForm extends tsc<IProps> {
  @Ref('addForm') addFormRef: any;
  /* 用于重复检验 */
  @Prop({ default: () => [], type: Array }) spaceList: ISpaceItem[];

  /** 研发项目的编辑状态 */
  researchStatus: ResearchStatus = ResearchStatus.edit;

  /** 项目列表 */
  projectList = [];

  /** 编辑表单数据 */
  editValue: IFormValue = {
    project: '',
    spaceName: '',
    spaceId: '',
    organizationStr: '',
    bg_id: '',
    dept_id: '',
    center_id: '',
    desc: '',
    project_type: ''
  };
  /** 新建表单数据 */
  addValue: IFormValue = {
    spaceName: '',
    spaceId: '',
    desc: '',
    organization: [],
    project_type: ''
  };
  addValueRules = {
    spaceName: [normalRule, spaceNameRule],
    spaceId: [normalRule, englishNameRule],
    project_type: [normalRule],
    desc: [normalRule]
  };

  /* 用于重复校验 */
  spaceNameList: string[] = [];
  spaceIdList: string[] = [];

  loading = false;

  created() {
    this.spaceNameList = this.spaceList.map(item => item.space_name || '');
    this.spaceIdList = this.spaceList.map(item => (item.space_id || '').toLocaleLowerCase());
    this.addValueRules.spaceName.push(deduplicationRule(this.spaceNameList, 'spaceName') as any);
    this.addValueRules.spaceId.push(deduplicationRule(this.spaceIdList, 'spaceId') as any);
    this.getProjectList();
  }

  /* 获取项目列表 */
  async getProjectList() {
    const data = await listDevopsSpaces().catch(() => []);
    this.projectList = data;
  }

  handleOrganization(value: string[]) {
    this.addValue.organization = value;
  }

  /* 保存 */
  async handleSave() {
    const isValidata = await this.validate();
    if (!isValidata) return;
    this.loading = true;
    let params = null;
    if (this.researchStatus === ResearchStatus.edit) {
      params = {
        space_name: this.editValue.spaceName, // 空间名
        space_id: this.editValue.spaceId, // 英文名
        project_type: this.editValue.project_type, // 蓝盾项目类型id
        description: this.editValue.desc,
        bg_id: this.editValue.bg_id, // bg id
        dept_id: this.editValue.dept_id, // 部门 id
        center_id: this.editValue.center_id, // 中心id
        space_type_id: 'bkci', // 空间类型，填bkci
        is_exist: true // 是否为已有项目
      };
    } else {
      params = {
        space_name: this.addValue.spaceName, // 空间名
        space_id: this.addValue.spaceId, // 英文名
        project_type: this.addValue.project_type, // 蓝盾项目类型id
        description: this.addValue.desc,
        bg_id: this.addValue.organization[0], // bg id
        dept_id: this.addValue.organization[1], // 部门 id
        center_id: this.addValue.organization[2], // 中心id
        space_type_id: 'bkci', // 空间类型，填bkci
        is_exist: false // 是否为已有项目
      };
    }
    createSpace(params)
      .then(() => {
        this.$emit('success');
        this.$bkMessage({
          theme: 'success',
          message: this.$t('保存成功')
        });
        this.loading = false;
      })
      .catch(() => {
        this.loading = false;
      });
  }
  handleCancel() {
    this.$emit('cancel');
  }

  /* 校验 */
  validate() {
    return new Promise(resolve => {
      if (this.researchStatus === ResearchStatus.edit) {
        resolve(!!this.editValue.project);
      } else {
        this.addFormRef.validate().then(
          () => {
            resolve(true);
          },
          () => {
            resolve(false);
          }
        );
      }
    });
  }

  handleSelectProject() {
    const data = this.projectList.find(item => item.englishName === this.editValue.project);
    if (data) {
      this.editValue = {
        ...this.editValue,
        spaceName: data.projectName,
        spaceId: data.englishName,
        organizationStr: `${data.bgName}/${data.deptName}/${data.centerName}`,
        bg_id: data.bg_id,
        dept_id: data.dept_id,
        center_id: data.center_id,
        desc: data.description,
        project_type: data.project_type
      };
    }
  }

  render() {
    return (
      <div
        class='research-form'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='research-header'>
          <bk-radio-group v-model={this.researchStatus}>
            <bk-radio value={ResearchStatus.edit}>{this.$tc('已有项目')}</bk-radio>
            <bk-radio value={ResearchStatus.add}>{this.$tc('新建项目')}</bk-radio>
          </bk-radio-group>
          <span class='research-tips'>
            <i class='icon-monitor icon-hint'></i>
            {this.$tc('新建项目将会同步创建蓝盾项目')}
          </span>
          {/* <a class="research-link" href={'/'}>
            <i class="icon-monitor icon-mc-detail"></i>
            { this.$t('文档说明') }
          </a> */}
        </div>
        <div class='research-form-mian'>
          {this.researchStatus === ResearchStatus.edit ? (
            <div class='research-form-edit'>
              <bk-select
                v-model={this.editValue.project}
                clearable={false}
                searchable
                onSelected={this.handleSelectProject}
              >
                {this.projectList.map(opt => (
                  <bk-option
                    id={opt.englishName}
                    name={opt.projectName}
                  ></bk-option>
                ))}
              </bk-select>
              {this.editValue.project && (
                <div class='form-edit-desc'>
                  <div class='edit-desc-row'>
                    <div class='label'>{this.$tc('空间名')}&nbsp;:&nbsp;</div>
                    <div class='label'>{this.editValue.spaceName}</div>
                  </div>
                  <div class='edit-desc-row'>
                    <div class='label'>{this.$tc('英文名')}&nbsp;:&nbsp;</div>
                    <div class='label'>{this.editValue.spaceId}</div>
                  </div>
                  <div class='edit-desc-row'>
                    <div class='label'>{this.$tc('所属组织')}&nbsp;:&nbsp;</div>
                    <div class='label'>{this.editValue.organizationStr}</div>
                  </div>
                </div>
              )}
              <div class='desc-label label'>{this.$tc('说明')}</div>
              <bk-input
                class='textarea'
                v-model={this.editValue.desc}
                placeholder={this.$tc('输入')}
                type='textarea'
                rows={3}
                maxlength={100}
              ></bk-input>
            </div>
          ) : (
            <div class='research-form-add'>
              <bk-form
                form-type='vertical'
                ref='addForm'
                {...{
                  props: {
                    model: this.addValue,
                    rules: this.addValueRules
                  }
                }}
              >
                <bk-form-item
                  label={this.$tc('空间名')}
                  required={true}
                  property={'spaceName'}
                  error-display-type={'normal'}
                >
                  <bk-input v-model_trim={this.addValue.spaceName}></bk-input>
                </bk-form-item>
                <bk-form-item
                  label={this.$tc('英文名')}
                  required={true}
                  property={'spaceId'}
                  error-display-type={'normal'}
                >
                  <bk-input v-model={this.addValue.spaceId}></bk-input>
                </bk-form-item>
                <bk-form-item
                  label={this.$tc('说明')}
                  required={true}
                  property={'desc'}
                  error-display-type={'normal'}
                >
                  <bk-input
                    v-model={this.addValue.desc}
                    class='textarea'
                    type='textarea'
                    rows={3}
                    maxlength={100}
                  ></bk-input>
                </bk-form-item>
                <bk-form-item
                  label={this.$tc('所属组织')}
                  required={true}
                >
                  <OrganizationSelector onChange={this.handleOrganization}></OrganizationSelector>
                </bk-form-item>
                <bk-form-item
                  label={this.$tc('项目类型')}
                  required={true}
                  property={'project_type'}
                  error-display-type={'normal'}
                >
                  <div class='project-type'>
                    <bk-select
                      v-model={this.addValue.project_type}
                      clearable={false}
                    >
                      {projectTypeList.map(item => (
                        <bk-option
                          id={item.id}
                          name={item.name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  </div>
                </bk-form-item>
              </bk-form>
            </div>
          )}
          <div class='btn-groups'>
            <bk-button
              theme='primary'
              onClick={this.handleSave}
            >
              {this.$tc('保存')}
            </bk-button>
            <bk-button onClick={this.handleCancel}>{this.$tc('取消')}</bk-button>
          </div>
        </div>
      </div>
    );
  }
}
