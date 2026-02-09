```python
import subprocess
import os

# Путь к папке с настройками
SETTINGS_DIR = "settings"

# Путь к файлу, где будут храниться пути к приложениям
APPS_FILE = os.path.join(SETTINGS_DIR, "apps.txt")

# Список приложений
applications = []

# Функция проверки и создания папки с настройками
def check_settings_folder():
    if not os.path.exists(SETTINGS_DIR):
        choice = input("Хотите ли вы, чтобы создалась папка с сохранением ваших настроек? (Y/n): ").lower()

        if choice == 'y' or choice == '':
            os.makedirs(SETTINGS_DIR, exist_ok=True)
            print(f"Папка '{SETTINGS_DIR}' создана.\n")
        else:
            print("Папка с настройками не будет создана. Настройки не будут сохранены.\n")
    else:
        print(f"Папка '{SETTINGS_DIR}' уже существует. Загружаем данные...\n")
        load_applications_from_file()

# Функция загрузки приложений из файла
def load_applications_from_file():
    global applications
    if os.path.exists(APPS_FILE):
        with open(APPS_FILE, 'r', encoding='utf-8') as f:
            apps = f.read().splitlines()
        applications = apps
        print(f"Загружено {len(applications)} приложений из файла.\n")
    else:
        print("Файл с приложениями не найден. Список пуст.\n")

# Функция сохранения приложений в файл
def save_applications_to_file():
    with open(APPS_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(applications))

# Функция добавления приложения
def add_application():
    path = input("Введите полный путь к .exe или .lnk файлу: ")
    path = path.strip().strip('"')

    if os.path.exists(path):
        applications.append(path)
        if os.path.exists(SETTINGS_DIR):
            save_applications_to_file()
        print(f"Приложение {path} успешно добавлено!\n")
    else:
        print("Файл не найден. Убедитесь, что путь правильный.\n")

# Функция запуска приложения
def run_application():
    if len(applications) == 0:
        print("Список приложений пуст. Сначала добавьте приложение.\n")
        return

    print("Доступные приложения:")
    for index in range(len(applications)):
        print(f"{index + 1}. {applications[index]}")

    try:
        choice = int(input("Выберите номер приложения для запуска: ")) - 1
        if 0 <= choice < len(applications):
            app_path = applications[choice]

            # Проверяем, это .lnk или .exe
            if app_path.lower().endswith('.lnk'):
                subprocess.run(['explorer', app_path])
            else:
                subprocess.run([app_path])

            print(f"Запущено: {app_path}\n")
        else:
            print("Неверный номер. Попробуйте снова.\n")
    except ValueError:
        print("Введите число.\n")

# Функция удаления приложения
def delete_application():
    if len(applications) == 0:
        print("Список приложений пуст. Нечего удалять.\n")
        return

    print("Доступные приложения:")
    for index in range(len(applications)):
        print(f"{index + 1}. {applications[index]}")

    try:
        choice = int(input("Выберите номер приложения для удаления: ")) - 1
        if 0 <= choice < len(applications):
            removed_app = applications.pop(choice)
            if os.path.exists(SETTINGS_DIR):
                save_applications_to_file()
            print(f"Приложение '{removed_app}' успешно удалено.\n")
        else:
            print("Неверный номер. Попробуйте снова.\n")
    except ValueError:
        print("Введите число.\n")

# Главный цикл
if __name__ == "__main__":
    check_settings_folder()

    while True:
        print("Меню:")
        print("1. Добавить приложение")
        print("2. Запустить приложение")
        print("3. Удалить приложение")
        print("4. Выйти")

        user_choice = input("Выберите действие (1/2/3/4): ")

        if user_choice == "1":
            add_application()
        elif user_choice == "2":
            run_application()
        elif user_choice == "3":
            delete_application()
        elif user_choice == "4":
            print("Программа завершена.")
            break
        else:
            print("Неверный выбор. Попробуйте снова.\n")

```

Код работает без проблем, в дальнейшем функционал будет разрастаться все больше пока это только тестовая версия
