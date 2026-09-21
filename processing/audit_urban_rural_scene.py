import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATA = PROJECT_ROOT / "outputs"
OUTPUT_DATA = PROJECT_ROOT / "outputs" / "clean_data"
SAVE_EVERY = 20
REQUEST_SLEEP = 0.5
RETRY_TIMES = 3
RETRY_SLEEP = 1.5
DASHSCOPE_BASE_URL = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
DASHSCOPE_MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen-vl-plus")
VALID_SCENE_VALUES = {"rural", "urban", "unknown_or_mixed"}
VALID_CONFIDENCE_VALUES = {"high", "medium", "low"}
MODEL_FILES = {
    "GPT": SOURCE_DATA / "GPT" / "GPT_stats_ready_cn_agency_rule_based.csv",
    "jimeng": SOURCE_DATA / "jimeng" / "jimeng_stats_ready_cn_agency_rule_based.csv",
    "midjourney": SOURCE_DATA / "midjourney" / "midjourney_stats_ready_cn_agency_rule_based.csv",
    "tongyi": SOURCE_DATA / "tongyi" / "tongyi_stats_ready_cn_agency_rule_based.csv",
}

URBAN_RURAL_PROMPT = """
你是一名传播学研究助理，正在为图像中的“城乡场景”变量做补充编码。

请严格依据图像中【可以直接观察到的视觉线索】判断主要人物所处环境，不要根据人物年龄、国籍、服装气质或故事背景进行推测。
如果画面中没有足够线索，请选择 unknown_or_mixed。
只输出 JSON，不要输出解释性文字。

变量 urban_rural_scene 只能取以下三类：

1. rural
图像中存在明确乡村、农业、村落或非城市化生活空间线索。
户外线索包括：农田、菜地、果园、乡村道路、村庄、农舍、低密度乡镇建筑、牲畜、农具、自然山野与农业生产/乡村生活环境。
室内图像如果出现明确乡村居住、生产或生活线索，也可以判为 rural，例如农舍/乡村厨房、土墙或明显乡村民居结构、农具、粮食或作物储存、牲畜、可见庭院农事空间。
仅有普通植物、普通庭院、木桌、老旧家具或传统装饰，不足以判为 rural。

2. urban
图像中存在明确城市、城镇建成环境或现代城市生活空间线索。
户外线索包括：高楼、街道、商店、写字楼、医院、现代小区、城市道路、交通设施、商业空间、公共广场、城市公园。
室内图像如果出现明确城市生活或机构空间线索，也可以判为 urban，例如现代公寓/小区室内、办公室、医院/诊所、商场/商店、餐厅、图书馆、公共服务机构、城市交通或现代商业设施可见。

3. unknown_or_mixed
图像缺乏足够城乡线索，或城乡线索混合、模糊、被遮挡，或只有人物特写/中性背景。
普通家庭室内、普通旧家具、普通盆栽、传统装饰或无法定位的居家场景，如果不能明确指向乡村或城市，应判为 unknown_or_mixed。

Return only this JSON:
{
  "urban_rural_scene": "rural / urban / unknown_or_mixed",
  "confidence": "high / medium / low",
  "evidence": "short English visual evidence"
}
""".strip()


def safe_model_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_\-]+", "_", name.strip()).strip("_") or "model"


def normalize_scene_value(value: Any) -> str:
    if value is None:
        return "unknown_or_mixed"
    s = str(value).strip().lower()
    s = s.replace(" ", "_").replace("-", "_")
    alias_map = {
        "rural_scene": "rural",
        "countryside": "rural",
        "village": "rural",
        "farm": "rural",
        "farmland": "rural",
        "urban_scene": "urban",
        "city": "urban",
        "cityscape": "urban",
        "town": "urban",
        "unknown": "unknown_or_mixed",
        "unclear": "unknown_or_mixed",
        "mixed": "unknown_or_mixed",
        "unknown_mixed": "unknown_or_mixed",
        "ambiguous": "unknown_or_mixed",
        "neutral": "unknown_or_mixed",
        "null": "unknown_or_mixed",
        "none": "unknown_or_mixed",
    }
    if s in VALID_SCENE_VALUES:
        return s
    return alias_map.get(s, "unknown_or_mixed")


def normalize_confidence(value: Any) -> str:
    if value is None:
        return "low"
    s = str(value).strip().lower()
    if s in VALID_CONFIDENCE_VALUES:
        return s
    if s in {"certain", "strong"}:
        return "high"
    if s in {"moderate", "middle"}:
        return "medium"
    return "low"


