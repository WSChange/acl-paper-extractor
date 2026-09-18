import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import hashlib
import random
import time

st.set_page_config(page_title="ACL Anthology 论文提取器", layout="wide")

VENUES = {
    "ACL": "acl",
    "EMNLP": "emnlp",
    "NAACL": "naacl",
    "EACL": "eacl",
    "COLING": "coling",
    "Findings": "findings",
}

XML_BASE = "https://raw.githubusercontent.com/acl-org/acl-anthology/master/data/xml"
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB

VOLUME_TYPE_MAP = {
    "long": "Long_Papers",
    "short": "Short_Papers",
    "findings": "Findings",
    "demo": "System_Demos",
    "srw": "Student_Workshop",
    "tutorial": "Tutorials",
    "industry": "Industry_Track",
    "workshop": "Workshop",
    "main": "Main",
}


def fetch_xml(venue_code: str, year: int) -> tuple[ET.Element | None, str]:
    url = f"{XML_BASE}/{year}.{venue_code}.xml"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code} — 该年份/会议组合可能不存在"
        return ET.fromstring(resp.content), ""
    except requests.RequestException as e:
        return None, f"请求失败: {e}"


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_volume_type(volume_id: str) -> str:
    vid = volume_id.lower()
    for key, label in VOLUME_TYPE_MAP.items():
        if key in vid:
            return label
    return "Other"


def parse_papers_by_volume(root: ET.Element) -> dict[str, dict]:
    volumes = {}
    for volume in root.findall(".//volume"):
        volume_id = volume.get("id", "")
        vol_type = extract_volume_type(volume_id)

        volume_name_el = volume.find("meta/booktitle")
        volume_name = clean_text("".join(volume_name_el.itertext())) if volume_name_el is not None else f"Volume {volume_id}"

        papers = []
        for paper in volume.findall("paper"):
            paper_id = paper.get("id", "")
            title_el = paper.find("title")
            title = clean_text("".join(title_el.itertext())) if title_el is not None else ""

            authors = []
            for author in paper.findall("author"):
                first = author.findtext("first", "")
                last = author.findtext("last", "")
                name = f"{first} {last}".strip()
                if name:
                    authors.append(name)

            abstract_el = paper.find("abstract")
            abstract = clean_text("".join(abstract_el.itertext())) if abstract_el is not None else ""

            pages = paper.findtext("pages", "")
            doi = paper.findtext("doi", "")

            papers.append({
                "volume": volume_id,
                "id": paper_id,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "pages": pages,
                "doi": doi,
            })

        key = f"{vol_type} ({volume_id})"
        volumes[key] = {"type": vol_type, "volume_id": volume_id, "name": volume_name, "papers": papers}
    return volumes


