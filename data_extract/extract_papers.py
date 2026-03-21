#!/usr/bin/env python3
"""批量提取 PDF 论文数据 - 支持多提供商"""

import os
import json
import time
import glob
from pathlib import Path
from datetime import datetime

import requests

# 从配置文件导入
from config import (
    PROVIDERS, ACTIVE_PROVIDER, EXTRACTION_PROMPT,
    BASE_DIR, PDF_ROOT, OUTPUT_ROOT, DEFAULT_WORKERS
)

try:
    import fitz  # PyMuPDF
except ImportError:
    print("请先安装 PyMuPDF: pip install pymupdf")
    raise


def get_provider_config():
    """获取当前提供商配置"""
    return PROVIDERS[ACTIVE_PROVIDER]


def extract_text_from_pdf(pdf_path: str) -> str:
    """使用 PyMuPDF 提取 PDF 文本"""
    doc = fitz.open(pdf_path)
    text_parts = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
    
    page_count = len(doc)
    doc.close()
    
    full_text = "\n\n".join(text_parts)
    print(f"  提取了 {page_count} 页, {len(full_text)} 字符")
    return full_text


def call_api_with_pdf(pdf_path: str) -> dict:
    """调用 LLM API 提取 PDF 数据"""
    config = get_provider_config()
    
    # 提取文本
    pdf_text = extract_text_from_pdf(pdf_path)
    
    # 构建请求头
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }

    # 合并自定义 headers（如果配置中有的话）
    if "headers" in config:
        headers.update(config["headers"])
    
    # 构建 payload - 自动传递配置里的参数
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": pdf_text}
        ],
        "stream": False,
    }
    
    # 自动添加配置里的可选参数
    optional_params = [
        "max_tokens", "temperature", "top_p", "top_k", 
        "frequency_penalty", "thinking_budget", "response_format"
    ]
    for param in optional_params:
        if param in config:
            payload[param] = config[param]
    
    # 火山方舟特有参数
    if ACTIVE_PROVIDER == "volcengine":
        payload["thinking"] = {"type": "enabled"}
        if "reasoning_effort" in config:
            payload["reasoning_effort"] = config["reasoning_effort"]
    
    resp = requests.post(config["api_url"], headers=headers, json=payload, timeout=600)
    
    if resp.status_code != 200:
        print(f"API 状态码: {resp.status_code}")
        print(f"API 响应: {resp.text[:1000]}")
    
    resp.raise_for_status()
    return resp.json()


