# -*- coding: utf-8 -*-
# !/usr/bin/python
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

import git
import yaml


def check_command_exists(command):
    try:
        subprocess.check_output(["which", command])
        return True
    except subprocess.CalledProcessError:
        return False


def execute_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    while True:
        output = process.stdout.readline().decode().strip()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output, flush=True)

    return process.poll()


def main():
    repo = git.Repo()
    print(f"project path: {repo.working_dir}")

    if not check_command_exists("preci"):
        print("skip pre-push check because preci not found")
        return 0

    # 项目路径hash(sha1)
    project_hash = hashlib.sha1(repo.working_dir.encode("utf-8")).hexdigest()
    if not project_hash:
        print("Please init PreCI first")
        return 1

    # 获取推送目标分支
    remote_branch = os.getenv("PRE_COMMIT_REMOTE_BRANCH")
    if remote_branch.startswith("refs/heads/"):
        remote_branch = remote_branch[len("refs/heads/") :]

    print(f"push branch: {remote_branch}")

    # 获取远程仓库
    remote_name = os.getenv("PRE_COMMIT_REMOTE_NAME", None)
    if not remote_name:
        print("remote name is empty")
        return 1
    remote = repo.remote(remote_name)
    remote.fetch()

    # 获取远程分支
    remote_ref = None
    for ref in remote.refs:
        # 获取远程分支
        if f"refs/remotes/{remote_name}/{remote_branch}" != ref.path:
            continue
        remote_ref = ref
        break

    if not remote_ref:
        print(f"remote branch: {remote_name}/{remote_branch} not found, use master instead")
        remote_ref = repo.branches.master
    else:
        print(f"remote branch: {remote_name}/{remote_branch}")

    # 获取差异的commit
    local_commits = set(repo.iter_commits())
    remote_commits = set(remote_ref.commit.iter_parents())
    diff_commits = local_commits - remote_commits

    # 获取差异包含的所有文件
    changed_files = set()
    for commit in diff_commits:
        diff = commit.diff(None)
        for item in diff:
            changed_files.add(item.b_path)

    if not changed_files:
        return 0
    print(f"changed files: {len(changed_files)}")

    # 创建临时文件夹
    with tempfile.TemporaryDirectory() as temp_dir:
        # 将差异文件复制到临时文件夹
        for file in changed_files:
            file_path = os.path.join(temp_dir, file)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            try:
                shutil.copyfile(file, file_path)
            except FileNotFoundError:
                pass

        # 创建临时PreCI项目
        temp_hash = hashlib.sha1(temp_dir.encode("utf-8")).hexdigest()
        temp_preci_path = f"{os.path.expanduser('~')}/PreCI/projects/{temp_hash}"
        os.makedirs(temp_preci_path, exist_ok=True)

        # 复制init.yaml并修改projectPath
        with open(f"{os.path.expanduser('~')}/PreCI/projects/{project_hash}/init.yaml") as f:
            preci_config = yaml.load(f.read(), Loader=yaml.FullLoader)
        preci_config["projectPath"] = temp_dir
        with open(f"{temp_preci_path}/init.yaml", "w") as f:
            f.write(yaml.dump(preci_config))

        # 复制build.yml
        shutil.copyfile(f"{repo.working_dir}/build.yml", f"{temp_dir}/build.yml")

        sys.stdout.flush()

        # 执行PreCI
        child = subprocess.Popen(
            f"preci run --projectPath {temp_dir}", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True
        )
        while True:
            output = child.stdout.readline().decode().strip()
            if output == '' and child.poll() is not None:
                break
            if output:
                print(output, flush=True)
            else:
                time.sleep(0.1)

        result = child.returncode

        # 清理临时PreCI项目
        shutil.rmtree(temp_preci_path)

        if result != 0:
            print("PreCI failed")
            return 1

    return 0


def lock(func):
    repo = git.Repo()
    lockfile = os.path.join(repo.working_dir, ".git", "pre-push.lock")
    try:
        fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, repo.head.commit.hexsha.encode())
    except OSError:
        fd = os.open(lockfile, os.O_RDONLY)
        commit = os.read(fd, 40).decode().strip()

        if not commit or commit == repo.head.commit.hexsha:
            sys.exit(0)
        else:
            print(f"pre-push is running with commit({commit}), please wait or remove {lockfile}")
            sys.exit(1)

    try:
        sys.exit(func())
    finally:
        os.close(fd)
        os.unlink(lockfile)


if __name__ == "__main__":
    lock(func=main)
