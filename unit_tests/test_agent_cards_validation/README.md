# Agent Card Validation Test Suite

This mini-suite validates the *static* integrity of every `agent_cards/*.json` file.
It is completely offline (no network or API keys needed) and covers three layers:

1. **Schema soundness** – each JSON document must load and parse into
   `CustomAgentCard` (Pydantic) without errors.
2. **Field-level sanity** – mandatory string fields present, skills list well-formed,
   capability flags present and using the strings "True" / "False", unique `skill.id`s.
3. **Cross-file integrity** –
   * each `url` is unique across the folder
   * every value in `nextAgent` matches the `url` of another card (no dangling pointers).

The implementation lives in `test_agent_cards_validation/test_agent_cards_validation.py`.

## Running just this suite
```bash
pytest unit_tests/test_agent_cards_validation -q
```
