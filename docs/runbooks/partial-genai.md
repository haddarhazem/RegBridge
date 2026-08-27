# Partial GenAI failure

**Symptom:** an orchestration event reports `partial`, or a child
`agent_run.transitioned` event is failed while another child succeeded.

**First check:** use `request_id`, `run_id`, `parent_run_id`, capability and
bounded error category. Do not inspect private context in logs.

**Recovery:** preserve successful results and provenance, retry only the failed
safe boundary, and avoid repeating irreversible actions. Confirm the final
response uses the documented partial/fallback behavior.

**Verify:** the failed component is localized and the successful child state
remains available under the same request correlation.