def generate_markdown(papers: list[dict], venue: str, year: int, volume_label: str = "", compact: bool = False, include_translation: bool = False) -> str:
    title_prefix = f"[{volume_label}] " if volume_label else ""
    lines = [
        f"# {title_prefix}{venue} {year} 论文汇总",
        "",
        f"> 共 {len(papers)} 篇论文 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    for i, p in enumerate(papers, 1):
        authors_str = ", ".join(p["authors"]) if p["authors"] else "未知"
        if compact:
            lines.append(f"{i}. {p['title']}")
            if include_translation and p.get("title_translated"):
                lines.append(f"   翻译: {p['title_translated']}")
            lines.append(f"   作者: {authors_str}")
            lines.append("")
        else:
            lines.append(f"## {i}. {p['title']}")
            if include_translation and p.get("title_translated"):
                lines.append(f"**翻译:** {p['title_translated']}")
                lines.append("")
            lines.append(f"作者: {authors_str}")
            lines.append("")
            if p["abstract"]:
                lines.append(f"摘要: {p['abstract']}")
                lines.append("")
            if include_translation and p.get("abstract_translated"):
                lines.append(f"**摘要翻译:** {p['abstract_translated']}")
                lines.append("")
    return "\n".join(lines)


def split_papers_into_chunks(papers: list[dict], venue: str, year: int, volume_label: str, compact: bool) -> list[tuple[str, str]]:
    """Split papers into chunks that each produce < MAX_FILE_SIZE bytes."""
    chunks = []
    current_papers = []
    current_lines = []
    chunk_idx = 1

    header_lines = [
        f"# [{volume_label}] {venue} {year} 论文汇总",
        "",
    ]

    for i, p in enumerate(papers, 1):
        authors_str = ", ".join(p["authors"]) if p["authors"] else "未知"
        if compact:
            block = [f"{i}. {p['title']}", f"   作者: {authors_str}", ""]
        else:
            block = [f"## {i}. {p['title']}", "", f"作者: {authors_str}", ""]
            if p["abstract"]:
                block.append(f"摘要: {p['abstract']}")
                block.append("")

        test_content = "\n".join(header_lines + [f"> 共 {len(current_papers) + 1} 篇论文 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""] + current_lines + block)
        if len(test_content.encode("utf-8")) > MAX_FILE_SIZE and current_papers:
            chunk_md = "\n".join(header_lines + [f"> 共 {len(current_papers)} 篇论文 (第{chunk_idx}部分) | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""] + current_lines)
            chunks.append((f"第{chunk_idx}部分", chunk_md))
            current_papers = []
            current_lines = []
            chunk_idx += 1
            header_lines = [f"# [{volume_label}] {venue} {year} 论文汇总 (续{chunk_idx - 1})"]

        current_papers.append(p)
        current_lines.extend(block)

    if current_papers:
        suffix = f" (第{chunk_idx}部分)" if chunk_idx > 1 else ""
        chunk_md = "\n".join(header_lines + [f"> 共 {len(current_papers)} 篇论文{suffix} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""] + current_lines)
        chunks.append((f"第{chunk_idx}部分" if chunk_idx > 1 else "", chunk_md))

    return chunks


def translate_openai(text: str, api_base: str, api_key: str, model: str) -> str:
    """Translate using OpenAI-compatible API."""
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a translator. Translate the following academic paper text to Chinese. Keep technical terms accurate. Only output the translation, no explanations."
            },
            {"role": "user", "content": text}
        ],
        "temperature": 0.3,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    error_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
    raise RuntimeError(f"HTTP {resp.status_code} - {error_msg}")


def translate_deepl(text: str, api_key: str) -> str:
    """Translate using DeepL API Free."""
    url = "https://api-free.deepl.com/v2/translate"
    headers = {
        "Authorization": f"DeepL-Auth-Key {api_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "text": text,
        "target_lang": "ZH",
    }
    resp = requests.post(url, headers=headers, data=data, timeout=60)
    if resp.status_code == 200:
        return resp.json()["translations"][0]["text"].strip()
    error_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
    raise RuntimeError(f"HTTP {resp.status_code} - {error_msg}")


def translate_baidu(text: str, appid: str, secret_key: str) -> str:
    """Translate using Baidu Translation API."""
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    salt = str(random.randint(10000, 99999))
    sign_str = appid + text + salt + secret_key
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    params = {
        "q": text,
        "from": "en",
        "to": "zh",
        "appid": appid,
        "salt": salt,
        "sign": sign,
    }
    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code == 200:
        result = resp.json()
        if "trans_result" in result:
            return result["trans_result"][0]["dst"].strip()
        error_msg = result.get("error_msg", "未知错误")
        raise RuntimeError(f"百度翻译错误: {error_msg}")
    error_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
    raise RuntimeError(f"HTTP {resp.status_code} - {error_msg}")


def translate_baidu_llm(text: str, appid: str, secret_key: str, api_key: str = None) -> str:
    """Translate using Baidu Large Model Translation API."""
    url = "https://fanyi-api.baidu.com/ait/api/aiTextTranslate"
    headers = {"Content-Type": "application/json"}
    
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "appid": appid,
            "from": "en",
            "to": "zh",
            "q": text,
            "model_type": "llm",
        }
    else:
        salt = str(random.randint(10000, 99999))
        sign_str = appid + text + salt + secret_key
        sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
        payload = {
            "appid": appid,
            "from": "en",
            "to": "zh",
            "q": text,
            "model_type": "llm",
            "salt": salt,
            "sign": sign,
        }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code == 200:
        result = resp.json()
        if "trans_result" in result:
            return result["trans_result"][0]["dst"].strip()
        error_code = result.get("error_code", "")
        error_msg = result.get("error_msg", "未知错误")
        if error_code in ["54004", "54003"]:
            raise RuntimeError(f"QUOTA_EXCEEDED:{error_msg}")
        raise RuntimeError(f"百度大模型翻译错误: {error_msg}")
    error_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
    raise RuntimeError(f"HTTP {resp.status_code} - {error_msg}")


def check_baidu_quota(appid: str, secret_key: str, api_key: str = None) -> dict:
    """Check Baidu translation quota by making a test request."""
    try:
        test_text = "test"
        url = "https://fanyi-api.baidu.com/ait/api/aiTextTranslate"
        headers = {"Content-Type": "application/json"}
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "appid": appid,
                "from": "en",
                "to": "zh",
                "q": test_text,
                "model_type": "llm",
            }
        else:
            salt = str(random.randint(10000, 99999))
            sign_str = appid + test_text + salt + secret_key
            sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
            payload = {
                "appid": appid,
                "from": "en",
                "to": "zh",
                "q": test_text,
                "model_type": "llm",
                "salt": salt,
                "sign": sign,
            }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            if "trans_result" in result:
                return {"available": True}
            error_code = result.get("error_code", "")
            error_msg = result.get("error_msg", "")
            if error_code in ["54004", "54003"]:
                return {"available": False, "reason": error_msg}
            return {"available": False, "reason": error_msg}
        return {"available": False, "reason": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"available": False, "reason": str(e)}


def translate_libre(text: str, api_url: str) -> str:
    """Translate using LibreTranslate API."""
    url = f"{api_url.rstrip('/')}/translate"
    payload = {
        "q": text,
        "source": "en",
        "target": "zh",
    }
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code == 200:
        return resp.json()["translatedText"].strip()
    error_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
    raise RuntimeError(f"HTTP {resp.status_code} - {error_msg}")


def get_deepl_usage(api_key: str) -> dict:
    """Get DeepL API usage statistics."""
    url = "https://api-free.deepl.com/v2/usage"
    headers = {
        "Authorization": f"DeepL-Auth-Key {api_key}",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def translate_text(text: str, service: str, config: dict) -> str:
    """Dispatch translation to the selected service."""
    if not text.strip():
        return ""
    try:
        if service == "DeepL":
            return translate_deepl(text, config["api_key"])
        elif service == "百度翻译":
            return translate_baidu(text, config["appid"], config["secret_key"])
        elif service == "百度大模型翻译":
            try:
                return translate_baidu_llm(
                    text, 
                    config["appid"], 
                    config["secret_key"],
                    config.get("api_key")
                )
            except RuntimeError as e:
                if "QUOTA_EXCEEDED" in str(e):
                    if not config.get("_quota_warning_shown", False):
                        config["_quota_warning_shown"] = True
                        st.warning("百度大模型翻译额度已用完，自动切换到通用翻译")
                    return translate_baidu(text, config["appid"], config["secret_key"])
                raise
        elif service == "LibreTranslate":
            return translate_libre(text, config["api_url"])
        else:
            return translate_openai(text, config["api_base"], config["api_key"], config["model"])
    except Exception as e:
        return f"[翻译失败: {e}]"


def translate_papers(papers: list[dict], service: str, config: dict, translate_target: str, progress_callback=None) -> list[dict]:
    """Translate titles and abstracts for a list of papers."""
    translated = []
    total = len(papers)

    for i, p in enumerate(papers):
        if st.session_state.get("stop_translation", False):
            break

        translated_p = p.copy()

        if translate_target in ["仅题目", "题目+摘要"]:
            translated_p["title_translated"] = translate_text(p["title"], service, config)
            time.sleep(0.5)

        if st.session_state.get("stop_translation", False):
            break

        if translate_target in ["仅摘要", "题目+摘要"] and p["abstract"]:
            translated_p["abstract_translated"] = translate_text(p["abstract"], service, config)
            time.sleep(0.5)

        translated.append(translated_p)

        if progress_callback:
            progress_callback((i + 1) / total)

    return translated


st.title("ACL Anthology 论文提取器")
st.caption("从 ACL Anthology 提取论文题目、作者与摘要，导出为 Markdown 文件")

col1, col2, col3 = st.columns(3)
with col1:
    venue_name = st.selectbox("选择会议", list(VENUES.keys()))
with col2:
    year = st.number_input("选择年份", min_value=1963, max_value=2026, value=2024, step=1)
with col3:
    compact = st.checkbox("紧凑模式 (仅题目+作者)", value=False)

venue_code = VENUES[venue_name]

if st.button("获取论文列表", type="primary"):
    with st.spinner(f"正在获取 {venue_name} {year} 的数据..."):
        root, err = fetch_xml(venue_code, year)
        if err:
            st.error(err)
            st.stop()

        volumes_data = parse_papers_by_volume(root)
        if not volumes_data:
            st.warning("未找到任何论文数据")
            st.stop()

        st.session_state.volumes_data = volumes_data
        st.session_state.venue_name = venue_name
        st.session_state.year = year
        st.session_state.compact = compact

if "volumes_data" in st.session_state:
    volumes_data = st.session_state.volumes_data
    venue_name = st.session_state.venue_name
    year = st.session_state.year
    compact = st.session_state.compact

    papers = []
    for v in volumes_data.values():
        papers.extend(v["papers"])

    st.success(f"成功获取 {len(papers)} 篇论文，分为 {len(volumes_data)} 个卷")

    with st.expander("翻译设置 (可选)", expanded=False):
        service = st.selectbox(
            "翻译服务",
            ["OpenAI 兼容接口", "DeepL", "百度翻译", "百度大模型翻译", "LibreTranslate"],
            help="选择翻译服务。DeepL免费版每月50万字符免费额度；百度翻译标准版每月5万字符免费；百度大模型翻译额度用尽自动切换通用翻译；LibreTranslate为开源免费服务"
        )

        config = {}
        if service == "OpenAI 兼容接口":
            st.caption("支持 OpenAI、DeepSeek、智谱等兼容接口")
            api_col1, api_col2 = st.columns(2)
            with api_col1:
                config["api_base"] = st.text_input("API Base URL", value="https://api.openai.com/v1", help="API 端点地址")
                config["api_key"] = st.text_input("API Key", type="password", help="你的 API 密钥")
            with api_col2:
                config["model"] = st.text_input("模型名称", value="gpt-3.5-turbo", help="如 gpt-3.5-turbo, deepseek-chat 等")
        elif service == "DeepL":
            st.caption("DeepL API Free: 注册 https://www.deepl.com/pro-api 获取免费 Auth Key")
            config["api_key"] = st.text_input("DeepL Auth Key", type="password", help="DeepL API 密钥")
            if config["api_key"]:
                if st.button("查询 DeepL 用量", key="check_deepl_usage"):
                    usage = get_deepl_usage(config["api_key"])
                    st.session_state.deepl_usage = usage

                if "deepl_usage" in st.session_state:
                    usage = st.session_state.deepl_usage
                    if "error" in usage:
                        st.error(f"查询失败: {usage['error']}")
                    else:
                        char_count = usage.get("character_count", 0)
                        char_limit = usage.get("character_limit", 500000)
                        usage_pct = (char_count / char_limit * 100) if char_limit > 0 else 0
                        st.info(f"**本月用量:** {char_count:,} / {char_limit:,} 字符 ({usage_pct:.1f}%)")
                        st.progress(min(usage_pct / 100, 1.0))
        elif service == "百度翻译":
            st.caption("百度翻译开放平台: https://fanyi-api.baidu.com/ 注册获取 APP ID 和密钥")
            baidu_col1, baidu_col2 = st.columns(2)
            with baidu_col1:
                config["appid"] = st.text_input("APP ID", help="百度翻译 APP ID")
            with baidu_col2:
                config["secret_key"] = st.text_input("密钥", type="password", help="百度翻译密钥")
        elif service == "百度大模型翻译":
            st.caption("百度大模型文本翻译: https://fanyi-api.baidu.com/doc/21 额度用尽自动切换通用翻译")
            baidu_llm_col1, baidu_llm_col2 = st.columns(2)
            with baidu_llm_col1:
                config["appid"] = st.text_input("APP ID", key="baidu_llm_appid", help="百度翻译 APP ID")
            with baidu_llm_col2:
                config["secret_key"] = st.text_input("密钥", type="password", key="baidu_llm_secret", help="百度翻译密钥")
            config["api_key"] = st.text_input("API Key (可选)", type="password", key="baidu_llm_apikey", help="如使用 API Key 认证则填写，否则使用上方 APP ID + 密钥认证")
            if config.get("appid") and config.get("secret_key"):
                if st.button("检测大模型翻译额度", key="check_baidu_llm"):
                    with st.spinner("正在检测..."):
                        quota_result = check_baidu_quota(config["appid"], config["secret_key"], config.get("api_key") or None)
                        st.session_state.baidu_llm_quota = quota_result
                if "baidu_llm_quota" in st.session_state:
                    quota = st.session_state.baidu_llm_quota
                    if quota["available"]:
                        st.success("大模型翻译额度可用")
                    else:
                        st.warning(f"大模型翻译不可用: {quota['reason']}，将自动切换至通用翻译")
        elif service == "LibreTranslate":
            st.caption("LibreTranslate 开源翻译服务，可使用公共实例或自建")
            config["api_url"] = st.text_input("LibreTranslate URL", value="https://libretranslate.com", help="LibreTranslate 实例地址")

        translate_target = st.selectbox("翻译内容", ["仅题目", "仅摘要", "题目+摘要"], help="选择要翻译的部分")

        all_chunks = {}
        chunk_labels = {}
        for vol_key, vol_info in volumes_data.items():
            vol_type = vol_info["type"]
            vol_id = vol_info["volume_id"]
            vol_papers = vol_info["papers"]
            test_md = generate_markdown(vol_papers, venue_name, year, volume_label=vol_type, compact=compact)
            file_size = len(test_md.encode("utf-8"))

            if file_size > MAX_FILE_SIZE:
                current_papers = []
                chunk_idx = 1
                chunk_list = []
                for p in vol_papers:
                    test_chunk = generate_markdown(current_papers + [p], venue_name, year, volume_label=vol_type, compact=compact)
                    if len(test_chunk.encode("utf-8")) > MAX_FILE_SIZE and current_papers:
                        chunk_list.append(current_papers)
                        current_papers = [p]
                        chunk_idx += 1
                    else:
                        current_papers.append(p)
                if current_papers:
                    chunk_list.append(current_papers)

                for idx, chunk_papers in enumerate(chunk_list, 1):
                    chunk_key = f"{vol_key}_第{idx}部分"
                    all_chunks[chunk_key] = {"vol_info": vol_info, "papers": chunk_papers, "part": idx}
                    chunk_labels[chunk_key] = f"{vol_type} ({vol_id}) 第{idx}部分 — {len(chunk_papers)}篇"
            else:
                chunk_key = f"{vol_key}_完整"
                all_chunks[chunk_key] = {"vol_info": vol_info, "papers": vol_papers, "part": 0}
                chunk_labels[chunk_key] = f"{vol_type} ({vol_id}) — {len(vol_papers)}篇"

        chunk_options = list(all_chunks.keys())
        selected_chunks = st.multiselect(
            "选择要翻译的部分 (与下载文件对应)",
            options=chunk_options,
            default=chunk_options,
            format_func=lambda x: chunk_labels[x],
            help="每个部分独立翻译，生成原文+翻译对照文件"
        )

        if st.button("开始翻译", type="secondary"):
            st.session_state.stop_translation = False
            valid = True
            if service == "OpenAI 兼容接口" and not config.get("api_key"):
                st.error("请输入 API Key")
                valid = False
            elif service == "DeepL" and not config.get("api_key"):
                st.error("请输入 DeepL Auth Key")
                valid = False
            elif service == "百度翻译" and (not config.get("appid") or not config.get("secret_key")):
                st.error("请输入百度翻译 APP ID 和密钥")
                valid = False
            elif service == "百度大模型翻译" and (not config.get("appid") or not config.get("secret_key")):
                st.error("请输入百度大模型翻译 APP ID 和密钥")
                valid = False
            elif not selected_chunks:
                st.warning("请至少选择一个部分")
                valid = False

            if valid:
                progress_bar = st.progress(0)
                status_text = st.empty()
                stop_button_placeholder = st.empty()

                def update_progress(p):
                    progress_bar.progress(p)
                    status_text.text(f"翻译进度: {int(p * 100)}%")

                translated_chunks = {}
                total_papers = sum(len(all_chunks[ck]["papers"]) for ck in selected_chunks)
                progress_state = {"count": 0}

                with stop_button_placeholder.container():
                    if st.button("停止翻译", type="secondary", key="stop_translation_btn"):
                        st.session_state.stop_translation = True
                        st.warning("正在停止...")

                for chunk_key in selected_chunks:
                    if st.session_state.get("stop_translation", False):
                        break

                    chunk_data = all_chunks[chunk_key]
                    vol_info = chunk_data["vol_info"]

                    def chunk_progress(p):
                        progress_state["count"] += p
                        update_progress(progress_state["count"] / total_papers)

                    translated_papers = translate_papers(
                        chunk_data["papers"], service, config, translate_target,
                        progress_callback=chunk_progress
                    )

                    if translated_papers:
                        translated_chunks[chunk_key] = {
                            "vol_info": vol_info,
                            "papers": translated_papers,
                            "part": chunk_data["part"],
                        }

                st.session_state.translated_chunks = translated_chunks
                st.session_state.translate_target = translate_target
                st.session_state.chunk_labels = chunk_labels

                if st.session_state.get("stop_translation", False):
                    progress_bar.progress(progress_state["count"] / total_papers)
                    status_text.text("翻译已停止")
                    st.warning(f"翻译已停止。共翻译 {progress_state['count']} / {total_papers} 篇论文。")
                    st.session_state.stop_translation = False
                else:
                    progress_bar.progress(1.0)
                    status_text.text("翻译完成!")
                    st.success(f"翻译完成! 共翻译 {total_papers} 篇论文，{len(selected_chunks)} 个部分。请向下滚动查看翻译版本下载按钮。")

    st.subheader("下载文件 (原文)")
    st.caption(f"单文件超过 1MB 时自动拆分，确保 Typora 可流畅打开")

    for vol_key, vol_info in volumes_data.items():
        vol_type = vol_info["type"]
        vol_id = vol_info["volume_id"]
        vol_papers = vol_info["papers"]

        test_md = generate_markdown(vol_papers, venue_name, year, volume_label=vol_type, compact=compact)
        file_size = len(test_md.encode("utf-8"))

        if file_size > MAX_FILE_SIZE:
            st.markdown(f"**{vol_type}** ({vol_id}) — {len(vol_papers)}篇 — 文件过大，自动拆分为多个部分")
            chunks = split_papers_into_chunks(vol_papers, venue_name, year, vol_type, compact)
            for part_label, chunk_md in chunks:
                suffix = "_紧凑" if compact else ""
                part_suffix = f"_{part_label}" if part_label else ""
                filename = f"{venue_name}_{year}_{vol_type}_{vol_id}{part_suffix}{suffix}.md"
                st.download_button(
                    label=f"下载 {vol_type} {part_label} ({chunk_md.count('## ' if not compact else chr(10) + str(1) + '.')}篇)",
                    data=chunk_md.encode("utf-8"),
                    file_name=filename,
                    mime="text/markdown",
                    key=f"dl_{vol_id}_{part_label}",
                )
        else:
            suffix = "_紧凑" if compact else ""
            size_kb = file_size // 1024
            filename = f"{venue_name}_{year}_{vol_type}_{vol_id}{suffix}.md"
            st.download_button(
                label=f"下载 {vol_type} ({len(vol_papers)}篇, {size_kb}KB)",
                data=test_md.encode("utf-8"),
                file_name=filename,
                mime="text/markdown",
                key=f"dl_{vol_id}",
            )

    if "translated_chunks" in st.session_state:
        st.divider()
        st.subheader("📥 下载翻译版本")
        st.caption("原文和翻译对照，翻译内容紧跟在原文下方")
        st.info(f"已翻译 {len(st.session_state.translated_chunks)} 个部分")

        translated_chunks = st.session_state.translated_chunks

        for chunk_key, chunk_data in translated_chunks.items():
            vol_info = chunk_data["vol_info"]
            vol_type = vol_info["type"]
            vol_id = vol_info["volume_id"]
            chunk_papers = chunk_data["papers"]
            part_num = chunk_data["part"]

            chunk_md = generate_markdown(chunk_papers, venue_name, year, volume_label=vol_type, compact=compact, include_translation=True)
            suffix = "_紧凑" if compact else ""
            part_suffix = f"_第{part_num}部分" if part_num > 0 else ""
            filename = f"{venue_name}_{year}_{vol_type}_{vol_id}{part_suffix}_翻译{suffix}.md"
            size_kb = len(chunk_md.encode("utf-8")) // 1024

            st.download_button(
                label=f"下载翻译版 {st.session_state.chunk_labels[chunk_key]} ({size_kb}KB)",
                data=chunk_md.encode("utf-8"),
                file_name=filename,
                mime="text/markdown",
                key=f"dl_trans_{chunk_key}",
            )
