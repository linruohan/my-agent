"""测试文件搜索功能"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools.file.search import find_files_impl

print("测试搜索 main.py 文件...")
result = find_files_impl("main.py", root=str(Path.home()), file_type="file", max_results=10)
print("结果:")
print(result)
print("\n" + "="*80 + "\n")

print("测试搜索 main.rs 文件...")
result = find_files_impl("main.rs", root=str(Path.home()), file_type="file", max_results=10)
print("结果:")
print(result)