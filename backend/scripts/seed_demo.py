"""Deterministic synthetic seed data for the demo environment only."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.config.environments import EnvironmentKind
from app.repositories.collection_registry import COLLECTIONS

SEED_TIMESTAMP = datetime(2026, 8, 29, 0, 0, tzinfo=UTC)
LIBRARY_VERSION = "quote-library-v1"


def build_demo_seed_bundle(environment_kind: EnvironmentKind) -> dict[str, Any]:
    if environment_kind is not EnvironmentKind.DEMO:
        raise ValueError("demo seed data can only be generated for demo environments")

    collections: dict[str, list[dict[str, Any]]] = {name: [] for name in COLLECTIONS}
    collections["user_accounts"] = [_user_account()]
    collections["consent_records"] = _consent_records()
    collections["anonymous_identities"] = [_anonymous_identity()]
    collections["support_resources"] = _support_resources()
    collections["quote_entries"] = _quote_entries()
    collections["admin_accounts"] = [_admin_account()]

    return {
        "generated_at": SEED_TIMESTAMP.isoformat(),
        "library_version": LIBRARY_VERSION,
        "collections": collections,
    }


def main() -> int:
    print(json.dumps(build_demo_seed_bundle(EnvironmentKind.DEMO), ensure_ascii=False, indent=2))
    return 0


def _metadata(document_id: str) -> dict[str, Any]:
    return {
        "_id": document_id,
        "created_at": SEED_TIMESTAMP.isoformat(),
        "updated_at": SEED_TIMESTAMP.isoformat(),
        "version": 1,
    }


def _user_account() -> dict[str, Any]:
    return {
        **_metadata("demo-user-001"),
        "auth_subject_hash": "hash_demo_subject_001",
        "status": "active",
        "base_consent_status": "accepted",
        "base_consent_version": "base-consent-v1",
        "base_consent_at": SEED_TIMESTAMP.isoformat(),
        "community_consent_status": "accepted",
        "community_consent_version": "community-consent-v1",
        "community_consent_at": SEED_TIMESTAMP.isoformat(),
        "identity_record_id": None,
        "anonymous_identity_id": "demo-anon-001",
        "stop_requested_at": None,
        "recovery_deadline_at": None,
        "purged_at": None,
    }


def _consent_records() -> list[dict[str, Any]]:
    return [
        {
            **_metadata("demo-consent-001"),
            "user_id": "demo-user-001",
            "consent_kind": "base_service",
            "action": "accepted",
            "document_version": "base-consent-v1",
            "source": "admin_seed",
            "occurred_at": SEED_TIMESTAMP.isoformat(),
            "request_id": "seed-demo-base-consent",
        },
        {
            **_metadata("demo-consent-002"),
            "user_id": "demo-user-001",
            "consent_kind": "community_content",
            "action": "accepted",
            "document_version": "community-consent-v1",
            "source": "admin_seed",
            "occurred_at": SEED_TIMESTAMP.isoformat(),
            "request_id": "seed-demo-community-consent",
        },
    ]


def _anonymous_identity() -> dict[str, Any]:
    return {
        **_metadata("demo-anon-001"),
        "user_id": "demo-user-001",
        "display_name": "海边长颈鹿",
        "generation_version": "demo-name-v1",
        "status": "active",
    }


def _support_resources() -> list[dict[str, Any]]:
    return [
        {
            **_metadata("support-demo-001"),
            "environment_scope": "demo",
            "category": "trusted_person",
            "title": "演示环境求助卡片",
            "description": "仅用于演示界面联调，不代表真实支持承诺。",
            "action_type": "copy",
            "action_target": "DEMO-SUPPORT-TRUSTED-001",
            "availability_text": "演示数据，始终可见",
            "source_text": "心语 V2 演示环境",
            "verified_at": SEED_TIMESTAMP.isoformat(),
            "resource_set_version": "support-v1",
            "expires_at": None,
            "enabled": True,
            "sort_order": 1,
        },
        {
            **_metadata("support-demo-002"),
            "environment_scope": "demo",
            "category": "campus",
            "title": "演示校园资源页",
            "description": "示例链接，用于前后端联调。",
            "action_type": "open_url",
            "action_target": "https://demo-campus-support.example.invalid/resource",
            "availability_text": "演示链接",
            "source_text": "心语 V2 演示环境",
            "verified_at": SEED_TIMESTAMP.isoformat(),
            "resource_set_version": "support-v1",
            "expires_at": None,
            "enabled": True,
            "sort_order": 2,
        },
        {
            **_metadata("support-demo-003"),
            "environment_scope": "demo",
            "category": "emergency",
            "title": "演示紧急支持说明",
            "description": "仅演示入口排版，不提供现实世界联系方式。",
            "action_type": "text_only",
            "action_target": None,
            "availability_text": "演示文案",
            "source_text": "心语 V2 演示环境",
            "verified_at": SEED_TIMESTAMP.isoformat(),
            "resource_set_version": "support-v1",
            "expires_at": None,
            "enabled": True,
            "sort_order": 3,
        },
    ]


def _admin_account() -> dict[str, Any]:
    return {
        **_metadata("admin-demo-001"),
        "login_name": "demo_admin",
        "display_name": "心理健康中心工作人员",
        "capability_label": "超级管理员",
        "status": "active",
        "password_hash_reference": "config://admin_password_hash",
        "last_login_at": None,
    }


def _quote_entries() -> list[dict[str, Any]]:
    enabled = [
        (
            "Q-0001",
            "天行健，君子以自强不息。",
            "《周易·乾》",
            None,
            "public_domain",
            "公版古典文本，已核验",
            1,
        ),
        (
            "Q-0002",
            "地势坤，君子以厚德载物。",
            "《周易·坤》",
            None,
            "public_domain",
            "公版古典文本，已核验",
            2,
        ),
        (
            "Q-0003",
            "千里之行，始于足下。",
            "《道德经》第六十四章",
            None,
            "public_domain",
            "公版古典文本，已核验",
            3,
        ),
        (
            "Q-0004",
            "合抱之木，生于毫末。",
            "《道德经》第六十四章",
            None,
            "public_domain",
            "公版古典文本，已核验",
            4,
        ),
        (
            "Q-0005",
            "九层之台，起于累土。",
            "《道德经》第六十四章",
            None,
            "public_domain",
            "公版古典文本，已核验",
            5,
        ),
        (
            "Q-0006",
            "知人者智，自知者明。",
            "《道德经》第三十三章",
            None,
            "public_domain",
            "公版古典文本，已核验",
            6,
        ),
        (
            "Q-0007",
            "胜人者有力，自胜者强。",
            "《道德经》第三十三章",
            None,
            "public_domain",
            "公版古典文本，已核验",
            7,
        ),
        (
            "Q-0008",
            "不积跬步，无以至千里。",
            "荀子",
            "劝学",
            "public_domain",
            "公版古典文本，已核验",
            8,
        ),
        (
            "Q-0009",
            "锲而不舍，金石可镂。",
            "荀子",
            "劝学",
            "public_domain",
            "公版古典文本，已核验",
            9,
        ),
        (
            "Q-0010",
            "三军可夺帅也，匹夫不可夺志也。",
            "《论语·子罕》",
            None,
            "public_domain",
            "公版古典文本，已核验",
            10,
        ),
        (
            "Q-0011",
            "知者不惑，仁者不忧，勇者不惧。",
            "《论语·子罕》",
            None,
            "public_domain",
            "公版古典文本，已核验",
            11,
        ),
        (
            "Q-0012",
            "博学而笃志，切问而近思。",
            "《论语·子张》",
            None,
            "public_domain",
            "公版古典文本，已核验",
            12,
        ),
        (
            "Q-0013",
            "岁寒，然后知松柏之后凋也。",
            "《论语·子罕》",
            None,
            "public_domain",
            "公版古典文本，已核验",
            13,
        ),
        (
            "Q-0014",
            "路漫漫其修远兮，吾将上下而求索。",
            "屈原",
            "离骚",
            "public_domain",
            "公版古典文本，已核验",
            14,
        ),
        (
            "Q-0015",
            "长风破浪会有时，直挂云帆济沧海。",
            "李白",
            "行路难",
            "public_domain",
            "公版古典文本，已核验",
            15,
        ),
        (
            "Q-0016",
            "天生我材必有用，千金散尽还复来。",
            "李白",
            "将进酒",
            "public_domain",
            "公版古典文本，已核验",
            16,
        ),
        (
            "Q-0017",
            "大鹏一日同风起，扶摇直上九万里。",
            "李白",
            "上李邕",
            "public_domain",
            "公版古典文本，已核验",
            17,
        ),
        (
            "Q-0018",
            "会当凌绝顶，一览众山小。",
            "杜甫",
            "望岳",
            "public_domain",
            "公版古典文本，已核验",
            18,
        ),
        (
            "Q-0019",
            "欲穷千里目，更上一层楼。",
            "王之涣",
            "登鹳雀楼",
            "public_domain",
            "公版古典文本，已核验",
            19,
        ),
        (
            "Q-0020",
            "海内存知己，天涯若比邻。",
            "王勃",
            "送杜少府之任蜀州",
            "public_domain",
            "公版古典文本，已核验",
            20,
        ),
        (
            "Q-0021",
            "莫愁前路无知己，天下谁人不识君。",
            "高适",
            "别董大",
            "public_domain",
            "公版古典文本，已核验",
            21,
        ),
        (
            "Q-0022",
            "野火烧不尽，春风吹又生。",
            "白居易",
            "赋得古原草送别",
            "public_domain",
            "公版古典文本，已核验",
            22,
        ),
        (
            "Q-0023",
            "千淘万漉虽辛苦，吹尽狂沙始到金。",
            "刘禹锡",
            "浪淘沙",
            "public_domain",
            "公版古典文本，已核验",
            23,
        ),
        (
            "Q-0024",
            "沉舟侧畔千帆过，病树前头万木春。",
            "刘禹锡",
            "酬乐天扬州初逢席上见赠",
            "public_domain",
            "公版古典文本，已核验",
            24,
        ),
        (
            "Q-0025",
            "行到水穷处，坐看云起时。",
            "王维",
            "终南别业",
            "public_domain",
            "公版古典文本，已核验",
            25,
        ),
        (
            "Q-0026",
            "山重水复疑无路，柳暗花明又一村。",
            "陆游",
            "游山西村",
            "public_domain",
            "公版古典文本，已核验",
            26,
        ),
        (
            "Q-0027",
            "纸上得来终觉浅，绝知此事要躬行。",
            "陆游",
            "冬夜读书示子聿",
            "public_domain",
            "公版古典文本，已核验",
            27,
        ),
        (
            "Q-0028",
            "不畏浮云遮望眼，自缘身在最高层。",
            "王安石",
            "登飞来峰",
            "public_domain",
            "公版古典文本，已核验",
            28,
        ),
        (
            "Q-0029",
            "莫听穿林打叶声，何妨吟啸且徐行。",
            "苏轼",
            "定风波",
            "public_domain",
            "公版古典文本，已核验",
            29,
        ),
        (
            "Q-0030",
            "但愿人长久，千里共婵娟。",
            "苏轼",
            "水调歌头",
            "public_domain",
            "公版古典文本，已核验",
            30,
        ),
        (
            "Q-0031",
            "今天只做一件能完成的小事，也算向前。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            31,
        ),
        (
            "Q-0032",
            "累的时候，先让自己喘口气。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            32,
        ),
        (
            "Q-0033",
            "你不需要每一天都很有答案。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            33,
        ),
        (
            "Q-0034",
            "先照顾此刻，再考虑远方。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            34,
        ),
        (
            "Q-0035",
            "慢一点，也是在前进。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            35,
        ),
        (
            "Q-0036",
            "能够求助，也是一种力量。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            36,
        ),
        (
            "Q-0037",
            "今天的感受，值得被认真听见。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            37,
        ),
        (
            "Q-0038",
            "给自己留一点没有任务的时间。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            38,
        ),
        (
            "Q-0039",
            "一次没做好，不代表你做不到。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            39,
        ),
        (
            "Q-0040",
            "把很大的事情，先缩成眼前的一小步。",
            "心语短句库",
            None,
            "project_original",
            "项目原创温和短句，已启用",
            40,
        ),
    ]
    disabled = [
        (
            "Q-C001",
            "直到最后都不能放弃希望。",
            "安西教练",
            "灌篮高手",
            "copyright_pending",
            "待版权与正式译文核验",
            41,
        ),
        (
            "Q-C002",
            "教练，我想打篮球。",
            "三井寿",
            "灌篮高手",
            "copyright_pending",
            "待版权与正式译文核验",
            42,
        ),
        (
            "Q-C003",
            "相信的心就是你的魔法。",
            "夏莉欧",
            "小魔女学园",
            "copyright_pending",
            "待版权与正式译文核验",
            43,
        ),
    ]
    return [
        _quote_entry(
            item_id, quote_text, author_text, work_text, source_kind, rights_note, True, sort_order
        )
        for (
            item_id,
            quote_text,
            author_text,
            work_text,
            source_kind,
            rights_note,
            sort_order,
        ) in enabled
    ] + [
        _quote_entry(
            item_id, quote_text, author_text, work_text, source_kind, rights_note, False, sort_order
        )
        for (
            item_id,
            quote_text,
            author_text,
            work_text,
            source_kind,
            rights_note,
            sort_order,
        ) in disabled
    ]


def _quote_entry(
    item_id: str,
    quote_text: str,
    author_text: str,
    work_text: str | None,
    source_kind: str,
    rights_note: str,
    enabled: bool,
    sort_order: int,
) -> dict[str, Any]:
    return {
        **_metadata(item_id),
        "quote_text": quote_text,
        "author_text": author_text,
        "work_text": work_text,
        "source_kind": source_kind,
        "source_url": _quote_source_url(item_id, source_kind),
        "language_version": "zh-Hans",
        "review_status": "已启用" if enabled else "已停用",
        "rights_note": rights_note,
        "enabled": enabled,
        "display_from": None,
        "display_until": None,
        "sort_order": sort_order,
        "library_version": LIBRARY_VERSION,
    }


def _quote_source_url(item_id: str, source_kind: str) -> str:
    if item_id == "Q-0001":
        return "https://ctext.org/book-of-changes/qian/zh"
    if source_kind == "project_original":
        return f"project://docs/v2/V2_DAILY_QUOTE_LIBRARY.md#{item_id}"
    if source_kind == "copyright_pending":
        return "https://zh.wikiquote.org/wiki/Wikiquote:%E9%A6%96%E9%A1%B5"
    return "https://ctext.org/zh"


if __name__ == "__main__":
    raise SystemExit(main())
