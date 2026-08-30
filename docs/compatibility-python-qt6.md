# Python / Qt6 兼容性说明

## 目标运行环境

POMATO 当前设计目标为：

- Python 3.10+
- PyQt6
- Linux / Windows 主流桌面环境

## 为什么需要显式版本要求

项目中大量使用了 Python 3.10+ 的类型语法，例如：

- `str | None`
- `list[str]`
- `dict[str, Any]`

这个语法要求解释器至少为 Python 3.10。仅引入 `from __future__ import annotations` 不能让较低版本 Python 正确解析这些新语法；它只能延迟类型求值。

## 运行时校验

应用入口 [main.py](../main.py) 已增加版本检查：

```python
if sys.version_info < (3, 10):
    raise RuntimeError(
        "POMATO requires Python 3.10+ because it targets Qt6 and uses Python 3.10+ type syntax."
    )
```

这样可以在启动阶段提前给出清晰错误，而不是在运行时出现难以定位的 SyntaxError 或 ImportError。

## 兼容性建议

### 若运行环境低于 3.10

建议升级到 Python 3.10+，不要试图在旧版本解释器上直接运行此项目。

### 若需要更宽兼容

如果未来希望支持 Python 3.8/3.9，需要把类型注解改写成 `typing` 旧写法，例如：

```python
from typing import Optional, List

def foo(x: Optional[str] = None) -> List[str]:
    ...
```

而不是：

```python
def foo(x: str | None = None) -> list[str]:
    ...
```

## 其他说明

- `from __future__ import annotations` 作为注解兼容辅助，可以保留在主模块中。
- 本项目的 Python 版本要求必须和 Qt6 运行时保持一致。
- Linux 输入法问题与 Python 版本不是同一类问题，但在低版本 Python / 缺失 Qt6 环境中，会出现更难定位的运行时异常。
