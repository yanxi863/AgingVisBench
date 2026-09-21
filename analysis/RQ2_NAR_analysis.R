# =========================
# RQ2_NAR_analysis.R
# Text-to-image ageism audit: RQ1 / RQ2 / RQ3 analysis
# =========================

# 本脚本适配中文列名 + rule-based 新主体性变量版本，并合并 GPT、jimeng、midjourney、tongyi 四个模型数据。
# 使用 --pipeline-dir 指定包含各模型 stats-ready CSV 的私有目录。
# 目标：围绕年龄差异、年龄×性别/国籍交互、老年叙事结构三个问题生成可直接查看的表格和图像。

# -------------------------
# 0. 安装 / 加载包
# -------------------------
required_packages <- c(
  "tidyverse",
  "readr",
  "writexl",
  "janitor",
  "nnet",
  "broom",
  "rstatix",
  "cluster",
  "ggplot2",
  "forcats",
  "stringr"
)

installed <- rownames(installed.packages())
missing_packages <- required_packages[!required_packages %in% installed]
if (length(missing_packages) > 0) {
  stop(
    "缺少 R 包：", paste(missing_packages, collapse = ", "),
    "。请先在独立环境中安装；本脚本不会自动修改用户的 R 环境。"
  )
}

library(tidyverse)
library(readr)
library(writexl)
library(janitor)
library(nnet)
library(broom)
library(rstatix)
library(cluster)
library(ggplot2)
library(forcats)
library(stringr)

# -------------------------
# 1. 通用辅助函数
# -------------------------

# Excel 不接受 NaN/Inf，这里统一转成 NA，避免导出中断。
clean_for_xlsx <- function(x) {
  if (!is.data.frame(x)) return(x)

  numeric_cols <- vapply(x, is.numeric, logical(1))
  x[numeric_cols] <- lapply(x[numeric_cols], function(col) {
    col[!is.finite(col)] <- NA_real_
    col
  })
  x
}

write_xlsx_clean <- function(x, path) {
  if (is.list(x) && !is.data.frame(x)) {
    x <- lapply(x, clean_for_xlsx)
  } else {
    x <- clean_for_xlsx(x)
  }

  writexl::write_xlsx(x, path = path)
}

safe_mean <- function(x) if (all(is.na(x))) NA_real_ else mean(x, na.rm = TRUE)
safe_sd <- function(x) if (sum(!is.na(x)) < 2) NA_real_ else sd(x, na.rm = TRUE)
safe_median <- function(x) if (all(is.na(x))) NA_real_ else median(x, na.rm = TRUE)
safe_min <- function(x) if (all(is.na(x))) NA_real_ else min(x, na.rm = TRUE)
safe_max <- function(x) if (all(is.na(x))) NA_real_ else max(x, na.rm = TRUE)

present_vars <- function(vars, data) {
  vars[vars %in% names(data)]
}

enough_levels <- function(data, var) {
  var %in% names(data) && n_distinct(data[[var]][!is.na(data[[var]])]) >= 2
}

valid_predictors <- function(data, vars) {
  vars[vapply(vars, function(v) enough_levels(data, v), logical(1))]
}

build_rhs <- function(data, vars, fallback = "1") {
  rhs_vars <- valid_predictors(data, vars)
  if (length(rhs_vars) == 0) return(fallback)
  paste(rhs_vars, collapse = " + ")
}

analysis_note <- function(label, message) {
  tibble(
    analysis = label,
    note = message
  )
}

# -------------------------
# 2. 路径设置
# -------------------------
get_script_dir <- function() {
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd_args, value = TRUE)
  if (length(file_arg) > 0) {
    return(dirname(normalizePath(sub("^--file=", "", file_arg[1]), winslash = "/", mustWork = FALSE)))
  }

  ofiles <- vapply(sys.frames(), function(frame) {
    if (!is.null(frame$ofile)) frame$ofile else NA_character_
  }, character(1))
  ofiles <- ofiles[!is.na(ofiles)]
  if (length(ofiles) > 0) {
    return(dirname(normalizePath(ofiles[length(ofiles)], winslash = "/", mustWork = FALSE)))
  }

  normalizePath(getwd(), winslash = "/", mustWork = FALSE)
}

script_dir <- get_script_dir()
cli_args <- commandArgs(trailingOnly = TRUE)
arg_value <- function(name, default) {
  prefix <- paste0("--", name, "=")
  match <- grep(paste0("^", prefix), cli_args, value = TRUE)
  if (length(match) == 0) return(default)
  sub(paste0("^", prefix), "", match[1])
}

project_root <- normalizePath(
  arg_value("project-root", file.path(script_dir, "..")),
  winslash = "/",
  mustWork = FALSE
)
pipeline_dir <- normalizePath(
  arg_value("pipeline-dir", file.path(project_root, "outputs", "rq2_pipeline_20260508_192005")),
  winslash = "/",
  mustWork = FALSE
)

if (!dir.exists(pipeline_dir)) {
  stop(
    "未找到分析输入目录：", pipeline_dir,
    "\n请通过 --pipeline-dir=<path> 指定包含四模型 stats-ready CSV 的私有目录。"
  )
}

expected_models <- c("GPT", "jimeng", "midjourney", "tongyi")

data_paths <- file.path(
  pipeline_dir,
  expected_models,
  paste0(expected_models, "_stats_ready_cn_agency_rule_based.csv")
)

missing_data_paths <- data_paths[!file.exists(data_paths)]
if (length(missing_data_paths) > 0) {
  stop(
    "未找到 rule-based 新主体性数据文件：\n",
    paste(missing_data_paths, collapse = "\n")
  )
}

data_paths <- normalizePath(data_paths, winslash = "/", mustWork = TRUE)
model_dirs <- basename(dirname(data_paths))

output_dir <- normalizePath(
  arg_value("output-dir", file.path(project_root, "outputs", "analysis", "all_models")),
  winslash = "/",
  mustWork = FALSE
)
fig_dir <- file.path(output_dir, "figures")
if (!dir.exists(output_dir)) dir.create(output_dir, recursive = TRUE)
if (!dir.exists(fig_dir)) dir.create(fig_dir, recursive = TRUE)

cat("读取管线目录：", pipeline_dir, "\n")
cat("读取数据文件：\n")
for (p in data_paths) cat(" - ", p, "\n")
cat("输出目录：", output_dir, "\n")

# -------------------------
# 3. 读取数据与基础清洗
# -------------------------
df_raw <- map2_dfr(data_paths, model_dirs, function(path, model_dir) {
  readr::read_csv(path, show_col_types = FALSE, locale = locale(encoding = "UTF-8")) %>%
    mutate(source_file = path, source_model_dir = model_dir)
})

cn_to_en_names <- c(
  "模型" = "model",
  "文件夹" = "folder",
  "文件名" = "filename",
  "图片路径" = "image_path",
  "年龄标签" = "age",
  "国籍" = "nationality",
  "性别" = "gender",
  "行动类型" = "action_type",
  "主体性取向" = "agency_orientation",
  "发展取向主体性" = "development_oriented_agency",
  "原主体性水平" = "agency_level",
  "场景类型" = "scene_type",
  "空间类型" = "space_type",
  "物体" = "objects",
  "现代物体" = "modern_object",
  "传统文化标记" = "traditional_cultural_marker",
  "医疗辅助物体数量" = "medical_object_count",
  "环境类型" = "environment_type",
  "人物面积占比" = "area_ratio",
  "中心距离" = "center_distance",
  "头部偏航角" = "yaw",
  "头部俯仰角" = "pitch",
  "是否检测到面部" = "face_detected",
  "脊柱角度" = "spine_angle",
  "手臂弯曲度" = "arm_curl",
  "腿部弯曲度" = "leg_curl",
  "身体姿态指数" = "bhi",
  "人物数量" = "num_persons",
  "是否独处" = "is_alone",
  "背景亮度" = "bg_brightness",
  "背景饱和度" = "bg_saturation",
  "整图熵" = "image_entropy_full",
  "背景熵" = "image_entropy_background",
  "年龄数值" = "age_num",
  "年龄组" = "age_group_original",
  "主要行动" = "primary_action",
  "是否有行动" = "has_action",
  "是否有医疗辅助物体" = "has_medical_object",
  "人物数量组" = "num_persons_group",
  "原主体性_被动" = "agency_passive",
  "原主体性_主动" = "agency_active",
  "场景_家庭" = "scene_home",
  "场景_办公室" = "scene_office",
  "场景_医院" = "scene_hospital",
  "场景_街道" = "scene_street",
  "场景_公园" = "scene_park",
  "场景_庭院" = "scene_yard",
  "场景_其他户外" = "scene_outdoor_other",
  "场景_未知" = "scene_unknown",
  "空间_室内" = "space_indoor",
  "空间_庭院" = "space_courtyard",
  "空间_户外" = "space_outdoor",
  "空间_未知" = "space_unknown",
  "环境_室内" = "environment_indoor",
  "环境_庭院" = "environment_courtyard",
  "环境_户外" = "environment_outdoor",
  "环境_未知" = "environment_unknown",
  "年龄组_60岁以下" = "agegroup_under_60",
  "年龄组_60多岁" = "agegroup_60s",
  "年龄组_70多岁" = "agegroup_70s",
  "年龄组_80多岁" = "agegroup_80s",
  "年龄组_90岁及以上" = "agegroup_90_plus"
)

df_raw <- df_raw %>%
  rename_with(~if_else(.x %in% names(cn_to_en_names), unname(cn_to_en_names[.x]), .x)) %>%
  clean_names()

# 兼容旧列名；新格式使用 traditional_cultural_marker。
if ("traditional_symbol" %in% names(df_raw) && !"traditional_cultural_marker" %in% names(df_raw)) {
  df_raw <- df_raw %>% rename(traditional_cultural_marker = traditional_symbol)
}

# 如果某些新列在旧数据中不存在，补 NA，后续分析会自动跳过或输出说明。
optional_columns <- c(
  "model", "space_type", "environment_type", "natural_or_nonmodern_environment",
  "traditional_cultural_marker", "objects", "image_path", "agency_active",
  "action_type", "primary_action", "agency_orientation", "development_oriented_agency"
)
for (col in optional_columns) {
  if (!col %in% names(df_raw)) df_raw[[col]] <- NA
}

