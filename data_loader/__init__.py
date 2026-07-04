def __getattr__(name):
    """Lazy import — 避免 -m 运行时的循环导入警告。"""
    import importlib

    module = importlib.import_module("data_loader.loader")
    return getattr(module, name)


__all__ = ["load_documents", "get_loader_for_file", "SUPPORTED_EXTENSIONS"]
