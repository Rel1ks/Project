## 1. Использование модуля `webbrowser` 

```python
import webbrowser

# Открыть URL в браузере по умолчанию
webbrowser.open('https://www.google.com')

# Открыть в новом окне
webbrowser.open_new('https://www.google.com')

# Открыть в новой вкладке (если браузер уже открыт)
webbrowser.open_new_tab('https://www.google.com')
```

## 2. Использование модуля `os` или `subprocess`

```python
import os
import subprocess
import platform

url = 'https://www.google.com'

# Кроссплатформенный способ
def open_url(url):
    system = platform.system()
    
    if system == 'Windows':
        os.startfile(url)  # Windows
    elif system == 'Darwin':
        subprocess.run(['open', url])  # macOS
    else:
        subprocess.run(['xdg-open', url])  # Linux

open_url(url)
```

## 3. Использование `subprocess` с конкретным браузером

```python
import subprocess

url = 'https://www.google.com'

# Открыть в конкретном браузере
# Chrome
subprocess.run(['start', 'chrome', url], shell=True)  # Windows
subprocess.run(['google-chrome', url])  # Linux
subprocess.run(['open', '-a', 'Google Chrome', url])  # macOS

# Firefox
subprocess.run(['start', 'firefox', url], shell=True)  # Windows
subprocess.run(['firefox', url])  # Linux
```

## 4. Полный пример CLI-утилиты

```python
#!/usr/bin/env python3
import argparse
import webbrowser
import sys

def main():
    parser = argparse.ArgumentParser(description='Открыть URL в браузере')
    parser.add_argument('url', help='URL для открытия')
    parser.add_argument('--new-window', '-w', action='store_true', 
                       help='Открыть в новом окне')
    parser.add_argument('--browser', '-b', help='Браузер (chrome, firefox, safari)')
    
    args = parser.parse_args()
    
    # Добавляем https:// если нет протокола
    url = args.url if args.url.startswith('http') else f'https://{args.url}'
    
    try:
        if args.browser:
            # Открыть в конкретном браузере
            controller = webbrowser.get(f'{args.browser} %s')
            controller.open(url, new=1 if args.new_window else 0)
        else:
            # Браузер по умолчанию
            if args.new_window:
                webbrowser.open_new(url)
            else:
                webbrowser.open(url)
        print(f"✓ Открыто: {url}")
    except Exception as e:
        print(f"✗ Ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```