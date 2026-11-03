"""Convert the project icon to platform icon containers without changing its design."""
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parent
source = QImage(str(ROOT / 'jiqiu.png'))
if source.isNull():
    raise RuntimeError('无法读取图标源文件')

images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    image = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise RuntimeError('无法生成图标尺寸')
    images.append((size, bytes(data)))

header = struct.pack('<HHH', 0, 1, len(images))
offset = 6 + 16 * len(images)
entries = []
for size, data in images:
    entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
    offset += len(data)
(ROOT / 'jiqiu.ico').write_bytes(header + b''.join(entries) + b''.join(data for _, data in images))
if not source.scaled(512, 512, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(ROOT / 'jiqiu.icns'), 'ICNS'):
    raise RuntimeError('无法生成 macOS 图标')
