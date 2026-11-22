from collections import Counter, defaultdict
from datetime import datetime, timedelta

from app.services.v2.identity_service import HmacIdentityCipher
from app.services.v2.rules.assessment import score_questionnaire
from scripts.defense_data import (
    END,
    MODULES,
    PREFIX,
    RESERVED_NUMBER,
    SHANGHAI,
    START,
    Band,
    Bundle,
    build_bundle,
    dashboard_snapshot,
    local_questionnaires,
    roster,
)
from scripts.defense_import import equal_document


def sample() -> Bundle:
    return build_bundle(HmacIdentityCipher("test-defense"), local_questionnaires())


def test_defense_cohort_uses_distinct_answers_and_paired_results() -> None:
    bundle = sample()
    accounts = {row["_id"] for row in bundle["user_accounts"]}
    assert accounts == set(roster()) and len(accounts) == 30
    assert RESERVED_NUMBER not in {number for _, number in roster().values()}
    assert all(row["_id"].startswith(PREFIX) for group in bundle.values() for row in group)
    assert len({name for name, _ in roster().values()}) == 30
    assert all(len(number) == 8 and number.startswith("104253") for _, number in roster().values())
    sessions = {row["_id"]: row for row in bundle["assessment_sessions"]}
    assert len(sessions) == len(bundle["assessment_results"]) == 495
    by_user = Counter((row["user_id"], row["module_code"]) for row in sessions.values())
    for module in MODULES:
        assert sorted(by_user[user, module] for user in accounts) == [5] * 15 + [6] * 15
    questionnaires = local_questionnaires()
    answer_profiles: dict[str, list[tuple[str, tuple[tuple[str, str], ...]]]] = defaultdict(list)
    for row in bundle["assessment_results"]:
        session = sessions[row["session_id"]]
        assert row["user_id"] == session["user_id"]
        assert session["state"] == "completed" and session["completed_at"] == row["created_at"]
        answers = [(answer["question_key"], answer["option_key"]) for answer in session["answers"]]
        answer_profiles[row["user_id"]].append((row["module_code"], tuple(answers)))
        outcome = score_questionnaire(questionnaires[row["module_code"]], answers)
        assert outcome.score == row["score"] and outcome.reference_band == row["reference_band"]
        assert outcome.answers_snapshot == row["answers_snapshot"] and not outcome.safety_triggered
    assert len({tuple(profile) for profile in answer_profiles.values()}) == 30
    assert all(not row["safety_triggered"] for row in sessions.values())


def test_snapshot_preserves_interval_and_person_based_risk() -> None:
    bundle = sample()
    snapshot = dashboard_snapshot(bundle)
    posts = bundle["treehole_posts"]
    assert len({post["body_sanitized"] for post in posts}) == len(posts) == 108
    assert Counter(Counter(row["author_user_id"] for row in posts).values()) == {3: 12, 4: 18}
    assert all(post["visibility_state"] == "published" for post in posts)
    assert all(post["display_name_snapshot"].endswith(" · 演示") for post in posts)
    expected_weeks = set(range((END - START).days // 7 + 1))
    for kind in ("assessments", "posts"):
        dates = [datetime.fromisoformat(row["at"]).astimezone(SHANGHAI) for row in snapshot[kind]]
        assert all(START <= date <= END for date in dates)
        assert min(dates).date() == START.date() and max(dates).date() == END.date()
        assert {
            (date.date() - START.date()) // timedelta(days=7) for date in dates
        } == expected_weeks
    latest: dict[tuple[str, str], Band] = {}
    deep_night: Counter[Band] = Counter()
    for row in snapshot["assessments"]:
        if row["band"] is None:
            continue
        latest[row["caseId"], row["module"]] = row["band"]
        if int(row["at"][11:13]) in {0, 1, 2, 3, 23}:
            deep_night[row["band"]] += 1
    order = {"low": 0, "elevated": 1, "high": 2}
    assert Counter(
        max((latest[case, "phq9"], latest[case, "gad7"]), key=order.__getitem__)
        for case, module in latest
        if module == "phq9"
    ) == {"low": 15, "elevated": 12, "high": 3}
    assert deep_night["elevated"] > deep_night.total() / 2
    assert deep_night["low"] > 0 and deep_night["high"] > 0
    assert set(snapshot["assessments"][0]) == {"caseId", "module", "at", "band"}
    assert set(snapshot["posts"][0]) == {"caseId", "at"}


def test_seed_check_allows_only_identical_records_or_equivalent_ciphertext() -> None:
    cipher = HmacIdentityCipher("test-defense")
    record = sample()["identity_records"][0]
    recreated = {
        **record,
        "student_name_ciphertext": cipher.encrypt(roster()[record["user_id"]][0]),
    }
    assert equal_document(record, recreated, cipher)
    assert not equal_document({**record, "version": 2}, recreated, cipher)
    assert not equal_document(
        {**record, "student_name_ciphertext": cipher.encrypt("另一个人")}, recreated, cipher
    )