numeric_vars <- present_vars(c(
  "age_num", "has_action", "modern_object", "traditional_cultural_marker",
  "medical_object_count", "has_medical_object", "natural_or_nonmodern_environment",
  "num_persons", "is_alone", "area_ratio", "center_distance", "yaw", "pitch",
  "face_detected", "spine_angle", "arm_curl", "leg_curl", "bhi",
  "bg_brightness", "bg_saturation", "image_entropy_full", "image_entropy_background",
  "agency_passive", "agency_active", "development_oriented_agency",
  "space_indoor", "space_courtyard", "space_outdoor", "space_unknown"
), df_raw)

# 新版 Agency_Level 是 active/passive；旧版 routine_active/goal_directed_active 会合并为 active。
df <- df_raw %>%
  mutate(across(all_of(numeric_vars), ~as.numeric(.))) %>%
  mutate(
    model = if_else(is.na(model) | str_squish(as.character(model)) == "", source_model_dir, as.character(model)),
    model = factor(model),
    age_from_label = as.numeric(str_extract(as.character(age), "\\d+")),
    age_num = case_when(
      !is.na(age_from_label) ~ age_from_label,
      !is.na(age_num) ~ as.numeric(age_num),
      TRUE ~ NA_real_
    ),
    age_value = factor(
      age_num,
      levels = c(18, 45, 60, 75, 90),
      labels = c("18", "45", "60", "75", "90"),
      ordered = FALSE
    ),
    age_value_ordered = factor(
      age_num,
      levels = c(18, 45, 60, 75, 90),
      labels = c("18", "45", "60", "75", "90"),
      ordered = TRUE
    ),
    age_label = factor(
      paste0(age_num, "yo"),
      levels = c("18yo", "45yo", "60yo", "75yo", "90yo"),
      ordered = TRUE
    ),
    age_group = age_value,
    is_older = if_else(!is.na(age_num) & age_num >= 60, 1, 0),
    age_binary = factor(
      if_else(is_older == 1, "older_60_75_90", "younger_18_45"),
      levels = c("younger_18_45", "older_60_75_90")
    ),
    gender = as.factor(gender),
    nationality = as.factor(nationality),
    agency_level = case_when(
      agency_level %in% c("active", "routine_active", "goal_directed_active") ~ "active",
      agency_level == "passive" ~ "passive",
      TRUE ~ as.character(agency_level)
    ),
    agency_level = factor(agency_level, levels = c("passive", "active")),
    agency_orientation = factor(
      agency_orientation,
      levels = c("maintenance", "social_participation", "achievement_growth")
    ),
    development_oriented_agency = as.numeric(development_oriented_agency),
    agency_active = case_when(
      !is.na(agency_active) ~ as.numeric(agency_active),
      agency_level == "active" ~ 1,
      agency_level == "passive" ~ 0,
      TRUE ~ NA_real_
    ),
    scene_type = factor(
      scene_type,
      levels = c("home", "office", "hospital", "street", "park", "yard", "outdoor_other", "unknown")
    ),
    space_type = factor(
      space_type,
      levels = c("indoor", "courtyard", "outdoor", "unknown")
    ),
    environment_type = factor(environment_type),
    natural_or_nonmodern_environment = case_when(
      !is.na(natural_or_nonmodern_environment) ~ as.numeric(natural_or_nonmodern_environment),
      environment_type %in% c("courtyard") ~ 1,
      environment_type %in% c("indoor", "outdoor", "unknown") ~ 0,
      TRUE ~ NA_real_
    ),
    num_persons_group = as.factor(num_persons_group)
  )

# 主分析样本：必须有年龄数值与规范年龄取值。
df_main <- df %>%
  filter(!is.na(age_value), !is.na(age_num), !is.na(age_binary)) %>%
  mutate(row_id = row_number())

older_df <- df_main %>% filter(is_older == 1)
younger_df <- df_main %>% filter(is_older == 0)

print(names(df_main))
glimpse(df_main)

# -------------------------
# 4. 变量组：对应三个研究问题
# -------------------------

# RQ1：年轻人与老年人的系统性视觉差异。
categorical_visual_vars <- present_vars(c(
  "agency_orientation", "development_oriented_agency", "agency_level", "scene_type", "space_type", "environment_type", "has_action",
  "modern_object", "traditional_cultural_marker", "has_medical_object",
  "natural_or_nonmodern_environment", "num_persons_group", "is_alone", "face_detected"
), df_main)

# action_type / primary_action 类别可能很多，单独输出，避免和核心分类变量混在一起。
action_vars <- present_vars(c("action_type", "primary_action"), df_main)

binary_visual_vars <- present_vars(c(
  "development_oriented_agency", "agency_active", "has_action", "modern_object", "traditional_cultural_marker",
  "has_medical_object", "natural_or_nonmodern_environment", "is_alone", "face_detected"
), df_main)

continuous_visual_vars <- present_vars(c(
  "medical_object_count", "num_persons", "area_ratio", "center_distance", "yaw", "pitch",
  "spine_angle", "arm_curl", "leg_curl", "bhi", "bg_brightness", "bg_saturation",
  "image_entropy_full", "image_entropy_background"
), df_main)

# RQ3：用于构造“叙事结构”的视觉元素。
narrative_vars <- present_vars(c(
  "agency_orientation", "agency_level", "scene_type", "space_type", "is_alone",
  "has_medical_object", "modern_object", "traditional_cultural_marker",
  "natural_or_nonmodern_environment"
), df_main)

# -------------------------
# 5. 统计函数：频数、检验、模型
# -------------------------
freq_by_group <- function(data, group, var) {
  if (!all(c(group, var) %in% names(data))) return(tibble())

  data %>%
    filter(!is.na(.data[[group]]), !is.na(.data[[var]])) %>%
    count(.data[[group]], .data[[var]], name = "n") %>%
    group_by(.data[[group]]) %>%
    mutate(
      group_total = sum(n),
      percent = n / group_total * 100
    ) %>%
    ungroup() %>%
    transmute(
      group_var = group,
      group_value = as.character(.data[[group]]),
      variable = var,
      value = as.character(.data[[var]]),
      n,
      group_total,
      percent
    )
}

continuous_by_group <- function(data, group, vars) {
  if (!group %in% names(data)) return(tibble())

  map_dfr(vars, function(v) {
    if (!v %in% names(data)) return(tibble())

    data %>%
      filter(!is.na(.data[[group]])) %>%
      group_by(.data[[group]]) %>%
      summarise(
        n = sum(!is.na(.data[[v]])),
        mean = safe_mean(.data[[v]]),
        sd = safe_sd(.data[[v]]),
        median = safe_median(.data[[v]]),
        min = safe_min(.data[[v]]),
        max = safe_max(.data[[v]]),
        .groups = "drop"
      ) %>%
      transmute(
        group_var = group,
        group_value = as.character(.data[[group]]),
        variable = v,
        n,
        mean,
        sd,
        median,
        min,
        max
      )
  })
}

run_chisq <- function(data, group, var) {
  if (!all(c(group, var) %in% names(data))) {
    return(tibble(group = group, variable = var, n = NA_integer_, statistic = NA_real_, df = NA_real_, p_value = NA_real_, cramers_v = NA_real_, note = "Missing variable"))
  }

  tmp <- data %>%
    filter(!is.na(.data[[group]]), !is.na(.data[[var]])) %>%
    mutate(across(all_of(c(group, var)), ~droplevels(as.factor(.))))

  if (nrow(tmp) == 0 || n_distinct(tmp[[group]]) < 2 || n_distinct(tmp[[var]]) < 2) {
    return(tibble(group = group, variable = var, n = nrow(tmp), statistic = NA_real_, df = NA_real_, p_value = NA_real_, cramers_v = NA_real_, note = "Insufficient levels"))
  }

  tab <- table(tmp[[group]], tmp[[var]])
  test <- suppressWarnings(chisq.test(tab))
  n_total <- sum(tab)
  min_dim <- min(dim(tab))
  cramers_v <- if (min_dim > 1) sqrt(unname(test$statistic) / (n_total * (min_dim - 1))) else NA_real_

  tibble(
    group = group,
    variable = var,
    n = n_total,
    statistic = unname(test$statistic),
    df = unname(test$parameter),
    p_value = unname(test$p.value),
    cramers_v = cramers_v,
    note = NA_character_
  )
}

run_wilcox <- function(data, outcome, group = "age_binary") {
  if (!all(c(group, outcome) %in% names(data))) {
    return(tibble(group = group, outcome = outcome, n = NA_integer_, statistic = NA_real_, p_value = NA_real_, median_group_1 = NA_real_, median_group_2 = NA_real_, median_diff = NA_real_, note = "Missing variable"))
  }

  tmp <- data %>%
    filter(!is.na(.data[[group]]), !is.na(.data[[outcome]])) %>%
    mutate(group_value = droplevels(as.factor(.data[[group]])))

  group_levels <- levels(tmp$group_value)
  if (nrow(tmp) == 0 || length(group_levels) != 2) {
    return(tibble(group = group, outcome = outcome, n = nrow(tmp), statistic = NA_real_, p_value = NA_real_, median_group_1 = NA_real_, median_group_2 = NA_real_, median_diff = NA_real_, note = "Wilcoxon requires exactly two groups"))
  }

  test <- suppressWarnings(wilcox.test(as.formula(paste(outcome, "~ group_value")), data = tmp))
  medians <- tmp %>% group_by(group_value) %>% summarise(median = safe_median(.data[[outcome]]), .groups = "drop")
  median_1 <- medians$median[match(group_levels[1], medians$group_value)]
  median_2 <- medians$median[match(group_levels[2], medians$group_value)]

  tibble(
    group = group,
    outcome = outcome,
    n = nrow(tmp),
    statistic = unname(test$statistic),
    p_value = unname(test$p.value),
    group_1 = group_levels[1],
    group_2 = group_levels[2],
    median_group_1 = median_1,
    median_group_2 = median_2,
    median_diff = median_2 - median_1,
    note = NA_character_
  )
}

