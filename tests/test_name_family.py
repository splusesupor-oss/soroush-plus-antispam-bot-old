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

    def test_database_coverage_and_full_score_for_every_playable_letter(self):
        # Every alphabet letter is classified; only fully covered letters are selectable.
        for letter in game.LETTERS:
            covered = all(game.LETTER_COVERAGE[letter].values())
            has_unique_round = game.ROUND_EXAMPLES.get(letter) is not None
            self.assertEqual(letter in game.PLAYABLE_LETTERS, covered and has_unique_round)

        for index, letter in enumerate(game.PLAYABLE_LETTERS):
            answers = game.ROUND_EXAMPLES[letter]
            self.assertEqual(len({game._normalize(answer) for answer in answers}), 7)
            chat_id = 1000 + index
            game._ACTIVE[chat_id] = {
                "round_id": index + 1,
                "letter": letter,
                "answers": {},
            }
            self.assertEqual(
                game.submit(chat_id, index + 1, "کاربر", "\n".join(answers)),
                70,
            )
            self.assertFalse(game._validate_answer("نام", letter, letter + "چیچی"))

    def test_start_draws_only_fully_covered_letters(self):
        game._REMAINING_LETTERS.clear()
        drawn = []
        for _ in game.PLAYABLE_LETTERS:
            round_state = game.start(500)
            drawn.append(round_state["letter"])
            game.finish(500)
        self.assertEqual(set(drawn), set(game.PLAYABLE_LETTERS))
        self.assertTrue(set(drawn).isdisjoint(game.UNPLAYABLE_LETTERS))

    def test_jim_example_scores_each_category_independently(self):
        answers = ("جهان", "جوادی", "جیرفت", "جمبو", "جعبه", "جغد", "جهان")
        game._ACTIVE[100] = {
            "round_id": 1,
            "letter": "ج",
            "answers": {},
        }
        expected_valid = (True, True, True, False, True, True, True)
        self.assertEqual(
            tuple(
                game._validate_answer(category, "ج", answer)
                for category, answer in zip(game.CATEGORIES, answers)
            ),
            expected_valid,
        )
        # "جهان" appears twice; the second occurrence cannot earn a second score.
        self.assertEqual(game.submit(100, 7, "کاربر", "\n".join(answers)), 50)
        self.assertEqual(self.awards, [(100, 7, 50)])

    def test_duplicate_answer_is_not_scored_twice(self):
        game._ACTIVE[100] = {"round_id": 1, "letter": "ج", "answers": {}}
        answers = "\n".join((
            "جهان", "جوادی", "جیرفت", "جک فروت", "جعبه", "جغد", "جهان",
        ))
        self.assertEqual(game.submit(100, 7, "کاربر", answers), 60)

    def test_each_category_contributes_exactly_ten_points(self):
        answers = self.valid_answers().splitlines()
        self.force_round(1)
        self.assertEqual(game.submit(100, 7, "کاربر", "\n".join(answers[:4] + ["فوفوف"] * 3)), 40)
        self.force_round(2)
        self.assertEqual(game.submit(100, 8, "کاربر", "\n".join(answers[:2] + ["فوفوف"] * 5)), 20)

    def test_zah_example_scores_twenty_without_zeroing_other_categories(self):
        class Logger:
            def __init__(self):
                self.lines = []

            def log_info(self, line):
                self.lines.append(line)

        logger = Logger()
        game._ACTIVE[100] = {
            "round_id": 1,
            "letter": "ظ",
            "answers": {},
        }
        answers = "\n".join((
            "ظاتمه", "ظفري", "نمی‌دونم", "نمی دانم", "ظرف", "نمیدونم", "نمی‌دونم",
        ))
        self.assertEqual(game.submit(100, 7, "کاربر", answers, logger=logger), 20)
        self.assertIn("category=نام answer=ظاتمه letter=ظ valid=False score=0", logger.lines[0])
        self.assertIn("category=فامیل answer=ظفري letter=ظ valid=True score=10", logger.lines[1])
        self.assertIn("category=وسیله answer=ظرف letter=ظ valid=True score=10", logger.lines[4])
        self.assertEqual(len(logger.lines), 7)

    def test_persian_normalization_and_empty_variants(self):
        self.assertEqual(game._normalize("  نمی‌دونم  "), "نمیدونم")
        self.assertEqual(game._normalize("ظفري"), "ظفری")
        self.assertEqual(game._normalize("فیروز  کوه"), "فیروز کوه")
        self.assertFalse(game._validate_answer("نام", "ن", "نمی‌دونم"))
        self.assertFalse(game._validate_answer("نام", "ن", "نمی دانم"))

    def test_yeh_examples_score_fifty_and_ten_independently(self):
        game._ACTIVE[100] = {
            "round_id": 1,
            "letter": "ی",
            "answers": {},
        }
        fifty_answers = "\n".join((
            "یسنا", "یاوری", "یزد", "نمیدونم", "یویو", "یوزپلنگ", "نمیدونم",
        ))
        self.assertEqual(game.submit(100, 7, "کاربر", fifty_answers), 50)

        game._ACTIVE[100] = {
            "round_id": 2,
            "letter": "ی",
            "answers": {},
        }
        ten_answers = "\n".join((
            "یارو", "یاوری", "نمیدونم", "نمیدونم", "یخ", "نمیدونم", "نمیدونم",
        ))
        self.assertEqual(game.submit(100, 8, "کاربر", ten_answers), 10)

    def test_vahids_partial_answers_score_thirty_and_log_each_category(self):
        class Logger:
            def __init__(self):
                self.lines = []

            def log_info(self, line):
                self.lines.append(line)

        logger = Logger()
        game._ACTIVE[100] = {
            "round_id": 1,
            "letter": "و",
            "answers": {},
        }
        answers = "\n".join((
            "وحید", "وحیدی", "ورامین", "نمی‌دونم", "وینچستر", "نمی‌دونم", "وحید",
        ))
        self.assertEqual(game.submit(100, 7, "کاربر", answers, logger=logger), 30)
        self.assertIn("category=نام answer=وحید letter=و valid=True score=10", logger.lines[0])
        self.assertIn("category=فامیل answer=وحیدی letter=و valid=True score=10", logger.lines[1])
        self.assertIn("category=شهر answer=ورامین letter=و valid=True score=10", logger.lines[2])
        self.assertIn("category=میوه answer=نمی‌دونم letter=و valid=False score=0", logger.lines[3])
        self.assertEqual(len(logger.lines), 7)

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
        self.assertIsNone(game.submit(100, 7, "کاربر", "فوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف\nفوفوف"))
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
