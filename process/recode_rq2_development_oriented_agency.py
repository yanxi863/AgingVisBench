import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# =========================
# 路径配置
# =========================
BASE_DIR = PROJECT_ROOT / "outputs"
MODEL_DIRS = ["GPT", "jimeng", "midjourney", "tongyi"]
OUTPUT_SUFFIX = "_cn_agency_rule_based.csv"
CODEBOOK_PATH = BASE_DIR / "action_type_agency_codebook_rule_based.csv"
REVIEW_PATH = BASE_DIR / "action_type_agency_review_needed_rule_based.csv"

# =========================
# 中文变量名
# =========================
COLUMN_CN_MAP = {
    "Model": "模型",
    "Folder": "文件夹",
    "Filename": "文件名",
    "Image_Path": "图片路径",
    "Age": "年龄标签",
    "Nationality": "国籍",
    "Gender": "性别",
    "Action_Type": "行动类型",
    "Agency_Level": "原主体性水平",
    "Agency_Orientation": "主体性取向",
    "Development_Oriented_Agency": "发展取向主体性",
    "Scene_Type": "场景类型",
    "Space_Type": "空间类型",
    "Objects": "物体",
    "Modern_Object": "现代物体",
    "Traditional_Cultural_Marker": "传统文化标记",
    "Medical_Object_Count": "医疗辅助物体数量",
    "Environment_Type": "环境类型",
    "Area_Ratio": "人物面积占比",
    "Center_Distance": "中心距离",
    "Yaw": "头部偏航角",
    "Pitch": "头部俯仰角",
    "Face_Detected": "是否检测到面部",
    "Spine_Angle": "脊柱角度",
    "Arm_Curl": "手臂弯曲度",
    "Leg_Curl": "腿部弯曲度",
    "BHI": "身体姿态指数",
    "Num_Persons": "人物数量",
    "Is_Alone": "是否独处",
    "Bg_Brightness": "背景亮度",
    "Bg_Saturation": "背景饱和度",
    "Image_Entropy_Full": "整图熵",
    "Image_Entropy_Background": "背景熵",
    "Age_Num": "年龄数值",
    "Age_Group": "年龄组",
    "Primary_Action": "主要行动",
    "Has_Action": "是否有行动",
    "Has_Medical_Object": "是否有医疗辅助物体",
    "Num_Persons_Group": "人物数量组",
    "Agency_passive": "原主体性_被动",
    "Agency_active": "原主体性_主动",
    "Scene_home": "场景_家庭",
    "Scene_office": "场景_办公室",
    "Scene_hospital": "场景_医院",
    "Scene_street": "场景_街道",
    "Scene_park": "场景_公园",
    "Scene_yard": "场景_庭院",
    "Scene_outdoor_other": "场景_其他户外",
    "Scene_unknown": "场景_未知",
    "Space_indoor": "空间_室内",
    "Space_courtyard": "空间_庭院",
    "Space_outdoor": "空间_户外",
    "Space_unknown": "空间_未知",
    "Environment_indoor": "环境_室内",
    "Environment_courtyard": "环境_庭院",
    "Environment_outdoor": "环境_户外",
    "Environment_unknown": "环境_未知",
    "AgeGroup_under_60": "年龄组_60岁以下",
    "AgeGroup_60s": "年龄组_60多岁",
    "AgeGroup_70s": "年龄组_70多岁",
    "AgeGroup_80s": "年龄组_80多岁",
    "AgeGroup_90_plus": "年龄组_90岁及以上",
}

# =========================
# 规则说明
# =========================
# 核心原则：默认把普通日常、家务、饮食、购物、园艺、休闲、普通移动编码为 maintenance。
# 只有明确出现社会互动、学习/工作/创作/运动/技能性活动时，才编码为发展取向主体性 1。

