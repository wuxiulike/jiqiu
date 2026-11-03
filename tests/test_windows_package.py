import sys
import ast
import os
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != 'win32', reason='仅检查 Windows 打包产物')
def test_packaged_icu_provides_qt_required_symbols():
    pefile = pytest.importorskip('pefile')
    manifest = Path(__file__).resolve().parents[1] / 'build' / '吉球' / 'Analysis-00.toc'
    if not manifest.exists():
        pytest.skip('尚未构建 Windows 包')
    def entries(value):
        if isinstance(value, (list, tuple)):
            if len(value) == 3 and all(isinstance(item, str) for item in value):
                yield value
            else:
                for item in value:
                    yield from entries(item)
    files = {name.replace('\\', '/').lower(): source for name, source, kind in entries(ast.literal_eval(manifest.read_text(encoding='utf-8'))) if kind == 'BINARY'}
    qt = Path(files['pyside6/qt6core.dll'])
    icu = Path(files.get('icuuc.dll', str(Path(os.environ['SystemRoot']) / 'System32' / 'icuuc.dll')))
    qt_pe = pefile.PE(str(qt))
    imported = next(entry for entry in qt_pe.DIRECTORY_ENTRY_IMPORT if entry.dll.lower() == b'icuuc.dll')
    required = {item.name for item in imported.imports if item.name}
    icu_pe = pefile.PE(str(icu))
    exports = {item.name for item in icu_pe.DIRECTORY_ENTRY_EXPORT.symbols if item.name}
    assert required <= exports, f'{icu} 缺少 Qt 需要的符号：{sorted(required - exports)}'
