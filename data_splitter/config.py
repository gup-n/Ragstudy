"""切割器配置——修改参数只需改这里。"""

from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)

# ---------------------------------------------------------------------------
# 切割策略注册表
# ---------------------------------------------------------------------------
# 键：策略名称，值：对应的 TextSplitter 类
DEFAULT_SPLITTER = "recursive"

SPLITTER_MAPPING = {
    "recursive": RecursiveCharacterTextSplitter,
    "character": CharacterTextSplitter,
}

# 每种切割器的默认参数
SPLITTER_ARGS = {
    "recursive": {
        "chunk_size": 800,
        "chunk_overlap": 150,
        "separators": [
            "\n\n",
            "\n",
            "。",
            "！",
            "？",
            "；",
            "，",
            " ",
            "",
        ],
    },
    "character": {
        "separator": "\n",
        "chunk_size": 800,
        "chunk_overlap": 150,
    },
}
