#!/usr/bin/env python3
"""
Скрипт для поэтапного запуска тестов в 2 этапа:
1. Юнит тесты
2. Тесты реальных сценариев (E2E)

Результаты сохраняются в tests/results/

Использование:
    python tests/utils/run_staged.py
    или из корня проекта:
    python -m tests.utils.run_staged
"""
import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


# Глобальная переменная для MD файла
_md_file_handle = None

def set_md_file(md_file):
    """Установка файла для записи"""
    global _md_file_handle
    _md_file_handle = md_file

def strip_ansi_codes(text):
    """Удаление ANSI escape-кодов из текста"""
    import re
    if not text:
        return text
    # Удаляем все ANSI escape-коды: \033[...m, \033[...K, \x1b[...m и т.д.
    # Поддерживаем разные форматы: \033, \x1b, \u001b
    ansi_escape = re.compile(r'(?:\033|\x1b|\u001b)\[[0-9;]*[a-zA-Z]')
    return ansi_escape.sub('', text)

def write_to_md(text, strip_colors=True):
    """Запись текста в MD файл"""
    global _md_file_handle
    if _md_file_handle:
        # Убираем ANSI коды цветов для MD файла
        if strip_colors:
            text_no_colors = strip_ansi_codes(text)
            _md_file_handle.write(text_no_colors)
        else:
            _md_file_handle.write(text)
        _md_file_handle.flush()

