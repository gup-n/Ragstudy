"""Streamlit frontend connected to the FastAPI RAG backend."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import streamlit as st

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def _api_base_url() -> str:
    default_url = os.getenv("RAG_API_BASE_URL", DEFAULT_API_BASE_URL)
    return st.sidebar.text_input("API 地址", value=default_url).rstrip("/")


def _request_json(
    method: str,
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    url = urljoin(f"{base_url}/", path.lstrip("/"))
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}, None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw).get("detail", raw)
        except json.JSONDecodeError:
            detail = raw
        return None, f"{exc.code}: {detail}"
    except URLError as exc:
        return None, f"无法连接 API: {exc.reason}"
    except TimeoutError:
        return None, "请求超时"
    except Exception as exc:
        return None, f"请求失败: {exc}"


def api_get(base_url: str, path: str) -> tuple[dict[str, Any] | None, str | None]:
    return _request_json("GET", base_url, path)


def api_post(
    base_url: str,
    path: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    return _request_json("POST", base_url, path, payload)


def render_status(base_url: str) -> None:
    health, health_error = api_get(base_url, "/health")
    config, config_error = api_get(base_url, "/config/status")
    stats, stats_error = api_get(base_url, "/stats")

    if health_error:
        st.error(health_error)
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("API", health.get("status", "unknown") if health else "unknown")
    col2.metric(
        "向量 Chunks",
        stats.get("total_chunks", 0) if stats and not stats_error else 0,
    )
    col3.metric("文件数", len(stats.get("files", [])) if stats else 0)

    if config_error:
        st.warning(config_error)
    elif config:
        st.subheader("配置状态")
        st.write(
            {
                "Embedding": config.get("embedding_configured"),
                "Embedding Provider": config.get("embedding_provider"),
                "Embedding Model": config.get("embedding_model"),
                "LLM": config.get("llm_configured"),
                "LLM Provider": config.get("llm_provider"),
                "LLM Model": config.get("llm_model"),
                "LLM Source": config.get("llm_source"),
            }
        )

    if stats_error:
        st.warning(stats_error)
    elif stats:
        with st.expander("已入库文件", expanded=False):
            files = stats.get("files", [])
            if files:
                for file in files:
                    st.write(file)
            else:
                st.write("暂无文件")


def render_index(base_url: str) -> None:
    with st.form("index_form"):
        directory = st.text_input("文档目录", value="")
        splitter = st.selectbox("切割策略", ["recursive", "character"], index=0)
        recursive = st.checkbox("递归扫描", value=True)
        reindex = st.checkbox("全量重建", value=False)
        prune_deleted = st.checkbox("清理已删除源文件", value=False)
        submitted = st.form_submit_button("执行入库")

    if not submitted:
        return

    payload = {
        "directory": directory.strip() or None,
        "splitter": splitter,
        "recursive": recursive,
        "reindex": reindex,
        "prune_deleted": prune_deleted,
    }
    with st.spinner("正在入库..."):
        data, error = api_post(base_url, "/index", payload)

    if error:
        st.error(error)
        return
    st.success("入库完成")
    st.json(data)


def render_retrieve(base_url: str) -> None:
    with st.form("retrieve_form"):
        query = st.text_area("查询", height=100)
        col1, col2 = st.columns(2)
        top_k = col1.number_input("返回片段数", min_value=1, max_value=20, value=5)
        use_threshold = col2.checkbox(
            "启用分数阈值",
            value=False,
            key="retrieve_use_threshold",
        )
        score_threshold = st.slider(
            "最低相关性分数",
            0.0,
            1.0,
            0.3,
            0.05,
            key="retrieve_score_threshold",
        )
        submitted = st.form_submit_button("检索")

    if not submitted:
        return

    payload = {
        "query": query,
        "top_k": int(top_k),
        "score_threshold": score_threshold if use_threshold else None,
    }
    data, error = api_post(base_url, "/retrieve", payload)
    if error:
        st.error(error)
        return

    st.caption(f"向量库 Chunks: {data.get('total_chunks', 0)}")
    for item in data.get("results", []):
        score = item.get("score")
        title = f"#{item.get('index')} score={score:.4f}" if score is not None else f"#{item.get('index')}"
        with st.expander(title, expanded=True):
            metadata = item.get("metadata", {})
            st.write(
                {
                    "filename": metadata.get("filename"),
                    "source_id": metadata.get("source_id"),
                    "chunk_id": metadata.get("chunk_id"),
                }
            )
            st.write(item.get("content", ""))


def render_answer(base_url: str) -> None:
    with st.form("answer_form"):
        query = st.text_area("问题", height=100)
        col1, col2 = st.columns(2)
        top_k = col1.number_input("检索片段数", min_value=1, max_value=20, value=5)
        context_max_chars = col2.number_input(
            "上下文最大字符数",
            min_value=1000,
            max_value=50000,
            value=12000,
            step=1000,
        )
        use_threshold = st.checkbox(
            "启用分数阈值",
            value=False,
            key="answer_use_threshold",
        )
        score_threshold = st.slider(
            "最低相关性分数",
            0.0,
            1.0,
            0.3,
            0.05,
            key="answer_score_threshold",
        )
        submitted = st.form_submit_button("生成回答")

    if not submitted:
        return

    payload = {
        "query": query,
        "top_k": int(top_k),
        "score_threshold": score_threshold if use_threshold else None,
        "context_max_chars": int(context_max_chars),
    }
    with st.spinner("正在生成回答..."):
        data, error = api_post(base_url, "/answer", payload)

    if error:
        st.error(error)
        return

    st.subheader("回答")
    st.write(data.get("answer", ""))
    st.subheader("引用来源")
    for source in data.get("sources", []):
        score = source.get("score")
        title = (
            f"[{source.get('index')}] {source.get('filename')} score={score:.4f}"
            if score is not None
            else f"[{source.get('index')}] {source.get('filename')}"
        )
        with st.expander(title, expanded=False):
            st.write(
                {
                    "source_id": source.get("source_id"),
                    "chunk_id": source.get("chunk_id"),
                }
            )
            st.write(source.get("excerpt", ""))


def main() -> None:
    st.set_page_config(page_title="RAG 控制台", layout="wide")
    st.title("RAG 控制台")

    base_url = _api_base_url()
    tabs = st.tabs(["状态", "入库", "检索", "问答"])
    with tabs[0]:
        render_status(base_url)
    with tabs[1]:
        render_index(base_url)
    with tabs[2]:
        render_retrieve(base_url)
    with tabs[3]:
        render_answer(base_url)


if __name__ == "__main__":
    main()
