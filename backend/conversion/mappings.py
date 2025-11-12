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
    'UITextView': 'RichTextBox',
    'UISwitch': 'ToggleSwitch',
    'UISlider': 'Slider',
    'UIPickerView': 'ComboBox',
    'UITableView': 'ListView',
    'UICollectionView': 'ListView',
    'UIImageView': 'Image',
    'UIScrollView': 'ScrollViewer',
    'UINavigationController': 'NavigationView',
    'UITabBarController': 'TabView',
    'UIAlertController': 'ContentDialog',
    'UIActivityIndicatorView': 'ProgressRing',
    'UIProgressView': 'ProgressBar',
    'UIStackView': 'StackPanel',
    'UserDefaults': 'ApplicationData.Current.LocalSettings',
    'Keychain': 'PasswordVault',
    'CoreData': 'Entity Framework',
    'FileManager': 'System.IO.File / Directory',
    'Bundle.main': 'App.Current.Resources',
    'NotificationCenter': 'Windows.UI.Notifications',
    'URLSession': 'HttpClient',
    'URLRequest': 'HttpRequestMessage',
    'DispatchQueue': 'Task / Dispatcher',
    # SwiftUI
    'Text': 'TextBlock',
    'Image': 'Image',
    'Button': 'Button',
    'Toggle': 'ToggleSwitch',
    'Slider': 'Slider',
    'Picker': 'ComboBox',
    'List': 'ListView',
    'NavigationStack': 'NavigationView',
    'TabView': 'TabView',
    'Alert': 'ContentDialog',
    'Sheet': 'ContentDialog',
    'Menu': 'MenuBar',
    'ContextMenu': 'MenuFlyout',
    'ProgressView': 'ProgressBar'
  },
  'win-to-mac': {
    'FrameworkElement': 'NSView',
    'Button': 'UIButton',
    'TextBlock': 'UILabel',
    'TextBox': 'UITextField',
    'RichTextBox': 'UITextView',
    'ToggleSwitch': 'UISwitch',
    'Slider': 'UISlider',
    'ComboBox': 'UIPickerView',
    'ListView': 'UITableView',
    'Image': 'UIImageView',
    'ScrollViewer': 'UIScrollView',
    'NavigationView': 'UINavigationController',
    'TabView': 'UITabBarController',
    'ContentDialog': 'UIAlertController',
    'ProgressRing': 'UIActivityIndicatorView',
    'ProgressBar': 'UIProgressView',
    'StackPanel': 'UIStackView',
    'ApplicationData.Current.LocalSettings': 'UserDefaults',
    'PasswordVault': 'Keychain',
    'Entity Framework': 'Core Data',
    'System.IO.File': 'FileManager',
    'App.Current.Resources': 'Bundle.main',
    'Windows.UI.Notifications': 'NotificationCenter',
    'HttpClient': 'URLSession',
    'HttpRequestMessage': 'URLRequest',
    'Task': 'DispatchQueue',
    'Dispatcher': 'DispatchQueue.main',
    # SwiftUI targets
    'MenuBar': 'Menu',
    'MenuFlyout': 'ContextMenu'
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

SHORTCUT_MAP = {
  'mac-to-win': {
    'Command': 'Ctrl',
    'Option': 'Alt',
    'Shift': 'Shift',
    'Control': 'Ctrl',
    'Escape': 'Esc'
  },
  'win-to-mac': {
    'Ctrl': 'Command',
    'Alt': 'Option',
    'Shift': 'Shift',
    'Esc': 'Escape'
  }
}

MENU_ROLE_MAP = {
  'mac-to-win': {
    'About': 'Help/About',
    'Preferences': 'File/Settings',
    'Quit': 'File/Exit',
    'Hide': 'Window/Minimize'
  },
  'win-to-mac': {
    'Help/About': 'About',
    'File/Settings': 'Preferences',
    'File/Exit': 'Quit',
    'Window/Minimize': 'Hide'
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
