import unittest

import modules.name_family as game


class NameFamilyValidationTests(unittest.TestCase):
    def setUp(self):
        self.original_add = game.add
        self.awards = []
        game.add = lambda chat_id, user_id, name, points: self.awards.append(
            (chat_id, user_id, points)
        )
        game._ACTIVE.clear()

    def tearDown(self):
        game.add = self.original_add
        game._ACTIVE.clear()

    @staticmethod
    def valid_answers():
        return "\n".join((
            "فریبا", "فری", "فردوس", "فندق", "فرغون", "فیل", "فرهاد",
        ))

    def force_round(self, round_id):
        game._ACTIVE[100] = {
            "round_id": round_id,
            "letter": "ف",
            "answers": {},
        }

    def test_valid_category_answers_receive_seventy_points(self):
        self.force_round(1)
        self.assertEqual(game.submit(100, 7, "کاربر", self.valid_answers()), 70)
        self.assertEqual(self.awards, [(100, 7, 70)])

    def test_jim_example_scores_each_category_independently(self):
        answers = ("جهان", "جوادی", "جیرفت", "جمبو", "جعبه", "جغد", "جهان")
        game._ACTIVE[100] = {
            "round_id": 1,
            "letter": "ج",
            "answers": {},
        }
        for category, answer in zip(game.CATEGORIES, answers):
            self.assertTrue(game._validate_answer(category, "ج", answer))
        self.assertEqual(game.submit(100, 7, "کاربر", "\n".join(answers)), 70)
        self.assertEqual(self.awards, [(100, 7, 70)])

    def test_fabricated_answers_receive_zero_points(self):
        self.force_round(1)
        fabricated = "\n".join((
            "فوفوف", "فچچس", "فسوسس", "فغغغ", "فپپپ", "فززز", "فککک",
        ))
        self.assertEqual(game.submit(100, 7, "کاربر", fabricated), 0)
        self.assertEqual(self.awards, [(100, 7, 0)])

    def test_category_mismatch_and_non_letters_are_invalid(self):
        self.assertFalse(game._validate_answer("شهر", "ف", "فریبا"))
        self.assertFalse(game._validate_answer("نام", "ف", "فریبا123"))
        self.assertTrue(game._validate_answer("نام", "ف", "فریبا"))

    def test_only_seven_raw_nonempty_lines_are_accepted(self):
        self.assertEqual(game._parse_answers(self.valid_answers()), self.valid_answers().splitlines())
        self.assertIsNone(game._parse_answers("پیام عادی"))
        self.assertIsNone(game._parse_answers(self.valid_answers().replace("\n", " | ")))
        self.assertIsNone(game._parse_answers(self.valid_answers().replace("\n", "،")))
        labelled = "\n".join(
            f"{category}: {answer}"
            for category, answer in zip(game.CATEGORIES, self.valid_answers().splitlines())
        )
        self.assertIsNone(game._parse_answers(labelled))
        self.assertIsNone(game._parse_answers(self.valid_answers() + "\n"))

    def test_unrelated_messages_do_not_create_a_submission(self):
        self.force_round(1)
        self.assertIsNone(game.submit(100, 7, "کاربر", "سلام ربات"))
        self.assertEqual(game._ACTIVE[100]["answers"], {})
        self.assertEqual(self.awards, [])

    def test_duplicate_submission_does_not_add_points_twice(self):
        self.force_round(1)
        self.assertEqual(game.submit(100, 7, "کاربر", self.valid_answers()), 70)
        self.assertEqual(game.submit(100, 7, "کاربر", "فوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف"), 70)
        self.assertEqual(self.awards, [(100, 7, 70)])

    def test_scores_do_not_transfer_between_rounds(self):
        self.force_round(1)
        game.submit(100, 7, "کاربر", self.valid_answers())
        self.assertEqual(game.finish(100)[0]["points"], 70)
        self.force_round(2)
        self.assertEqual(game.submit(100, 7, "کاربر", "فوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف"), 0)
        finished = game.finish(100)
        self.assertEqual(finished[0]["round_id"], 2)
        self.assertEqual(finished[0]["points"], 0)


if __name__ == "__main__":
    unittest.main()
