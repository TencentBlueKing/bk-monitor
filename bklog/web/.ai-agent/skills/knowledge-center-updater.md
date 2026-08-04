# Skill: Knowledge Center Updater

After every feature, fix, refactor or architecture change:

1. Run aafe knowledge update in the target project.
2. Run aafe knowledge-web to refresh the modular visual Knowledge Web.
3. Read the current .docs architecture sources and Mermaid diagrams.
4. Update generated relationship views under .docs/aafe-generated/.
4. Preserve original .docs documents and only update generated views automatically.
5. Use the generated views as Knowledge Center input.
6. Update the modular impact.html page with the current impact scope and recommended tests.
7. Run the mandatory architecture impact and test forecast before reporting completion.

Generated views:
- .docs/aafe-generated/组件关系.md
- .docs/aafe-generated/业务关系与数据流.md
- .docs/aafe-generated/影响范围与测试预测.md

Do not claim that generated documentation is a complete business truth. Include source paths, scan version and unresolved conflicts.