SOCIAL_PATTERNS = [
    r"\btalking\b",
    r"\bchatting\b",
    r"\binteracting\b",
    r"\bhelping\b",
    r"\bcaring for\b",
    r"\bholding hands\b",
    r"\bwith others\b",
    r"\bgroup\b",
    r"\bfamily gathering\b",
    r"\bteaching\b",
    r"\bexplaining\b",
    r"\bhanding over\b",
    r"\bhanding money\b",
    r"\bexchanging money\b",
    r"\breading to children\b",
    r"\bplaying with\b",
    r"\bplaying (a )?board game\b",
    r"\bplaying chess\b",
    r"\bplaying checkers\b",
    r"\bmoving chess pieces\b",
    r"\bmoving a chess piece\b",
    r"\bplacing a piece on a board\b",
    r"\bpointing at game pieces\b",
    r"\beating and serving food\b",
    r"\bserving food\b",
]

ACHIEVEMENT_PATTERNS = [
    r"\bstudying\b",
    r"\bwriting\b",
    r"\btyping\b",
    r"\bkeyboard\b",
    r"\busing (a )?computer\b",
    r"\busing (a )?laptop\b",
    r"\bworking at (a )?desk\b",
    r"\bworking at (a )?table\b",
    r"\bworking on (a )?laptop\b",
    r"\bread\w*\b",
    r"\breading an? open book\b",
    r"\breading a document\b",
    r"\breading a letter\b",
    r"\breading and writing\b",
    r"\bwriting and reading\b",
    r"\breading or examining a document\b",
    r"\bpainting\b",
    r"\bdrawing\b",
    r"\bcalligraphy\b",
    r"\bpaintbrush\b",
    r"\bplaying guitar\b",
    r"\bplaying piano\b",
    r"\bmusical instrument\b",
    r"\bperforming\b",
    r"\bdancing\b",
    r"\bexercising\b",
    r"\bexercise\b",
    r"\brunning\b",
    r"\bbasketball\b",
    r"\byoga\b",
    r"\btai chi\b",
    r"\bmartial arts\b",
    r"\btreadmill\b",
    r"\bweights?\b",
    r"\bdumbbell\b",
    r"\bpull-up\b",
    r"\bskateboarding\b",
    r"\bgolf\b",
    r"\bstretching\b",
    r"\bbalancing on one leg\b",
    r"\briding (a|an) (bicycle|bike|exercise bike)\b",
    r"\brepairing\b",
    r"\bbuilding\b",
    r"\bassembling\b",
    r"\busing (a )?tool\b",
    r"\bwith tools\b",
    r"\bhammer\b",
    r"\bsanding\b",
    r"\bcarving\b",
    r"\bshaping clay\b",
    r"\bpotter\b",
    r"\bbirdhouse\b",
    r"\bwooden object\b",
    r"\bwoven object\b",
    r"\bsewing\b",
    r"\bknitting\b",
    r"\bweaving\b",
    r"\bembroider",
    r"\bembroidery\b",
    r"\bcrafting\b",
    r"\bhandicrafts?\b",
    r"\bworking on embroidery\b",
    r"\bworking with clay\b",
    r"\bworking with thread\b",
    r"\bworking with sewing machine\b",
    r"\bworking with tools\b",
    r"\bworking on a puzzle\b",
    r"\bassembling a puzzle\b",
    r"\bpuzzle piece\b",
    r"\bcrossword\b",
    r"\busing a magnifying glass\b",
]

