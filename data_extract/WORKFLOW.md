# PDF 论文数据提取工作流

## 1. 概述

从 `Z1-Z16` 目录下的 PDF 论文中提取有机半导体材料的关键参数，输出结构化 JSON 数据。

## 1.1 数据源

- CSV 文件：`alldata_Z_unique_doi.csv`（按 DOI 去重后的 MA 列表）
- PDF 数量：316 个（已清理重复）
- 唯一 DOI：334 个

## 2. 目录结构

```
lunwen/
├── extracted_data/
│   ├── Z1引用文献/
│   │   └── Z1引用文献_Z1-1_extracted.json
│   ├── Z2引用文献/
│   ...
│   └── all_extracted_data.json
└── Z1-Z16/
    ├── Z1引用文献/
    ├── Z2引用文献/
    ...
```

命名规则：`{来源目录}/{来源目录}_{文件名}_extracted.json`

## 3. Codex 调用参数

```
- cd: /Users/aari/Documents/lunwen
- 先用工具读取 PDF 全文：mcp__pdf-reader__read_pdf
- 再用 PROMPT（见下方提示词模板）从“PDF 全文文本”中抽取
- sandbox: "workspace-write"（需要写入 extracted_data/）
```

## 3.1 用 pdf-reader 读取 PDF（必须全读）

说明：模型不能“直接读取本地文件路径”。必须先用 `pdf-reader` 的 `read_pdf` 把 PDF 转成文本，再把文本作为输入进行抽取。

**一次性读取全文（推荐）：**

```json
{
  "include_full_text": true,
  "include_metadata": true,
  "include_page_count": true,
  "sources": [
    { "path": "Z1-Z16/Z1引用文献/Z1-1.pdf" }
  ]
}
```

如果全文过长超出上下文窗口：按页分段读取（但必须覆盖所有页），例如 `1-20`、`21-40`…；抽取时逐段扫描/合并结果，确保不漏页。

## 4. 提示词模板

```
You are a professional materials science data extraction assistant.
Your task is to extract key parameters for ALL organic semiconductor materials/compounds mentioned in the paper text provided below.

**CRITICAL INSTRUCTIONS:**
1. Extract EVERY compound mentioned in the paper.
2. If the paper compares multiple compounds (e.g., P1, P2, P3), extract data for EACH of them separately.
3. Look for compound names in: title, text, tables, and figures.
4. **Think carefully**: For each value you extract, mentally note where it came from (page number, table, figure caption, etc.) to ensure accuracy. However, DO NOT include source annotations in the final JSON output.

**FIELDS TO EXTRACT (Return null if not found):**

1.  **compound_name**: The abbreviation or name used in the text.
2.  **Mobility**:
    *   `max_electron_mobility`: Max electron mobility (cm²/V·s).
    *   `max_hole_mobility`: Max hole mobility (cm²/V·s).
    *   *Note: If "average" and "max" are given, prefer "max".*

3.  **Energy Levels** (eV):
    *   `HOMO`: Highest Occupied Molecular Orbital.
    *   `LUMO`: Lowest Unoccupied Molecular Orbital.
    *   `EA`: Electron Affinity.
    *   `Eg`: Optical Bandgap.
    *   `IP`: Ionization Potential (if HOMO is not explicitly stated).

4.  **Molecular Properties**:
    *   `Mn`: Number-average molecular weight (kDa).
    *   `Mw`: Weight-average molecular weight (kDa).
    *   `PDI`: Polydispersity Index.
    *   *Note: If only Mw and PDI are given, extract them (Mn can be calculated).*

5.  **Microstructure** (Å):
    *   `pi_stacking_distance`: π-π stacking distance.
    *   `lamella_distance`: Lamella distance / d-spacing.

6.  **Device Config**:
    *   `structure`: Device architecture (e.g., "TGBC" for Top-Gate Bottom-Contact, "BGBC", "TGTC", "BGTC"). extract strictly as acronym.

7.  **Processing Conditions**:
    *   `doped`: "Yes" or "No".
    *   `dopant`: Name of dopant (e.g., F4TCNQ).
    *   `dopant_amount`: Amount/Ratio of dopant.
    *   `annealed`: "Yes" or "No".
    *   `annealing_temperature`: Temperature in °C.
    *   `annealing_atmosphere`: Atmosphere (e.g., "Vacuum", "N2", "Air").

**RULES:**
- Only extract values explicitly stated.
- For numbers, extract the value (e.g., "0.5").
- Do NOT convert units unless obvious (e.g. 50000 Da -> 50 kDa).
- Use only the paper text provided below. Do not guess or use outside knowledge.
- Return ONLY a single JSON object that matches the schema in Section 5.
- **OUTPUT FORMAT: Valid JSON only. No explanations, no markdown code blocks (no ```json), no additional text before or after the JSON.**