def parse_response(api_response: dict) -> tuple[dict, str]:
    """解析 API 响应。
    返回: (解析后的字典, 原始文本)
    """
    import re
    choices = api_response.get("choices", [])
    content = ""
    if choices:
        content = choices[0].get("message", {}).get("content", "")
    
    if not content:
        return {"parse_error": "Empty content"}, ""

    # 1. 尝试提取 ```json ... ``` 块
    json_blocks = re.findall(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_blocks:
        try:
            return json.loads(json_blocks[-1]), content
        except json.JSONDecodeError:
            pass # 提取了代码块但解析失败，继续尝试下面的方法

    # 2. 如果没找到代码块或解析失败，尝试在全文寻找最外层的 { ... }
    # 这能处理 Z1-17 这种前面有废话且没有代码块的情况
    try:
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = content[start:end+1]
            return json.loads(json_str), content
    except json.JSONDecodeError as e:
        return {"parse_error": str(e)}, content

    # 3. 实在不行，尝试直接解析（虽然走到这一步概率很低）
    try:
        return json.loads(content.strip()), content
    except json.JSONDecodeError as e:
        return {"parse_error": str(e)}, content


def ma_to_paths(ma: str) -> tuple[str, str]:
    """MA 编号转换为 PDF 路径和输出路径

    Z1-1 → Z1-Z16/Z1引用文献/Z1-1.pdf
    Z1-1 → extracted_data/Z1引用文献/Z1引用文献_Z1-1_extracted.json
    """
    z_num = ma.split("-")[0]  # Z1, Z8, Z10 等
    folder = f"{z_num}引用文献"
    pdf_path = PDF_ROOT / folder / f"{ma}.pdf"
    output_path = OUTPUT_ROOT / folder / f"{folder}_{ma}_extracted.json"
    return str(pdf_path), str(output_path)


def get_all_pdfs(z_filter: str = None) -> list[tuple[str, str, str]]:
    """获取所有 PDF 文件列表，返回 (ma, pdf_path, output_path)
    
    z_filter: 可选，如 'Z1' 只处理 Z1 文件夹
    """
    results = []

    for pdf_file in glob.glob(str(PDF_ROOT / "*引用文献/*.pdf")):
        pdf_path = Path(pdf_file)
        ma = pdf_path.stem  # Z1-1, Z2-3 等
        z_num = ma.split("-")[0]
        
        # 过滤 Z 编号
        if z_filter and z_num != z_filter:
            continue
            
        folder = f"{z_num}引用文献"
        output_path = OUTPUT_ROOT / folder / f"{folder}_{ma}_extracted.json"
        results.append((ma, str(pdf_path), str(output_path)))

    def sort_key(item):
        ma = item[0]
        parts = ma.split("-")
        # 提取 Z1 中的 1
        z_num = int(parts[0][1:]) if parts[0].startswith("Z") and parts[0][1:].isdigit() else 0
        # 提取后缀中的数字，如 P13a -> 13
        s_num = 0
        if len(parts) > 1:
            digits = "".join(filter(str.isdigit, parts[1]))
            s_num = int(digits) if digits else 0
        return (z_num, s_num, ma)

    return sorted(results, key=sort_key)


def process_single_pdf(ma: str, pdf_path: str, output_path: str) -> bool:
    """处理单个 PDF 文件，始终保存结果（成功或失败日志）"""
    # 只有当文件存在且状态为 success 时才跳过
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("status") == "success":
                    print(f"跳过已处理: {ma}")
                    return True
        except Exception:
            pass # 读取出错则视同未处理，继续

    max_retries = 3
    retry_delay = 5
    final_output = {}
    is_success = False

    for attempt in range(max_retries):
        try:
            print(f"处理: {ma} (尝试 {attempt + 1}/{max_retries})")
            
            api_response = call_api_with_pdf(pdf_path)
            extracted, raw_content = parse_response(api_response)

            # 检查解析是否失败
            if "parse_error" in extracted:
                print(f"  JSON 解析失败 (尝试 {attempt + 1}): {extracted['parse_error']}")
                # 保存此次失败的详情，如果这是最后一次尝试，它将被写入文件
                final_output = {
                    "source_file": os.path.basename(pdf_path),
                    "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "parse_error",
                    "error_details": extracted.get("parse_error"),
                    "raw_content": raw_content
                }
                
                # 如果还有重试机会，休息一下再试
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    is_success = False
                    break # 次数用尽，退出循环，保存最后一次的错误

            # 成功提取
            final_output = {
                "source_file": os.path.basename(pdf_path),
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "status": "success",
                "compounds": extracted.get("compounds", [])
            }
            
            num_compounds = len(final_output["compounds"])
            if num_compounds == 0:
                print(f"  完成: 但未提取到化合物")
            else:
                print(f"  完成: 提取了 {num_compounds} 个化合物")

            is_success = True
            break

        except requests.exceptions.RequestException as e:
            print(f"  API 错误 (尝试 {attempt + 1}): {e}")
            if attempt >= max_retries - 1:
                final_output = {
                    "source_file": os.path.basename(pdf_path),
                    "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "api_error",
                    "error_details": str(e)
                }
            time.sleep(retry_delay * (attempt + 1))
        
        except Exception as e:
            print(f"  处理时发生未知错误: {e}")
            final_output = {
                "source_file": os.path.basename(pdf_path),
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "status": "unknown_error",
                "error_details": str(e)
            }
            is_success = False
            break

    # 确保输出目录存在并保存最终的文件
    if final_output:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
            
    return is_success

from concurrent.futures import ThreadPoolExecutor, as_completed

def main(z_filter: str = None, workers: int = DEFAULT_WORKERS):
    """主函数
    
    z_filter: 可选，如 'Z1' 只处理 Z1 文件夹
    workers: 并发数量，默认使用 config.py 中的 DEFAULT_WORKERS
    """
    config = get_provider_config()
    if not config.get("api_key"):
        print(f"错误: 请在 config.py 中设置 {ACTIVE_PROVIDER} 的 api_key")
        return

    # 获取所有 PDF
    all_pdfs = get_all_pdfs(z_filter)
    
    # 过滤待处理的文件
    to_process = []
    for ma, pdf_path, output_path in all_pdfs:
        if not os.path.exists(output_path):
            to_process.append((ma, pdf_path, output_path))
            continue
        
        # 如果文件存在，检查状态
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("status") != "success":
                    # 如果不是成功状态，重新加入待处理列表
                    to_process.append((ma, pdf_path, output_path))
        except Exception:
            # 如果文件读取失败或损坏，也重新处理
            to_process.append((ma, pdf_path, output_path))

    skipped = len(all_pdfs) - len(to_process)
    
    if z_filter:
        print(f"只处理 {z_filter}，共 {len(all_pdfs)} 个 PDF，跳过 {skipped} 个已处理，待处理 {len(to_process)} 个")
    else:
        print(f"共 {len(all_pdfs)} 个 PDF，跳过 {skipped} 个已处理，待处理 {len(to_process)} 个")
    
    if not to_process:
        print("没有需要处理的文件")
        return
    
    print(f"启动 {workers} 个并发工作线程...")

    # 统计
    success = 0
    failed = 0
    failed_list = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # 提交所有任务
        future_to_ma = {
            executor.submit(process_single_pdf, ma, pdf_path, output_path): ma 
            for ma, pdf_path, output_path in to_process
        }
        
        # 收集结果
        for i, future in enumerate(as_completed(future_to_ma)):
            ma = future_to_ma[future]
            try:
                if future.result():
                    success += 1
                    print(f"[{i+1}/{len(to_process)}] ✓ {ma}")
                else:
                    failed += 1
                    failed_list.append(ma)
                    print(f"[{i+1}/{len(to_process)}] ✗ {ma}")
            except Exception as e:
                failed += 1
                failed_list.append(ma)
                print(f"[{i+1}/{len(to_process)}] ✗ {ma}: {e}")

    # 汇总
    print(f"\n{'='*50}")
    print(f"处理完成!")
    print(f"  成功: {success}")
    print(f"  跳过: {skipped}")
    print(f"  失败: {failed}")

    if failed_list:
        print(f"\n失败列表:")
        for ma in failed_list:
            print(f"  - {ma}")
        # 保存失败列表
        with open(BASE_DIR / "failed.log", "w") as f:
            f.write("\n".join(failed_list))


def test_single():
    """测试单个 PDF"""
    config = get_provider_config()
    if not config.get("api_key") or config["api_key"] == "YOUR_SILICONFLOW_KEY":
        print(f"错误: 请在 config.py 中设置 {ACTIVE_PROVIDER} 的 api_key")
        return

    # 测试第一个 PDF
    test_pdf = str(PDF_ROOT / "Z8引用文献/Z8-P13a.pdf")
    if not os.path.exists(test_pdf):
        print(f"测试文件不存在: {test_pdf}")
        return

    print(f"测试 PDF: {test_pdf}")
    print(f"文件大小: {os.path.getsize(test_pdf) / 1024:.1f} KB")

    try:
        response = call_api_with_pdf(test_pdf)
        print(f"\nAPI 响应:")
        print(json.dumps(response, indent=2, ensure_ascii=False)[:2000])

        extracted = parse_response(response)
        print(f"\n提取结果:")
        print(json.dumps(extracted, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_single()
    elif len(sys.argv) > 1 and sys.argv[1].startswith("Z"):
        # 指定 Z 编号，如 python extract_papers.py Z1
        main(z_filter=sys.argv[1])
    else:
        main()
