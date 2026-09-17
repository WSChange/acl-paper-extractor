import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re

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


def generate_markdown(papers: list[dict], venue: str, year: int, volume_label: str = "", compact: bool = False) -> str:
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
            lines.append(f"   作者: {authors_str}")
            lines.append("")
        else:
            lines.append(f"## {i}. {p['title']}")
            lines.append("")
            lines.append(f"作者: {authors_str}")
            lines.append("")
            if p["abstract"]:
                lines.append(f"摘要: {p['abstract']}")
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

        papers = []
        for v in volumes_data.values():
            papers.extend(v["papers"])

        st.success(f"成功获取 {len(papers)} 篇论文，分为 {len(volumes_data)} 个卷")

        with st.expander("论文预览 (前20篇)", expanded=True):
            for i, p in enumerate(papers[:20], 1):
                authors_str = ", ".join(p["authors"][:3])
                if len(p["authors"]) > 3:
                    authors_str += f" 等 {len(p['authors'])} 人"
                st.markdown(f"**{i}. {p['title']}**")
                st.caption(f"作者: {authors_str}")
                if p["abstract"]:
                    st.caption(p["abstract"][:200] + "...")
                st.divider()

        st.subheader("下载文件")
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
