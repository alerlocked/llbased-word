"""Seed implementation-rules knowledge into specialty profiles.

Sources the three layers of 《工艺规程细化量化规范性用语通用实施细则》:
  - mandatory params (附录A 带*)     -> Profile.knowledge (ConditionGroup)
  - normative templates (表1-9)      -> Profile.principles (Principle)

Run (cwd = project root, env = gywj):
    conda run -n gywj --no-capture-output python -m backend.scripts.seed_impl_rules --domain all

Idempotent: Profile.add_knowledge / add_principle dedupe by entity+conditions
and name+dimension, so reruns do not grow counts.
"""
import argparse
import sys
from pathlib import Path

# Allow running as a module (-m backend.scripts.seed_impl_rules) from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.models.profile import (  # noqa: E402
    Profile,
    ConditionGroup,
    Principle,
    get_default_welding_profile,
)

# Paths resolved via settings to avoid cwd-dependence (pitfalls T02)
PROFILES_DIR: Path = settings.DATA_DIR / "profiles"
COMPLIANCE_DIR: Path = settings.DATA_DIR / "compliance"

# Each entry: entity=process step (appears in text), conditions tags specialty,
# attributes = REQUIRED(示例值) drawn verbatim from 附录A.
MANDATORY_PARAMS: list[ConditionGroup] = [
    # ---- 装配 assembly (表8 / 附录A) ----
    ConditionGroup(
        entity="气密检查",
        conditions={"专业": "装配"},
        attributes={
            "检查压力": "REQUIRED(XXMPa)",
            "检查时间": "REQUIRED(XXmin)",
            "压降上限": "REQUIRED(不大于XXMPa)",
        },
        source="工艺规程细化量化通用实施细则-附录A/表8",
    ),
    ConditionGroup(
        entity="管路安装",
        conditions={"专业": "装配"},
        attributes={
            "充气压力": "REQUIRED(XXMPa)",
            "保压时间": "REQUIRED(XXmin)",
            "压降": "REQUIRED(不大于XXMPa)",
        },
        source="工艺规程细化量化通用实施细则-附录A/表8",
    ),
    ConditionGroup(
        entity="螺纹连接",
        conditions={"专业": "装配"},
        attributes={"拧紧力矩": "REQUIRED(如1.2N·m±0.2N·m)"},
        source="工艺规程细化量化通用实施细则-附录A/表8",
    ),
    ConditionGroup(
        entity="仓段对接",
        conditions={"专业": "装配"},
        attributes={"紧固件安装力矩": "REQUIRED(XXN·m)"},
        source="工艺规程细化量化通用实施细则-附录A/表8",
    ),
    # ---- 焊接 welding (表2 / 附录A) ----
    ConditionGroup(
        entity="TIG焊接",
        conditions={"专业": "焊接"},
        attributes={
            "钨极直径": "REQUIRED(ΦX～ΦXmm)",
            "焊接电流": "REQUIRED(XA～XA)",
            "氩气流量": "REQUIRED(XL/min)",
        },
        source="工艺规程细化量化通用实施细则-附录A/表2",
    ),
    ConditionGroup(
        entity="激光焊接",
        conditions={"专业": "焊接"},
        attributes={
            "激光功率": "REQUIRED(XW～XW)",
            "焊接速度": "REQUIRED(Xm/min或Xm/s)",
            "氩气流量": "REQUIRED(XL/min)",
        },
        source="工艺规程细化量化通用实施细则-附录A/表2",
    ),
    ConditionGroup(
        entity="真空钎焊",
        conditions={"专业": "焊接"},
        attributes={
            "真空度": "REQUIRED(XX-XPa)",
            "钎焊温度": "REQUIRED(X℃)",
            "保温时间": "REQUIRED(XXmin)",
        },
        source="工艺规程细化量化通用实施细则-附录A/表2",
    ),
    # ---- 涂装 coating (表3 表面工程) ----
    ConditionGroup(
        entity="喷涂",
        conditions={"专业": "涂装"},
        attributes={
            "环境温度": "REQUIRED(12~30°C)",
            "环境湿度": "REQUIRED(≤75%)",
        },
        source="工艺规程细化量化通用实施细则-附录A/表3",
    ),
    ConditionGroup(
        entity="固化",
        conditions={"专业": "涂装"},
        attributes={
            "固化温度": "REQUIRED(室温或60~80°C)",
            "固化时间": "REQUIRED(≥24h或1~2h)",
        },
        source="工艺规程细化量化通用实施细则-附录A/表3",
    ),
]

