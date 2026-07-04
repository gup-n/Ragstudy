def __getattr__(name):
    """延迟导入，避免 -m 运行时的循环导入警告。"""
    import importlib

    module = importlib.import_module("data_splitter.splitter")
    return getattr(module, name)


__all__ = ["split_documents", "get_text_splitter", "SUPPORTED_SPLITTERS"]
