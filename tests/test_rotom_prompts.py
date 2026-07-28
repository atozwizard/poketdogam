# Run: python -m unittest tests/test_rotom_prompts.py
from __future__ import annotations

import unittest

from app.agents.pokedex_agent.prompts.rotom import (
    RESPONSE_PROMPT,
    ROUTER_PROMPT,
    build_system_prompt,
    load_character_bible,
)


class RotomPromptTest(unittest.TestCase):
    def test_character_bible_exists_and_has_guardrails(self) -> None:
        bible = load_character_bible()
        self.assertIn("Rotom Dex OS", bible)
        self.assertIn("가드레일", bible)
        self.assertIn("-로", bible)

    def test_system_prompt_grounded_includes_facts_boundary(self) -> None:
        prompt = build_system_prompt(
            grounded=True,
            context='{"name_ko":"피카츄","types":["electric"]}',
            safe_template="피카츄는 전기 타입",
        )
        self.assertIn("피카츄", prompt)
        self.assertIn("FACTS", prompt)
        self.assertIn("공식", RESPONSE_PROMPT)
        self.assertIn("dex", ROUTER_PROMPT)


if __name__ == "__main__":
    unittest.main()
