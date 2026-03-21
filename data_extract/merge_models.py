#!/usr/bin/env python3
"""合并两个模型的提取结果 - 互补填充，冲突标注"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE_DIR = Path("/home/aari/workplace/lunwen")

# 输入目录
KIMI_DIR = BASE_DIR / "extracted_data_moonshotai_Kimi-K2-Thinking"
QWEN_DIR = BASE_DIR / "extracted_data_Qwen3-Coder-480B-A35B-Instruct"

# 输出目录
OUTPUT_DIR = BASE_DIR / "extracted_data_merged_Kimi_Qwen"

# 需要合并的字段
FIELDS = [
    "compound_name", "max_electron_mobility", "max_hole_mobility",
    "HOMO", "LUMO", "EA", "Eg", "IP",
    "Mn", "Mw", "PDI",
    "pi_stacking_distance", "lamella_distance",
    "structure", "doped", "dopant", "dopant_amount",
    "annealed", "annealing_temperature", "annealing_atmosphere"
]


def is_empty(value):
    """判断值是否为空"""
    return value is None or value == "" or value == "null"


def normalize_compound_name(name):
    """标准化化合物名称用于匹配"""
    if not name:
        return ""
    # 去空格、转小写，便于模糊匹配
    return str(name).strip().lower().replace(" ", "").replace("-", "")


def merge_compound(kimi_compound: dict, qwen_compound: dict) -> dict:
    """合并两个化合物的数据

    返回: {合并后的化合物数据, 包含 _conflicts 字段标注冲突}
    """
    merged = {}
    conflicts = {}

    for field in FIELDS:
        kimi_val = kimi_compound.get(field)
        qwen_val = qwen_compound.get(field)

        kimi_empty = is_empty(kimi_val)
        qwen_empty = is_empty(qwen_val)

        if kimi_empty and qwen_empty:
            # 都没有
            merged[field] = None
        elif kimi_empty and not qwen_empty:
            # Kimi 没有，Qwen 有
            merged[field] = qwen_val
            merged[f"_{field}_source"] = "qwen"
        elif not kimi_empty and qwen_empty:
            # Kimi 有，Qwen 没有
            merged[field] = kimi_val
            merged[f"_{field}_source"] = "kimi"
        else:
            # 都有值，检查是否一致
            # 对于数值，允许小误差
            if kimi_val == qwen_val:
                merged[field] = kimi_val
            elif isinstance(kimi_val, (int, float)) and isinstance(qwen_val, (int, float)):
                # 数值型，检查相对误差
                if abs(kimi_val - qwen_val) / max(abs(kimi_val), abs(qwen_val), 1e-9) < 0.01:
                    # 误差小于1%，取平均或 Kimi 的值
                    merged[field] = kimi_val
                else:
                    # 冲突
                    merged[field] = kimi_val  # 默认用 Kimi
                    conflicts[field] = {"kimi": kimi_val, "qwen": qwen_val}
            else:
                # 字符串等，不一致就是冲突
                # 特殊处理：Yes/No 类型的字段，忽略大小写
                if str(kimi_val).lower() == str(qwen_val).lower():
                    merged[field] = kimi_val
                else:
                    merged[field] = kimi_val  # 默认用 Kimi
                    conflicts[field] = {"kimi": kimi_val, "qwen": qwen_val}

    if conflicts:
        merged["_conflicts"] = conflicts

    return merged


def merge_compounds_list(kimi_compounds: list, qwen_compounds: list) -> list:
    """合并两个化合物列表

    策略：
    1. 通过 compound_name 匹配
    2. 匹配到的合并
    3. 没匹配到的都保留
    """
    merged = []

    # 建立 Qwen 化合物的索引
    qwen_by_name = {}
    qwen_used = set()
    for i, comp in enumerate(qwen_compounds):
        name = normalize_compound_name(comp.get("compound_name"))
        if name:
            qwen_by_name[name] = i

    # 遍历 Kimi 化合物，尝试匹配
    for kimi_comp in kimi_compounds:
        kimi_name = normalize_compound_name(kimi_comp.get("compound_name"))

        if kimi_name and kimi_name in qwen_by_name:
            # 找到匹配，合并
            qwen_idx = qwen_by_name[kimi_name]
            qwen_comp = qwen_compounds[qwen_idx]
            qwen_used.add(qwen_idx)

            merged_comp = merge_compound(kimi_comp, qwen_comp)
            merged_comp["_matched"] = True
            merged.append(merged_comp)
        else:
            # Kimi 独有
            kimi_comp_copy = dict(kimi_comp)
            kimi_comp_copy["_source"] = "kimi_only"
            merged.append(kimi_comp_copy)

    # 添加 Qwen 独有的化合物
    for i, qwen_comp in enumerate(qwen_compounds):
        if i not in qwen_used:
            qwen_comp_copy = dict(qwen_comp)
            qwen_comp_copy["_source"] = "qwen_only"
            merged.append(qwen_comp_copy)

    return merged


def get_all_files(root_dir: Path) -> dict:
    """获取目录下所有 JSON 文件，返回 {ma: (folder, filepath)}"""
    results = {}
    for folder in root_dir.iterdir():
        if not folder.is_dir():
            continue
        for json_file in folder.glob("*.json"):
            # Z1引用文献_Z1-1_extracted.json -> Z1-1
            parts = json_file.stem.split("_")
            if len(parts) >= 2:
                ma = parts[1]
            else:
                ma = json_file.stem
            results[ma] = (folder.name, json_file)
    return results


def main():
    print("加载文件列表...")
    kimi_files = get_all_files(KIMI_DIR)
    qwen_files = get_all_files(QWEN_DIR)

    all_mas = set(kimi_files.keys()) | set(qwen_files.keys())
    print(f"Kimi: {len(kimi_files)} 个文件")
    print(f"Qwen: {len(qwen_files)} 个文件")
    print(f"合计: {len(all_mas)} 个唯一文件")

    # 统计
    stats = {
        "total": 0,
        "both_success": 0,
        "kimi_only": 0,
        "qwen_only": 0,
        "merged_compounds": 0,
        "kimi_only_compounds": 0,
        "qwen_only_compounds": 0,
        "files_with_conflicts": 0,
        "total_conflicts": 0,
    }

    for ma in sorted(all_mas):
        stats["total"] += 1

        kimi_data = None
        qwen_data = None
        folder_name = None

        # 加载 Kimi 数据
        if ma in kimi_files:
            folder_name, kimi_path = kimi_files[ma]
            try:
                with open(kimi_path, "r", encoding="utf-8") as f:
                    kimi_data = json.load(f)
            except:
                pass

        # 加载 Qwen 数据
        if ma in qwen_files:
            folder_name, qwen_path = qwen_files[ma]
            try:
                with open(qwen_path, "r", encoding="utf-8") as f:
                    qwen_data = json.load(f)
            except:
                pass

        # 决定合并策略
        kimi_success = kimi_data and kimi_data.get("status") == "success"
        qwen_success = qwen_data and qwen_data.get("status") == "success"

        if kimi_success and qwen_success:
            # 两者都成功，合并
            stats["both_success"] += 1
            kimi_compounds = kimi_data.get("compounds", [])
            qwen_compounds = qwen_data.get("compounds", [])

            merged_compounds = merge_compounds_list(kimi_compounds, qwen_compounds)

            # 统计
            for comp in merged_compounds:
                if comp.get("_matched"):
                    stats["merged_compounds"] += 1
                elif comp.get("_source") == "kimi_only":
                    stats["kimi_only_compounds"] += 1
                elif comp.get("_source") == "qwen_only":
                    stats["qwen_only_compounds"] += 1

                if "_conflicts" in comp:
                    stats["total_conflicts"] += len(comp["_conflicts"])

            if any("_conflicts" in c for c in merged_compounds):
                stats["files_with_conflicts"] += 1

            output_data = {
                "source_file": kimi_data.get("source_file"),
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "status": "merged",
                "merge_info": {
                    "kimi_compounds": len(kimi_compounds),
                    "qwen_compounds": len(qwen_compounds),
                    "merged_total": len(merged_compounds),
                },
                "compounds": merged_compounds
            }

        elif kimi_success:
            # 只有 Kimi 成功
            stats["kimi_only"] += 1
            for comp in kimi_data.get("compounds", []):
                stats["kimi_only_compounds"] += 1
            output_data = kimi_data.copy()
            output_data["status"] = "kimi_only"

        elif qwen_success:
            # 只有 Qwen 成功
            stats["qwen_only"] += 1
            for comp in qwen_data.get("compounds", []):
                stats["qwen_only_compounds"] += 1
            output_data = qwen_data.copy()
            output_data["status"] = "qwen_only"

        else:
            # 都失败了
            output_data = {
                "source_file": f"{ma}.pdf",
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "status": "both_failed",
                "kimi_status": kimi_data.get("status") if kimi_data else "missing",
                "qwen_status": qwen_data.get("status") if qwen_data else "missing",
            }

        # 保存
        output_folder = OUTPUT_DIR / folder_name
        output_folder.mkdir(parents=True, exist_ok=True)
        output_path = output_folder / f"{folder_name}_{ma}_extracted.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    # 打印统计
    print(f"\n{'='*60}")
    print("合并完成!")
    print(f"{'='*60}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"\n📊 文件统计:")
    print(f"  总文件数: {stats['total']}")
    print(f"  两者都成功并合并: {stats['both_success']}")
    print(f"  仅 Kimi 成功: {stats['kimi_only']}")
    print(f"  仅 Qwen 成功: {stats['qwen_only']}")

    print(f"\n🧪 化合物统计:")
    total_compounds = stats['merged_compounds'] + stats['kimi_only_compounds'] + stats['qwen_only_compounds']
    print(f"  合并后总化合物数: {total_compounds}")
    print(f"  匹配并合并的化合物: {stats['merged_compounds']}")
    print(f"  Kimi 独有化合物: {stats['kimi_only_compounds']}")
    print(f"  Qwen 独有化合物: {stats['qwen_only_compounds']}")

    print(f"\n⚠️  冲突统计:")
    print(f"  有冲突的文件数: {stats['files_with_conflicts']}")
    print(f"  总冲突字段数: {stats['total_conflicts']}")


if __name__ == "__main__":
    main()