run_kruskal <- function(data, outcome, group = "age_group") {
  if (!all(c(group, outcome) %in% names(data))) {
    return(tibble(group = group, outcome = outcome, n = NA_integer_, statistic = NA_real_, df = NA_real_, p_value = NA_real_, note = "Missing variable"))
  }

  tmp <- data %>% filter(!is.na(.data[[group]]), !is.na(.data[[outcome]]))
  if (nrow(tmp) == 0 || n_distinct(tmp[[group]]) < 2) {
    return(tibble(group = group, outcome = outcome, n = nrow(tmp), statistic = NA_real_, df = NA_real_, p_value = NA_real_, note = "Kruskal-Wallis requires at least two groups"))
  }

  test <- kruskal.test(as.formula(paste(outcome, "~", group)), data = tmp)
  tibble(
    group = group,
    outcome = outcome,
    n = nrow(tmp),
    statistic = unname(test$statistic),
    df = unname(test$parameter),
    p_value = unname(test$p.value),
    note = NA_character_
  )
}

run_pairwise_dunn <- function(data, outcome, group = "age_group") {
  if (!all(c(group, outcome) %in% names(data))) {
    return(tibble(outcome = outcome, group = group, group1 = NA_character_, group2 = NA_character_, p = NA_real_, p.adj = NA_real_, note = "Missing variable"))
  }

  tmp <- data %>% filter(!is.na(.data[[group]]), !is.na(.data[[outcome]]))
  if (nrow(tmp) == 0 || n_distinct(tmp[[group]]) < 2) {
    return(tibble(outcome = outcome, group = group, group1 = NA_character_, group2 = NA_character_, p = NA_real_, p.adj = NA_real_, note = "Dunn test requires at least two groups"))
  }

  tryCatch(
    rstatix::dunn_test(tmp, as.formula(paste(outcome, "~", group)), p.adjust.method = "bonferroni") %>%
      mutate(outcome = outcome, group = group, note = NA_character_, .before = 1),
    error = function(e) tibble(outcome = outcome, group = group, group1 = NA_character_, group2 = NA_character_, p = NA_real_, p.adj = NA_real_, note = conditionMessage(e))
  )
}

model_error <- function(model_label, model_type, outcome, message) {
  tibble(
    model_label = model_label,
    model_type = model_type,
    outcome = outcome,
    n = NA_integer_,
    term = NA_character_,
    estimate = NA_real_,
    std.error = NA_real_,
    statistic = NA_real_,
    p.value = NA_real_,
    conf.low = NA_real_,
    conf.high = NA_real_,
    note = message
  )
}

safe_lm <- function(data, outcome, rhs, model_label) {
  rhs_vars <- all.vars(as.formula(paste("~", rhs)))
  missing_vars <- setdiff(c(outcome, rhs_vars), names(data))
  if (length(missing_vars) > 0) return(model_error(model_label, "linear", outcome, paste("Missing:", paste(missing_vars, collapse = ", "))))

  model_data <- data %>% drop_na(all_of(c(outcome, rhs_vars)))
  if (nrow(model_data) < 10 || n_distinct(model_data[[outcome]]) < 2) {
    return(model_error(model_label, "linear", outcome, "Insufficient data or outcome variation"))
  }

  fit <- tryCatch(lm(as.formula(paste(outcome, "~", rhs)), data = model_data), error = function(e) e)
  if (inherits(fit, "error")) return(model_error(model_label, "linear", outcome, conditionMessage(fit)))

  broom::tidy(fit, conf.int = TRUE) %>%
    mutate(model_label = model_label, model_type = "linear", outcome = outcome, n = nrow(model_data), note = NA_character_, .before = 1)
}

safe_glm_binomial <- function(data, outcome, rhs, model_label) {
  rhs_vars <- all.vars(as.formula(paste("~", rhs)))
  missing_vars <- setdiff(c(outcome, rhs_vars), names(data))
  if (length(missing_vars) > 0) return(model_error(model_label, "logit", outcome, paste("Missing:", paste(missing_vars, collapse = ", "))))

  model_data <- data %>% drop_na(all_of(c(outcome, rhs_vars)))
  outcome_values <- sort(unique(model_data[[outcome]]))
  if (nrow(model_data) < 10 || length(outcome_values) < 2 || !all(outcome_values %in% c(0, 1))) {
    return(model_error(model_label, "logit", outcome, "Binary logit requires 0/1 outcome with both values present"))
  }

  fit <- tryCatch(glm(as.formula(paste(outcome, "~", rhs)), data = model_data, family = binomial()), error = function(e) e)
  if (inherits(fit, "error")) return(model_error(model_label, "logit", outcome, conditionMessage(fit)))

  broom::tidy(fit, conf.int = FALSE, exponentiate = TRUE) %>%
    rename(odds_ratio = estimate) %>%
    mutate(
      estimate = odds_ratio,
      model_label = model_label,
      model_type = "logit_odds_ratio",
      outcome = outcome,
      n = nrow(model_data),
      conf.low = NA_real_,
      conf.high = NA_real_,
      note = NA_character_,
      .before = 1
    )
}

safe_multinom <- function(data, outcome, rhs, model_label) {
  rhs_vars <- all.vars(as.formula(paste("~", rhs)))
  missing_vars <- setdiff(c(outcome, rhs_vars), names(data))
  if (length(missing_vars) > 0) {
    return(tibble(model_label = model_label, model_type = "multinomial", outcome = outcome, n = NA_integer_, outcome_level = NA_character_, term = NA_character_, estimate = NA_real_, odds_ratio = NA_real_, std.error = NA_real_, statistic = NA_real_, p.value = NA_real_, note = paste("Missing:", paste(missing_vars, collapse = ", "))))
  }

  model_data <- data %>% drop_na(all_of(c(outcome, rhs_vars))) %>% mutate(.outcome = droplevels(as.factor(.data[[outcome]])))
  if (nrow(model_data) < 10 || n_distinct(model_data$.outcome) < 2) {
    return(tibble(model_label = model_label, model_type = "multinomial", outcome = outcome, n = nrow(model_data), outcome_level = NA_character_, term = NA_character_, estimate = NA_real_, odds_ratio = NA_real_, std.error = NA_real_, statistic = NA_real_, p.value = NA_real_, note = "Insufficient data or outcome variation"))
  }

  formula <- as.formula(paste(".outcome ~", rhs))
  fit <- tryCatch(nnet::multinom(formula, data = model_data, trace = FALSE), error = function(e) e)
  if (inherits(fit, "error")) {
    return(tibble(model_label = model_label, model_type = "multinomial", outcome = outcome, n = nrow(model_data), outcome_level = NA_character_, term = NA_character_, estimate = NA_real_, odds_ratio = NA_real_, std.error = NA_real_, statistic = NA_real_, p.value = NA_real_, note = conditionMessage(fit)))
  }

  s <- summary(fit)
  coef_mat <- s$coefficients
  se_mat <- s$standard.errors
  if (is.null(dim(coef_mat))) {
    outcome_level <- levels(model_data$.outcome)[2]
    coef_mat <- matrix(coef_mat, nrow = 1, dimnames = list(outcome_level, names(coef_mat)))
    se_mat <- matrix(se_mat, nrow = 1, dimnames = list(outcome_level, names(se_mat)))
  }

  coef_df <- as.data.frame(coef_mat) %>% rownames_to_column("outcome_level") %>% pivot_longer(-outcome_level, names_to = "term", values_to = "estimate")
  se_df <- as.data.frame(se_mat) %>% rownames_to_column("outcome_level") %>% pivot_longer(-outcome_level, names_to = "term", values_to = "std.error")

  coef_df %>%
    left_join(se_df, by = c("outcome_level", "term")) %>%
    mutate(
      statistic = estimate / std.error,
      p.value = 2 * (1 - pnorm(abs(statistic))),
      odds_ratio = exp(estimate),
      model_label = model_label,
      model_type = "multinomial_logit",
      outcome = outcome,
      n = nrow(model_data),
      note = NA_character_,
      .before = 1
    )
}

# -------------------------
# 6. 数据概览输出
# -------------------------
column_overview <- tibble(
  variable = names(df_main),
  type = vapply(df_main, function(x) paste(class(x), collapse = "/"), character(1)),
  missing_n = vapply(df_main, function(x) sum(is.na(x)), integer(1)),
  missing_pct = vapply(df_main, function(x) mean(is.na(x)) * 100, numeric(1))
)

sample_age_binary <- df_main %>% count(age_binary, name = "n") %>% mutate(percent = n / sum(n) * 100)
sample_age_value <- df_main %>% count(age_value, name = "n") %>% mutate(percent = n / sum(n) * 100)
sample_gender <- df_main %>% count(gender, name = "n") %>% mutate(percent = n / sum(n) * 100)
sample_nationality <- df_main %>% count(nationality, name = "n") %>% mutate(percent = n / sum(n) * 100)
sample_cross <- df_main %>% count(model, age_value, gender, nationality, name = "n")

write_xlsx_clean(
  list(
    columns = column_overview,
    sample_age_binary = sample_age_binary,
    sample_age_value = sample_age_value,
    sample_gender = sample_gender,
    sample_nationality = sample_nationality,
    sample_cross = sample_cross
  ),
  file.path(output_dir, "00_data_overview.xlsx")
)

writeLines(
  c(
    "RQ1：与年轻人相比，老年人在视觉要素中呈现哪些系统性差异？",
    "可做：年龄二分/年龄组描述统计、卡方检验、Wilcoxon/Kruskal-Wallis 检验、对象词频差异、控制性别和国籍的回归模型。",
    "",
    "RQ2：性别与国籍是否与年龄交互影响视觉要素呈现？",
    "可做：全年龄组的年龄×性别、年龄×国籍交互模型；并按性别、国籍、年龄×性别、年龄×国籍输出分层描述。",
    "",
    "RQ3：AI生成图像是否通过有限的视觉要素组合，构建稳定的视觉叙事结构？",
    "可做：N/共鸣层、A/行动者层、R/关系层、综合层四套签名；比较全年龄组、年龄组、性别、国籍及交叉组的 Top 组合、Top-N 覆盖率、HHI 集中度、Shannon 熵及标准化熵。"
  ),
  file.path(output_dir, "00_analysis_scope.txt"),
  useBytes = TRUE
)

# -------------------------
# 7. RQ1：老年人与年轻人的系统性视觉差异
# -------------------------

# 7.1 分类视觉要素：年龄二分与细分年龄组。
rq1_cat_age_binary <- map_dfr(categorical_visual_vars, ~freq_by_group(df_main, "age_binary", .x))
rq1_cat_age_value <- map_dfr(categorical_visual_vars, ~freq_by_group(df_main, "age_value", .x))
rq1_action_age_binary <- map_dfr(action_vars, ~freq_by_group(df_main, "age_binary", .x))
rq1_action_age_value <- map_dfr(action_vars, ~freq_by_group(df_main, "age_value", .x))

