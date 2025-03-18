import os
import sys

project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_path)

from libs.mysql_funcs import setup_database
from libs.trade import init_step_size

if __name__ == "__main__":
    setup_database()
    init_step_size()