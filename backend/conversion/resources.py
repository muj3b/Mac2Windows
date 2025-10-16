from __future__ import annotations

import plistlib
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image

from backend.conversion.models import ChunkRecord, ChunkWorkItem, Stage


class ResourceConverter:
  def __init__(self) -> None:
    self.storyboard_namespace = {
      'ib': 'http://apple.com/IB'  # placeholder namespace mapping
    }

  def convert(self, direction: str, chunk: ChunkWorkItem, target_path: Path) -> List[Path]:
    source = Path(chunk.file_path)
    if not source.exists():
      raise FileNotFoundError(source)
    suffix = source.suffix.lower()
    output_dir = target_path.parent if target_path.is_file() else target_path

    if suffix in {'.png', '.jpg', '.jpeg'}:
      return self._convert_images(direction, source, output_dir)
    if suffix == '.strings':
      if direction == 'mac-to-win':
        return [self._strings_to_resx(source, output_dir)]
      return [self._resx_to_strings(source, output_dir)]
    if suffix in {'.storyboard', '.xib'} and direction == 'mac-to-win':
      return [self._interface_builder_to_xaml(source, output_dir)]
    if suffix == '.xaml' and direction == 'win-to-mac':
      return [self._xaml_to_storyboard(source, output_dir)]
    if suffix == '.plist' and direction == 'mac-to-win':
      return [self._plist_to_manifest(source, output_dir)]
    if suffix == '.app.manifest' and direction == 'win-to-mac':
      return [self._manifest_to_plist(source, output_dir)]

    destination = output_dir / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return [destination]

  def _convert_images(self, direction: str, source: Path, output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    image = Image.open(source)
    if direction == 'mac-to-win':
      base_name = source.stem.split('@')[0]
      for scale_name, factor in [('Scale-100', 1.0), ('Scale-200', 2.0), ('Scale-400', 4.0)]:
        size = tuple(int(dim / factor) if factor != 0 else dim for dim in image.size)
        resized = image.resize(size, Image.LANCZOS)
        target = output_dir / f'{base_name}.{scale_name}{source.suffix}'
        resized.save(target)
        outputs.append(target)
    else:
      base_name = source.stem
      for suffix, factor in [('@1x', 1.0), ('@2x', 2.0), ('@3x', 3.0)]:
        size = tuple(int(dim * factor) for dim in image.size)
        resized = image.resize(size, Image.LANCZOS)
        target = output_dir / f'{base_name}{suffix}{source.suffix}'
        resized.save(target)
        outputs.append(target)
    return outputs

  def _strings_to_resx(self, source: Path, output_dir: Path) -> Path:
    pattern = re.compile(r'^\s*"(?P<key>.+?)"\s*=\s*"(?P<value>.*?)"\s*;\s*$')
    entries: Dict[str, str] = {}
    with source.open('r', encoding='utf-8') as handle:
      for line in handle:
        match = pattern.match(line)
        if match:
          entries[match.group('key')] = match.group('value')

    resx = ET.Element('root')
    ET.SubElement(resx, 'resheader', name='resmimetype').text = 'text/microsoft-resx'
    for key, value in entries.items():
      data = ET.SubElement(resx, 'data', name=key, xml_space='preserve')
      value_el = ET.SubElement(data, 'value')
      value_el.text = value
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (source.stem + '.resx')
    tree = ET.ElementTree(resx)
    tree.write(output, encoding='utf-8', xml_declaration=True)
    return output

  def _resx_to_strings(self, source: Path, output_dir: Path) -> Path:
    tree = ET.parse(source)
    root = tree.getroot()
    lines: List[str] = []
    for data in root.findall('data'):
      key = data.attrib.get('name')
      value_node = data.find('value')
      if key and value_node is not None:
        value = value_node.text or ''
        lines.append(f'"{key}" = "{value}";')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (source.stem + '.strings')
    output.write_text('\n'.join(lines), encoding='utf-8')
    return output

  def _interface_builder_to_xaml(self, source: Path, output_dir: Path) -> Path:
    tree = ET.parse(source)
    root = tree.getroot()
    page = ET.Element('Page')
    page.attrib['xmlns'] = 'http://schemas.microsoft.com/winfx/2006/xaml/presentation'
    page.attrib['xmlns:x'] = 'http://schemas.microsoft.com/winfx/2006/xaml'
    grid = ET.SubElement(page, 'Grid')
    for view in root.findall('.//view'):
      control = ET.SubElement(grid, 'Grid')
      control.attrib['Tag'] = view.attrib.get('id', '')
    for button in root.findall('.//button'):
      control = ET.SubElement(grid, 'Button')
      control.attrib['Content'] = button.attrib.get('title', 'Button')
    for label in root.findall('.//label'):
      control = ET.SubElement(grid, 'TextBlock')
      control.attrib['Text'] = label.attrib.get('text', 'Label')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (source.stem + '.xaml')
    ET.ElementTree(page).write(output, encoding='utf-8', xml_declaration=True)
    return output

  def _xaml_to_storyboard(self, source: Path, output_dir: Path) -> Path:
    tree = ET.parse(source)
    root = tree.getroot()
    document = ET.Element('document')
    scene = ET.SubElement(document, 'scene')
    objects = ET.SubElement(scene, 'objects')
    view_controller = ET.SubElement(objects, 'viewController')
    view = ET.SubElement(view_controller, 'view')
    for button in root.findall('.//{http://schemas.microsoft.com/winfx/2006/xaml/presentation}Button'):
      control = ET.SubElement(view, 'button')
      control.attrib['title'] = button.attrib.get('Content', 'Button')
    for textblock in root.findall('.//{http://schemas.microsoft.com/winfx/2006/xaml/presentation}TextBlock'):
      control = ET.SubElement(view, 'label')
      control.attrib['text'] = textblock.attrib.get('Text', 'Label')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (source.stem + '.storyboard')
    ET.ElementTree(document).write(output, encoding='utf-8', xml_declaration=True)
    return output

  def _plist_to_manifest(self, source: Path, output_dir: Path) -> Path:
    with source.open('rb') as handle:
      plist_data = plistlib.load(handle)
    assembly = ET.Element('assembly')
    assembly.attrib['xmlns'] = 'urn:schemas-microsoft-com:asm.v1'
    ET.SubElement(assembly, 'assemblyIdentity', name=plist_data.get('CFBundleExecutable', 'App'), version=plist_data.get('CFBundleVersion', '1.0.0.0'))
    ET.SubElement(assembly, 'description').text = plist_data.get('CFBundleName', 'Converted Application')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'app.manifest'
    ET.ElementTree(assembly).write(output, encoding='utf-8', xml_declaration=True)
    return output

  def _manifest_to_plist(self, source: Path, output_dir: Path) -> Path:
    tree = ET.parse(source)
    root = tree.getroot()
    name = root.findtext('description', default='Converted Application')
    identity = root.find('assemblyIdentity')
    version = identity.attrib.get('version') if identity is not None else '1.0'
    plist_dict = {
      'CFBundleName': name,
      'CFBundleExecutable': name.replace(' ', ''),
      'CFBundleVersion': version
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'Info.plist'
    with output.open('wb') as handle:
      plistlib.dump(plist_dict, handle)
    return output