rq1_chisq_age_binary <- map_dfr(categorical_visual_vars, ~run_chisq(df_main, "age_binary", .x))
rq1_chisq_age_value <- map_dfr(categorical_visual_vars, ~run_chisq(df_main, "age_value", .x))

# 7.2 连续视觉要素：位置、姿态、视觉氛围、图像复杂度等。
rq1_cont_age_binary <- continuous_by_group(df_main, "age_binary", continuous_visual_vars)
rq1_cont_age_value <- continuous_by_group(df_main, "age_value", continuous_visual_vars)
rq1_wilcox_age_binary <- map_dfr(continuous_visual_vars, ~run_wilcox(df_main, .x, "age_binary"))
rq1_kruskal_age_value <- map_dfr(continuous_visual_vars, ~run_kruskal(df_main, .x, "age_value"))
rq1_pairwise_age_value <- map_dfr(
  present_vars(c("bhi", "bg_brightness", "bg_saturation", "image_entropy_background", "area_ratio", "num_persons", "medical_object_count"), df_main),
  ~run_pairwise_dunn(df_main, .x, "age_value")
)

# 7.3 控制性别、国籍与模型后的年龄效应模型。
# 主模型：age_value 把 18/45/60/75/90 作为五个实验年龄条件，适合观察每个年龄点相对 18 岁的差异。
# 辅助模型：age_binary 把 18/45 与 60/75/90 合并，适合做“年轻 vs 老年”的整体对比。
# 趋势模型：age_num 把年龄当作数值变量，适合检验视觉要素是否随年龄单调变化。
rq1_rhs_age_value <- build_rhs(df_main, c("age_value", "gender", "nationality", "model"), fallback = "age_num")
rq1_rhs_age_binary <- build_rhs(df_main, c("age_binary", "gender", "nationality", "model"), fallback = "age_num")
rq1_rhs_age_num <- build_rhs(df_main, c("age_num", "gender", "nationality", "model"), fallback = "age_num")

run_rq1_model_set <- function(rhs, model_tag) {
  list(
    logit = map_dfr(binary_visual_vars, ~safe_glm_binomial(df_main, .x, rhs, paste0("RQ1_", model_tag, "_", .x))),
    linear = map_dfr(continuous_visual_vars, ~safe_lm(df_main, .x, rhs, paste0("RQ1_", model_tag, "_", .x))),
    multinom = map_dfr(present_vars(c("scene_type", "space_type", "environment_type"), df_main), ~safe_multinom(df_main, .x, rhs, paste0("RQ1_", model_tag, "_", .x)))
  )
}

rq1_models_age_value <- run_rq1_model_set(rq1_rhs_age_value, "age_value_main")
rq1_models_age_binary <- run_rq1_model_set(rq1_rhs_age_binary, "age_binary_aux")
rq1_models_age_num <- run_rq1_model_set(rq1_rhs_age_num, "age_num_trend")

write_xlsx_clean(
  list(
    cat_age_binary = rq1_cat_age_binary,
    cat_age_value = rq1_cat_age_value,
    action_age_binary = rq1_action_age_binary,
    action_age_value = rq1_action_age_value,
    chi_age_binary = rq1_chisq_age_binary,
    chi_age_value = rq1_chisq_age_value,
    cont_age_binary = rq1_cont_age_binary,
    cont_age_value = rq1_cont_age_value,
    wilcox_age_binary = rq1_wilcox_age_binary,
    kruskal_age_value = rq1_kruskal_age_value,
    pairwise_age_value = rq1_pairwise_age_value,
    logit_age_value_main = rq1_models_age_value$logit,
    linear_age_value_main = rq1_models_age_value$linear,
    multinom_age_value_main = rq1_models_age_value$multinom,
    logit_age_binary_aux = rq1_models_age_binary$logit,
    linear_age_binary_aux = rq1_models_age_binary$linear,
    multinom_age_binary_aux = rq1_models_age_binary$multinom,
    logit_age_num_trend = rq1_models_age_num$logit,
    linear_age_num_trend = rq1_models_age_num$linear,
    multinom_age_num_trend = rq1_models_age_num$multinom
  ),
  file.path(output_dir, "RQ1_age_differences.xlsx")
)

# 7.4 Objects 列拆分：分析老年/年轻图像中反复出现的物体。
build_objects_long <- function(data) {
  if (!"objects" %in% names(data)) return(tibble())

  data %>%
    select(row_id, age_binary, age_value, gender, nationality, model, objects) %>%
    filter(!is.na(objects), str_squish(objects) != "") %>%
    separate_rows(objects, sep = "\\s*,\\s*") %>%
    mutate(object = str_squish(str_to_lower(objects))) %>%
    filter(!is.na(object), object != "", !object %in% c("none", "unknown", "na")) %>%
    distinct(row_id, age_binary, age_value, gender, nationality, model, object)
}

object_prevalence_by_group <- function(objects_long, data, group) {
  if (nrow(objects_long) == 0 || !group %in% names(data) || !group %in% names(objects_long)) return(tibble())

  denoms <- data %>%
    filter(!is.na(.data[[group]])) %>%
    count(.data[[group]], name = "n_images")

  objects_long %>%
    filter(!is.na(.data[[group]])) %>%
    count(.data[[group]], object, name = "image_n") %>%
    left_join(denoms, by = group) %>%
    mutate(prevalence_pct = image_n / n_images * 100) %>%
    arrange(.data[[group]], desc(prevalence_pct), desc(image_n)) %>%
    transmute(
      group_var = group,
      group_value = as.character(.data[[group]]),
      object,
      image_n,
      n_images,
      prevalence_pct
    )
}

compare_object_prevalence <- function(object_prev_age) {
  if (nrow(object_prev_age) == 0) return(tibble())

  wide <- object_prev_age %>%
    filter(group_var == "age_binary") %>%
    select(group_value, object, image_n, prevalence_pct) %>%
    pivot_wider(
      names_from = group_value,
      values_from = c(image_n, prevalence_pct),
      values_fill = 0
    )

  needed <- c(
    "image_n_younger_18_45", "image_n_older_60_75_90",
    "prevalence_pct_younger_18_45", "prevalence_pct_older_60_75_90"
  )
  for (col in needed) {
    if (!col %in% names(wide)) wide[[col]] <- 0
  }

  wide %>%
    mutate(
      older_minus_younger_pct = prevalence_pct_older_60_75_90 - prevalence_pct_younger_18_45,
      prevalence_ratio_smoothed = (prevalence_pct_older_60_75_90 + 0.5) / (prevalence_pct_younger_18_45 + 0.5)
    ) %>%
    arrange(desc(abs(older_minus_younger_pct)))
}

objects_long <- build_objects_long(df_main)
rq1_object_age_binary <- object_prevalence_by_group(objects_long, df_main, "age_binary")
rq1_object_age_value <- object_prevalence_by_group(objects_long, df_main, "age_value")
rq1_object_compare <- compare_object_prevalence(rq1_object_age_binary)

write_xlsx_clean(
  list(
    object_age_binary = rq1_object_age_binary,
    object_age_value = rq1_object_age_value,
    object_compare = rq1_object_compare
  ),
  file.path(output_dir, "RQ1_object_differences.xlsx")
)

# -------------------------
# 8. RQ2：年龄 × 性别 / 国籍的交互影响
# -------------------------

# 交互模型检验的是：年龄差异是否因性别或国籍而改变。
# 主交互：age_value * gender / nationality，保留 18、45、60、75、90 五个年龄条件的差异。
# 辅助交互：age_binary * gender / nationality，提供年轻组 vs 老年组的简洁对比。
# 趋势交互：age_num * gender / nationality，检验年龄数值趋势是否因性别或国籍而改变。
build_rq2_rhs <- function(age_var) {
  terms <- c()
  if (enough_levels(df_main, age_var) && enough_levels(df_main, "gender")) {
    terms <- c(terms, paste0(age_var, " * gender"))
  }
  if (enough_levels(df_main, age_var) && enough_levels(df_main, "nationality")) {
    terms <- c(terms, paste0(age_var, " * nationality"))
  }
  if (enough_levels(df_main, "model")) {
    terms <- c(terms, "model")
  }
  if (length(terms) == 0) return(age_var)
  paste(terms, collapse = " + ")
}

run_rq2_interaction_set <- function(rhs, model_tag) {
  list(
    binary = map_dfr(binary_visual_vars, ~safe_glm_binomial(df_main, .x, rhs, paste0("RQ2_", model_tag, "_", .x))),
    continuous = map_dfr(continuous_visual_vars, ~safe_lm(df_main, .x, rhs, paste0("RQ2_", model_tag, "_", .x))),
    multinom = map_dfr(present_vars(c("scene_type", "space_type", "environment_type"), df_main), ~safe_multinom(df_main, .x, rhs, paste0("RQ2_", model_tag, "_", .x)))
  )
}

rq2_rhs_age_value <- build_rq2_rhs("age_value")
rq2_rhs_age_binary <- build_rq2_rhs("age_binary")
rq2_rhs_age_num <- build_rq2_rhs("age_num")

rq2_models_age_value <- run_rq2_interaction_set(rq2_rhs_age_value, "age_value_interaction_main")
rq2_models_age_binary <- run_rq2_interaction_set(rq2_rhs_age_binary, "age_binary_interaction_aux")
rq2_models_age_num <- run_rq2_interaction_set(rq2_rhs_age_num, "age_num_interaction_trend")

rq2_interaction_terms_age_value <- bind_rows(
  rq2_models_age_value$binary,
  rq2_models_age_value$continuous,
  rq2_models_age_value$multinom
) %>% filter(str_detect(term, ":"))

rq2_interaction_terms_age_binary <- bind_rows(
  rq2_models_age_binary$binary,
  rq2_models_age_binary$continuous,
  rq2_models_age_binary$multinom
) %>% filter(str_detect(term, ":"))

rq2_interaction_terms_age_num <- bind_rows(
  rq2_models_age_num$binary,
  rq2_models_age_num$continuous,
  rq2_models_age_num$multinom
) %>% filter(str_detect(term, ":"))

