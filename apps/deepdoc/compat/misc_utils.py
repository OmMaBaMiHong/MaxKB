# 替代 RAGFlow common.misc_utils.pip_install_torch：混沌海不内置 torch，本地模型按需自行安装。
def pip_install_torch():  # noqa: D401
    raise RuntimeError("混沌海不内置 torch；如需本地推理模型请单独安装")
