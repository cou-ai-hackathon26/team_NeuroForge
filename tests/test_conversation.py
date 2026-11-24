from modules.conversation import next_question


def test_followup_for_headache():
    x = {"severe_headache": True, "gestational_age_weeks": 24}
    assert "ঝাপসা" in next_question(x)


def test_no_followup_when_nothing_reported():
    assert next_question({}) is None