# 全年龄组分层描述：性别、国籍、年龄×性别、年龄×国籍都输出，不再局限于老年子样本。
df_rq2 <- df_main %>%
  mutate(
    age_gender = interaction(age_binary, gender, drop = TRUE, sep = " | "),
    age_nationality = interaction(age_binary, nationality, drop = TRUE, sep = " | "),
    age_model = interaction(age_binary, model, drop = TRUE, sep = " | "),
    age_value_gender = interaction(age_value, gender, drop = TRUE, sep = " | "),
    age_value_nationality = interaction(age_value, nationality, drop = TRUE, sep = " | "),
    model_age_value = interaction(model, age_value, drop = TRUE, sep = " | "),
    model_age_binary = interaction(model, age_binary, drop = TRUE, sep = " | ")
  )

rq2_group_vars <- present_vars(c(
  "gender", "nationality", "model", "age_gender", "age_nationality", "age_model",
  "age_value_gender", "age_value_nationality", "model_age_value", "model_age_binary"
), df_rq2)
rq2_object_group_cols <- setdiff(rq2_group_vars, names(objects_long))
objects_long_rq2 <- objects_long %>%
  left_join(df_rq2 %>% select(row_id, all_of(rq2_object_group_cols)), by = "row_id")

rq2_cat_by_group <- map_dfr(rq2_group_vars, function(g) {
  map_dfr(categorical_visual_vars, ~freq_by_group(df_rq2, g, .x))
})
rq2_cont_by_group <- map_dfr(rq2_group_vars, ~continuous_by_group(df_rq2, .x, continuous_visual_vars))
rq2_chisq_by_group <- map_dfr(rq2_group_vars, function(g) {
  map_dfr(categorical_visual_vars, ~run_chisq(df_rq2, g, .x))
})
rq2_kruskal_by_group <- map_dfr(rq2_group_vars, function(g) {
  map_dfr(continuous_visual_vars, ~run_kruskal(df_rq2, .x, g))
})
rq2_objects_by_group <- map_dfr(rq2_group_vars, function(g) {
  object_prevalence_by_group(objects_long_rq2, df_rq2, g)
})

write_xlsx_clean(
  list(
    binary_age_value_main = rq2_models_age_value$binary,
    cont_age_value_main = rq2_models_age_value$continuous,
    multi_age_value_main = rq2_models_age_value$multinom,
    terms_age_value_main = rq2_interaction_terms_age_value,
    binary_age_binary_aux = rq2_models_age_binary$binary,
    cont_age_binary_aux = rq2_models_age_binary$continuous,
    multi_age_binary_aux = rq2_models_age_binary$multinom,
    terms_age_binary_aux = rq2_interaction_terms_age_binary,
    binary_age_num_trend = rq2_models_age_num$binary,
    cont_age_num_trend = rq2_models_age_num$continuous,
    multi_age_num_trend = rq2_models_age_num$multinom,
    terms_age_num_trend = rq2_interaction_terms_age_num,
    cat_by_gender_nat_age = rq2_cat_by_group,
    cont_by_gender_nat_age = rq2_cont_by_group,
    chi_by_gender_nat_age = rq2_chisq_by_group,
    kruskal_by_gender_nat_age = rq2_kruskal_by_group,
    objects_by_gender_nat_age = rq2_objects_by_group
  ),
  file.path(output_dir, "RQ2_intersections.xlsx")
)

# -------------------------
# 9. RQ3：分模型 K-means 视觉叙事聚类
# -------------------------

# RQ3 只使用 11 个预先指定的 N/A/R 变量，并在每个模型内部单独聚类。
rq3_variable_dictionary <- tibble(
  layer = c(
    "N层/叙事层", "N层/叙事层",
    "A层/行动层", "A层/行动层", "A层/行动层", "A层/行动层",
    "R层/共鸣层", "R层/共鸣层", "R层/共鸣层", "R层/共鸣层", "R层/共鸣层"
  ),
  variable = c(
    "scene_type", "is_alone",
    "development_oriented_agency", "bhi", "modern_object", "traditional_cultural_marker",
    "bg_brightness", "bg_saturation", "image_entropy_background", "center_distance", "area_ratio"
  ),
  chinese_name = c(
    "场景类型", "是否独处",
    "发展导向能动性", "身体姿态收缩指数（BHI）", "现代性符号", "传统文化符号",
    "背景亮度", "背景饱和度", "背景信息熵", "视觉中心距离", "人物占图像比"
  ),
  processing = c(
    "类别变量，独热编码", "二元变量，独处/非独处",
    "二元变量，0=维持性活动，1=发展导向性活动", "模型内三分位分箱：低/中/高",
    "二元变量，有/无现代性符号", "二元变量，有/无传统文化符号",
    "模型内三分位分箱：低/中/高", "模型内三分位分箱：低/中/高",
    "模型内三分位分箱：低/中/高", "模型内三分位分箱：中心/中等/边缘",
    "模型内三分位分箱：小/中/大"
  )
)

rq3_continuous_vars <- c("bhi", "bg_brightness", "bg_saturation", "image_entropy_background", "center_distance", "area_ratio")
rq3_continuous_labels <- c(
  bhi = "BHI",
  bg_brightness = "背景亮度",
  bg_saturation = "背景饱和度",
  image_entropy_background = "背景信息熵",
  center_distance = "视觉中心距离",
  area_ratio = "人物占图像比"
)

rq3_scene_labels <- c(
  home = "居家",
  office = "办公",
  hospital = "医院",
  street = "街道",
  park = "公园",
  yard = "庭院",
  outdoor_other = "其他户外",
  unknown = "未知"
)

cn_font_family <- if (.Platform$OS.type == "windows") "Microsoft YaHei" else ""
cn_theme <- function() {
  theme_minimal(base_family = cn_font_family) +
    theme(
      plot.title = element_text(face = "bold"),
      axis.text.x = element_text(angle = 30, hjust = 1)
    )
}

mode_value <- function(x) {
  x <- x[!is.na(x)]
  if (length(x) == 0) return(NA_character_)
  names(sort(table(x), decreasing = TRUE))[1]
}

bin_tertile_cn <- function(x, low_label, mid_label, high_label, typical_label, unknown_label) {
  x_num <- as.numeric(x)
  out <- rep(unknown_label, length(x_num))
  valid <- !is.na(x_num)
  if (sum(valid) == 0) return(out)
  if (n_distinct(x_num[valid]) < 2) {
    out[valid] <- typical_label
    return(out)
  }

  qs <- unique(quantile(x_num[valid], probs = c(1 / 3, 2 / 3), na.rm = TRUE, names = FALSE))
  if (length(qs) < 2) {
    out[valid] <- typical_label
    return(out)
  }

  out[valid] <- case_when(
    x_num[valid] <= qs[1] ~ low_label,
    x_num[valid] <= qs[2] ~ mid_label,
    TRUE ~ high_label
  )
  out
}

rq3_threshold_table <- function(data) {
  map_dfr(rq3_continuous_vars, function(v) {
    if (!v %in% names(data)) return(tibble())
    x <- as.numeric(data[[v]])
    valid <- !is.na(x)
    if (sum(valid) == 0 || n_distinct(x[valid]) < 2) {
      return(tibble(
        variable = v,
        chinese_name = unname(rq3_continuous_labels[v]),
        low_upper = NA_real_,
        middle_upper = NA_real_,
        note = "有效值不足，未分三档"
      ))
    }
    qs <- unique(quantile(x[valid], probs = c(1 / 3, 2 / 3), na.rm = TRUE, names = FALSE))
    tibble(
      variable = v,
      chinese_name = unname(rq3_continuous_labels[v]),
      low_upper = if_else(length(qs) >= 1, qs[1], NA_real_),
      middle_upper = if_else(length(qs) >= 2, qs[2], NA_real_),
      note = if_else(length(qs) >= 2, "低≤low_upper；中≤middle_upper；高>middle_upper", "阈值重复，使用典型值")
    )
  })
}

build_rq3_binned_data <- function(data) {
  data %>%
    mutate(
      场景类型 = recode(as.character(scene_type), !!!rq3_scene_labels, .default = "未知", .missing = "未知"),
      是否独处 = case_when(is_alone == 1 ~ "独处", is_alone == 0 ~ "非独处", TRUE ~ "未知"),
      发展导向能动性 = case_when(development_oriented_agency == 1 ~ "发展导向性活动", development_oriented_agency == 0 ~ "维持性活动", TRUE ~ "未知"),
      现代性符号 = case_when(modern_object == 1 ~ "有现代性符号", modern_object == 0 ~ "无现代性符号", TRUE ~ "未知"),
      传统文化符号 = case_when(traditional_cultural_marker == 1 ~ "有传统文化符号", traditional_cultural_marker == 0 ~ "无传统文化符号", TRUE ~ "未知"),
      BHI分箱 = bin_tertile_cn(bhi, "BHI低", "BHI中", "BHI高", "BHI典型", "BHI未知"),
      背景亮度分箱 = bin_tertile_cn(bg_brightness, "亮度低", "亮度中", "亮度高", "亮度典型", "亮度未知"),
      背景饱和度分箱 = bin_tertile_cn(bg_saturation, "饱和度低", "饱和度中", "饱和度高", "饱和度典型", "饱和度未知"),
      背景信息熵分箱 = bin_tertile_cn(image_entropy_background, "背景熵低", "背景熵中", "背景熵高", "背景熵典型", "背景熵未知"),
      视觉中心距离分箱 = bin_tertile_cn(center_distance, "中心", "中等距离", "边缘", "中心距离典型", "中心距离未知"),
      人物占图像比分箱 = bin_tertile_cn(area_ratio, "占比小", "占比中", "占比大", "占比典型", "占比未知")
    )
}

rq3_feature_cols <- c(
  "场景类型", "是否独处", "发展导向能动性", "BHI分箱", "现代性符号", "传统文化符号",
  "背景亮度分箱", "背景饱和度分箱", "背景信息熵分箱", "视觉中心距离分箱", "人物占图像比分箱"
)

