# -*- coding: utf-8 -*-
#
import os

from dotenv import load_dotenv

from .conf import ConfigManager

__all__ = ['BASE_DIR', 'PROJECT_DIR', 'VERSION', 'CONFIG']

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)
VERSION = '2.0.0'
# 产品改造：日志目录支持环境变量覆盖；容器外开发回落仓库内 .runtime（容器内 /opt 布局不变）
LOG_DIR = os.environ.get('MAXKB_LOG_DIR') or (
    os.path.join('/', 'opt', 'maxkb', 'logs') if os.path.isdir('/opt/maxkb')
    else os.path.join(BASE_DIR, '.runtime/logs'))

# load environment variables from .env file
load_dotenv()
# print(os.getenv('MAXKB_CONFIG'))
if os.getenv('MAXKB_CONFIG') is not None:
    CONFIG = ConfigManager.load_user_config(root_path=PROJECT_DIR)
else:
    CONFIG = ConfigManager.load_user_config(root_path=os.path.abspath('/opt/maxkb/conf'))

