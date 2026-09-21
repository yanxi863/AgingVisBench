import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMAGE_ROOT = os.path.join(PROJECT_ROOT, "data", "images")
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "outputs")
YOLO_WEIGHTS = os.environ.get("YOLO_WEIGHTS", os.path.join(PROJECT_ROOT, "models", "yolov8s.pt"))
DASHSCOPE_BASE_URL = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
DASHSCOPE_MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen-vl-plus")

DRY_RUN = True
RUN_CV = True
RUN_SEMANTIC = True
MERGE_RESULTS = True
MAX_IMAGES_PER_MODEL = None
SAVE_EVERY = 20
REQUEST_SLEEP = 0.5
RETRY_TIMES = 3
RETRY_SLEEP = 1.5

CONDA_COMMAND = os.environ.get("CONDA_EXE", "conda")
USE_PYTHON_M_CONDA = False
PIPELINE_PYTHON = os.environ.get("PIPELINE_PYTHON", "").strip()
VISION_PYTHON = os.environ.get("VISION_PYTHON", PIPELINE_PYTHON).strip()
AUDIT_PYTHON = os.environ.get("AUDIT_PYTHON", PIPELINE_PYTHON).strip()
VISION_ENV = "ai_vision"
AUDIT_ENV = "ai_audit"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SPLIT_FIRST_MODEL_KEYWORDS = ("gpt", "mj", "midjourney", "mid_journey")
MIN_PERSON_AREA_RATIO = 0.01

SEMANTIC_PROMPT = """
你是一名传播学研究助理，正在进行“老年形象的视觉再现审计”。

请严格依据图像中【可以直接观察到的视觉元素】进行判断：
- 不允许进行主观推测。
- 不允许脑补人物身份、文化背景、职业或故事。
- 如果无法确认，请输出 null、unknown 或 0。
- 只输出 JSON，不要输出解释性文字。
- 请优先判断画面中最主要的人物及其所处环境。
- Output all variable values in English.

1. Activity

action_type:
  Describe the observable physical action of the main person.
  Do not infer intention, occupation, identity, or backstory.
  Use a short English phrase.

agency_level:
  Classify the main person's agency level as one of:
  - passive
  - active

Classify as passive when the main person is only sitting, lying down, standing still, leaning, resting, sleeping, waiting, posing, smiling at the camera without another visible action, being helped, being fed, being supported while walking, being pushed in a wheelchair, or passively present.

Classify as active when the main person is visibly working, teaching, exercising, caring for another person, helping another person, repairing, building, making handicrafts, cooking, shopping, reading, writing, using a phone/computer/tablet/tool, gardening with tools, cleaning, driving, performing, leading, or actively talking to a visible person.

If uncertain between passive and active, choose passive.

2. Scene and Space

scene_type:
  Classify the main semantic environment as one of:
  home / office / hospital / street / park / yard / outdoor_other / unknown

space_type:
  Classify the physical spatial type as one of:
  indoor / courtyard / outdoor / unknown

3. Objects, Modernity, and Cultural Markers

objects:
  List up to 5 clearly visible objects in English.

modern_object_presence:
  1 = at least one clearly visible modern object appears.
  0 = no clearly visible modern object.

Count as modern objects only if they clearly belong to digital devices, modern transportation, modern household appliances, modern office/medical equipment, or modern urban infrastructure.

traditional_cultural_marker_presence:
  1 = at least one clearly visible traditional cultural marker appears.
  0 = no clearly visible traditional cultural marker.

Count as traditional cultural markers only if they clearly belong to traditional clothing or ethnic costume, temple, shrine, pagoda, ancestral hall, classical courtyard, old-style wooden house, calligraphy, lantern, incense burner, ritual object, folding fan, traditional musical instrument, religious/folk ceremonial object, or visibly classical/historical architecture.

medical_object_count:
  Count clearly visible medical or assistive objects: wheelchair, walker, walking cane, crutch, hospital bed, IV stand, medicine bottle, oxygen tube, medical monitor. If none, output 0.

environment_type:
  Classify the physical environment type as one of:
  - indoor
  - courtyard
  - outdoor
  - unknown

Definitions:
  - indoor: inside a building or enclosed room
  - courtyard: outside the house/building but visibly attached to a private residence, such as a courtyard, backyard, front yard, garden, or enclosed domestic outdoor space
  - outdoor: public or open outdoor space, such as street, park, field, mountain, riverside, market, open road, rural village, farmland, or natural landscape
  - unknown: cannot determine

Return only the following JSON:
{
  "action_type": "short English action phrase",
  "agency_level": "passive or active",
  "scene_type": "home / office / hospital / street / park / yard / outdoor_other / unknown",
  "space_type": "indoor / courtyard / outdoor / unknown",
  "objects": ["object1", "object2", "object3"],
  "modern_object_presence": 0,
  "traditional_cultural_marker_presence": 0,
  "medical_object_count": 0,
  "environment_type": "indoor / courtyard / outdoor / unknown"
}
""".strip()

