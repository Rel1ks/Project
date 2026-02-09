## 1. Чтение реестра Windows 

```python
import winreg
import json

def get_installed_programs_from_registry():
    programs = []
    
    # Ключи реестра с установленными программами
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    
    for hkey, path in registry_paths:
        try:
            with winreg.OpenKey(hkey, path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            program = {}
                            
                            # Основные поля
                            fields = {
                                'name': 'DisplayName',
                                'version': 'DisplayVersion',
                                'publisher': 'Publisher',
                                'install_date': 'InstallDate',
                                'install_location': 'InstallLocation',
                                'uninstall_string': 'UninstallString',
                                'size': 'EstimatedSize'
                            }
                            
                            for field, value_name in fields.items():
                                try:
                                    value, _ = winreg.QueryValueEx(subkey, value_name)
                                    program[field] = value
                                except WindowsError:
                                    program[field] = None
                            
                            if program.get('name'):
                                programs.append(program)
                                
                    except WindowsError:
                        continue
        except WindowsError:
            continue
    
    return programs

# Использование
programs = get_installed_programs_from_registry()
print(f"Найдено программ: {len(programs)}")

# Сохранение в JSON
with open('installed_programs.json', 'w', encoding='utf-8') as f:
    json.dump(programs, f, ensure_ascii=False, indent=2)
```

## 2. Расширенный анализ с WMI

```python
import subprocess
import json

def get_programs_wmi():
    """Использует WMI для получения программ"""
    cmd = 'wmic product get Name,Version,Vendor,InstallDate,InstallLocation /format:json'
    
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    
    if result.returncode == 0:
        try:
            # WMIC возвращает JSON в старом формате
            data = json.loads(result.stdout)
            return data
        except:
            # Fallback на текстовый парсинг
            return parse_wmic_text(result.stdout)
    
    return []

def parse_wmic_text(output):
    """Парсинг текстового вывода WMIC"""
    lines = output.strip().split('\n')
    programs = []
    
    # Пропускаем заголовки
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            programs.append({
                'name': parts[0],
                'version': parts[1] if len(parts) > 1 else 'unknown'
            })
    
    return programs
```

## 3. Анализ ярлыков в меню Пуск

```python
import os
from pathlib import Path
import win32com.client  # pip install pywin32

def get_start_menu_programs():
    """Анализ ярлыков в меню Пуск"""
    programs = []
    
    # Пути к меню Пуск
    start_menu_paths = [
        Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
        Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
    ]
    
    shell = win32com.client.Dispatch("WScript.Shell")
    
    for start_path in start_menu_paths:
        if not start_path.exists():
            continue
            
        for shortcut in start_path.rglob('*.lnk'):
            try:
                link = shell.CreateShortCut(str(shortcut))
                target = link.TargetPath
                
                programs.append({
                    'name': shortcut.stem,
                    'shortcut_path': str(shortcut),
                    'target_path': target,
                    'icon_location': link.IconLocation,
                    'working_directory': link.WorkingDirectory
                })
            except Exception as e:
                continue
    
    return programs
```

## 4. Поиск portable-программ (эвристика)

```python
import os
from pathlib import Path

def find_portable_programs():
    """Поиск portable-программ по характерным признакам"""
    portable_paths = [
        Path('C:/Program Files'),
        Path('C:/Program Files (x86)'),
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs',
        Path('C:/tools'),
        Path('C:/portable')
    ]
    
    found_programs = []
    
    for base_path in portable_paths:
        if not base_path.exists():
            continue
            
        for item in base_path.iterdir():
            if item.is_dir():
                # Проверяем наличие исполняемых файлов
                exe_files = list(item.glob('*.exe'))
                if exe_files:
                    found_programs.append({
                        'name': item.name,
                        'path': str(item),
                        'executables': [str(e) for e in exe_files[:5]],  # первые 5 exe
                        'is_portable': True
                    })
    
    return found_programs
```

## 5. Полная система сканирования