def print_header(text):
    """Вывод заголовка этапа"""
    header_line = f"\n{'='*80}\n"
    title_line = f"{text.center(80)}\n"
    output = header_line + title_line + header_line + "\n"
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}{text.center(80)}{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")
    write_to_md(output)


def print_success(text):
    """Вывод успешного сообщения"""
    output = f"✅ {text}\n"
    print(f"{GREEN}✅ {text}{RESET}")
    write_to_md(output)


def print_error(text):
    """Вывод сообщения об ошибке"""
    output = f"❌ {text}\n"
    print(f"{RED}❌ {text}{RESET}")
    write_to_md(output)


def print_info(text):
    """Вывод информационного сообщения"""
    output = f"ℹ️  {text}\n"
    print(f"{BLUE}ℹ️  {text}{RESET}")
    write_to_md(output)


def run_stage(stage_name, marker, description, additional_args=None, md_file=None):
    # md_file здесь означает путь до текстового лога запуска
    """Запуск этапа тестирования с сохранением результатов"""
    global _md_file_handle
    
    project_root = Path(__file__).parent.parent.parent
    tests_dir = project_root / "tests"
    
    if md_file is None:
        md_file = tests_dir / "test_results.md"
    
    # Записываем заголовок этапа в LOG и выводим в консоль
    header_text = f"ЭТАП {stage_name}: {description}"
    print_header(header_text)
    
    cmd = ["python", "-m", "pytest", "-v", "-m", marker]
    
    if additional_args:
        cmd.extend(additional_args)
    
    info_text = f"Запуск команды: {' '.join(cmd)}"
    print_info(info_text)
    
    print()
    
    start_time = datetime.now()
    
    # Запускаем тесты с записью в реальном времени
    import subprocess
    # Устанавливаем переменную окружения для отключения буферизации Python
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    process = subprocess.Popen(
        cmd,
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        bufsize=1,
        env=env
    )
    
    # Читаем вывод построчно и дублируем в консоль и файл в реальном времени
    output_lines = []
    
    def should_skip_line(line):
        """Проверяет, нужно ли пропустить строку при записи в файл"""
        line_lower = line.lower()
        # Пропускаем DEBUG и INFO сообщения от сторонних библиотек
        if any(skip in line_lower for skip in [
            ' - asyncio - DEBUG -',
            ' - httpx - INFO -',
            ' - httpx - DEBUG -',
            ' - backend.app.main - WARNING - Failed to update active_users metric',
            ' - backend.app.workers.prediction_tasks - ERROR -',  # Ожидаемые ошибки в тестах
            'could not translate host name "postgres"',  # Ожидаемая ошибка подключения к PostgreSQL в тестах
            'Traceback (most recent call last):',  # Traceback от ожидаемых исключений в тестах
            'ExceptionGroup:',  # ExceptionGroup от ожидаемых исключений
            'Exception: Test error',  # Ожидаемое исключение в тесте
            'ValueError:',  # Ожидаемые ValueError в тестах
        ]):
            return True
        # Пропускаем строки traceback (начинаются с пробелов и содержат File или |)
        if line_stripped.startswith(' ') and ('File "' in line_stripped or '|' in line_stripped or '^' in line_stripped):
            return True
        return False
    
    for line in iter(process.stdout.readline, ''):
        if not line:
            break
        line_stripped = line.rstrip()
        output_lines.append(line_stripped)
        print(line_stripped)  # Выводим в консоль с цветами
        if _md_file_handle:
            # Пропускаем служебные логи при записи в файл
            if not should_skip_line(line_stripped):
                # Удаляем ANSI коды перед записью в файл
                line_clean = strip_ansi_codes(line)
                _md_file_handle.write(line_clean)  # Записываем в файл без ANSI кодов, построчно
                _md_file_handle.flush()  # Немедленно записываем в файл
    
    process.wait()
    result_code = process.returncode
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Парсим вывод pytest для статистики
    output = '\n'.join(output_lines)
    lines = output.split('\n')
    
    # Ищем строку с итогами (например: "150 passed, 2 skipped in 27.56s")
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    
    for line in lines:
        if "passed" in line.lower() and ("failed" in line.lower() or "error" in line.lower() or "skipped" in line.lower()):
            import re
            # Парсим строку типа "150 passed, 2 skipped in 27.56s"
            passed_match = re.search(r'(\d+)\s+passed', line)
            failed_match = re.search(r'(\d+)\s+failed', line)
            skipped_match = re.search(r'(\d+)\s+skipped', line)
            error_match = re.search(r'(\d+)\s+error', line)
            
            if passed_match:
                passed = int(passed_match.group(1))
            if failed_match:
                failed = int(failed_match.group(1))
            if skipped_match:
                skipped = int(skipped_match.group(1))
            if error_match:
                errors = int(error_match.group(1))
    
    # Записываем итоги этапа в LOG
    if _md_file_handle:
        status_text = "УСПЕШНО" if result_code == 0 else "ПРОВАЛЕН"
        status_icon = "[OK]" if result_code == 0 else "[FAIL]"
        
        _md_file_handle.write("\n" + "-" * 80 + "\n")
        _md_file_handle.write(f"Статус: {status_icon} {status_text}\n")
        _md_file_handle.write(f"Время начала: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        _md_file_handle.write(f"Время завершения: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        _md_file_handle.write(f"Длительность: {duration:.2f} секунд\n")
        _md_file_handle.write(f"Код возврата: {result_code}\n")
        
        if passed > 0 or failed > 0 or skipped > 0:
            _md_file_handle.write("\nСтатистика:\n")
            if passed > 0:
                _md_file_handle.write(f"  Пройдено: {passed}\n")
            if failed > 0:
                _md_file_handle.write(f"  Провалено: {failed}\n")
            if skipped > 0:
                _md_file_handle.write(f"  Пропущено: {skipped}\n")
            if errors > 0:
                _md_file_handle.write(f"  Ошибок: {errors}\n")
        
        _md_file_handle.write("\n" + "=" * 80 + "\n\n")
        _md_file_handle.flush()
    
    # Сохраняем результаты в JSON структуру
    stage_result = {
        "stage": stage_name,
        "description": description,
        "marker": marker,
        "timestamp": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration,
        "success": result_code == 0,
        "return_code": result_code,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors
    }
    
    if result_code == 0:
        print_success(f"Этап {stage_name} завершен успешно")
        return True, stage_result
    else:
        print_error(f"Этап {stage_name} завершился с ошибками")
        return False, stage_result


def run_e2e_scenarios(md_file=None):
    # md_file здесь означает путь до текстового лога запуска
    """Запуск E2E сценариев (отдельный скрипт) с сохранением результатов"""
    global _md_file_handle
    
    project_root = Path(__file__).parent.parent.parent
    tests_dir = project_root / "tests"
    
    if md_file is None:
        md_file = tests_dir / "test_results.md"
    
    # Записываем заголовок этапа в LOG и выводим в консоль
    header_text = "ЭТАП 2: Тесты реальных сценариев (E2E)"
    print_header(header_text)
    
    e2e_script = project_root / "tests" / "e2e" / "test_real_world_scenarios.py"
    
    if not e2e_script.exists():
        print_error(f"Файл {e2e_script} не найден")
        return False, None
    
    info_text = f"Запуск скрипта: {e2e_script}"
    print_info(info_text)
    
    print()
    
    start_time = datetime.now()
    
    # Запускаем E2E тесты с записью в реальном времени
    process = subprocess.Popen(
        ["python", str(e2e_script)],
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        bufsize=1
    )
    
    # Читаем вывод построчно и выводим в консоль, но в файл записываем только краткую информацию
    output_lines = []
    scenario_results = []  # Список результатов сценариев: (номер, название, успех)
    scenario_names = {}  # Словарь номер -> название сценария
    import re
    
    # Записываем заголовок для списка сценариев в файл
    if _md_file_handle:
        _md_file_handle.write("\n")
        _md_file_handle.flush()
    
    for line in iter(process.stdout.readline, ''):
        if not line:
            break
        line_stripped = line.rstrip()
        output_lines.append(line_stripped)
        print(line_stripped)  # Выводим в консоль с цветами
        
        # Парсим строки для извлечения информации о сценариях
        line_clean = strip_ansi_codes(line_stripped)
        
        # Сначала ищем заголовки сценариев и сохраняем их названия
        scenario_header_match = re.search(r'СЦЕНАРИЙ\s+(\d+)[:\s]+(.+)', line_clean)
        if scenario_header_match:
            scenario_num = int(scenario_header_match.group(1))
            scenario_title = scenario_header_match.group(2).strip()
            # Убираем лишние символы вроде тире в начале
            scenario_title = re.sub(r'^[-:\s]+', '', scenario_title)
            if scenario_title:
                scenario_names[scenario_num] = scenario_title
        
        # Ищем строки типа "✅ ✅ scenario_1" или "❌ scenario_1" (может быть один или два ✅)
        scenario_match = re.search(r'(✅+\s+|❌\s+)scenario_(\d+)', line_clean)
        if scenario_match:
            status_icon = scenario_match.group(1).strip()
            scenario_num = int(scenario_match.group(2))
            is_success = "✅" in status_icon
            
            # Используем сохраненное название или ищем в предыдущих строках
            if scenario_num in scenario_names:
                scenario_name = f"Сценарий {scenario_num}: {scenario_names[scenario_num]}"
            else:
                # Fallback: ищем в последних 200 строках
                scenario_name = f"Сценарий {scenario_num}"
                for prev_line in reversed(output_lines[-200:]):
                    prev_clean = strip_ansi_codes(prev_line)
                    name_match = re.search(r'СЦЕНАРИЙ\s+(\d+)[:\s]+(.+)', prev_clean)
                    if name_match and int(name_match.group(1)) == scenario_num:
                        name_part = name_match.group(2).strip()
                        name_part = re.sub(r'^[-:\s]+', '', name_part)
                        if name_part:
                            scenario_name = f"Сценарий {scenario_num}: {name_part}"
                            scenario_names[scenario_num] = name_part
                            break
            
            scenario_results.append((scenario_num, scenario_name, is_success))
            
            # Сразу записываем результат сценария в файл с эмодзи
            if _md_file_handle:
                status_emoji = "✅" if is_success else "❌"
                status_text = "успешно" if is_success else "провален"
                _md_file_handle.write(f"{status_emoji} {scenario_name} - {status_text}\n")
                _md_file_handle.flush()
    
    # Добавляем пустую строку после всех сценариев
    if _md_file_handle:
        _md_file_handle.write("\n")
        _md_file_handle.flush()
    
    process.wait()
    result_code = process.returncode
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Парсим вывод для статистики
    output = '\n'.join(output_lines)
    lines = output.split('\n')
    
    # Используем информацию из scenario_results для статистики
    total_scenarios = len(scenario_results)
    passed_scenarios = sum(1 for _, _, success in scenario_results if success)
    failed_scenarios = total_scenarios - passed_scenarios
    
    # Также пытаемся найти информацию в итоговой строке для проверки
    for line in lines:
        if "сценариев выполнено успешно" in line.lower() or "scenarios" in line.lower():
            import re
            # Пытаемся найти числа
            match = re.search(r'(\d+)[/\s]+(\d+)', line)
            if match:
                passed_from_summary = int(match.group(1))
                total_from_summary = int(match.group(2))
                # Используем данные из итоговой строки, если они есть
                if total_from_summary > 0:
                    total_scenarios = total_from_summary
                    passed_scenarios = passed_from_summary
                    failed_scenarios = total_scenarios - passed_scenarios
    
    # Записываем итоги этапа в LOG
    if _md_file_handle:
        status_text = "УСПЕШНО" if result_code == 0 else "ПРОВАЛЕН"
        status_icon = "[OK]" if result_code == 0 else "[FAIL]"
        
        _md_file_handle.write("\n" + "-" * 80 + "\n")
        _md_file_handle.write(f"Статус: {status_icon} {status_text}\n")
        _md_file_handle.write(f"Время начала: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        _md_file_handle.write(f"Время завершения: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        _md_file_handle.write(f"Длительность: {duration:.2f} секунд\n")
        _md_file_handle.write(f"Код возврата: {result_code}\n")
        
        if total_scenarios > 0:
            _md_file_handle.write("\nСтатистика:\n")
            _md_file_handle.write(f"  Пройдено сценариев: {passed_scenarios}\n")
            if failed_scenarios > 0:
                _md_file_handle.write(f"  Провалено сценариев: {failed_scenarios}\n")
            _md_file_handle.write(f"  Всего сценариев: {total_scenarios}\n")
        
        _md_file_handle.write("\n" + "=" * 80 + "\n\n")
        _md_file_handle.flush()
    
    # Сохраняем результаты в JSON структуру
    stage_result = {
        "stage": "2",
        "description": "E2E сценарии",
        "timestamp": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration,
        "success": result_code == 0,
        "return_code": result_code,
        "total_scenarios": total_scenarios,
        "passed_scenarios": passed_scenarios,
        "failed_scenarios": failed_scenarios
    }
    
    if result_code == 0:
        print_success("Этап 2 завершен успешно")
        return True, stage_result
    else:
        print_error("Этап 2 завершился с ошибками")
        return False, stage_result


def main():
    """Главная функция"""
    # Переходим в корень проекта для корректной работы pytest
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)
    
    # Файлы результатов в tests/ (перезаписываются каждый раз)
    tests_dir = project_root / "tests"
    log_file = tests_dir / "test_results.log"
    
    # Очищаем файлы результатов перед новым прогоном
    if log_file.exists():
        log_file.unlink()
    
    # Удаляем JSON файл, если он существует (больше не создаем)
    summary_file = tests_dir / "test_results.json"
    if summary_file.exists():
        summary_file.unlink()
    
    # Удаляем XML файл, если он существует (больше не создаем)
    xml_file = tests_dir / "test_results.xml"
    if xml_file.exists():
        xml_file.unlink()
    
    start_time = datetime.now()
    
    # Открываем LOG файл для записи
    log_handle = open(log_file, 'w', encoding='utf-8')
    set_md_file(log_handle)
    
    # Записываем заголовок в LOG файл и выводим в консоль
    log_handle.write("=" * 80 + "\n")
    log_handle.write("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ\n")
    log_handle.write("=" * 80 + "\n")
    log_handle.write(f"Время начала: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_handle.write(f"Проект: ML Inference Service\n")
    log_handle.write("=" * 80 + "\n\n")
    log_handle.flush()
    
    header_line = f"{'='*80}"
    title_line = "ПОЭТАПНОЕ ТЕСТИРОВАНИЕ ML INFERENCE SERVICE"
    
    print(f"\n{BOLD}{CYAN}{header_line}{RESET}")
    print(f"{BOLD}{CYAN}{title_line.center(80)}{RESET}")
    print(f"{BOLD}{CYAN}{header_line}{RESET}")
    
    info_text = f"Результаты сохраняются в: {log_file}"
    print_info(info_text)
    print()
    log_handle.write("\n")
    
    results = []
    stage_results = []
    
    # Этап 1: Юнит тесты
    success, stage_result = run_stage(
        "1",
        "stage1_unit",
        "Юнит тесты",
        ["--tb=short"],
        md_file=log_file
    )
    results.append(("Этап 1: Юнит тесты", success))
    stage_results.append(stage_result)
    
    if not success:
        print_error("\n⚠️  Этап 1 провален. Продолжение тестирования...")
        print_info("Вы можете остановить выполнение (Ctrl+C) или продолжить\n")
    
    # Этап 2: E2E сценарии
    success, stage_result = run_e2e_scenarios(md_file=log_file)
    results.append(("Этап 2: E2E сценарии", success))
    stage_results.append(stage_result)
    
    if not success:
        print_error("\n⚠️  Этап 2 провален.")
        print_info("Вы можете остановить выполнение (Ctrl+C) или продолжить\n")
    
    # Итоговая сводка
    print_header("ИТОГОВАЯ СВОДКА")
    
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    
    all_passed = True
    summary_data = {
        "timestamp": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "total_duration_seconds": total_duration,
        "total_stages": len(results),
        "passed_stages": 0,
        "failed_stages": 0,
        "all_passed": False,
        "stages": []
    }
    
    for stage_name, stage_success in results:
        if stage_success:
            print_success(f"{stage_name}: ПРОЙДЕН")
            summary_data["passed_stages"] += 1
        else:
            print_error(f"{stage_name}: ПРОВАЛЕН")
            summary_data["failed_stages"] += 1
            all_passed = False
    
    summary_data["all_passed"] = all_passed
    summary_data["stages"] = stage_results
    
    # Добавляем итоговую сводку в LOG файл
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write("ИТОГОВАЯ СВОДКА\n")
        f.write("=" * 80 + "\n\n")
        
        status_text = "ВСЕ ЭТАПЫ ПРОЙДЕНЫ" if all_passed else "ЕСТЬ ПРОВАЛЕННЫЕ ЭТАПЫ"
        status_icon = "[OK]" if all_passed else "[FAIL]"
        
        f.write(f"Статус: {status_icon} {status_text}\n")
        f.write(f"Время начала: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Время завершения: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Общая длительность: {total_duration:.2f} секунд\n\n")
        
        f.write("Статистика по этапам:\n")
        f.write("-" * 80 + "\n")
        
        for stage_name, stage_success in results:
            status = "[OK]" if stage_success else "[FAIL]"
            f.write(f"{status} {stage_name}\n")
        
        f.write("\n")
        f.write("Детальная статистика:\n")
        f.write("-" * 80 + "\n")
        f.write(f"Всего этапов: {summary_data['total_stages']}\n")
        f.write(f"Пройдено: {summary_data['passed_stages']}\n")
        f.write(f"Провалено: {summary_data['failed_stages']}\n")
        f.write(f"Общее время: {total_duration:.2f} сек\n\n")
        
        # Добавляем детали по каждому этапу
        f.write("Детали этапов:\n")
        f.write("-" * 80 + "\n")
        for stage in stage_results:
            stage_num = stage.get("stage", "?")
            desc = stage.get("description", "")
            success = stage.get("success", False)
            duration = stage.get("duration_seconds", 0)
            
            f.write(f"\nЭтап {stage_num}: {desc}\n")
            f.write(f"  Статус: {'[OK] Успешно' if success else '[FAIL] Провален'}\n")
            f.write(f"  Длительность: {duration:.2f} сек\n")
            
            if "passed" in stage:
                f.write(f"  Пройдено тестов: {stage.get('passed', 0)}\n")
            if "failed" in stage:
                f.write(f"  Провалено тестов: {stage.get('failed', 0)}\n")
            if "skipped" in stage:
                f.write(f"  Пропущено тестов: {stage.get('skipped', 0)}\n")
            if "total_scenarios" in stage:
                f.write(f"  Всего сценариев: {stage.get('total_scenarios', 0)}\n")
                f.write(f"  Пройдено сценариев: {stage.get('passed_scenarios', 0)}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"Отчет сгенерирован автоматически\n")
        f.write("=" * 80 + "\n")
    
    print()
    print_info(f"Результаты сохранены в: {log_file.name}")
    
    if all_passed:
        print_success("🎉 Все этапы тестирования пройдены успешно!")
        return 0
    else:
        print_error("⚠️  Некоторые этапы тестирования провалены")
        return 1


if __name__ == "__main__":
    sys.exit(main())
