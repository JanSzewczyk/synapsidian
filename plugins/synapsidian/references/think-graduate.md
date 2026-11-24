# think: graduate

Turn an idea into work: a project with its first tasks, or just tasks on an existing project. Without synapsidian-projects (see conventions) it is always tasks, with no `project` field. No thinking note; the idea itself records where it went.

1. Find the idea (`synapsidian find --type idea "<name>"`) and read it. If it is vague, ask the one or two questions that make it actionable (goal, done-criteria, size).
2. **Project or tasks?** With projects: a project when it needs several steps over more than a week or has its own decisions; otherwise tasks on an existing project (`synapsidian find --type project`).
3. **Project**: `synapsidian note new --type project --title "<name>" --field summary="<goal in one sentence>"` (its hub comes with a board); fill Goal and Status from the idea; link the idea under Related.
4. **Tasks**: 2-5 first tasks, each a concrete next action, via `synapsidian note new --type task ... [--field project="<project>"] --field source=manual --field source_link="<idea title>"`. Dates only when the user gives them.
5. Mark the idea: `synapsidian note set --file "<idea>" --field status=graduated --field graduated_to="<project or first task>"`, and add a dated line to it saying what it became.
6. Answer with the new project / tasks as `[[links]]`.