prepare_kmeans_matrix <- function(data) {
  binned <- build_rq3_binned_data(data)
  feature_data <- binned %>%
    select(row_id, all_of(rq3_feature_cols)) %>%
    mutate(across(all_of(rq3_feature_cols), ~factor(replace_na(as.character(.), "未知"))))

  dummy_blocks <- map(rq3_feature_cols, function(v) {
    values <- droplevels(feature_data[[v]])
    block <- model.matrix(~ values - 1) %>% as.data.frame(check.names = FALSE)
    names(block) <- paste0(v, "=", levels(values))
    keep <- vapply(block, function(x) sd(x, na.rm = TRUE) > 0, logical(1))
    block <- block[, keep, drop = FALSE]
    if (ncol(block) == 0) return(NULL)
    block
  })
  dummy_blocks <- dummy_blocks[!vapply(dummy_blocks, is.null, logical(1))]
  if (length(dummy_blocks) == 0) {
    return(list(row_id = binned$row_id, matrix = NULL, feature_names = character(), binned_data = binned, dummy_unweighted = NULL))
  }

  dummy_unweighted <- bind_cols(dummy_blocks)
  weighted_blocks <- map(dummy_blocks, function(block) block / sqrt(ncol(block)))
  feature_df <- bind_cols(weighted_blocks)
  feature_names <- names(feature_df)
  feature_matrix <- as.matrix(feature_df)
  feature_matrix[!is.finite(feature_matrix)] <- 0

  list(
    row_id = binned$row_id,
    matrix = feature_matrix,
    feature_names = feature_names,
    binned_data = binned,
    dummy_unweighted = dummy_unweighted
  )
}

cluster_distribution_by_age <- function(assignments) {
  assignments %>%
    filter(!is.na(age_value), !is.na(cluster)) %>%
    count(age_value, cluster, name = "n") %>%
    group_by(age_value) %>%
    mutate(percent_within_age = n / sum(n) * 100) %>%
    ungroup() %>%
    mutate(年龄组 = as.character(age_value)) %>%
    select(年龄组, cluster, n, percent_within_age)
}

make_cluster_profile <- function(assignments, binned_data) {
  profile_data <- assignments %>%
    select(row_id, cluster) %>%
    left_join(binned_data, by = "row_id")

  profile_data %>%
    group_by(cluster) %>%
    summarise(
      样本量 = n(),
      主要场景 = mode_value(场景类型),
      独处比例 = mean(is_alone == 1, na.rm = TRUE),
      发展导向比例 = mean(development_oriented_agency == 1, na.rm = TRUE),
      平均BHI = safe_mean(bhi),
      BHI分箱众数 = mode_value(BHI分箱),
      现代性符号比例 = mean(modern_object == 1, na.rm = TRUE),
      传统文化符号比例 = mean(traditional_cultural_marker == 1, na.rm = TRUE),
      平均背景亮度 = safe_mean(bg_brightness),
      背景亮度分箱众数 = mode_value(背景亮度分箱),
      平均背景饱和度 = safe_mean(bg_saturation),
      背景饱和度分箱众数 = mode_value(背景饱和度分箱),
      平均背景信息熵 = safe_mean(image_entropy_background),
      背景信息熵分箱众数 = mode_value(背景信息熵分箱),
      平均视觉中心距离 = safe_mean(center_distance),
      视觉中心距离分箱众数 = mode_value(视觉中心距离分箱),
      平均人物占图像比 = safe_mean(area_ratio),
      人物占图像比分箱众数 = mode_value(人物占图像比分箱),
      .groups = "drop"
    ) %>%
    mutate(
      聚类命名 = pmap_chr(
        list(主要场景, 独处比例, 发展导向比例, 现代性符号比例, 传统文化符号比例),
        function(scene, alone, dev, modern, traditional) {
          relation <- if_else(is.na(alone), "关系混合", if_else(alone >= 0.6, "独处", if_else(alone <= 0.4, "共处", "关系混合")))
          agency <- if_else(is.na(dev), "行动混合", if_else(dev >= 0.5, "发展导向", "维持"))
          symbol <- case_when(
            !is.na(traditional) && traditional >= 0.5 ~ "传统",
            !is.na(modern) && modern >= 0.5 ~ "现代",
            TRUE ~ "非现代"
          )
          paste0(relation, scene, symbol, agency, "型")
        }
      ),
      cluster_label = paste0("聚类", str_remove(as.character(cluster), "cluster_"), "：", 聚类命名)
    ) %>%
    relocate(cluster, cluster_label, 聚类命名, 样本量)
}

make_cluster_feature_contribution <- function(assignments, dummy_unweighted) {
  if (is.null(dummy_unweighted) || ncol(dummy_unweighted) == 0) return(tibble())
  dummy_df <- dummy_unweighted %>%
    mutate(row_id = assignments$row_id) %>%
    left_join(assignments %>% select(row_id, cluster), by = "row_id")
  overall <- dummy_df %>%
    summarise(across(-c(row_id, cluster), safe_mean)) %>%
    pivot_longer(everything(), names_to = "特征", values_to = "总体比例")

  dummy_df %>%
    group_by(cluster) %>%
    summarise(across(-row_id, safe_mean), .groups = "drop") %>%
    pivot_longer(-cluster, names_to = "特征", values_to = "聚类内比例") %>%
    left_join(overall, by = "特征") %>%
    mutate(
      相对总体差异 = 聚类内比例 - 总体比例,
      变量 = str_replace(特征, "=.*$", ""),
      类别 = str_replace(特征, "^.*=", "")
    ) %>%
    group_by(cluster) %>%
    arrange(desc(abs(相对总体差异)), .by_group = TRUE) %>%
    mutate(rank = row_number()) %>%
    ungroup()
}

make_age_prediction_diagnostic <- function(assignments) {
  model_data <- assignments %>%
    filter(!is.na(cluster), !is.na(age_value)) %>%
    mutate(cluster = factor(cluster), age_value = factor(age_value))
  if (nrow(model_data) == 0 || n_distinct(model_data$cluster) < 2 || n_distinct(model_data$age_value) < 2) {
    return(analysis_note("年龄预测聚类", "聚类或年龄组水平不足，未建模。"))
  }

  tab <- table(model_data$age_value, model_data$cluster)
  chi <- suppressWarnings(chisq.test(tab))
  baseline_accuracy <- max(table(model_data$cluster)) / nrow(model_data)
  fit <- tryCatch(nnet::multinom(cluster ~ age_value, data = model_data, trace = FALSE), error = function(e) NULL)
  null_fit <- tryCatch(nnet::multinom(cluster ~ 1, data = model_data, trace = FALSE), error = function(e) NULL)
  if (is.null(fit)) {
    return(tibble(
      指标 = c("样本量", "多数类基线准确率", "卡方检验p值"),
      数值 = c(nrow(model_data), baseline_accuracy, chi$p.value),
      说明 = c("用于年龄预测诊断的样本数", "不使用年龄时始终预测最大簇", "检验年龄组与聚类是否独立")
    ))
  }

  pred <- predict(fit, newdata = model_data, type = "class")
  accuracy <- mean(pred == model_data$cluster)
  pseudo_r2 <- if (!is.null(null_fit) && is.finite(null_fit$deviance) && null_fit$deviance > 0) 1 - fit$deviance / null_fit$deviance else NA_real_
  recommendation <- if_else(accuracy - baseline_accuracy >= 0.05, "可作为补充诊断，不作为主结论", "相对多数类基线提升有限，不建议展开为主分析")
  tibble(
    指标 = c("样本量", "多数类基线准确率", "年龄模型训练准确率", "准确率提升", "McFadden伪R2", "卡方检验p值", "建议"),
    数值 = c(nrow(model_data), baseline_accuracy, accuracy, accuracy - baseline_accuracy, pseudo_r2, chi$p.value, NA_real_),
    说明 = c("用于年龄预测诊断的样本数", "不使用年龄时始终预测最大簇", "cluster ~ age_value 的训练集准确率", "年龄模型准确率减去基线准确率", "仅作关联强度参考", "检验年龄组与聚类是否独立", recommendation)
  )
}

plot_model_rq3_outputs <- function(model_name, model_dir_safe, model_output_dir, assignments, cluster_profile, age_cluster_distribution, feature_contribution, kmeans_matrix, output_suffix = "") {
  plot_assignments <- assignments %>%
    left_join(cluster_profile %>% select(cluster, cluster_label), by = "cluster") %>%
    mutate(年龄组 = as.character(age_value))

  if (!is.null(kmeans_matrix) && ncol(kmeans_matrix) >= 2 && nrow(kmeans_matrix) >= 3) {
    pca <- prcomp(kmeans_matrix, center = TRUE, scale. = FALSE)
    pca_df <- as.data.frame(pca$x[, 1:2, drop = FALSE]) %>%
      mutate(row_id = assignments$row_id) %>%
      left_join(plot_assignments, by = "row_id")
    p_pca <- pca_df %>%
      ggplot(aes(x = PC1, y = PC2, color = cluster_label, shape = 年龄组)) +
      geom_point(alpha = 0.65, size = 1.7) +
      labs(title = paste0(model_name, "：RQ3 K-means 聚类PCA投影"), x = "主成分1", y = "主成分2", color = "聚类", shape = "年龄组") +
      cn_theme()
    ggsave(file.path(model_output_dir, paste0(model_dir_safe, "_RQ3_kmeans_pca_cn", output_suffix, ".png")), p_pca, width = 10, height = 7, dpi = 300)
  }

  age_plot_data <- age_cluster_distribution
  if (!"cluster_label" %in% names(age_plot_data)) {
    age_plot_data <- age_plot_data %>% left_join(cluster_profile %>% select(cluster, cluster_label), by = "cluster")
  }
  p_age <- age_plot_data %>%
    ggplot(aes(x = 年龄组, y = percent_within_age, fill = cluster_label)) +
    geom_col() +
    scale_y_continuous(labels = function(x) paste0(x, "%"), limits = c(0, 100)) +
    labs(title = paste0(model_name, "：五个年龄组的聚类分布"), x = "年龄组", y = "组内比例", fill = "聚类") +
    cn_theme()
  ggsave(file.path(model_output_dir, paste0(model_dir_safe, "_RQ3_age_cluster_distribution_cn", output_suffix, ".png")), p_age, width = 10, height = 6, dpi = 300)

  heatmap_data <- feature_contribution %>% filter(rank <= 8)
  if (!"cluster_label" %in% names(heatmap_data)) {
    heatmap_data <- heatmap_data %>% left_join(cluster_profile %>% select(cluster, cluster_label), by = "cluster")
  }
  heatmap_data <- heatmap_data %>%
    mutate(特征标签 = paste0(变量, "：", 类别))
  if (nrow(heatmap_data) > 0) {
    p_heat <- heatmap_data %>%
      ggplot(aes(x = fct_reorder(特征标签, 相对总体差异), y = cluster_label, fill = 相对总体差异)) +
      geom_tile(color = "white") +
      scale_fill_gradient2(low = "#2c7bb6", mid = "white", high = "#d7191c", midpoint = 0) +
      labs(title = paste0(model_name, "：聚类特征画像"), x = "突出特征", y = "聚类", fill = "相对总体差异") +
      cn_theme() +
      theme(axis.text.x = element_text(angle = 45, hjust = 1))
    ggsave(file.path(model_output_dir, paste0(model_dir_safe, "_RQ3_cluster_profile_heatmap_cn", output_suffix, ".png")), p_heat, width = 12, height = 7, dpi = 300)
  }
}

