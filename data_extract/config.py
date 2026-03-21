#!/usr/bin/env python3
"""配置文件 - 提供商、模型、提示词"""

from pathlib import Path

# ============ 路径配置 ============
BASE_DIR = Path("/home/aari/workplace/lunwen")
PDF_ROOT = BASE_DIR / "Z1-Z16"

# ============ 提供商配置 ============
PROVIDERS = {
    "siliconflow": {
        "name": "SiliconFlow (便宜)",
        "api_url": "https://api.siliconflow.cn/v1/chat/completions",
        "api_key": "sk-rreelokvxzhhiohugkebktsekvzvdzmkfznclxmeyniwvzrm",
        "model": "moonshotai/Kimi-K2-Thinking",
        "max_tokens": 8192,
        "temperature": 0.0,
        "top_p": 0.7,
        "top_k": 50,
        "frequency_penalty": 0,
        "thinking_budget": 4096,
    },
    "volcengine": {
        "name": "火山方舟 (doubao)",
        "api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key": "b1806401-372c-4845-af51-cc1ddfbae7c6",
        "model": "doubao-seed-1-6-251015",
        "max_tokens": 16384,
        "temperature": 0.0,
        "top_p": 0.7,
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
    },
    "xaio": {
        "name": "X-AIO (多模型)",
        "api_url": "https://code-api.x-aio.com/v1/chat/completions",
        "api_key": "sk-9bac320b2ac34b68a0511360457",
        "model": "Qwen3-Coder-480B-A35B-Instruct",  # 最强模型 480B，准确率最高，Coder版本擅长结构化数据提取
        "max_tokens": 8192,
        "temperature": 0.0,
        "top_p": 0.7,
        "headers": {
            "User-Agent": "claude-code/2.1.3",
            "X-Client-Name": "claude-code",
            "X-Client-Version": "2.1.3",
        },
    },
}

# 当前使用的提供商
ACTIVE_PROVIDER = "siliconflow"

# 动态生成输出目录（根据模型名称）
def get_output_root():
    """根据当前活跃的提供商和模型生成输出目录"""
    provider_config = PROVIDERS[ACTIVE_PROVIDER]
    model_name = provider_config["model"].replace("/", "_").replace(":", "_")
    return BASE_DIR / f"extracted_data_{model_name}"

OUTPUT_ROOT = get_output_root()

# ============ 提示词 ============
EXTRACTION_PROMPT = """You are a professional materials science data extraction assistant.
Your task is to extract key parameters for ALL organic semiconductor materials/compounds mentioned in the paper.

**CRITICAL INSTRUCTIONS:**
1. Extract EVERY compound mentioned in the paper.
2. If the paper compares multiple compounds (e.g., P1, P2, P3), extract data for EACH of them separately.
3. Look for compound names in: title, text, tables, and figures.

**FIELDS TO EXTRACT (Return null if not found):**

1.  **compound_name**: The abbreviation or name used in the text.
2.  **Mobility**:
    *   `max_electron_mobility`: Max electron mobility (cm²/V·s).
    *   `max_hole_mobility`: Max hole mobility (cm²/V·s).

3.  **Energy Levels** (eV):
    *   `HOMO`: Highest Occupied Molecular Orbital.
    *   `LUMO`: Lowest Unoccupied Molecular Orbital.
    *   `EA`: Electron Affinity.
    *   `Eg`: Optical Bandgap.
    *   `IP`: Ionization Potential.

4.  **Molecular Properties**:
    *   `Mn`: Number-average molecular weight (kDa).
    *   `Mw`: Weight-average molecular weight (kDa).
    *   `PDI`: Polydispersity Index.

5.  **Microstructure** (Å):
    *   `pi_stacking_distance`: π-π stacking distance.
    *   `lamella_distance`: Lamella distance / d-spacing.

6.  **Device Config**:
    *   `structure`: Device architecture (e.g., "TGBC", "BGBC", "TGTC", "BGTC").

7.  **Processing Conditions**:
    *   `doped`: "Yes" or "No".
    *   `dopant`: Name of dopant.
    *   `dopant_amount`: Amount/Ratio of dopant.
    *   `annealed`: "Yes" or "No".
    *   `annealing_temperature`: Temperature in °C.
    *   `annealing_atmosphere`: Atmosphere (e.g., "Vacuum", "N2", "Air").

**RULES:**
- Only extract values explicitly stated.
- Use null for missing values.
- Return ONLY valid JSON. No markdown, no explanations.

**OUTPUT FORMAT:**
{
  "compounds": [
    {
      "compound_name": "...",
      "max_electron_mobility": ...,
      "max_hole_mobility": ...,
      "HOMO": ...,
      "LUMO": ...,
      "EA": ...,
      "Eg": ...,
      "IP": ...,
      "Mn": ...,
      "Mw": ...,
      "PDI": ...,
      "pi_stacking_distance": ...,
      "lamella_distance": ...,
      "structure": ...,
      "doped": ...,
      "dopant": ...,
      "dopant_amount": ...,
      "annealed": ...,
      "annealing_temperature": ...,
      "annealing_atmosphere": ...
    }
  ]
}"""

# ============ 并发配置 ============
DEFAULT_WORKERS = 3
