"""数据库连接与会话管理。

设计原则：
1. Session 生命周期由 `with get_session()` 显式管理，每个事务对应一个 Session。
2. 数据库特有配置（SQLite PRAGMA）集中在 Engine 层，通过事件监听统一设置。
3. 配置保持克制：只暴露真正需要调节的参数（如 ENABLE_WAL），不为未来过度抽象。
4. expire_on_commit=False：匹配脚本项目“对象在事务外传递”的使用模式。
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from embedding.config import DATABASE_PATH, ENABLE_SQLITE_WAL

logger = logging.getLogger(__name__)

# 确保数据目录存在
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# 创建引擎
engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    echo=False,
    connect_args={
        "check_same_thread": False,  # 允许多线程借用不同连接，Session 本身不跨线程
        "timeout": 10,  # 等待锁的秒数，防止瞬时锁竞争直接失败
    },
)


@event.listens_for(engine, "connect")
def configure_sqlite(dbapi_connection, _):
    """配置 SQLite 连接。

    将数据库特有的 PRAGMA 集中在 Engine 层设置，保持业务代码对数据库类型无感。
    分类说明：
      - foreign_keys：数据完整性。仅当 Schema 确实使用外键时才有意义，此处保留但建议按需开启。
      - journal_mode / synchronous：性能策略，通过配置开关控制。
      - cache_size / temp_store：机器相关优化，不建议默认设置。
    """
    cursor = dbapi_connection.cursor()

    # 外键约束：建议在 Schema 真正使用 FOREIGN KEY 时开启
    # 如果当前 models.py 没有任何外键，这行不会产生任何效果，可注释掉
    cursor.execute("PRAGMA foreign_keys = ON")

    if ENABLE_SQLITE_WAL:
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")

    cursor.close()


# 创建 Session 工厂
# expire_on_commit=False：Session 提交后对象仍可访问属性，适合脚本中“读取后传递到事务外”的模式
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def init_db() -> None:
    """初始化数据库，创建所有表。

    在应用程序启动时调用一次即可。
    如果存在循环导入问题，可将 `from embedding.models import Base` 移入函数内部。
    """
    from embedding.models import Base
    import llm.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at %s", DATABASE_PATH)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """获取数据库会话的上下文管理器。

    每个 `with` 块对应一个独立事务：
      - 正常退出：自动 commit
      - 异常退出：自动 rollback 并重新抛出异常
      - 无论何种退出：自动 close 释放连接

    Usage:
        with get_session() as session:
            config = crud.get_config(session)
            # 多个 CRUD 操作在同一个事务中

    注意：事务内不应包含耗时操作（如 Embedding 推理、HTTP 请求），
    以免长时间持有数据库连接或锁。
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Session rolled back due to error")
        raise
    finally:
        session.close()


def close_db() -> None:
    """释放引擎持有的连接池资源。

    仅在应用关闭或需要热重载时调用。
    注意：dispose() 只会关闭池中空闲连接，不会强制关闭正在使用的连接。
    已借出的连接会在归还后自动关闭。
    """
    engine.dispose()
    logger.debug("Database engine disposed")
