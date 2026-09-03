## Weak Topic Drill

Tools → Drill My Weak Topics…  Reads your review log, finds the topics you have
been failing, asks Claude for NBME-style single-best-answer vignettes on exactly
those, and quizzes you.

Nothing is written to your collection — this reads review history and shows
questions.

**Requires the Claude Code CLI**, the same binary Card Chat uses. Install Claude
Code, run `claude` once and `/login`. If the binary is somewhere unusual, set
`claude_path` to its full path.

- `window_days`: how far back to look. `1` means today — the topics you
  struggled with in this session. If today is too thin to rank anything, it
  automatically widens to a week and tells you it did.
- `min_reviews`: reviews a topic needs in the window before it can be ranked.
  Lower this if you get "not enough review history".
- `topic_count`: how many weak topics the questions are drawn from.
- `question_count`: how many questions to ask for.
- `tag_prefixes`: which tag hierarchies count as topics — the same shape Topic
  Stats uses, so the two agree about what a topic is. Set to `[]` to rank your
  own raw tags instead of AnKing's.
- `group_levels`: how many tag segments after the prefix make one topic.
- `model`: passed to the CLI as `--model`. Empty uses its default.
- `timeout_seconds`: writing five vignettes takes a while; 180 is a sane floor.

> Privacy: this sends your weak topic *names* and accuracy percentages to
> Anthropic through the CLI. It does not send your cards.