```python
import winreg
import json
import os
from pathlib import Path
from datetime import datetime

class WindowsSoftwareScanner:
    def __init__(self):
        self.programs = []
        self.scan_methods = []
    
    def scan_all(self):
        """Запуск всех методов сканирования"""
        print("🔍 Начинаю сканирование системы...")
        
        # Метод 1: Реестр
        print("  📋 Чтение реестра...")
        registry_progs = self._scan_registry()
        self._add_programs(registry_progs, 'registry')
        
        # Метод 2: Ярлыки
        print("  🎯 Анализ ярлыков...")
        shortcut_progs = self._scan_shortcuts()
        self._add_programs(shortcut_progs, 'shortcut')
        
        # Метод 3: Portable
        print("  💼 Поиск portable программ...")
        portable_progs = self._scan_portable()
        self._add_programs(portable_progs, 'portable')
        
        # Метод 4: Windows Apps (UWP)
        print("  🏪 Поиск UWP приложений...")
        uwp_progs = self._scan_uwp()
        self._add_programs(uwp_progs, 'uwp')
        
        return self.programs
    
    def _scan_registry(self):
        """Сканирование реестра"""
        programs = []
        paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        
        for hkey, path in paths:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                prog = self._read_registry_values(subkey)
                                if prog.get('name'):
                                    programs.append(prog)
                        except:
                            continue
            except:
                continue
        
        return programs
    
    def _read_registry_values(self, key):
        """Чтение значений из ключа реестра"""
        prog = {}
        fields = {
            'name': 'DisplayName',
            'version': 'DisplayVersion',
            'publisher': 'Publisher',
            'install_date': 'InstallDate',
            'install_location': 'InstallLocation',
            'uninstall_string': 'UninstallString',
            'size_mb': 'EstimatedSize',
            'url': 'URLInfoAbout',
            'comments': 'Comments'
        }
        
        for field, value_name in fields.items():
            try:
                value, _ = winreg.QueryValueEx(key, value_name)
                if field == 'size_mb' and value:
                    value = round(value / 1024, 2)  # Конвертация в МБ
                prog[field] = value
            except:
                prog[field] = None
        
        return prog
    
    def _scan_shortcuts(self):
        """Сканирование ярлыков"""
        programs = []
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            
            paths = [
                Path(os.environ.get('PROGRAMDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
                Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
            ]
            
            for start_path in paths:
                if start_path.exists():
                    for shortcut in start_path.rglob('*.lnk'):
                        try:
                            link = shell.CreateShortCut(str(shortcut))
                            if link.TargetPath and os.path.exists(link.TargetPath):
                                programs.append({
                                    'name': shortcut.stem,
                                    'target_path': link.TargetPath,
                                    'shortcut_location': str(shortcut.parent)
                                })
                        except:
                            continue
        except ImportError:
            print("    ⚠️ Для анализа ярлыков установите: pip install pywin32")
        
        return programs
    
    def _scan_portable(self):
        """Поиск portable программ"""
        programs = []
        check_paths = [
            Path('C:/Program Files'),
            Path('C:/Program Files (x86)'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs'
        ]
        
        for base in check_paths:
            if base.exists():
                for folder in base.iterdir():
                    if folder.is_dir():
                        exe_files = list(folder.glob('*.exe'))
                        if exe_files:
                            programs.append({
                                'name': folder.name,
                                'path': str(folder),
                                'main_executable': str(exe_files[0]) if exe_files else None,
                                'exe_count': len(exe_files)
                            })
        
        return programs
    
    def _scan_uwp(self):
        """Поиск UWP приложений (Windows Store)"""
        programs = []
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-Command', 'Get-AppxPackage | Select-Object Name, PackageFullName, InstallLocation | ConvertTo-Json'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                for app in data:
                    programs.append({
                        'name': app.get('Name'),
                        'package_name': app.get('PackageFullName'),
                        'install_location': app.get('InstallLocation'),
                        'is_uwp': True
                    })
        except Exception as e:
            print(f"    ⚠️ Ошибка сканирования UWP: {e}")
        
        return programs
    
    def _add_programs(self, new_programs, source):
        """Добавление программ с проверкой дубликатов"""
        for prog in new_programs:
            prog['source'] = source
            prog['scan_date'] = datetime.now().isoformat()
            self.programs.append(prog)
    
    def export_json(self, filename='software_inventory.json'):
        """Экспорт в JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.programs, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Сохранено в: {filename}")
    
    def print_summary(self):
        """Вывод сводки"""
        print(f"\n{'='*50}")
        print(f"📊 НАЙДЕНО ПРОГРАММ: {len(self.programs)}")
        print(f"{'='*50}")
        
        sources = {}
        for p in self.programs:
            src = p.get('source', 'unknown')
            sources[src] = sources.get(src, 0) + 1
        
        for src, count in sources.items():
            print(f"  • {src}: {count}")
        
        # Топ-10 по размеру (если есть данные)
        sized = [p for p in self.programs if p.get('size_mb')]
        if sized:
            print(f"\n📦 Топ-10 по размеру:")
            for prog in sorted(sized, key=lambda x: x.get('size_mb', 0), reverse=True)[:10]:
                print(f"  • {prog['name']}: {prog['size_mb']} МБ")

# Запуск
if __name__ == "__main__":
    scanner = WindowsSoftwareScanner()
    scanner.scan_all()
    scanner.print_summary()
    scanner.export_json()
```