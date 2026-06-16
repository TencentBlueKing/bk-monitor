# Skill: Downloadable Skills Installer

Install published AAFE Agent Skills from GitHub into a target Agent Skills directory.

This skill is only for the GitHub Agent SKILLS download scenario. It must not be used to initialize or update `.ai-agent` inside a business project.

When to use:
- The user wants to download an AAFE Skill from GitHub.
- The user wants to install published AAFE Agent SKILLS into a specified Agent / AI tool Skills directory.
- The user explicitly provides or relies on an Agent Skills target directory.

Do not use when:
- The user wants a business project to install or update `@aafe/agent-runtime`.
- The user wants to generate or refresh project `.ai-agent/`, `.aafe.config.json` or editor runtime files.
- For project runtime work, use `aafe init`, `aafe update`, `aafe analyze` and `aafe doctor` instead.

Commands:

```bash
aafe skills list --github
aafe skills install aafe-vue-complex-runtime --github
```

Target resolution:
1. If `--target=<dir>` is provided, install into that Agent Skills directory.
2. Else if `$SIBOOT_WORKSPACE_PATH` exists, install into `$SIBOOT_WORKSPACE_PATH/skills`.
3. Else install into `./skills` under the current working directory.

Idempotency:
- If the target `SKILL.md` already has the same content, leave it unchanged.
- Use `--dry-run` before writing when the target directory is uncertain.
- Use `--force` only when the user explicitly wants to rewrite the target file.

Published manifest:
- https://raw.githubusercontent.com/xintaoLi/aafe-agent-runtime/main/skills/manifest.json

Required artifacts:
- downloadable_skills_install_plan
