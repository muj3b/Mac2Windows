from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import aiohttp
from cachetools import TTLCache

logger = logging.getLogger(__name__)


@dataclass
class VulnerabilityRecord:
  package: str
  ecosystem: str
  identifier: str
  summary: str
  severity: str
  url: Optional[str]


class OSVClient:
  BASE_URL = 'https://api.osv.dev/v1/query'

  def __init__(self, cache_ttl: int = 3600) -> None:
    self.cache = TTLCache(maxsize=256, ttl=cache_ttl)

  async def query(self, package: str, ecosystem: str) -> List[VulnerabilityRecord]:
    cache_key = f'{ecosystem}:{package}'
    if cache_key in self.cache:
      return self.cache[cache_key]

    payload = {
      'package': {
        'name': package,
        'ecosystem': ecosystem
      }
    }
    try:
      async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.post(self.BASE_URL, json=payload) as response:
          response.raise_for_status()
          data = await response.json()
    except Exception as exc:  # pragma: no cover - network failure
      logger.warning('OSV query failed for %s (%s): %s', package, ecosystem, exc)
      return []

    vulns: List[VulnerabilityRecord] = []
    for entry in data.get('vulns', []):
      severity = 'unknown'
      for rating in entry.get('severity', []):
        if 'score' in rating:
          severity = rating.get('score')
      vulns.append(
        VulnerabilityRecord(
          package=package,
          ecosystem=ecosystem,
          identifier=entry.get('id', 'unknown'),
          summary=entry.get('summary', 'No summary provided'),
          severity=str(severity),
          url=entry.get('details')
        )
      )

    self.cache[cache_key] = vulns
    return vulns

  async def query_multiple(self, packages: Dict[str, str]) -> Dict[str, List[VulnerabilityRecord]]:
    results: Dict[str, List[VulnerabilityRecord]] = {}
    for name, ecosystem in packages.items():
      results[name] = await self.query(name, ecosystem)
    return results