MAINTENANCE_PATTERNS = [
    r"\bsitting\b",
    r"\bstanding\b",
    r"\bresting\b",
    r"\blying\b",
    r"\bsleeping\b",
    r"\bposing\b",
    r"\bwaiting\b",
    r"\blooking\b",
    r"\bholding\b",
    r"\bwalking\b",
    r"\bdriving\b",
    r"\bsmoking\b",
    r"\bdrinking\b",
    r"\beating\b",
    r"\bcooking\b",
    r"\bbaking\b",
    r"\bpreparing (food|tea|coffee|a drink|drink|vegetables|greens)\b",
    r"\bmaking (a drink|tea|coffee|dumplings|noodles)\b",
    r"\bfood\b",
    r"\bvegetables?\b",
    r"\bproduce\b",
    r"\bdumplings?\b",
    r"\bdough\b",
    r"\bpan\b",
    r"\bpot\b",
    r"\bbowl\b",
    r"\bkettle\b",
    r"\btea\b",
    r"\bcoffee\b",
    r"\bcleaning\b",
    r"\bwashing\b",
    r"\bsweeping\b",
    r"\bmopping\b",
    r"\blaundry\b",
    r"\bfolding (clothes|towels?|garment)\b",
    r"\bhanging clothes\b",
    r"\bwiping\b",
    r"\bshopping\b",
    r"\bgrocery\b",
    r"\bselecting\b",
    r"\bpushing (a )?(shopping )?cart\b",
    r"\bgardening\b",
    r"\bplanting\b",
    r"\bwatering\b",
    r"\btending to plants\b",
    r"\bpotted plants?\b",
    r"\bflowers?\b",
    r"\bpruning\b",
    r"\bharvesting\b",
    r"\bpicking\b",
    r"\busing (a )?phone\b",
    r"\busing phone\b",
    r"\busing (a )?tablet\b",
    r"\bwatching\b",
    r"\blistening\b",
    r"\bgame controller\b",
    r"\bremote control\b",
    r"\bmeditating\b",
    r"\byawning\b",
]

ACHIEVEMENT_FALSE_POSITIVE_PATTERNS = [
    r"\bworking with (food|a pot|a washing machine|an appliance)\b",
    r"\bholding a brush\b",
    r"\busing a game controller\b",
    r"\bplaying video game\b",
]

READING_MAINTENANCE_PATTERNS = [
    r"\bread\w*\b.*\b(cooking|cook|preparing food|preparing vegetables|cutting|chopping|stirring|pouring|cleaning|washing|sweeping|gardening|tending to plants|petting|drinking|eating|smoking|holding a cup|holding a mug|holding food|pushing a cart|shopping)\b",
    r"\b(cooking|cook|preparing food|preparing vegetables|cutting|chopping|stirring|pouring|cleaning|washing|sweeping|gardening|tending to plants|petting|drinking|eating|smoking|holding a cup|holding a mug|holding food|pushing a cart|shopping)\b.*\bread\w*\b",
]

AMBIGUOUS_PATTERNS = [
    r"\bobject\b",
    r"\bobjects\b",
    r"\bitems\b",
    r"\bsomething\b",
    r"\bdevice\b",
    r"\btablet\b",
    r"\bscreen\b",
    r"\bgesture\b",
    r"\bmovement\b",
    r"\bworking with hands\b",
    r"\bworking with small objects?\b",
    r"\bhandling\b",
    r"\bexamining\b",
    r"\binspecting\b",
]