# RQ3 主结果只在四个分模型目录中输出；不再生成跨模型签名表或总体聚类表。

# -------------------------
# 10. 图像输出：辅助论文写作与快速浏览
# -------------------------
save_stacked_age_plot <- function(data, var, filename, title) {
  if (!all(c("age_value", var) %in% names(data))) return(invisible(NULL))

  plot_data <- data %>%
    filter(!is.na(age_value), !is.na(.data[[var]])) %>%
    mutate(plot_value = as.factor(.data[[var]]))
  if (nrow(plot_data) == 0 || n_distinct(plot_data$plot_value) < 2) return(invisible(NULL))

  p <- plot_data %>%
    ggplot(aes(x = age_value, fill = plot_value)) +
    geom_bar(position = "fill") +
    labs(title = title, x = "Age", y = "Proportion", fill = var) +
    theme_minimal()

  ggsave(file.path(fig_dir, filename), p, width = 9, height = 5, dpi = 300)
}

save_boxplot_age <- function(data, var, filename, title) {
  if (!all(c("age_value", var) %in% names(data))) return(invisible(NULL))

  plot_data <- data %>% filter(!is.na(age_value), !is.na(.data[[var]]))
  if (nrow(plot_data) == 0 || n_distinct(plot_data$age_value) < 2) return(invisible(NULL))

  p <- plot_data %>%
    ggplot(aes(x = age_value, y = .data[[var]])) +
    geom_boxplot() +
    labs(title = title, x = "Age", y = var) +
    theme_minimal()

  ggsave(file.path(fig_dir, filename), p, width = 8, height = 5, dpi = 300)
}

save_stacked_age_plot(df_main, "agency_orientation", "RQ1_agency_orientation_by_age.png", "Agency orientation by age group")
save_stacked_age_plot(df_main, "development_oriented_agency", "RQ1_development_oriented_agency_by_age.png", "Development-oriented agency by age group")
save_stacked_age_plot(df_main, "agency_level", "RQ1_original_agency_by_age.png", "Original active/passive agency by age group")
save_stacked_age_plot(df_main, "scene_type", "RQ1_scene_by_age.png", "Scene type by age group")
save_stacked_age_plot(df_main, "space_type", "RQ1_space_by_age.png", "Space type by age group")
save_stacked_age_plot(df_main, "is_alone", "RQ1_solitude_by_age.png", "Solitude by age group")

for (v in present_vars(c("bhi", "area_ratio", "center_distance", "bg_brightness", "bg_saturation", "image_entropy_background"), df_main)) {
  save_boxplot_age(df_main, v, paste0("RQ1_", v, "_by_age.png"), paste(v, "by age group"))
}

# RQ3 现在只在分模型目录输出 K-means 中文图表。
# -------------------------
# 11. 论文可直接引用的核心表
# -------------------------
paper_rq1_core <- bind_rows(
  rq1_chisq_age_binary %>% transmute(rq = "RQ1", analysis = "categorical_age_binary", variable, p_value, effect_size = cramers_v, note),
  rq1_chisq_age_value %>% transmute(rq = "RQ1", analysis = "categorical_age_value", variable, p_value, effect_size = cramers_v, note),
  rq1_wilcox_age_binary %>% transmute(rq = "RQ1", analysis = "continuous_age_binary", variable = outcome, p_value, effect_size = median_diff, note),
  rq1_kruskal_age_value %>% transmute(rq = "RQ1", analysis = "continuous_age_value", variable = outcome, p_value, effect_size = statistic, note)
)

paper_rq2_interactions <- bind_rows(
  rq2_interaction_terms_age_value %>% transmute(rq = "RQ2", analysis = "age_value_interaction_main", outcome, term, estimate, p_value = p.value, note),
  rq2_interaction_terms_age_binary %>% transmute(rq = "RQ2", analysis = "age_binary_interaction_aux", outcome, term, estimate, p_value = p.value, note),
  rq2_interaction_terms_age_num %>% transmute(rq = "RQ2", analysis = "age_num_interaction_trend", outcome, term, estimate, p_value = p.value, note)
)

write_xlsx_clean(
  list(
    RQ1_core_tests = paper_rq1_core,
    RQ2_interactions = paper_rq2_interactions,
    RQ3_variable_dictionary = rq3_variable_dictionary
  ),
  file.path(output_dir, "paper_core_tables.xlsx")
)


# -------------------------
# 12. 按模型单独汇报：每个模型各输出一套 RQ1/RQ2/RQ3 表
# -------------------------
model_output_root <- file.path(output_dir, "by_model")
if (!dir.exists(model_output_root)) dir.create(model_output_root, recursive = TRUE)