VALID_AGENCY = {"passive", "active"}
VALID_SCENE = {"home", "office", "hospital", "street", "park", "yard", "outdoor_other", "unknown"}
VALID_SPACE = {"indoor", "courtyard", "outdoor", "unknown"}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def safe_model_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_\-]+", "_", name.strip()).strip("_") or "model"


def image_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def parse_group_parts(group_name: str) -> Tuple[str, str, str]:
    parts = group_name.split("_")
    age = parts[0] if len(parts) > 0 else "Unknown"
    nationality = parts[1] if len(parts) > 1 else "Unknown"
    gender = parts[2] if len(parts) > 2 else "Unknown"
    return age, nationality, gender


def find_group_name_for_image(path: str, model_root: str) -> str:
    parent = os.path.basename(os.path.dirname(path))
    if parent.lower() == "split":
        return os.path.basename(os.path.dirname(os.path.dirname(path)))
    rel_parts = os.path.relpath(path, model_root).split(os.sep)
    for part in reversed(rel_parts[:-1]):
        if re.match(r"^\d+yo_", part, flags=re.IGNORECASE):
            return part
    return parent


def collect_images_for_model(model_name: str, model_root: str, max_images: Optional[int]) -> List[Dict[str, str]]:
    model_lower = model_name.lower()
    split_first = any(keyword in model_lower for keyword in SPLIT_FIRST_MODEL_KEYWORDS)
    selected_paths: List[str] = []

    if split_first:
        for root, dirs, files in os.walk(model_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() != "__pycache__"]
            if os.path.basename(root).lower() != "split":
                continue
            for filename in files:
                path = os.path.join(root, filename)
                if image_file(path):
                    selected_paths.append(path)

    if not selected_paths:
        for root, dirs, files in os.walk(model_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in {"__pycache__", "split"}]
            for filename in files:
                path = os.path.join(root, filename)
                if image_file(path):
                    selected_paths.append(path)

    selected_paths = sorted(set(selected_paths))
    if max_images is not None:
        selected_paths = selected_paths[:max_images]

    records = []
    for path in selected_paths:
        group = find_group_name_for_image(path, model_root)
        age, nationality, gender = parse_group_parts(group)
        records.append({
            "Model": model_name,
            "Folder": group,
            "Filename": os.path.basename(path),
            "Age": age,
            "Nationality": nationality,
            "Gender": gender,
            "Image_Path": path,
        })
    return records


def discover_model_images(image_root: str, max_images: Optional[int]) -> Dict[str, List[Dict[str, str]]]:
    if not os.path.isdir(image_root):
        raise FileNotFoundError(f"未找到图片根目录: {image_root}")
    model_map = {}
    for name in sorted(os.listdir(image_root)):
        path = os.path.join(image_root, name)
        if not os.path.isdir(path):
            continue
        image_records = collect_images_for_model(name, path, max_images)
        if image_records:
            model_map[name] = image_records
    return model_map


