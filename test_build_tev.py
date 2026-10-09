import json
import random
import unittest

import build_tev as b


def feat(**kw):
    f = {"address": "W", "fetched_at": 1_000_000, "first_seen": 1_000_000 - 86400 * 10, "tx_count": 5000,
         "tx_count_capped": True, "sample_size": 100, "sample_span_hours": 1.0, "sample_failed": 0,
         "sample_as_signer": 100, "sample_sol_delta": 0.0, "sample_program_categories": {},
         "sample_pump_instructions": {}, "sample_cosigners": 0, "funding": None}
    f.update(kw)
    return f


class BuildTev(unittest.TestCase):
    def test_render_letter_points_at_answer(self):
        rng = random.Random(0)
        for key in b.OPTIONS:
            rec = {"state": {}, "question": "q", "answer_key": key}
            out = b.render(rec, rng)
            options = json.loads(out["prompt"].split("<|im_start|>user\n")[1].split("<|im_end|>")[0])["options"]
            letter = out["completion"].removesuffix("<|im_end|>")
            self.assertEqual(next(o["key"] for o in options if o["label"] == letter), key)
            self.assertTrue(out["prompt"].endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n"))

    def test_mass_deployer(self):
        self.assertTrue(b.mass_deployer(feat(sample_pump_instructions={"CreateV2": 6})))
        self.assertFalse(b.mass_deployer(feat(sample_pump_instructions={"CreateV2": 1})))
        self.assertFalse(b.mass_deployer(feat(sample_pump_instructions={"CreateV2": 6}, tx_count=50)))

    def test_every_malicious_category_maps_to_scam(self):
        for c in ["Exploiter, Hackers & Scams", "Hacker", "Rugger", "Scammer", "Spam"]:
            self.assertEqual(b.CATEGORY_TO_CLASS[c], "scam_or_exploit")
        self.assertNotIn("Other", b.CATEGORY_TO_CLASS)

    def test_split_is_deterministic(self):
        self.assertEqual(b.split_of("abc"), b.split_of("abc"))


if __name__ == "__main__":
    unittest.main()
