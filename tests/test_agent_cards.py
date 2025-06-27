# noqa: D400
"""CI-visible wrapper for agent-card validation tests.

Imports every test from the main implementation in
`unit_tests.test_agent_cards_validation.test_agent_cards_validation`, making
sure they are executed by the default GitHub Action which only looks under the
`tests/` directory.
"""

from unit_tests.test_agent_cards_validation.test_agent_cards_validation import *  # noqa: F401,F403 