def clean_evidence(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())[:300]


def safe_parse_json(text: str) -> Dict[str, str]:
    parsed = {
        "urban_rural_scene": "unknown_or_mixed",
        "confidence": "low",
        "evidence": "",
        "raw_response": text or "",
    }
    try:
        if not text:
            return parsed
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`").replace("json", "", 1).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return parsed
        obj = json.loads(match.group())
        parsed["urban_rural_scene"] = normalize_scene_value(obj.get("urban_rural_scene"))
        parsed["confidence"] = normalize_confidence(obj.get("confidence"))
        parsed["evidence"] = clean_evidence(obj.get("evidence"))
        return parsed
    except Exception as exc:
        parsed["evidence"] = f"JSON parse error: {exc}"
        return parsed


def call_vlm_api(img_path: str, dashscope_module) -> Dict[str, str]:
    for i in range(RETRY_TIMES):
        try:
            response = dashscope_module.MultiModalConversation.call(
                model=DASHSCOPE_MODEL,
                messages=[{"role": "user", "content": [{"image": img_path}, {"text": URBAN_RURAL_PROMPT}]}],
            )
            content = response["output"]["choices"][0]["message"]["content"]
            if isinstance(content, list):
                text_parts = [part["text"] for part in content if isinstance(part, dict) and "text" in part]
                content = "\n".join(text_parts).strip() if text_parts else str(content)
            return safe_parse_json(str(content))
        except Exception as exc:
            print(f"[Retry {i + 1}/{RETRY_TIMES}] {img_path} -> {exc}")
            time.sleep(RETRY_SLEEP)
    return safe_parse_json("")


def make_audit_input(row: pd.Series) -> Dict[str, Any]:
    return {
        "模型": row.get("模型", ""),
        "文件夹": row.get("文件夹", ""),
        "文件名": row.get("文件名", ""),
        "图片路径": row.get("图片路径", ""),
        "年龄标签": row.get("年龄标签", ""),
        "国籍": row.get("国籍", ""),
        "性别": row.get("性别", ""),
        "场景类型": row.get("场景类型", ""),
        "环境类型": row.get("环境类型", ""),
    }


def audit_record(row: pd.Series, dashscope_module) -> Dict[str, Any]:
    item = make_audit_input(row)
    parsed = call_vlm_api(str(item["图片路径"]), dashscope_module)
    scene = normalize_scene_value(parsed.get("urban_rural_scene"))
    item.update({
        "城乡场景": scene,
        "乡村场景": 1 if scene == "rural" else 0,
        "城市场景": 1 if scene == "urban" else 0,
        "城乡场景_置信度": normalize_confidence(parsed.get("confidence")),
        "城乡场景_证据": clean_evidence(parsed.get("evidence")),
        "审计时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return item


def load_checkpoint(path: Path) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def build_done_keys(df: pd.DataFrame) -> Set[Tuple[str, str, str, str]]:
    required = {"模型", "文件夹", "文件名", "图片路径"}
    if df.empty or not required.issubset(df.columns):
        return set()
    return set(zip(
        df["模型"].astype(str),
        df["文件夹"].astype(str),
        df["文件名"].astype(str),
        df["图片路径"].astype(str),
    ))



def audit_one_model(model: str, source_csv: Path, output_root: Path, limit: Optional[int], skip_api: bool) -> Dict[str, Any]:
    if skip_api:
        return {"model": model, "status": "skipped_api", "source_csv": str(source_csv)}

    import dashscope

    if not source_csv.exists():
        raise FileNotFoundError(f"未找到源CSV: {source_csv}")
    source_df = pd.read_csv(source_csv, encoding="utf-8-sig")
    work_df = source_df.head(limit).copy() if limit is not None else source_df.copy()
    out_dir = output_root / model
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = safe_model_name(model)
    checkpoint = out_dir / f"{safe_name}_urban_rural_scene_audit_checkpoint.csv"
    audit_csv = out_dir / f"{safe_name}_urban_rural_scene_audit.csv"
    final_csv = out_dir / source_csv.name

    existing_df = load_checkpoint(checkpoint)
    records: List[Dict[str, Any]] = existing_df.to_dict("records") if not existing_df.empty else []
    done = build_done_keys(existing_df)

    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("未检测到 DASHSCOPE_API_KEY，无法运行城乡场景补充审计。")
    dashscope.base_http_api_url = DASHSCOPE_BASE_URL
    dashscope.api_key = api_key

    for idx, (_, row) in enumerate(work_df.iterrows(), start=1):
        item = make_audit_input(row)
        key = (str(item["模型"]), str(item["文件夹"]), str(item["文件名"]), str(item["图片路径"]))
        if key in done:
            continue
        print(f"[UrbanRural {model}] {idx}/{len(work_df)} {item['图片路径']}")
        try:
            records.append(audit_record(row, dashscope))
        except Exception as exc:
            failed = item | {
                "城乡场景": "unknown_or_mixed",
                "乡村场景": 0,
                "城市场景": 0,
                "城乡场景_置信度": "low",
                "城乡场景_证据": "",
                "城乡场景_error": str(exc),
                "审计时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            records.append(failed)
        done.add(key)
        if len(records) % SAVE_EVERY == 0:
            pd.DataFrame(records).to_csv(checkpoint, index=False, encoding="utf-8-sig")
        if not skip_api:
            time.sleep(REQUEST_SLEEP)

    audit_df = pd.DataFrame(records)
    audit_df.to_csv(audit_csv, index=False, encoding="utf-8-sig")
    audit_df.to_csv(checkpoint, index=False, encoding="utf-8-sig")

    if limit is None:
        merged = merge_audit_columns(source_df, audit_df)
    else:
        merged_sample = merge_audit_columns(work_df, audit_df)
        merged = source_df.copy()
        sample_keys = ["模型", "文件夹", "文件名", "图片路径"]
        add_cols = ["城乡场景", "乡村场景", "城市场景", "城乡场景_置信度", "城乡场景_证据"]
        merged = merged.merge(merged_sample[sample_keys + add_cols], on=sample_keys, how="left")
    merged.to_csv(final_csv, index=False, encoding="utf-8-sig")

    value_counts = merged["城乡场景"].value_counts(dropna=False).to_dict() if "城乡场景" in merged.columns else {}
    return {
        "model": model,
        "source_rows": len(source_df),
        "audited_rows": len(audit_df),
        "final_rows": len(merged),
        "output_csv": str(final_csv),
        "audit_csv": str(audit_csv),
        "checkpoint_csv": str(checkpoint),
        "value_counts": json.dumps(value_counts, ensure_ascii=False),
    }


def write_validation(output_root: Path, rows: List[Dict[str, Any]], limit: Optional[int]) -> None:
    validation = pd.DataFrame(rows)
    validation.insert(0, "run_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    validation.insert(1, "source_data", str(SOURCE_DATA))
    validation.insert(2, "output_data", str(output_root))
    validation.insert(3, "limit", "" if limit is None else limit)
    validation.to_csv(output_root / "urban_rural_scene_audit_validation.csv", index=False, encoding="utf-8-sig")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只补充审计城乡场景变量，并生成 clean_data_5.24 增强CSV。")
    parser.add_argument("--models", nargs="*", default=list(MODEL_FILES.keys()), choices=list(MODEL_FILES.keys()))
    parser.add_argument("--source-data", default=str(SOURCE_DATA))
    parser.add_argument("--output-data", default=str(OUTPUT_DATA))
    parser.add_argument("--limit", type=int, default=None, help="每个模型只审计前N行，用于小样本试跑。")
    parser.add_argument("--execute", action="store_true", help="实际执行 API 审计和文件写入。")
    parser.add_argument("--skip-api", action="store_true", help="不调用 API，并明确跳过本 stage；不生成伪标签。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global SOURCE_DATA, OUTPUT_DATA, MODEL_FILES
    SOURCE_DATA = Path(args.source_data)
    OUTPUT_DATA = Path(args.output_data)
    MODEL_FILES = {model: SOURCE_DATA / model / f"{model}_stats_ready_cn_agency_rule_based.csv" for model in MODEL_FILES}

    if args.skip_api:
        print("SKIPPED urban/rural audit: --skip-api was supplied; no files were written.")
        return
    if not args.execute:
        print("DRY-RUN urban/rural audit: add --execute to call the API and write files.")
        print(f"Source: {SOURCE_DATA}")
        print(f"Output: {OUTPUT_DATA}")
        return

    OUTPUT_DATA.mkdir(parents=True, exist_ok=True)
    summaries = []
    for model in args.models:
        summaries.append(audit_one_model(model, MODEL_FILES[model], OUTPUT_DATA, args.limit, args.skip_api))
    write_validation(OUTPUT_DATA, summaries, args.limit)
    print("Urban/rural scene audit finished")
    print(OUTPUT_DATA)
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__ == "__main__":
    main()