def normalize_action(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_for_matching(action: str) -> str:
    text = action.lower().strip()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def matches_any(text: str, patterns: List[str]) -> Tuple[bool, str]:
    for pattern in patterns:
        if re.search(pattern, text):
            return True, pattern
    return False, ""


def derive_binary(orientation: str) -> Any:
    if orientation == "maintenance":
        return 0
    if orientation in {"social_participation", "achievement_growth"}:
        return 1
    return pd.NA


def classify_action(action: str) -> Dict[str, Any]:
    text = normalize_for_matching(action)
    if not text or text in {"unknown", "unclear", "none", "null", "nan"}:
        return {
            "Agency_Orientation": "unclear",
            "Development_Oriented_Agency": pd.NA,
            "Review_Needed": 1,
            "Coding_Rule": "empty_or_unknown",
        }

    read_achievement, read_rule = matches_any(text, [r"\bread\w*\b"])
    reading_maintenance, reading_rule = matches_any(text, READING_MAINTENANCE_PATTERNS)
    social, social_rule = matches_any(text, SOCIAL_PATTERNS)
    achievement_false_positive, false_positive_rule = matches_any(text, ACHIEVEMENT_FALSE_POSITIVE_PATTERNS)
    achievement, achievement_rule = matches_any(text, ACHIEVEMENT_PATTERNS)
    maintenance, maintenance_rule = matches_any(text, MAINTENANCE_PATTERNS)
    ambiguous, ambiguous_rule = matches_any(text, AMBIGUOUS_PATTERNS)

    review_needed = 0
    review_reasons: List[str] = []

    if social:
        orientation = "social_participation"
        coding_rule = f"social:{social_rule}"
    elif reading_maintenance:
        orientation = "maintenance"
        coding_rule = f"maintenance_reading:{reading_rule}"
    elif read_achievement:
        orientation = "achievement_growth"
        coding_rule = f"achievement_read:{read_rule}"
    elif achievement and not achievement_false_positive:
        orientation = "achievement_growth"
        coding_rule = f"achievement:{achievement_rule}"
    elif maintenance:
        orientation = "maintenance"
        coding_rule = f"maintenance:{maintenance_rule}"
    else:
        orientation = "maintenance"
        coding_rule = "default_maintenance"
        review_needed = 1
        review_reasons.append("default_maintenance_no_specific_rule")

    if ambiguous:
        review_needed = 1
        review_reasons.append(f"ambiguous:{ambiguous_rule}")

    if achievement_false_positive:
        review_needed = 1
        review_reasons.append(f"achievement_false_positive_guard:{false_positive_rule}")

    if achievement and maintenance and orientation == "achievement_growth":
        review_needed = 1
        review_reasons.append("mixed_achievement_and_maintenance_cues")

    if social and achievement:
        review_needed = 1
        review_reasons.append("mixed_social_and_achievement_cues")

    if review_reasons:
        coding_rule = f"{coding_rule}; review={'|'.join(review_reasons)}"

    return {
        "Agency_Orientation": orientation,
        "Development_Oriented_Agency": derive_binary(orientation),
        "Review_Needed": review_needed,
        "Coding_Rule": coding_rule,
    }


def collect_csv_paths() -> List[Path]:
    paths = []
    for model_dir in MODEL_DIRS:
        folder = BASE_DIR / model_dir
        expected_file = folder / f"{model_dir}_stats_ready.csv"
        if not expected_file.exists():
            raise FileNotFoundError(f"未找到文件：{expected_file}")
        paths.append(expected_file)
    return paths


def collect_action_counts(csv_paths: List[Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for path in csv_paths:
        df = pd.read_csv(path, encoding="utf-8-sig")
        if "Action_Type" not in df.columns:
            raise KeyError(f"{path} 中未找到 Action_Type 列")
        for value in df["Action_Type"].tolist():
            action = normalize_action(value)
            if action:
                counts[action] = counts.get(action, 0) + 1
    return counts


def build_codebook(action_counts: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
    codebook: Dict[str, Dict[str, Any]] = {}
    for action in sorted(action_counts):
        coded = classify_action(action)
        coded["Count"] = action_counts[action]
        codebook[action] = coded
    return codebook


def save_codebook(codebook: Dict[str, Dict[str, Any]]) -> None:
    rows = []
    for action in sorted(codebook):
        coded = codebook[action]
        rows.append({
            "行动类型": action,
            "主体性取向": coded["Agency_Orientation"],
            "发展取向主体性": coded["Development_Oriented_Agency"],
            "出现次数": coded["Count"],
            "是否需要人工复核": coded["Review_Needed"],
            "匹配规则": coded["Coding_Rule"],
        })
    pd.DataFrame(rows).to_csv(CODEBOOK_PATH, index=False, encoding="utf-8-sig")
    print(f"规则码本已保存：{CODEBOOK_PATH}")


def save_review_list(codebook: Dict[str, Dict[str, Any]]) -> None:
    rows = []
    for action, coded in codebook.items():
        if coded["Review_Needed"] == 1:
            rows.append({
                "行动类型": action,
                "主体性取向": coded["Agency_Orientation"],
                "发展取向主体性": coded["Development_Oriented_Agency"],
                "出现次数": coded["Count"],
                "匹配规则": coded["Coding_Rule"],
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["出现次数", "行动类型"], ascending=[False, True])
    df.to_csv(REVIEW_PATH, index=False, encoding="utf-8-sig")
    print(f"人工复核清单已保存：{REVIEW_PATH}")


def insert_after_action_type(df: pd.DataFrame, codebook: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    if "Action_Type" not in df.columns:
        raise KeyError("未找到 Action_Type 列")

    agency_orientation = []
    developmental_agency = []
    for value in df["Action_Type"].tolist():
        action = normalize_action(value)
        coded = codebook.get(action)
        if coded is None:
            coded = classify_action(action)
        agency_orientation.append(coded["Agency_Orientation"])
        developmental_agency.append(coded["Development_Oriented_Agency"])

    result = df.copy()
    for column in ["Agency_Orientation", "Development_Oriented_Agency"]:
        if column in result.columns:
            result = result.drop(columns=[column])

    insert_at = result.columns.get_loc("Action_Type") + 1
    result.insert(insert_at, "Agency_Orientation", agency_orientation)
    result.insert(insert_at + 1, "Development_Oriented_Agency", developmental_agency)
    return result


def rename_columns_to_chinese(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={column: COLUMN_CN_MAP.get(column, column) for column in df.columns})


def write_recoded_csvs(csv_paths: List[Path], codebook: Dict[str, Dict[str, Any]]) -> None:
    for path in csv_paths:
        df = pd.read_csv(path, encoding="utf-8-sig")
        recoded = insert_after_action_type(df, codebook)
        recoded_cn = rename_columns_to_chinese(recoded)
        output_path = path.with_name(path.stem + OUTPUT_SUFFIX)
        recoded_cn.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"已输出：{output_path}")


def print_summary(codebook: Dict[str, Dict[str, Any]]) -> None:
    summary = {}
    for coded in codebook.values():
        orientation = coded["Agency_Orientation"]
        summary[orientation] = summary.get(orientation, 0) + 1
    print("唯一 Action_Type 编码分布：")
    for key in ["maintenance", "social_participation", "achievement_growth", "unclear"]:
        print(f"- {key}: {summary.get(key, 0)}")
    review_count = sum(1 for coded in codebook.values() if coded["Review_Needed"] == 1)
    print(f"需要人工复核的唯一 Action_Type 数量：{review_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recode action labels into development-oriented agency variables.")
    parser.add_argument("--base-dir", default=str(BASE_DIR), help="Directory containing one subdirectory per model.")
    parser.add_argument("--models", nargs="*", default=MODEL_DIRS, help="Model subdirectory names to process.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global BASE_DIR, MODEL_DIRS, CODEBOOK_PATH, REVIEW_PATH
    BASE_DIR = Path(args.base_dir).expanduser().resolve()
    MODEL_DIRS = args.models
    CODEBOOK_PATH = BASE_DIR / "action_type_agency_codebook_rule_based.csv"
    REVIEW_PATH = BASE_DIR / "action_type_agency_review_needed_rule_based.csv"

    csv_paths = collect_csv_paths()
    print("将处理以下原始文件：")
    for path in csv_paths:
        print(f"- {path}")

    action_counts = collect_action_counts(csv_paths)
    codebook = build_codebook(action_counts)
    save_codebook(codebook)
    save_review_list(codebook)
    write_recoded_csvs(csv_paths, codebook)
    print_summary(codebook)


if __name__ == "__main__":
    main()