**PAPER FULL TEXT (all pages, extracted via pdf-reader):**
{PDF_TEXT}
```

## 5. JSON 输出格式

```json
{
  "source_file": "Z1-1.pdf",
  "extraction_date": "2026-01-12",
  "compounds": [
    {
      "compound_name": "P1",
      "max_electron_mobility": null,
      "max_hole_mobility": 0.5,
      "HOMO": -5.2,
      "LUMO": -3.5,
      "EA": null,
      "Eg": 1.7,
      "IP": null,
      "Mn": 25.3,
      "Mw": 50.6,
      "PDI": 2.0,
      "pi_stacking_distance": 3.6,
      "lamella_distance": 21.5,
      "structure": "TGBC",
      "doped": "No",
      "dopant": null,
      "dopant_amount": null,
      "annealed": "Yes",
      "annealing_temperature": 200,
      "annealing_atmosphere": "N2"
    }
  ]
}
```

## 6. 数据标准化规则

| 字段 | 规则 |
|------|------|
| `annealed` | 布尔值 → "Yes" / "No" |
| `annealing_atmosphere` | "ambient" → "Air" |
| 范围值 | 保留原样（如 "4.0-4.4"） |

## 7. 批量处理流程

1. 读取 `alldata_Z_unique_doi.csv` 获取 MA 列表
2. 根据 MA 定位 PDF 路径（如 Z1-1 → Z1引用文献/Z1-1.pdf）
3. 对每个 PDF 用 `mcp__pdf-reader__read_pdf` 读取全文文本（必要时按页分段，但不能漏页）
4. 将全文文本填入提示词模板 `{PDF_TEXT}`，抽取得到结构化 JSON
5. 标准化数据后保存到 `extracted_data/{来源目录}/{来源目录}_{MA}_extracted.json`
6. 最终汇总到 `extracted_data/all_extracted_data.json`

## 8. MA 到 PDF 路径映射

```python
def ma_to_pdf_path(ma):
    """Z1-1 → Z1-Z16/Z1引用文献/Z1-1.pdf"""
    z_num = ma.split('-')[0]  # Z1, Z8, Z10 等
    folder = f'{z_num}引用文献'
    return f'Z1-Z16/{folder}/{ma}.pdf'

def ma_to_output_path(ma):
    """Z1-1 → extracted_data/Z1引用文献/Z1引用文献_Z1-1_extracted.json"""
    z_num = ma.split('-')[0]
    folder = f'{z_num}引用文献'
    return f'extracted_data/{folder}/{folder}_{ma}_extracted.json'
```

## 9. 断点续传

处理前检查输出文件是否已存在，跳过已处理的：

```python
import os
if os.path.exists(output_path):
    print(f'跳过已处理: {ma}')
    continue
```

## 10. 分批处理

按目录分批，每次处理一个 Z 目录：

| 目录 | 数量 |
|------|------|
| Z1 | 21 |
| Z2 | 14 |
| Z3 | 12 |
| Z4 | 67 |
| Z5 | 45 |
| Z6 | 3 |
| Z7 | 9 |
| Z8 | 50 |
| Z9 | 9 |
| Z10 | 5 |
| Z14 | 29 |
| Z15 | 18 |
| Z16 | 45 |
| Z18 | 7 |
| **总计** | **334** |

```python
# 按目录筛选
target_dir = 'Z1'  # 修改此值切换批次
ma_batch = [ma for ma in ma_list if ma.startswith(f'{target_dir}-')]
```

## 11. 错误处理

```python
import os

try:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
    # 先用 pdf-reader 读取全文文本，再进行抽取（此处为伪代码）
    pdf_text = read_pdf_full_text(pdf_path)
    prompt = PROMPT_TEMPLATE.format(PDF_TEXT=pdf_text)
    result = codex.extract(prompt)
    save_json(result, output_path)
except Exception as e:
    print(f'错误 {ma}: {e}')
    # 记录失败的 MA 到日志
    with open('failed.log', 'a') as f:
        f.write(f'{ma}\n')
```

## 12. 汇总脚本

```python
import json
import glob

all_data = []
for json_file in glob.glob('extracted_data/**/*_extracted.json', recursive=True):
    with open(json_file) as f:
        all_data.append(json.load(f))

with open('extracted_data/all_extracted_data.json', 'w') as f:
    json.dump(all_data, f, indent=2, ensure_ascii=False)
```
