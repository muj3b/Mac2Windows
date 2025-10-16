from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
  import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  psutil = None


@dataclass
class Thresholds:
  cpu_percent: float = 80.0
  memory_percent: float = 90.0
  disk_free_gb: float = 5.0


class ResourceMonitor:
  def __init__(self, thresholds: Optional[Thresholds] = None) -> None:
    self.thresholds = thresholds or Thresholds()

  def snapshot(self, minimal: bool = False) -> Dict[str, Any]:
    if psutil is None:
      disk = shutil.disk_usage('.')
      disk_free_gb = disk.free / (1024**3)
      core_payload = {
        'cpu': None,
        'memory': None,
        'disk': {
          'total_gb': disk.total / (1024**3),
          'free_gb': disk_free_gb,
          'percent': round((disk.used / disk.total) * 100, 1)
        },
        'network': None,
        'flags': {
          'cpu_high': False,
          'memory_high': False,
          'disk_low': disk_free_gb < self.thresholds.disk_free_gb
        }
      }
      return core_payload if not minimal else {'disk': core_payload['disk']}

    cpu_percent = psutil.cpu_percent(interval=0.05)
    virtual_mem = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('.')
    net_io = psutil.net_io_counters()

    payload = {
      'cpu': {'percent': round(cpu_percent, 1)},
      'memory': {
        'percent': round(virtual_mem.percent, 1),
        'used_gb': round(virtual_mem.used / (1024**3), 2),
        'total_gb': round(virtual_mem.total / (1024**3), 2)
      },
      'disk': {
        'percent': round(disk_usage.percent, 1),
        'free_gb': round(disk_usage.free / (1024**3), 2),
        'total_gb': round(disk_usage.total / (1024**3), 2)
      },
      'network': {
        'bytes_sent': net_io.bytes_sent,
        'bytes_recv': net_io.bytes_recv
      },
      'flags': {
        'cpu_high': cpu_percent >= self.thresholds.cpu_percent,
        'memory_high': virtual_mem.percent >= self.thresholds.memory_percent,
        'disk_low': (disk_usage.free / (1024**3)) <= self.thresholds.disk_free_gb
      }
    }
    return payload if not minimal else {'cpu': payload['cpu'], 'memory': payload['memory']}
