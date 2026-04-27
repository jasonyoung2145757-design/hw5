# Demo Prompts

Use these prompts in Codex, Claude Code, or another approved coding assistant when you record the walkthrough.

## 1. Normal case

Use `meeting-window-ranker` to find the best 60-minute overlap for the participants in `demo/normal-case.json`. Run the skill's Python script and summarize the top recommendation in plain English.

## 2. Edge case

Use `meeting-window-ranker` on `demo/edge-case-overnight.json`. This case includes an overnight shift in Los Angeles, so explain whether the skill handles cross-midnight work windows correctly and then summarize the top-ranked slot.

## 3. Cautious case

Use `meeting-window-ranker` on `demo/cautious-case-ambiguous-timezone.json`. If the input is ambiguous or unsafe to interpret, do not guess. Explain what the user must fix before the ranking can run.
