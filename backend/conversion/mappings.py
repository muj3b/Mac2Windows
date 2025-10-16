from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


DEPENDENCY_MAP = {
  'mac-to-win': {
    'Alamofire': 'HttpClient',
    'Kingfisher': 'ImageSharp',
    'RxSwift': 'Reactive Extensions (.NET)',
    'RealmSwift': 'Realm .NET',
    'Firebase': 'Firebase .NET',
    'URLSession': 'HttpClient',
    'SwiftPackageManager': 'NuGet',
    'CocoaPods': 'NuGet'
  },
  'win-to-mac': {
    'HttpClient': 'URLSession',
    'ImageSharp': 'Kingfisher',
    'Rx.NET': 'RxSwift',
    'Realm .NET': 'RealmSwift',
    'Firebase .NET': 'Firebase',
    'RestSharp': 'URLSession',
    'NuGet': 'SwiftPackageManager'
  }
}


API_MAP = {
  'mac-to-win': {
    'UIView': 'FrameworkElement',
    'NSView': 'FrameworkElement',
    'UIButton': 'Button',
    'UILabel': 'TextBlock',
    'UITextField': 'TextBox',
    'UITableView': 'ListView',
    'UIImageView': 'Image',
    'UIScrollView': 'ScrollViewer',
    'UINavigationController': 'NavigationView',
    'UIAlertController': 'ContentDialog',
    'UserDefaults': 'ApplicationData.Current.LocalSettings',
    'Keychain': 'PasswordVault',
    'CoreData': 'Entity Framework',
    'FileManager': 'System.IO.File / Directory',
    'Bundle.main': 'App.Current.Resources',
    'URLSession': 'HttpClient',
    'URLRequest': 'HttpRequestMessage',
    'DispatchQueue': 'Task / Dispatcher'
  },
  'win-to-mac': {
    'FrameworkElement': 'NSView',
    'Button': 'UIButton',
    'TextBlock': 'UILabel',
    'TextBox': 'UITextField',
    'ListView': 'UITableView',
    'Image': 'UIImageView',
    'ScrollViewer': 'UIScrollView',
    'NavigationView': 'UINavigationController',
    'ContentDialog': 'UIAlertController',
    'ApplicationData.Current.LocalSettings': 'UserDefaults',
    'PasswordVault': 'Keychain',
    'Entity Framework': 'Core Data',
    'System.IO.File': 'FileManager',
    'HttpClient': 'URLSession',
    'HttpRequestMessage': 'URLRequest',
    'Task': 'DispatchQueue',
    'Dispatcher': 'DispatchQueue.main'
  }
}


LANGUAGE_HINTS = {
  'mac-to-win': {
    'Swift': 'C#',
    'Objective-C': 'C#',
    'Objective-C++': 'C# with interop',
    'C++': 'C++ (interop)',
    'C#': 'C#',
    'VB.NET': 'C#',
    'F#': 'C#'
  },
  'win-to-mac': {
    'C#': 'Swift',
    'VB.NET': 'Swift',
    'F#': 'Swift',
    'C++': 'C++',
    'Swift': 'Swift',
    'Objective-C': 'Objective-C'
  }
}


@dataclass
class DependencyMapping:
  catalog: Dict[str, Dict[str, str]]

  def directional_map(self, direction: str) -> Dict[str, str]:
    return self.catalog.get(direction, {})


@dataclass
class ApiMappingCatalog:
  catalog: Dict[str, Dict[str, str]]

  def directional_map(self, direction: str) -> Dict[str, str]:
    return self.catalog.get(direction, {})