def create_run_output_dir(output_root: str) -> str:
    ensure_dir(output_root)
    base = os.path.join(output_root, f"rq2_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    candidate = base
    suffix = 1
    while os.path.exists(candidate):
        candidate = f"{base}_{suffix}"
        suffix += 1
    ensure_dir(candidate)
    return candidate


def load_checkpoint(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def build_done_keys(df: pd.DataFrame) -> Set[Tuple[str, str, str, str]]:
    required = {"Model", "Folder", "Filename", "Image_Path"}
    if df.empty or not required.issubset(df.columns):
        return set()
    return set(zip(df["Model"].astype(str), df["Folder"].astype(str), df["Filename"].astype(str), df["Image_Path"].astype(str)))


def save_dataframe_both(df: pd.DataFrame, csv_path: str, xlsx_path: str) -> None:
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    try:
        df.to_excel(xlsx_path, index=False)
    except PermissionError:
        backup = xlsx_path.replace(".xlsx", f"_backup_{datetime.now().strftime('%H%M%S')}.xlsx")
        df.to_excel(backup, index=False)
    except ImportError as e:
        print(f"Excel dependency missing; CSV saved only: {csv_path} ({e})")


def calculate_head_pose(landmarks, W, H):
    nose = np.array([landmarks[1].x * W, landmarks[1].y * H, landmarks[1].z * W])
    left_eye = np.array([landmarks[33].x * W, landmarks[33].y * H, landmarks[33].z * W])
    right_eye = np.array([landmarks[263].x * W, landmarks[263].y * H, landmarks[263].z * W])
    chin = np.array([landmarks[152].x * W, landmarks[152].y * H, landmarks[152].z * W])
    eye_vector = (right_eye - left_eye) / (np.linalg.norm(right_eye - left_eye) + 1e-6)
    vertical_vector = (chin - nose) / (np.linalg.norm(chin - nose) + 1e-6)
    yaw = np.degrees(np.arctan2(eye_vector[2], eye_vector[0]))
    pitch = np.degrees(np.arctan2(vertical_vector[1], vertical_vector[2]))
    return yaw, pitch


def get_head_pose_with_fallback(img, bbox, face_mesh, cv2):
    H, W, _ = img.shape
    x1, y1, x2, y2 = map(int, bbox)
    scale = 1.2
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    w, h = (x2 - x1) * scale, (y2 - y1) * scale
    x1n, y1n = int(max(cx - w / 2, 0)), int(max(cy - h / 2, 0))
    x2n, y2n = int(min(cx + w / 2, W)), int(min(cy + h / 2, H))
    crop = img[y1n:y2n, x1n:x2n]
    if crop.size != 0:
        res = face_mesh.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        if res.multi_face_landmarks:
            yaw, pitch = calculate_head_pose(res.multi_face_landmarks[0].landmark, x2n - x1n, y2n - y1n)
            return yaw, pitch, 1
    res_full = face_mesh.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    if res_full.multi_face_landmarks:
        yaw, pitch = calculate_head_pose(res_full.multi_face_landmarks[0].landmark, W, H)
        return yaw, pitch, 1
    return np.nan, np.nan, 0


def calculate_BHI(pose_landmarks, crop_shape):
    try:
        lm = pose_landmarks.landmark
        h_c, w_c, _ = crop_shape
        left_shoulder = np.array([lm[11].x * w_c, lm[11].y * h_c])
        left_hip = np.array([lm[23].x * w_c, lm[23].y * h_c])
        spine_vector = left_shoulder - left_hip
        spine_angle = np.degrees(np.arctan2(spine_vector[1], spine_vector[0]))
        left_elbow = np.array([lm[13].x * w_c, lm[13].y * h_c])
        left_wrist = np.array([lm[15].x * w_c, lm[15].y * h_c])
        body_height = np.linalg.norm(left_shoulder - left_hip) + 1e-6
        arm_curl = 1 - (np.linalg.norm(left_wrist - left_elbow) / body_height)
        left_knee = np.array([lm[25].x * w_c, lm[25].y * h_c])
        left_ankle = np.array([lm[27].x * w_c, lm[27].y * h_c])
        leg_curl = 1 - (np.linalg.norm(left_ankle - left_knee) / body_height)
        spine_norm = spine_angle / 90
        BHI = 0.5 * spine_norm + 0.25 * arm_curl + 0.25 * leg_curl
        return spine_angle, arm_curl, leg_curl, BHI
    except Exception:
        return np.nan, np.nan, np.nan, np.nan


def get_valid_person_boxes(detections, W, H):
    persons = []
    for box in detections.boxes:
        if int(box.cls[0]) != 0:
            continue
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        area = max(0, x2 - x1) * max(0, y2 - y1)
        ratio = area / (W * H)
        if ratio >= MIN_PERSON_AREA_RATIO:
            persons.append(box)
    return persons


def build_background_mask(H, W, persons):
    mask = np.ones((H, W), dtype=bool)
    for box in persons:
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(W, x2)
        y2 = min(H, y2)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = False
    return mask


def compute_background_brightness_saturation(img_bgr, bg_mask, cv2):
    if bg_mask is None or bg_mask.sum() == 0:
        return np.nan, np.nan
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    s_channel = hsv[:, :, 1].astype(np.float32)
    v_channel = hsv[:, :, 2].astype(np.float32)
    bg_brightness = float(v_channel[bg_mask].mean()) if np.any(bg_mask) else np.nan
    bg_saturation = float(s_channel[bg_mask].mean()) if np.any(bg_mask) else np.nan
    return bg_brightness, bg_saturation


def compute_entropy_from_gray(gray_img, mask=None):
    pixels = gray_img[mask] if mask is not None else gray_img.reshape(-1)
    if pixels.size == 0:
        return np.nan
    hist = np.bincount(pixels, minlength=256).astype(np.float64)
    prob = hist / hist.sum()
    prob = prob[prob > 0]
    return float(-np.sum(prob * np.log2(prob)))


def cv_record_for_image(image_record, yolo_model, pose, face_mesh, cv2):
    record = dict(image_record)
    record.update({
        "Area_Ratio": np.nan,
        "Center_Distance": np.nan,
        "Yaw": np.nan,
        "Pitch": np.nan,
        "Face_Detected": 0,
        "Spine_Angle": np.nan,
        "Arm_Curl": np.nan,
        "Leg_Curl": np.nan,
        "BHI": np.nan,
        "Num_Persons": 0,
        "Is_Alone": np.nan,
        "Bg_Brightness": np.nan,
        "Bg_Saturation": np.nan,
        "Image_Entropy_Full": np.nan,
        "Image_Entropy_Background": np.nan,
    })
    img = cv2.imread(image_record["Image_Path"])
    if img is None:
        record["CV_Error"] = "cv2_read_failed"
        return record
    H, W, _ = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    detections = yolo_model(img, verbose=False)[0]
    persons = get_valid_person_boxes(detections, W=W, H=H)
    record["Num_Persons"] = len(persons)
    if len(persons) == 1:
        record["Is_Alone"] = 1
    elif len(persons) >= 2:
        record["Is_Alone"] = 0
    bg_mask = build_background_mask(H, W, persons)
    record["Bg_Brightness"], record["Bg_Saturation"] = compute_background_brightness_saturation(img, bg_mask, cv2)
    record["Image_Entropy_Full"] = compute_entropy_from_gray(gray)
    record["Image_Entropy_Background"] = compute_entropy_from_gray(gray, mask=bg_mask)
    if persons:
        main_person = sorted(persons, key=lambda x: (x.xyxy[0][2] - x.xyxy[0][0]) * (x.xyxy[0][3] - x.xyxy[0][1]), reverse=True)[0]
        x1, y1, x2, y2 = map(int, main_person.xyxy[0].cpu().numpy())
        person_area = (x2 - x1) * (y2 - y1)
        record["Area_Ratio"] = person_area / (W * H)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        record["Center_Distance"] = np.sqrt((cx - W / 2) ** 2 + (cy - H / 2) ** 2) / np.sqrt((W / 2) ** 2 + (H / 2) ** 2)
        yaw, pitch, face_detected = get_head_pose_with_fallback(img, (x1, y1, x2, y2), face_mesh, cv2)
        record["Yaw"] = yaw
        record["Pitch"] = pitch
        record["Face_Detected"] = face_detected
        crop = img[y1:y2, x1:x2]
        if crop.size != 0:
            pose_result = pose.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            if pose_result.pose_landmarks:
                spine_angle, arm_curl, leg_curl, bhi = calculate_BHI(pose_result.pose_landmarks, crop.shape)
                record["Spine_Angle"] = spine_angle
                record["Arm_Curl"] = arm_curl
                record["Leg_Curl"] = leg_curl
                record["BHI"] = bhi
    return record


def run_cv_worker(args) -> None:
    import cv2
    import mediapipe as mp
    from ultralytics import YOLO

    ensure_dir(args.output_dir)
    manifest_df = pd.read_csv(args.manifest, encoding="utf-8-sig")
    image_records = manifest_df.to_dict("records")
    safe_name = safe_model_name(args.model)
    checkpoint = os.path.join(args.output_dir, f"{safe_name}_cv_checkpoint.csv")
    existing_df = load_checkpoint(checkpoint)
    records = existing_df.to_dict("records") if not existing_df.empty else []
    done = build_done_keys(existing_df)

    if not os.path.exists(args.yolo_weights):
        raise FileNotFoundError(
            f"未找到 YOLO 权重: {args.yolo_weights}。请通过 --yolo-weights 或 YOLO_WEIGHTS 指定本地文件。"
        )
    yolo_model = YOLO(args.yolo_weights)
    pose = mp.solutions.pose.Pose(static_image_mode=True)
    face_mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True)

    for idx, image_record in enumerate(image_records, start=1):
        key = (image_record["Model"], image_record["Folder"], image_record["Filename"], image_record["Image_Path"])
        if key in done:
            continue
        print(f"[CV {args.model}] {idx}/{len(image_records)} {image_record['Image_Path']}")
        records.append(cv_record_for_image(image_record, yolo_model, pose, face_mesh, cv2))
        done.add(key)
        if len(records) % SAVE_EVERY == 0:
            pd.DataFrame(records).to_csv(checkpoint, index=False, encoding="utf-8-sig")

    df = pd.DataFrame(records)
    save_dataframe_both(df, os.path.join(args.output_dir, f"{safe_name}_cv.csv"), os.path.join(args.output_dir, f"{safe_name}_cv.xlsx"))
    df.to_csv(checkpoint, index=False, encoding="utf-8-sig")


def normalize_binary(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    s = str(x).strip().lower()
    if s in {"1", "true", "yes"}:
        return 1
    if s in {"0", "false", "no"}:
        return 0
    return None


def normalize_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(float(x))
    except Exception:
        return None


def normalize_list_of_str(x: Any, max_items: int = 5) -> List[str]:
    if x is None:
        return []
    if isinstance(x, str):
        x = [i.strip() for i in re.split(r"[,\n;/]+", x) if i.strip()]
    if not isinstance(x, list):
        return []
    return [str(item).strip() for item in x if str(item).strip()][:max_items]


def normalize_agency_semantic(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in VALID_AGENCY:
        return s
    if s in {"routine", "routine_active", "goal_directed", "goal-directed", "goal_directed_active"}:
        return "active"
    if s == "inactive":
        return "passive"
    return None


def normalize_scene_semantic(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in VALID_SCENE:
        return s
    alias_map = {"house": "home", "indoors": "home", "indoor": "home", "road": "street", "garden": "yard", "outside": "outdoor_other", "outdoor": "outdoor_other"}
    return alias_map.get(s, "unknown")


def normalize_space_semantic(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in VALID_SPACE:
        return s
    alias_map = {"indoors": "indoor", "inside": "indoor", "yard": "courtyard", "backyard": "courtyard", "front yard": "courtyard", "garden": "courtyard", "outside": "outdoor", "outdoors": "outdoor"}
    return alias_map.get(s, "unknown")


def safe_parse_json(text: str) -> Dict[str, Any]:
    parsed = {
        "action_type": [],
        "agency_level": None,
        "scene_type": None,
        "space_type": None,
        "objects": [],
        "modern_object_presence": None,
        "traditional_cultural_marker_presence": None,
        "medical_object_count": None,
        "environment_type": None,
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
        parsed["action_type"] = normalize_list_of_str(obj.get("action_type"), max_items=3)
        parsed["agency_level"] = normalize_agency_semantic(obj.get("agency_level"))
        parsed["scene_type"] = normalize_scene_semantic(obj.get("scene_type"))
        parsed["space_type"] = normalize_space_semantic(obj.get("space_type"))
        parsed["objects"] = normalize_list_of_str(obj.get("objects"), max_items=5)
        parsed["modern_object_presence"] = normalize_binary(obj.get("modern_object_presence"))
        parsed["traditional_cultural_marker_presence"] = normalize_binary(obj.get("traditional_cultural_marker_presence"))
        parsed["medical_object_count"] = normalize_int(obj.get("medical_object_count"))
        parsed["environment_type"] = normalize_space_semantic(obj.get("environment_type"))
        return parsed
    except Exception as e:
        print("[JSON Error]", e)
        return parsed


def call_vlm_api(img_path: str, dashscope_module) -> Dict[str, Any]:
    for i in range(RETRY_TIMES):
        try:
            response = dashscope_module.MultiModalConversation.call(
                model=DASHSCOPE_MODEL,
                messages=[{"role": "user", "content": [{"image": img_path}, {"text": SEMANTIC_PROMPT}]}],
            )
            content = response["output"]["choices"][0]["message"]["content"]
            if isinstance(content, list):
                text_parts = [part["text"] for part in content if isinstance(part, dict) and "text" in part]
                content = "\n".join(text_parts).strip() if text_parts else str(content)
            return safe_parse_json(str(content))
        except Exception as e:
            print(f"[Retry {i + 1}/{RETRY_TIMES}] {img_path} -> {e}")
            time.sleep(RETRY_SLEEP)
    return safe_parse_json("")


def semantic_record_for_image(image_record: Dict[str, str], dashscope_module) -> Dict[str, Any]:
    semantic = call_vlm_api(image_record["Image_Path"], dashscope_module)
    return {
        **image_record,
        "Action_Type": ",".join(semantic.get("action_type", [])) if semantic.get("action_type") else "",
        "Agency_Level": semantic.get("agency_level"),
        "Scene_Type": semantic.get("scene_type"),
        "Space_Type": semantic.get("space_type"),
        "Objects": ",".join(semantic.get("objects", [])) if semantic.get("objects") else "",
        "Modern_Object": semantic.get("modern_object_presence"),
        "Traditional_Cultural_Marker": semantic.get("traditional_cultural_marker_presence"),
        "Medical_Object_Count": semantic.get("medical_object_count"),
        "Environment_Type": semantic.get("environment_type"),
    }


def run_semantic_worker(args) -> None:
    import dashscope

    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("未检测到 DASHSCOPE_API_KEY，无法运行 semantic audit。")
    dashscope.base_http_api_url = DASHSCOPE_BASE_URL
    dashscope.api_key = api_key

    ensure_dir(args.output_dir)
    manifest_df = pd.read_csv(args.manifest, encoding="utf-8-sig")
    image_records = manifest_df.to_dict("records")
    safe_name = safe_model_name(args.model)
    checkpoint = os.path.join(args.output_dir, f"{safe_name}_semantic_checkpoint.csv")
    existing_df = load_checkpoint(checkpoint)
    records = existing_df.to_dict("records") if not existing_df.empty else []
    done = build_done_keys(existing_df)

    for idx, image_record in enumerate(image_records, start=1):
        key = (image_record["Model"], image_record["Folder"], image_record["Filename"], image_record["Image_Path"])
        if key in done:
            continue
        print(f"[Semantic {args.model}] {idx}/{len(image_records)} {image_record['Image_Path']}")
        try:
            records.append(semantic_record_for_image(image_record, dashscope))
        except Exception as e:
            failed = dict(image_record)
            failed["Semantic_Error"] = str(e)
            records.append(failed)
        done.add(key)
        if len(records) % SAVE_EVERY == 0:
            pd.DataFrame(records).to_csv(checkpoint, index=False, encoding="utf-8-sig")
        time.sleep(REQUEST_SLEEP)

    df = pd.DataFrame(records)
    save_dataframe_both(df, os.path.join(args.output_dir, f"{safe_name}_semantic.csv"), os.path.join(args.output_dir, f"{safe_name}_semantic.xlsx"))
    df.to_csv(checkpoint, index=False, encoding="utf-8-sig")


def clean_text(x):
    if pd.isna(x):
        return np.nan
    x = str(x).strip()
    return x if x else np.nan


def normalize_numeric(x):
    if pd.isna(x):
        return np.nan
    try:
        return float(x)
    except Exception:
        return np.nan


def normalize_binary_stats(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, bool):
        return int(x)
    s = str(x).strip().lower()
    if s in ["1", "1.0", "true", "yes"]:
        return 1
    if s in ["0", "0.0", "false", "no"]:
        return 0
    return np.nan


def parse_primary_action(action_text):
    if pd.isna(action_text):
        return np.nan
    parts = [p.strip() for p in str(action_text).split(",") if p.strip()]
    return parts[0] if parts else np.nan


def normalize_age(age_value):
    if pd.isna(age_value):
        return np.nan
    match = re.search(r"\d+", str(age_value))
    return int(match.group()) if match else np.nan


def build_age_group(age_num):
    if pd.isna(age_num):
        return np.nan
    age_num = int(age_num)
    if age_num < 60:
        return "under_60"
    if 60 <= age_num <= 69:
        return "60s"
    if 70 <= age_num <= 79:
        return "70s"
    if 80 <= age_num <= 89:
        return "80s"
    return "90_plus"


def add_one_hot_columns(df, col_name, prefix, allowed_values):
    if col_name not in df.columns:
        return df
    for cat in allowed_values:
        new_col = f"{prefix}_{str(cat).replace(' ', '_').replace('-', '_')}"
        df[new_col] = df[col_name].apply(lambda x: 1 if pd.notna(x) and str(x) == str(cat) else 0)
    return df


def merge_and_prepare(model_name: str, output_dir: str) -> None:
    safe_name = safe_model_name(model_name)
    cv_path = os.path.join(output_dir, f"{safe_name}_cv.csv")
    semantic_path = os.path.join(output_dir, f"{safe_name}_semantic.csv")
    if not os.path.exists(cv_path) or not os.path.exists(semantic_path):
        print(f"跳过合并，缺少 CV 或 semantic 文件: {model_name}")
        return

    df_cv = pd.read_csv(cv_path, encoding="utf-8-sig")
    df_semantic = pd.read_csv(semantic_path, encoding="utf-8-sig")
    merge_keys = ["Model", "Folder", "Filename", "Age", "Nationality", "Gender", "Image_Path"]
    for df in [df_cv, df_semantic]:
        df.columns = [c.strip() for c in df.columns]
        for key in merge_keys:
            if key in df.columns:
                df[key] = df[key].astype(str).str.strip()

    df_cv = df_cv.drop_duplicates(subset=merge_keys, keep="first")
    df_semantic = df_semantic.drop_duplicates(subset=merge_keys, keep="first")
    df_merged = pd.merge(df_semantic, df_cv, on=merge_keys, how="outer", suffixes=("_vlm", "_cv"))
    preferred_order = [
        "Model", "Folder", "Filename", "Image_Path", "Age", "Nationality", "Gender",
        "Action_Type", "Agency_Level", "Scene_Type", "Space_Type", "Objects",
        "Modern_Object", "Traditional_Cultural_Marker", "Medical_Object_Count", "Environment_Type",
        "Area_Ratio", "Center_Distance", "Yaw", "Pitch", "Face_Detected",
        "Spine_Angle", "Arm_Curl", "Leg_Curl", "BHI", "Num_Persons", "Is_Alone",
        "Bg_Brightness", "Bg_Saturation", "Image_Entropy_Full", "Image_Entropy_Background",
    ]
    existing_cols = [c for c in preferred_order if c in df_merged.columns]
    other_cols = [c for c in df_merged.columns if c not in existing_cols]
    df_merged = df_merged[existing_cols + other_cols]

    df_stats = df_merged.copy()
    for col in ["Folder", "Filename", "Age", "Nationality", "Gender", "Action_Type", "Agency_Level", "Scene_Type", "Space_Type", "Objects"]:
        if col in df_stats.columns:
            df_stats[col] = df_stats[col].apply(clean_text)
    for col in ["Medical_Object_Count", "Area_Ratio", "Center_Distance", "Yaw", "Pitch", "Spine_Angle", "Arm_Curl", "Leg_Curl", "BHI", "Num_Persons", "Bg_Brightness", "Bg_Saturation", "Image_Entropy_Full", "Image_Entropy_Background"]:
        if col in df_stats.columns:
            df_stats[col] = df_stats[col].apply(normalize_numeric)
    for col in ["Modern_Object", "Traditional_Cultural_Marker", "Face_Detected", "Is_Alone"]:
        if col in df_stats.columns:
            df_stats[col] = df_stats[col].apply(normalize_binary_stats)
    if "Age" in df_stats.columns:
        df_stats["Age_Num"] = df_stats["Age"].apply(normalize_age)
        df_stats["Age_Group"] = df_stats["Age_Num"].apply(build_age_group)
    if "Action_Type" in df_stats.columns:
        df_stats["Primary_Action"] = df_stats["Action_Type"].apply(parse_primary_action)
        df_stats["Has_Action"] = df_stats["Action_Type"].apply(lambda x: 0 if pd.isna(x) or str(x).strip() == "" else 1)
    if "Medical_Object_Count" in df_stats.columns:
        df_stats["Has_Medical_Object"] = df_stats["Medical_Object_Count"].apply(lambda x: 1 if pd.notna(x) and x > 0 else 0 if pd.notna(x) else np.nan)
    if "Num_Persons" in df_stats.columns:
        df_stats["Num_Persons_Group"] = df_stats["Num_Persons"].apply(lambda x: np.nan if pd.isna(x) else "0" if x == 0 else "1" if x == 1 else "2_plus")
    df_stats = add_one_hot_columns(df_stats, "Agency_Level", "Agency", ["passive", "active"])
    df_stats = add_one_hot_columns(df_stats, "Scene_Type", "Scene", ["home", "office", "hospital", "street", "park", "yard", "outdoor_other", "unknown"])
    df_stats = add_one_hot_columns(df_stats, "Space_Type", "Space", ["indoor", "courtyard", "outdoor", "unknown"])
    df_stats = add_one_hot_columns(df_stats, "Environment_Type", "Environment", ["indoor", "courtyard", "outdoor", "unknown"])
    df_stats = add_one_hot_columns(df_stats, "Age_Group", "AgeGroup", ["under_60", "60s", "70s", "80s", "90_plus"])

    save_dataframe_both(df_merged, os.path.join(output_dir, f"{safe_name}_merged.csv"), os.path.join(output_dir, f"{safe_name}_merged.xlsx"))
    save_dataframe_both(df_stats, os.path.join(output_dir, f"{safe_name}_stats_ready.csv"), os.path.join(output_dir, f"{safe_name}_stats_ready.xlsx"))


def worker_python_for_env(env_name: str, python_executable: Optional[str] = None) -> Optional[str]:
    if python_executable:
        return python_executable
    mapping = {
        VISION_ENV: VISION_PYTHON,
        AUDIT_ENV: AUDIT_PYTHON,
    }
    candidate = mapping.get(env_name)
    if candidate:
        if os.path.exists(candidate):
            return candidate
        print(f"Configured Python executable does not exist and will be ignored: {candidate}")
    return None


def run_conda_worker(
    env_name: str,
    mode: str,
    manifest: str,
    output_dir: str,
    model_name: str,
    yolo_weights: str,
    python_executable: Optional[str] = None,
) -> None:
    script_args = [
        os.path.abspath(__file__),
        "--mode",
        mode,
        "--manifest",
        manifest,
        "--output-dir",
        output_dir,
        "--model",
        model_name,
        "--yolo-weights",
        yolo_weights,
        "--execute",
    ]
    direct_python = worker_python_for_env(env_name, python_executable)
    if direct_python:
        command = [direct_python, *script_args]
        print("Command:", " ".join(command))
        subprocess.run(command, check=True)
        return

    worker_args = ["run", "-n", env_name, "python", *script_args]
    command = [sys.executable, "-m", "conda", *worker_args] if USE_PYTHON_M_CONDA else [CONDA_COMMAND, *worker_args]
    print("Command:", " ".join(command))
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        fallback_command = [sys.executable, "-m", "conda", *worker_args]
        print("Conda command not found; fallback command:", " ".join(fallback_command))
        subprocess.run(fallback_command, check=True)


def run_orchestrator(args) -> None:
    max_images = args.max_images if args.max_images is not None else MAX_IMAGES_PER_MODEL
    dry_run = args.dry_run or (DRY_RUN and not args.execute)
    image_root = args.image_root or IMAGE_ROOT
    output_root = args.output_root or OUTPUT_ROOT
    python_executable = args.python_executable or PIPELINE_PYTHON or None
    yolo_weights = args.yolo_weights or YOLO_WEIGHTS
    model_images = discover_model_images(image_root, max_images)
    if args.models:
        requested = set(args.models)
        model_images = {name: rows for name, rows in model_images.items() if name in requested}
    if args.exclude_models:
        excluded = set(args.exclude_models)
        model_images = {name: rows for name, rows in model_images.items() if name not in excluded}

    summary_df = pd.DataFrame([{"Model": model, "Image_Count": len(records)} for model, records in model_images.items()])
    print("Image discovery summary:")
    print(summary_df.to_string(index=False) if not summary_df.empty else "No matching model images found.")
    print(f"Planned output root: {output_root}")
    print(f"Semantic API stage: {'skipped' if args.skip_api else 'enabled'}")

    if dry_run:
        print("DRY_RUN=True; no directories, manifests, API calls, or result files were created.")
        return

    run_dir = create_run_output_dir(output_root)
    save_dataframe_both(summary_df, os.path.join(run_dir, "discovery_summary.csv"), os.path.join(run_dir, "discovery_summary.xlsx"))
    for model_name, image_records in model_images.items():
        safe_name = safe_model_name(model_name)
        model_output_dir = os.path.join(run_dir, safe_name)
        ensure_dir(model_output_dir)
        manifest_path = os.path.join(model_output_dir, f"{safe_name}_manifest.csv")
        pd.DataFrame(image_records).to_csv(manifest_path, index=False, encoding="utf-8-sig")

    for model_name in model_images:
        safe_name = safe_model_name(model_name)
        model_output_dir = os.path.join(run_dir, safe_name)
        manifest_path = os.path.join(model_output_dir, f"{safe_name}_manifest.csv")
        print(f"\n=== 处理模型: {model_name} ===")
        if RUN_CV:
            run_conda_worker(
                VISION_ENV, "cv_worker", manifest_path, model_output_dir,
                model_name, yolo_weights, python_executable,
            )
        if RUN_SEMANTIC and not args.skip_api:
            run_conda_worker(
                AUDIT_ENV, "semantic_worker", manifest_path, model_output_dir,
                model_name, yolo_weights, python_executable,
            )
        elif RUN_SEMANTIC:
            print("SKIP semantic worker: --skip-api was supplied.")
        if MERGE_RESULTS and RUN_CV and RUN_SEMANTIC and not args.skip_api:
            merge_and_prepare(model_name, model_output_dir)
        elif MERGE_RESULTS:
            print("SKIP merge/stats-ready output: both CV and semantic outputs are required.")

    print("\nProcessing finished.")
    print(f"Output directory: {run_dir}")


def parse_args():
    parser = argparse.ArgumentParser(description="Discover and audit an AgingVisBench image corpus.")
    parser.add_argument("--mode", choices=["orchestrate", "cv_worker", "semantic_worker"], default="orchestrate")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="只发现并打印计划；不创建目录或文件。")
    parser.add_argument("--skip-api", action="store_true", help="跳过 DashScope semantic worker 和依赖其结果的合并。")
    parser.add_argument("--max-images", type=int, default=None)
    parser.add_argument("--models", nargs="*", default=None, help="只处理指定的模型目录名。")
    parser.add_argument("--exclude-models", nargs="*", default=None, help="排除指定的模型目录名。")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--output-root", default=OUTPUT_ROOT, help="orchestrator 的结果根目录。")
    parser.add_argument("--model", default=None)
    parser.add_argument("--image-root", default=IMAGE_ROOT, help="图片根目录。")
    parser.add_argument("--yolo-weights", default=YOLO_WEIGHTS, help="本地 YOLO 权重文件；不会自动下载。")
    parser.add_argument("--python-executable", default=None, help="worker 使用的 Python；默认 PIPELINE_PYTHON 或 conda 环境。")
    args = parser.parse_args()
    if args.execute and args.dry_run:
        parser.error("--execute and --dry-run are mutually exclusive")
    return args


def main():
    args = parse_args()
    if args.mode in {"cv_worker", "semantic_worker"} and not args.execute:
        raise SystemExit("Worker modes require --execute.")
    if args.mode == "cv_worker":
        run_cv_worker(args)
    elif args.mode == "semantic_worker":
        run_semantic_worker(args)
    else:
        run_orchestrator(args)


if __name__ == "__main__":
    main()
