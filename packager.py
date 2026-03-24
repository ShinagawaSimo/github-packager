import importlib.util
import sys

from pathlib import Path

root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
src_packager = src_dir / "packager.py"
spec = importlib.util.spec_from_file_location("packager_impl", src_packager)
module = importlib.util.module_from_spec(spec)
sys.modules["packager_impl"] = module
spec.loader.exec_module(module)
module.main()
