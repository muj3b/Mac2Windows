from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from backend.conversion.models import ConversionSettings


class ProjectGenerator:
    def create_windows_project(self, target_root: Path, settings: ConversionSettings) -> Path:
        solution_path = target_root / 'ConvertedApp.sln'
        project_path = target_root / 'ConvertedApp' / 'ConvertedApp.csproj'
        project_path.parent.mkdir(parents=True, exist_ok=True)

        project_guid = '{1F5B2D8E-0A4A-4D02-A2CC-0DF8A93A6E4F}'
        lines = [
            f'Project("{{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}}") = "ConvertedApp", "ConvertedApp\\ConvertedApp.csproj", "{project_guid}"',
            'EndProject',
            'Global',
            '    GlobalSection(SolutionConfigurationPlatforms) = preSolution',
            '        Debug|Any CPU = Debug|Any CPU',
            '        Release|Any CPU = Release|Any CPU',
            '    EndGlobalSection',
            'EndGlobal'
        ]
        solution_path.write_text('\n'.join(lines), encoding='utf-8')

        csproj_lines = [
            '<Project Sdk="Microsoft.NET.Sdk">',
            '  <PropertyGroup>',
            '    <OutputType>Exe</OutputType>',
            '    <TargetFramework>net8.0</TargetFramework>',
            f'    <RootNamespace>ConvertedApp</RootNamespace>',
            f'    <Nullable>enable</Nullable>',
            '  </PropertyGroup>',
            '  <ItemGroup>'
        ]
        for source_file in self._gather_files(target_root, {'.cs', '.xaml'}):
            rel = source_file.relative_to(project_path.parent)
            if rel.suffix == '.xaml':
                csproj_lines.append(f'    <Page Include="{rel.as_posix()}" />')
            else:
                csproj_lines.append(f'    <Compile Include="{rel.as_posix()}" />')
        csproj_lines.extend([
            '  </ItemGroup>',
            '  <ItemGroup>',
            '    <PackageReference Include="CommunityToolkit.Mvvm" Version="8.2.2" />',
            '  </ItemGroup>',
            '</Project>'
        ])
        project_path.write_text('\n'.join(csproj_lines), encoding='utf-8')
        return solution_path

    def create_mac_project(self, target_root: Path, settings: ConversionSettings) -> Path:
        xcodeproj = target_root / 'ConvertedApp.xcodeproj'
        project_file = xcodeproj / 'project.pbxproj'
        xcodeproj.mkdir(parents=True, exist_ok=True)
        sources = self._gather_files(target_root, {'.swift'})
        file_refs = [f'/* {path.name} */ = {{ isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {path.name}; }};' for path in sources]
        children = ', '.join(f'/* {path.name} */' for path in sources)
        project_content = f"""
// !$*UTF8*$!
{{
    archiveVersion = 1;
    classes = {{}};
    objectVersion = 56;
    objects = {{
        /* Begin PBXFileReference section */
        {' '.join(file_refs)}
        /* End PBXFileReference section */
    }};
    rootObject = /* Project object */;
}}
"""
        project_file.write_text(project_content.strip(), encoding='utf-8')
        for swift_file in sources:
            destination = xcodeproj.parent / swift_file.name
            if not destination.exists():
                destination.write_text(swift_file.read_text(encoding='utf-8'), encoding='utf-8')
        return xcodeproj

    def _gather_files(self, root: Path, extensions: Iterable[str]) -> List[Path]:
        files: List[Path] = []
        for ext in extensions:
            files.extend(root.rglob(f'*{ext}'))
        return files
