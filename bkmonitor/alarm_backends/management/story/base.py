# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.management.story.color import ConsoleColor


class StoryCollection(object):

    stories = []

    def register(self, story):
        self.stories.append(reset_story(story))

    def run(self):
        self.mark()
        self.pre_run()
        self.stories = list(filter(lambda s: len(s.steps) > 0, self.stories))
        for i, story in enumerate(self.stories):
            story = reset_story(story)
            story.log_header(f"{i+1}/{len(self.stories)}:  {story}".ljust(80, "*"))  # noqa
            story.check()

    @property
    def problems(self):
        problems = []
        for s in self.stories:
            problems.extend(s.problems)
        return problems

    def resolve(self):
        problems = self.problems
        if problems:
            print(f"{ConsoleColor.HEADER}" + "Problems List".center(80, "*") + f"{ConsoleColor.ENDC}")
        for i, p in enumerate(problems):
            print(f"{ConsoleColor.HEADER}{i+1}/{len(problems)}:  {p}{ConsoleColor.ENDC}")
            p.resolve()

    def pre_run(self):
        print("Valid check item: {}".format(len(self.stories)))

    @classmethod
    def mark(cls):
        print("*" * 80)


sc = StoryCollection()


def reset_story(story):
    story.problems = []
    return story


def register_story(*args, **kwargs):
    def register(cls):
        story = cls(*args, **kwargs)
        story.steps = []
        sc.register(story)
        return cls

    return register


def register_step(story_cls):
    story = None
    for s in sc.stories:
        if s.__class__ == story_cls:
            story = s
            break
    else:
        raise OSError("can't find story: {}".format(story_cls))

    def register(cls):
        step = cls(story)
        controller = getattr(step, "controller", StepController())
        if controller.can_be_loaded():
            story.steps.append(step)
        return cls

    return register


class StepController(object):
    def can_be_loaded(self):
        return self._check()

    def _check(self):
        return True


class Problem(object):
    def __init__(self, p_name, story, **context):
        self.name = p_name
        self.story = story
        self.context = context

    def position(self):
        raise NotImplementedError("position NotImplementedError")

    def resolve(self):
        self.story.info(f"try resolve [{self}]")
        try:
            ret = self.position()
            if ret:
                self.story.info("done!")
        except Exception as e:
            self.story.error(f"resolve failed, detail: {e}")

    def __str__(self):
        return self.name


class BaseStory(object):
    name = ""
    problems = []
    steps = []

    def check(self):
        for i, step in enumerate(self.steps):
            print("  [step]{}. {}...".format(i + 1, step))
            try:
                p = step.check()
            except Exception as err:
                p = StepCheckError("请关注！自监控执行健康检查异常: {}".format(err), self)
            if p:
                if isinstance(p, list):
                    self.problems.extend(p)
                    for _p in p:
                        self.error(f"Problems found: {_p}")
                else:
                    self.problems.append(p)
                    self.error(f"Problems found: {p}")
            else:
                self.info("done!")

    def warning(self, msg):
        print(f"\t{ConsoleColor.WARNING}* {msg}{ConsoleColor.ENDC}")

    def info(self, msg):
        print(f"\t{ConsoleColor.OKGREEN}* {msg}{ConsoleColor.ENDC}")

    def error(self, msg):
        print(f"\t{ConsoleColor.FAIL}* {msg}{ConsoleColor.ENDC}")

    def log_header(self, msg):
        print(f"{ConsoleColor.HEADER}* {msg}{ConsoleColor.ENDC}")

    def resolve(self):
        for p in self.problems:
            p.resolve()

    def __str__(self):
        return self.__class__.name


class CheckStep(object):
    name = ""
    controller = StepController()

    def __init__(self, story):
        self.story = story

    def check(self):
        raise NotImplementedError

    def __str__(self):
        return self.name


class ResolvedProblem(Problem):
    solution = ""

    def position(self):
        self.story.warning(self.solution)


class StepCheckError(Problem):
    def position(self):
        self.story.warning(self.name)
