# 替代 RAGFlow common.file_utils.get_project_base_directory：
# 混沌海侧模型目录始终显式传入，此默认值仅供上游代码兜底。
import os


def get_project_base_directory() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
