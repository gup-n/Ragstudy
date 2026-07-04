"""HuggingFace 模型下载器。

职责单一：
  - 只负责下载 HuggingFace 模型到本地缓存目录
  - 不操作数据库
  - 不调用 Factory

下载完成后，由 GUI 调用 crud.save_config() 保存配置。
"""

import logging
from pathlib import Path

from embedding.config import HF_MODEL_CACHE_DIR
from embedding.schema import ModelDownloadError

logger = logging.getLogger(__name__)


def _resolve_cache_dir(cache_dir: Path | None) -> Path:
    """解析缓存目录，若为 None 则使用默认值。纯函数，无副作用。"""
    return cache_dir or HF_MODEL_CACHE_DIR


def _ensure_dir(path: Path) -> None:
    """确保目录存在，若不存在则创建。纯副作用操作。"""
    path.mkdir(parents=True, exist_ok=True)


def download_huggingface_model(
    model_name: str,
    cache_dir: Path | None = None,
) -> Path:
    """下载 HuggingFace 模型到本地缓存目录。

    Args:
        model_name: HuggingFace 模型 ID，如 "BAAI/bge-small-zh-v1.5".
        cache_dir: 缓存根目录，默认使用 config.HF_MODEL_CACHE_DIR.

    Returns:
        模型快照目录（snapshot directory）的路径。该目录可直接用于
        `from_pretrained()` 等加载方法。

    Raises:
        ModelDownloadError: 下载失败时抛出。
    """
    target_dir = _resolve_cache_dir(cache_dir)
    _ensure_dir(target_dir)

    try:
        from huggingface_hub import snapshot_download

        logger.info("Downloading HuggingFace model '%s' to %s", model_name, target_dir)
        local_path = snapshot_download(
            repo_id=model_name,
            cache_dir=target_dir,
            # resume_download 已弃用，HF 默认支持断点续传
            # local_files_only 默认 False，允许联网
        )
        logger.info("Downloaded HuggingFace model '%s' to %s", model_name, local_path)
        return Path(local_path)

    except ImportError as e:
        raise ModelDownloadError(
            "huggingface_hub is not installed. Please install it via 'pip install huggingface-hub'."
        ) from e
    except Exception as e:
        raise ModelDownloadError(f"Failed to download model {model_name}: {e}") from e


def is_model_downloaded(model_name: str, cache_dir: Path | None = None) -> bool:
    """检查模型是否已在本地缓存中完整可用。

    当前实现是一种“存在性探测”（existence probe），
    它通过尝试加载本地缓存来判断模型是否完整可用，
    但不做文件哈希校验或深度完整性验证。
    对于绝大多数日常场景，这种简化可靠且高效。
    若未来需要严格验证，可考虑增加文件校验层或升级为缓存治理模块。

    Args:
        model_name: HuggingFace 模型 ID.
        cache_dir: 缓存根目录.

    Returns:
        模型是否已下载并可用于加载。

    Raises:
        抛出非 LocalEntryNotFoundError 的异常（如权限错误、磁盘错误），
        由上层决定是否捕获。
    """
    target_dir = _resolve_cache_dir(cache_dir)
    _ensure_dir(target_dir)

    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError

        # 仅尝试从本地缓存加载，若缺少任何必要文件则抛出 LocalEntryNotFoundError
        snapshot_download(
            repo_id=model_name,
            cache_dir=target_dir,
            local_files_only=True,
        )
        return True
    except LocalEntryNotFoundError:
        return False
    # 其他异常（如 OSError, PermissionError）自动向上传播
