# Postmortem: Project 1, The Grader

Team: Oussama Sfar, Ines Turki, Feriel Charrad, Faten Toujani.

This document covers what went wrong while building the golden set, the harness and the judge, what it cost us, and what we would do differently. The problems are listed roughly in the order they happened.

## Summary

| # | Problem | Impact | Status |
|---|---|---|---|
| 1 | The golden set has 100 items, not the 150+ the brief asks for | Misses a stated requirement | Accepted as a limitation |
| 2 | No calibration pilot before labelling | Lowest agreement on the "grounded" check (κ 0.50); one labeller pair at 68% | Documented; guide changes identified |
| 3 | Bug in the labelling page could silently drop items | Would have corrupted labels | Caught in testing before release |
| 4 | Running the model locally: runs stopped by low memory, long reasoning, a lenient judge | Restarts; slow judge; judge slightly over-reports quality | Done; all runs complete; leniency documented |
| 5 | The improved prompt (v2) scored lower than the baseline | No improvement to report | v1 kept by a rule fixed in advance; failure analysed |

## What went wrong

### 1. The golden set is smaller than required (100 instead of 150+)

The first plan had two people label every item of a 150-item set. We underestimated how long careful labelling takes: each item needs the policy section read in full, because the error is often a single clause. With the deadline close and no second labeller available at first, we cut the set to 100 items, keeping the balance (50 pass / 50 fail) and at least one item of every flaw type.

**Lesson:** count labelling time as roughly one minute per item per labeller, plus coordination, and recruit labellers on day one rather than after the data exists.

### 2. No calibration pilot

We planned a 20-item pilot where two labellers compare notes and fix the guide before labelling the rest. Under time pressure we skipped it and had four labellers work in parallel. The consequences show in the numbers:

- Verdict agreement was good (87/100, Fleiss' κ 0.74), but the **grounded** check was weak (77/100, κ 0.50). Most disagreements were answers that guess about a topic the policy does not cover, which one labeller accepted.
- 15 items had the same verdict but different failing checks, because some labellers marked all three checks "no" whenever they failed an answer.
- One labeller pair agreed on only 17/25 items (68%), against 88–96% for the other pairs.

A pilot would have caught all three in twenty minutes.

**Lesson:** the pilot is not optional. The guide needs one worked example per hard case, and an explicit rule to mark only the check that is actually broken.

### 3. A labelling-page bug that would have silently dropped items

The labelling page is keyboard-driven (`y`, `n`, `Enter`). In testing with simulated labellers we found that after writing a note or dropping an item, the text cursor stayed in that text box. The next item's `y`/`n` keys were typed into the box, and `Enter` then dropped or saved the wrong item. One simulated labeller ended up with 45 of 50 items "dropped", with reasons like `nyy`.

It was fixed (the cursor leaves every text box when a new item appears) and retested before the page was sent to anyone.

**Lesson:** test the labelling tool end to end with scripted input before real people use it. A bug there corrupts the data everything else is measured against, and it would not have shown up as an error.

### 4. Running the model locally: memory, long reasoning, and a lenient judge

Both roles run on `qwen3:8b` through Ollama on a laptop RTX 4070 (8 GB). That means no API key, no rate limits and no per-token cost, but it brought its own problems:

- **Runs were stopped by low memory.** The Ollama server and the experiment runner were killed twice when the machine ran low on RAM, with a browser holding about 9 GB next to the model. Closing it and running the Ollama app separately fixed it. Every finished call was cached, so no work was lost and each restart continued where it stopped.
- **Qwen reasons much longer than expected** (about 700–1,000 reasoning tokens per graded answer, up to 2,500), so a judged item takes about 20 s on average and the full set of experiments about 3 hours.
- **The judge errs on the lenient side.** 6 of its 7 errors over 100 items pass a flawed answer, mostly answers missing a condition or accepting a false premise from the question. It still agrees with humans on 93/100 items (κ 0.86) and 47/50 on test, but monitoring with it will slightly over-report quality.
- **The same model is both system and judge**, which risks self-preference. We tested it: when both answers were good, the judge preferred the system's answer 5 times and the golden answer 5 times; when only the golden answer was good, it chose it 6/6 times. No sign of self-preference.

**Lesson:** measure the real per-call time and memory of a local model on a few items before planning a full run, and make every step resumable. The cache is what made the interruptions harmless.

### 5. The improved prompt made things worse

System prompt v2 added rules for each failure type seen on dev (use the exact case, state conditions, correct false premises, say when the policy is silent). It scored 36/50 on dev against v1's 37/50. Per item it fixed 6 questions and broke 7: it helped on uncovered topics (5/8 → 7/8) and false premises (3/6 → 4/6), but hurt multi-condition questions (11/14 → 7/14), where the extra instructions made the small model misapply conditions.

Because the rule for the final run was fixed before seeing the result (the higher dev score goes to test, ties to v1), v1 went to test without any temptation to pick the better-looking number afterwards. It scored 38/50 (76%) on test.

**Lesson:** a longer prompt is not automatically better, especially for a small model. The single dev number (74% vs. 72%) hid large movements in both directions, and only the per-item comparison explained them. Next time, change one rule per version, so each change can be linked to its effect.

## What went well

- **Designed flaws.** Building each answer to contain exactly one known flaw gave us a balanced set that covers every failure mode, and made disagreements easy to diagnose.
- **A fictional policy.** Rules that differ from real airlines meant answers from memory were caught instead of passing by luck.
- **Block labelling design.** Four labellers × 50 items, arranged so every item has exactly two labels, spread the work and still measured agreement on every item.
- **The cache.** Every model call is cached, so reruns are free, failures and interruptions lose no work, and results can be reproduced exactly.
- **The judge.** It agrees with the human labels on 47/50 test items (94%, κ 0.88), more than our labellers agreed with each other. It shows no verbosity bias (0/44 grades changed by padding) and no preference for the first-shown answer (51.7%).
- **A selection rule fixed in advance.** Deciding before the v2 result how the final prompt would be chosen kept the test score honest.

## Still open at the time of writing

- Revision of the labelling guide for the "grounded" rule and single-check marking.
- Attack items (answers that try to instruct the grader) are defended against in the judge prompt but were not measured.
- Extending the golden set to 150+ items, with harder multi-rule and near-threshold questions.
