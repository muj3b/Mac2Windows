from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

DEFAULT_MAPPINGS = {
  'mac-to-win': {
    # UI Frameworks
    'AppKit': 'System.Windows.Forms',
    'UIKit': 'System.Windows.Controls (WPF)',
    'SwiftUI': 'WinUI 3 / MAUI',
    'Cocoa': 'WPF / WinForms',
    'CoreGraphics': 'System.Drawing / SkiaSharp',
    'CoreAnimation': 'System.Windows.Media.Animation',
    
    # Core Systems
    'Foundation': 'System',
    'CoreFoundation': 'System.Runtime.InteropServices',
    'Grand Central Dispatch (GCD)': 'System.Threading.Tasks (TPL)',
    'XPC': 'Named Pipes / WCF',
    'UserDefaults': 'System.Configuration.ConfigurationManager / Registry',
    'Keychain': 'Windows Credential Manager (CredentialVault)',
    
    # Data & Networking
    'CoreData': 'Entity Framework Core',
    'SQLite': 'Microsoft.Data.Sqlite',
    'URLSession': 'System.Net.Http.HttpClient',
    'CloudKit': 'Azure Mobile Apps / OneDrive SDK',
    
    # Hardware & Sensors
    'CoreLocation': 'Windows.Devices.Geolocation',
    'CoreBluetooth': 'Windows.Devices.Bluetooth',
    'AVFoundation': 'Windows.Media.Capture / MediaFoundation',
    'CoreMotion': 'Windows.Devices.Sensors',
    
    # System Integration
    'UserNotifications': 'Microsoft.Toolkit.Uwp.Notifications',
    'StoreKit': 'Windows.Services.Store',
    'WebKit': 'Microsoft.Web.WebView2',
    'EventKit': 'Windows.ApplicationModel.Appointments',
    'Contacts': 'Windows.ApplicationModel.Contacts'
  },
  'win-to-mac': {
    # UI Frameworks
    'System.Windows.Forms': 'AppKit',
    'WPF': 'AppKit / SwiftUI',
    'WinUI': 'SwiftUI',
    'UWP': 'SwiftUI / UIKit (Catalyst)',
    'MAUI': 'SwiftUI',
    
    # Core Systems
    'System': 'Foundation',
    'System.IO': 'Foundation (FileManager)',
    'System.Threading.Tasks': 'Grand Central Dispatch (GCD) / Swift Concurrency',
    'Registry': 'UserDefaults',
    'CredentialManager': 'Keychain Services',
    
    # Data & Networking
    'Entity Framework': 'CoreData',
    'ADO.NET': 'SQLite / CoreData',
    'HttpClient': 'URLSession',
    
    # Hardware & Sensors
    'Windows.Devices.Geolocation': 'CoreLocation',
    'Windows.Devices.Bluetooth': 'CoreBluetooth',
    'Windows.Media': 'AVFoundation',
    
    # System Integration
    'WebView2': 'WKWebView',
    'ToastNotifications': 'UserNotifications',
    'MSI/MSIX': 'Pkg / DMG'
  }
}


class DependencyGenerator:
    def convert_to_windows(self, project_root: Path, target_root: Path) -> Path:
        packages_config = target_root / 'packages.config'
        dependencies = self._collect_podfile_dependencies(project_root)
        dependencies.update(self._collect_swiftpm_dependencies(project_root))
        root = ET.Element('packages')
        for name, version in dependencies.items():
            mapped = DEPENDENCY_MAP.get(name, name)
            ET.SubElement(root, 'package', id=mapped, version=version or '1.0.0')
        packages_config.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(root).write(packages_config, encoding='utf-8', xml_declaration=True)
        return packages_config

    def convert_to_mac(self, project_root: Path, target_root: Path) -> Path:
        package_swift = target_root / 'Package.swift'
        dependencies = self._collect_csproj_dependencies(project_root)
        lines = [
            "// swift-tools-version:5.7",
            "import PackageDescription",
            "let package = Package(",
            "    name: \"ConvertedApp\",",
            "    platforms: [.macOS(.v13)],",
            "    products: [.executable(name: \"ConvertedApp\", targets: [\"App\"])],",
            "    dependencies: ["
        ]
        for name, version in dependencies.items():
            mapped = self._map_windows_dependency(name)
            formatted_version = version or "1.0.0"
            lines.append(f'        .package(url: "https://github.com/{mapped}.git", from: "{formatted_version}"),')
        lines.append('    ],')
        lines.append('    targets: [.target(name: "App", dependencies: [])]')
        lines.append(')')
        package_swift.parent.mkdir(parents=True, exist_ok=True)
        package_swift.write_text('\n'.join(lines), encoding='utf-8')
        return package_swift

    def _collect_podfile_dependencies(self, project_root: Path) -> Dict[str, str]:
        podfile = next(project_root.glob('**/Podfile'), None)
        if not podfile:
            return {}
        pattern = re.compile(r"pod\s+'(?P<name>[^']+)'(?:,\s*'(?P<version>[^']+)')?")
        deps: Dict[str, str] = {}
        for line in podfile.read_text(encoding='utf-8').splitlines():
            match = pattern.search(line)
            if match:
                deps[match.group('name')] = match.group('version')
        return deps

    def _collect_swiftpm_dependencies(self, project_root: Path) -> Dict[str, str]:
        package_swift = next(project_root.glob('**/Package.swift'), None)
        if not package_swift:
            return {}
        pattern = re.compile(r"\.package\(.*name:\s*\"(?P<name>[^\"]+)\".*from:\s*\"(?P<version>[^\"]+)\"", re.DOTALL)
        deps: Dict[str, str] = {}
        content = package_swift.read_text(encoding='utf-8')
        for match in pattern.finditer(content):
            deps[match.group('name')] = match.group('version')
        return deps

    def _collect_csproj_dependencies(self, project_root: Path) -> Dict[str, str]:
        deps: Dict[str, str] = {}
        for csproj in project_root.glob('**/*.csproj'):
            tree = ET.parse(csproj)
            root = tree.getroot()
            for pkg in root.findall('.//PackageReference'):
                include = pkg.attrib.get('Include')
                version = pkg.attrib.get('Version') or pkg.findtext('{*}Version')
                if include:
                    deps[include] = version
        packages_config = project_root / 'packages.config'
        if packages_config.exists():
            tree = ET.parse(packages_config)
            root = tree.getroot()
            for pkg in root.findall('package'):
                include = pkg.attrib.get('id')
                version = pkg.attrib.get('version')
                if include:
                    deps[include] = version
        return deps

    def _map_windows_dependency(self, name: str) -> str:
        reverse_map = {v: k for k, v in DEPENDENCY_MAP.items()}
        return reverse_map.get(name, name)