# Normative templates from 表1-9 + 附录B. Common + high-frequency only (~10).
PRINCIPLES: list[Principle] = [
    # ---- 通用 text_compliance / terminology ----
    Principle(
        dimension="text_compliance",
        name="量化控制禁不确定词",
        description="工艺规程量化控制项禁止使用‘大致/可能/大概/是否’等不确定表述，必须给出确定数值或范围。",
        check_expression="检查量化控制段落是否含不确定词(大致/可能/大概/是否)，命中即不合规。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表1~表9/附录B",
    ),
    Principle(
        dimension="terminology",
        name="禁模糊量词",
        description="禁止使用少量/少许/适量/适当/尽量/左右/大约/大部分等模糊量词，须以确定量值或可验证状态替代。",
        check_expression="全文检索模糊量词列表(见 compliance/sensitive_words.json)，命中须有量化替代。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-附录B-表B.1",
    ),
    Principle(
        dimension="data_validity",
        name="时间量须给区间",
        description="涉及时间的工序须给出确定区间而非‘一段时间后/XXmin以上’，如‘10min’或‘15min-20min’。",
        check_expression="检查时间表述是否含‘一段时间’‘以上’而无上限，命中即不合规。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-附录B-表B.1",
    ),
    # ---- 装配 ----
    Principle(
        dimension="terminology",
        name="涂胶禁模糊词",
        description="涂胶工序禁止‘少许/少量/适量’，须明确涂胶工具、涂胶位置、涂胶量/范围、胶层厚度、固化时间与温度。",
        check_expression="识别涂胶工序段落，检查是否含模糊量词且无量化涂胶量与胶层厚度。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表8",
    ),
    Principle(
        dimension="data_validity",
        name="螺纹拧紧力矩须量化",
        description="螺纹连接须给出拧紧力矩值及扭矩工具规格；有防松胶时须明胶液型号、涂抹量/长度及清理要求。",
        check_expression="查找螺纹连接/拧紧描述，验证是否给出力矩值(N·m)及工具规格。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表8",
    ),
    Principle(
        dimension="data_validity",
        name="气密检查参数齐全",
        description="气密/保压检查须明确充气压力、保压时间、压降上限(或真空度、保持时间、压强升高值)。",
        check_expression="识别气密检查段落，验证三个参数(压力/时间/压降)是否齐全。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表8",
    ),
    # ---- 焊接 ----
    Principle(
        dimension="data_validity",
        name="TIG焊接参数表述",
        description="TIG焊接须明确钨极直径、焊接电流、保护气体(氩气)流量；填丝焊须给焊丝牌号与规格。",
        check_expression="识别TIG焊接段落，验证钨极直径/电流/氩气流量是否齐全且为数值范围。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表2",
    ),
    Principle(
        dimension="data_validity",
        name="激光焊接参数表述",
        description="激光焊接须明确激光功率、焦点位置(离焦量)、焊接速度、保护气体压力/流量。",
        check_expression="识别激光焊接段落，验证激光功率/离焦量/焊接速度/氩气流量是否齐全。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表2",
    ),
    # ---- 涂装 ----
    Principle(
        dimension="data_validity",
        name="喷涂温湿度须量化",
        description="喷涂须明确环境温度、湿度要求，必要时应明确涂层厚度；如温度12~30°C、湿度≤75%。",
        check_expression="识别喷涂段落，验证环境温度与湿度是否均为确定数值/范围。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表3",
    ),
    Principle(
        dimension="data_validity",
        name="固化温时间须量化",
        description="喷涂后须明确涂料固化温度与固化时间，如室温干燥≥24h或60~80°C干燥1~2h。",
        check_expression="识别固化段落，验证固化温度与固化时间是否均为确定数值。",
        enabled=True,
        source="工艺规程细化量化通用实施细则-表3",
    ),
]

PRINCIPLE_BY_DOMAIN = {
    "assembly": [
        "量化控制禁不确定词", "禁模糊量词", "时间量须给区间",
        "涂胶禁模糊词", "螺纹拧紧力矩须量化", "气密检查参数齐全",
    ],
    "welding": [
        "量化控制禁不确定词", "禁模糊量词", "时间量须给区间",
        "TIG焊接参数表述", "激光焊接参数表述",
    ],
    "coating": [
        "量化控制禁不确定词", "禁模糊量词", "时间量须给区间",
        "喷涂温湿度须量化", "固化温时间须量化",
    ],
}

KNOWLEDGE_BY_DOMAIN = {
    "assembly": ["气密检查", "管路安装", "螺纹连接", "仓段对接"],
    "welding": ["TIG焊接", "激光焊接", "真空钎焊"],
    "coating": ["喷涂", "固化"],
}

_PRINCIPLE_INDEX = {p.name: p for p in PRINCIPLES}
_KNOWLEDGE_INDEX = {cg.entity: cg for cg in MANDATORY_PARAMS}


def _load_profile(domain: str) -> Profile:
    """Load existing profile or build a fresh default for the domain."""
    path = PROFILES_DIR / f"{domain}.json"
    if path.exists():
        return Profile.from_json(path)
    if domain == "assembly":
        # Build a minimal assembly profile (existing file is preserved by branch above)
        return Profile(id="default_assembly", user_id="default", domain="assembly")
    if domain == "welding":
        return get_default_welding_profile()
    # coating: brand-new
    return Profile(id="default_coating", user_id="default", domain="coating")


def seed_domain(domain: str) -> dict:
    """Seed knowledge + principles for one domain. Returns before/after counts."""
    profile = _load_profile(domain)
    before_k = len(profile.knowledge)
    before_p = len(profile.principles)

    for entity in KNOWLEDGE_BY_DOMAIN[domain]:
        profile.add_knowledge(_KNOWLEDGE_INDEX[entity])

    for pname in PRINCIPLE_BY_DOMAIN[domain]:
        profile.add_principle(_PRINCIPLE_INDEX[pname])

    out_path = PROFILES_DIR / f"{domain}.json"
    profile.to_json(out_path)

    return {
        "domain": domain,
        "path": str(out_path),
        "knowledge": f"{before_k}->{len(profile.knowledge)}",
        "principles": f"{before_p}->{len(profile.principles)}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed implementation rules into profiles")
    parser.add_argument(
        "--domain",
        choices=["assembly", "welding", "coating", "all"],
        default="all",
    )
    args = parser.parse_args(argv)

    targets = ["assembly", "welding", "coating"] if args.domain == "all" else [args.domain]
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"profiles_dir = {PROFILES_DIR}")
    for dom in targets:
        res = seed_domain(dom)
        print(
            f"[{res['domain']}] knowledge {res['knowledge']} | "
            f"principles {res['principles']} -> {res['path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
