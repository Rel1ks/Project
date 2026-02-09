## 1. Через переменную окружения PATH (самый простой)

```python
import subprocess
import os

def open_from_path(app_name, *args):
    """Открывает программу, если она в PATH"""
    try:
        # Проверяем, есть ли в PATH
        subprocess.run([app_name, *args], check=True)
    except FileNotFoundError:
        print(f"{app_name} не найден в PATH")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка запуска: {e}")

# Использование
open_from_path("firefox")           # Просто открыть
open_from_path("firefox", "https://google.com")  # С аргументами
open_from_path("code")              # VS Code
open_from_path("chrome")            # Google Chrome
```

## 2. Поиск в стандартных папках Windows

```python
import os
from pathlib import Path
import subprocess

def find_and_open(app_name, *args):
    """Ищет программу в стандартных местах и запускает"""
    
    # Расширения для Windows
    if os.name == 'nt':
        extensions = ['.exe', '.cmd', '.bat', '']
    else:
        extensions = ['']
    
    # Стандартные папки для программ
    search_paths = [
        Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')),
        Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')),
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs',
        Path(os.environ.get('USERPROFILE', '')) / 'AppData' / 'Local' / 'Programs',
        Path('C:/Windows/System32'),
    ]
    
    # Ищем файл
    for base_path in search_paths:
        if not base_path.exists():
            continue
            
        for ext in extensions:
            full_name = app_name + ext
            exe_path = base_path / full_name
            
            if exe_path.exists():
                print(f"Найдено: {exe_path}")
                subprocess.run([str(exe_path), *args])
                return True
            
            # Рекурсивный поиск в подпапках (только 1 уровень для скорости)
            for subfolder in base_path.iterdir():
                if subfolder.is_dir():
                    nested_path = subfolder / full_name
                    if nested_path.exists():
                        print(f"Найдено: {nested_path}")
                        subprocess.run([str(nested_path), *args])
                        return True
    
    print(f"{app_name} не найден")
    return False

# Использование
find_and_open("firefox", "https://github.com")
find_and_open("code")  # VS Code
```

## 3. Через ярлыки (Lnk файлы)

```python
import os
from pathlib import Path
import subprocess

def open_from_shortcut(app_name):
    """Ищет ярлык в меню Пуск и запускает"""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        
        start_menu_paths = [
            Path(os.environ.get('PROGRAMDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
            Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
        ]
        
        for start_path in start_menu_paths:
            if not start_path.exists():
                continue
                
            # Ищем ярлык
            for lnk_file in start_path.rglob('*.lnk'):
                if app_name.lower() in lnk_file.stem.lower():
                    shortcut = shell.CreateShortCut(str(lnk_file))
                    target = shortcut.TargetPath
                    
                    if os.path.exists(target):
                        print(f"Запуск через ярлык: {lnk_file.name}")
                        subprocess.Popen(target)
                        return True
        
        return False
    except ImportError:
        print("Установите: pip install pywin32")
        return False

# Использование
open_from_shortcut("firefox")
open_from_shortcut("visual studio code")
```

## 4. Через ассоциации файлов (ShellExecute)

```python
import os
import subprocess

def open_with_shell(app_name, *args):
    """Использует cmd / start для поиска"""
    if os.name == 'nt':
        # Windows: start ищет в PATH и App Paths
        cmd = f'start "" "{app_name}"'
        if args:
            cmd += ' ' + ' '.join(f'"{a}"' for a in args)
        subprocess.run(cmd, shell=True)
    else:
        # Linux/Mac: which + subprocess
        subprocess.run([app_name, *args])

# Использование
open_with_shell("firefox", "https://google.com")
open_with_shell("notepad")
```

## 5. Через реестр (App Paths)

```python
import winreg
import subprocess
import os

def open_from_registry(app_name):
    """Ищет путь в реестре Windows (App Paths)"""
    try:
        # Ключи реестра где Windows хранит пути к приложениям
        keys_to_check = [
            fr"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app_name}.exe",
            fr"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{app_name}.exe"
        ]
        
        for key_path in keys_to_check:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    path, _ = winreg.QueryValueEx(key, None)
                    if os.path.exists(path):
                        print(f"Найдено в реестре: {path}")
                        subprocess.Popen(path)
                        return True
            except WindowsError:
                continue
        
        return False
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

# Использование
open_from_registry("firefox")
open_from_registry("chrome")
```

## 6. Универсальный метод (комбинированный)

```python
import os
import subprocess
import winreg
from pathlib import Path

class AppLauncher:
    def __init__(self):
        self.cache = {}  # Кэш найденных путей
    
    def open(self, app_name, *args, **kwargs):
        """Универсальный запуск приложения"""
        
        # 1. Проверяем кэш
        if app_name in self.cache:
            return self._run(self.cache[app_name], *args)
        
        # 2. Пробуем PATH (самый быстрый)
        if self._try_path(app_name, *args):
            return True
        
        # 3. Ищем в реестре App Paths
        path = self._find_in_registry(app_name)
        if path:
            self.cache[app_name] = path
            return self._run(path, *args)
        
        # 4. Ищем в стандартных папках
        path = self._find_in_folders(app_name)
        if path:
            self.cache[app_name] = path
            return self._run(path, *args)
        
        # 5. Ищем через ярлыки
        path = self._find_in_shortcuts(app_name)
        if path:
            self.cache[app_name] = path
            return self._run(path, *args)
        
        print(f"❌ {app_name} не найден")
        return False
    
    def _try_path(self, app_name, *args):
        """Пробуем запустить из PATH"""
        try:
            subprocess.run([app_name, *args], check=True, 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.cache[app_name] = app_name  # Сохраняем имя команды
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False
    
    def _find_in_registry(self, app_name):
        """Ищем в реестре Windows"""
        exe_name = app_name if app_name.endswith('.exe') else f"{app_name}.exe"
        
        keys = [
            fr"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
            fr"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
        ]
        
        for key_path in keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    path, _ = winreg.QueryValueEx(key, None)
                    if os.path.exists(path):
                        return path
            except WindowsError:
                continue
        return None
    
    def _find_in_folders(self, app_name):
        """Ищем в Program Files"""
        exe_name = app_name if app_name.endswith('.exe') else f"{app_name}.exe"
        
        search_paths = [
            Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')),
            Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs',
        ]
        
        for base in search_paths:
            if not base.exists():
                continue
            
            # Прямой поиск
            direct = base / exe_name
            if direct.exists():
                return str(direct)
            
            # Поиск в подпапках (ограниченная глубина)
            for folder in base.iterdir():
                if folder.is_dir():
                    nested = folder / exe_name
                    if nested.exists():
                        return str(nested)
        return None
    
    def _find_in_shortcuts(self, app_name):
        """Ищем через ярлыки"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            
            paths = [
                Path(os.environ.get('PROGRAMDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu',
                Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu'
            ]
            
            for start_path in paths:
                if not start_path.exists():
                    continue
                for lnk in start_path.rglob('*.lnk'):
                    if app_name.lower() in lnk.stem.lower():
                        target = shell.CreateShortCut(str(lnk)).TargetPath
                        if os.path.exists(target):
                            return target
        except ImportError:
            pass
        return None
    
    def _run(self, path, *args):
        """Запускаем приложение"""
        try:
            print(f"🚀 Запуск: {path}")
            subprocess.Popen([path, *args])
            return True
        except Exception as e:
            print(f"Ошибка запуска: {e}")
            return False

# Использование
launcher = AppLauncher()

launcher.open("firefox", "https://google.com")
launcher.open("code")           # VS Code
launcher.open("chrome")
launcher.open("notepad")
launcher.open("steam")
```