run_single_model_reports <- function(model_name) {
  model_data <- df_main %>% filter(as.character(model) == model_name)
  if (nrow(model_data) == 0) return(invisible(NULL))

  model_dir_safe <- make.names(model_name)
  model_output_dir <- file.path(model_output_root, model_dir_safe)
  if (!dir.exists(model_output_dir)) dir.create(model_output_dir, recursive = TRUE)

  model_objects_long <- build_objects_long(model_data)

  model_cat_age_binary <- map_dfr(categorical_visual_vars, ~freq_by_group(model_data, "age_binary", .x))
  model_cat_age_value <- map_dfr(categorical_visual_vars, ~freq_by_group(model_data, "age_value", .x))
  model_action_age_binary <- map_dfr(action_vars, ~freq_by_group(model_data, "age_binary", .x))
  model_action_age_value <- map_dfr(action_vars, ~freq_by_group(model_data, "age_value", .x))
  model_chisq_age_binary <- map_dfr(categorical_visual_vars, ~run_chisq(model_data, "age_binary", .x))
  model_chisq_age_value <- map_dfr(categorical_visual_vars, ~run_chisq(model_data, "age_value", .x))
  model_cont_age_binary <- continuous_by_group(model_data, "age_binary", continuous_visual_vars)
  model_cont_age_value <- continuous_by_group(model_data, "age_value", continuous_visual_vars)
  model_wilcox_age_binary <- map_dfr(continuous_visual_vars, ~run_wilcox(model_data, .x, "age_binary"))
  model_kruskal_age_value <- map_dfr(continuous_visual_vars, ~run_kruskal(model_data, .x, "age_value"))
  model_pairwise_age_value <- map_dfr(
    present_vars(c("bhi", "bg_brightness", "bg_saturation", "image_entropy_background", "area_ratio", "num_persons", "medical_object_count"), model_data),
    ~run_pairwise_dunn(model_data, .x, "age_value")
  )

  model_rhs_age_value <- build_rhs(model_data, c("age_value", "gender", "nationality"), fallback = "age_num")
  model_rhs_age_binary <- build_rhs(model_data, c("age_binary", "gender", "nationality"), fallback = "age_num")
  model_rhs_age_num <- build_rhs(model_data, c("age_num", "gender", "nationality"), fallback = "age_num")

  run_model_rq1_model_set <- function(rhs, model_tag) {
    list(
      logit = map_dfr(binary_visual_vars, ~safe_glm_binomial(model_data, .x, rhs, paste0(model_name, "_RQ1_", model_tag, "_", .x))),
      linear = map_dfr(continuous_visual_vars, ~safe_lm(model_data, .x, rhs, paste0(model_name, "_RQ1_", model_tag, "_", .x))),
      multinom = map_dfr(present_vars(c("scene_type", "space_type", "environment_type"), model_data), ~safe_multinom(model_data, .x, rhs, paste0(model_name, "_RQ1_", model_tag, "_", .x)))
    )
  }

  model_rq1_age_value <- run_model_rq1_model_set(model_rhs_age_value, "age_value_main")
  model_rq1_age_binary <- run_model_rq1_model_set(model_rhs_age_binary, "age_binary_aux")
  model_rq1_age_num <- run_model_rq1_model_set(model_rhs_age_num, "age_num_trend")

  write_xlsx_clean(
    list(
      cat_age_binary = model_cat_age_binary,
      cat_age_value = model_cat_age_value,
      action_age_binary = model_action_age_binary,
      action_age_value = model_action_age_value,
      chi_age_binary = model_chisq_age_binary,
      chi_age_value = model_chisq_age_value,
      cont_age_binary = model_cont_age_binary,
      cont_age_value = model_cont_age_value,
      wilcox_age_binary = model_wilcox_age_binary,
      kruskal_age_value = model_kruskal_age_value,
      pairwise_age_value = model_pairwise_age_value,
      logit_age_value_main = model_rq1_age_value$logit,
      linear_age_value_main = model_rq1_age_value$linear,
      multinom_age_value_main = model_rq1_age_value$multinom,
      logit_age_binary_aux = model_rq1_age_binary$logit,
      linear_age_binary_aux = model_rq1_age_binary$linear,
      multinom_age_binary_aux = model_rq1_age_binary$multinom,
      logit_age_num_trend = model_rq1_age_num$logit,
      linear_age_num_trend = model_rq1_age_num$linear,
      multinom_age_num_trend = model_rq1_age_num$multinom
    ),
    file.path(model_output_dir, paste0(model_dir_safe, "_RQ1_age_differences.xlsx"))
  )

  model_object_age_binary <- object_prevalence_by_group(model_objects_long, model_data, "age_binary")
  model_object_age_value <- object_prevalence_by_group(model_objects_long, model_data, "age_value")
  model_object_compare <- compare_object_prevalence(model_object_age_binary)
  write_xlsx_clean(
    list(
      object_age_binary = model_object_age_binary,
      object_age_value = model_object_age_value,
      object_compare = model_object_compare
    ),
    file.path(model_output_dir, paste0(model_dir_safe, "_RQ1_object_differences.xlsx"))
  )

  build_model_rq2_rhs <- function(age_var) {
    terms <- c()
    if (enough_levels(model_data, age_var) && enough_levels(model_data, "gender")) {
      terms <- c(terms, paste0(age_var, " * gender"))
    }
    if (enough_levels(model_data, age_var) && enough_levels(model_data, "nationality")) {
      terms <- c(terms, paste0(age_var, " * nationality"))
    }
    if (length(terms) == 0) return(age_var)
    paste(terms, collapse = " + ")
  }

  run_model_rq2_interaction_set <- function(rhs, model_tag) {
    list(
      binary = map_dfr(binary_visual_vars, ~safe_glm_binomial(model_data, .x, rhs, paste0(model_name, "_RQ2_", model_tag, "_", .x))),
      continuous = map_dfr(continuous_visual_vars, ~safe_lm(model_data, .x, rhs, paste0(model_name, "_RQ2_", model_tag, "_", .x))),
      multinom = map_dfr(present_vars(c("scene_type", "space_type", "environment_type"), model_data), ~safe_multinom(model_data, .x, rhs, paste0(model_name, "_RQ2_", model_tag, "_", .x)))
    )
  }

  model_rq2_age_value <- run_model_rq2_interaction_set(build_model_rq2_rhs("age_value"), "age_value_interaction_main")
  model_rq2_age_binary <- run_model_rq2_interaction_set(build_model_rq2_rhs("age_binary"), "age_binary_interaction_aux")
  model_rq2_age_num <- run_model_rq2_interaction_set(build_model_rq2_rhs("age_num"), "age_num_interaction_trend")

  model_rq2 <- model_data %>%
    mutate(
      age_gender = interaction(age_binary, gender, drop = TRUE, sep = " | "),
      age_nationality = interaction(age_binary, nationality, drop = TRUE, sep = " | "),
      age_value_gender = interaction(age_value, gender, drop = TRUE, sep = " | "),
      age_value_nationality = interaction(age_value, nationality, drop = TRUE, sep = " | ")
    )
  model_rq2_group_vars <- present_vars(c("gender", "nationality", "age_gender", "age_nationality", "age_value_gender", "age_value_nationality"), model_rq2)
  model_object_group_cols <- setdiff(model_rq2_group_vars, names(model_objects_long))
  model_objects_long_rq2 <- if (nrow(model_objects_long) > 0) {
    model_objects_long %>%
      left_join(model_rq2 %>% select(row_id, all_of(model_object_group_cols)), by = "row_id")
  } else {
    model_objects_long
  }

  model_rq2_cat_by_group <- map_dfr(model_rq2_group_vars, function(g) {
    map_dfr(categorical_visual_vars, ~freq_by_group(model_rq2, g, .x))
  })
  model_rq2_cont_by_group <- map_dfr(model_rq2_group_vars, ~continuous_by_group(model_rq2, .x, continuous_visual_vars))
  model_rq2_chisq_by_group <- map_dfr(model_rq2_group_vars, function(g) {
    map_dfr(categorical_visual_vars, ~run_chisq(model_rq2, g, .x))
  })
  model_rq2_kruskal_by_group <- map_dfr(model_rq2_group_vars, function(g) {
    map_dfr(continuous_visual_vars, ~run_kruskal(model_rq2, .x, g))
  })
  model_rq2_objects_by_group <- map_dfr(model_rq2_group_vars, function(g) {
    object_prevalence_by_group(model_objects_long_rq2, model_rq2, g)
  })

  write_xlsx_clean(
    list(
      binary_age_value_main = model_rq2_age_value$binary,
      cont_age_value_main = model_rq2_age_value$continuous,
      multi_age_value_main = model_rq2_age_value$multinom,
      terms_age_value_main = bind_rows(model_rq2_age_value$binary, model_rq2_age_value$continuous, model_rq2_age_value$multinom) %>% filter(str_detect(term, ":")),
      binary_age_binary_aux = model_rq2_age_binary$binary,
      cont_age_binary_aux = model_rq2_age_binary$continuous,
      multi_age_binary_aux = model_rq2_age_binary$multinom,
      terms_age_binary_aux = bind_rows(model_rq2_age_binary$binary, model_rq2_age_binary$continuous, model_rq2_age_binary$multinom) %>% filter(str_detect(term, ":")),
      binary_age_num_trend = model_rq2_age_num$binary,
      cont_age_num_trend = model_rq2_age_num$continuous,
      multi_age_num_trend = model_rq2_age_num$multinom,
      terms_age_num_trend = bind_rows(model_rq2_age_num$binary, model_rq2_age_num$continuous, model_rq2_age_num$multinom) %>% filter(str_detect(term, ":")),
      cat_by_gender_nat_age = model_rq2_cat_by_group,
      cont_by_gender_nat_age = model_rq2_cont_by_group,
      chi_by_gender_nat_age = model_rq2_chisq_by_group,
      kruskal_by_gender_nat_age = model_rq2_kruskal_by_group,
      objects_by_gender_nat_age = model_rq2_objects_by_group
    ),
    file.path(model_output_dir, paste0(model_dir_safe, "_RQ2_intersections.xlsx"))
  )

  model_rq3_older <- model_rq2 %>% filter(age_value %in% c("60", "75", "90"))
  model_kmeans_input <- prepare_kmeans_matrix(model_rq3_older)
  if (is.null(model_kmeans_input$matrix) || nrow(model_kmeans_input$matrix) < 4) {
    model_kmeans_results <- list(kmeans_note = analysis_note("model_RQ3_kmeans_older_only", "Not enough usable older-adult rows/features for K-means."))
    write_xlsx_clean(model_kmeans_results, file.path(model_output_dir, paste0(model_dir_safe, "_RQ3_kmeans_cn_older_only.xlsx")))
    return(invisible(model_output_dir))
  }

  set.seed(1234)
  model_max_k <- min(8, nrow(model_kmeans_input$matrix) - 1)
  model_candidate_k <- 2:model_max_k
  model_silhouette_matrix <- model_kmeans_input$matrix
  model_silhouette_sample <- seq_len(nrow(model_silhouette_matrix))
  if (nrow(model_silhouette_matrix) > 2000) {
    set.seed(1234)
    model_silhouette_sample <- sample(seq_len(nrow(model_silhouette_matrix)), 2000)
    model_silhouette_matrix <- model_silhouette_matrix[model_silhouette_sample, , drop = FALSE]
  }

  model_kmeans_diagnostics <- map_dfr(model_candidate_k, function(k) {
    fit <- kmeans(model_kmeans_input$matrix, centers = k, nstart = 30, iter.max = 100)
    sil <- tryCatch(
      mean(cluster::silhouette(fit$cluster[model_silhouette_sample], dist(model_silhouette_matrix))[, "sil_width"]),
      error = function(e) NA_real_
    )
    tibble(k = k, tot_withinss = fit$tot.withinss, betweenss_ratio = fit$betweenss / fit$totss, avg_silhouette = sil)
  })
  model_selected_k <- model_kmeans_diagnostics %>% arrange(desc(avg_silhouette), tot_withinss) %>% slice(1) %>% pull(k)
  if (length(model_selected_k) == 0 || is.na(model_selected_k)) model_selected_k <- 3

  model_final_kmeans <- kmeans(model_kmeans_input$matrix, centers = model_selected_k, nstart = 50, iter.max = 100)
  model_cluster_assignments <- tibble(
    row_id = model_kmeans_input$row_id,
    cluster = factor(paste0("cluster_", model_final_kmeans$cluster))
  ) %>%
    left_join(
      model_kmeans_input$binned_data %>%
        select(row_id, model, filename, age, age_value, age_label, age_binary, gender, nationality, all_of(rq3_feature_cols)),
      by = "row_id"
    )

  model_cluster_profile <- make_cluster_profile(model_cluster_assignments, model_kmeans_input$binned_data)
  model_age_cluster_distribution <- cluster_distribution_by_age(model_cluster_assignments) %>%
    left_join(model_cluster_profile %>% select(cluster, cluster_label, 聚类命名), by = "cluster") %>%
    arrange(年龄组, cluster)
  model_feature_contribution <- make_cluster_feature_contribution(model_cluster_assignments, model_kmeans_input$dummy_unweighted) %>%
    left_join(model_cluster_profile %>% select(cluster, cluster_label, 聚类命名), by = "cluster") %>%
    arrange(cluster, rank)
  model_thresholds <- rq3_threshold_table(model_rq3_older)
  model_age_prediction <- make_age_prediction_diagnostic(model_cluster_assignments)

  plot_model_rq3_outputs(
    model_name = model_name,
    model_dir_safe = model_dir_safe,
    model_output_dir = model_output_dir,
    assignments = model_cluster_assignments,
    cluster_profile = model_cluster_profile,
    age_cluster_distribution = model_age_cluster_distribution,
    feature_contribution = model_feature_contribution,
    kmeans_matrix = model_kmeans_input$matrix,
    output_suffix = "_older_only"
  )

  model_kmeans_results <- list(
    变量说明 = rq3_variable_dictionary,
    连续变量分箱阈值 = model_thresholds,
    K值诊断 = model_kmeans_diagnostics,
    聚类画像 = model_cluster_profile,
    年龄组x聚类 = model_age_cluster_distribution,
    聚类特征贡献 = model_feature_contribution,
    聚类分配 = model_cluster_assignments,
    年龄预测诊断 = model_age_prediction
  )
  write_xlsx_clean(model_kmeans_results, file.path(model_output_dir, paste0(model_dir_safe, "_RQ3_kmeans_cn_older_only.xlsx")))

  invisible(model_output_dir)
}

walk(sort(unique(as.character(df_main$model))), run_single_model_reports)


cat("=====================================\n")
cat("分析完成，结果已保存到：\n")
cat(output_dir, "\n")
cat("\n")
cat("数据概览：\n")
cat("00_data_overview.xlsx\n")
cat("00_analysis_scope.txt\n")
cat("\n")
cat("RQ1 输出：\n")
cat("RQ1_age_differences.xlsx\n")
cat("RQ1_object_differences.xlsx\n")
cat("\n")
cat("RQ2 输出：\n")
cat("RQ2_intersections.xlsx\n")
cat("\n")
cat("RQ3 输出：\n")
cat("各模型目录下的 {model}_RQ3_kmeans_cn_older_only.xlsx 及老年组中文聚类图片\n")
cat("\n")
cat("按模型单独输出目录：\n")
cat(model_output_root, "\n")
cat("\n")
cat("论文核心表：\n")
cat("paper_core_tables.xlsx\n")
cat("\n")
cat("图像目录：\n")
cat(fig_dir, "\n")
cat("=====================================\n")

