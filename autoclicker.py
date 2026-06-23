import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import random
import ctypes
from ctypes import wintypes, byref, c_uint, c_long
import keyboard
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
import json
import os
import win32gui
import win32con
import win32api
import win32process
import psutil


# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

class ActionType(Enum):
    """Типы действий"""
    TEXT = "Текст"
    KEY = "Клавиша"
    COMBINATION = "Комбинация"
    MOUSE = "Мышь"
    SPECIAL = "Специальная"


class InputMethod(Enum):
    """Методы ввода"""
    SENDINPUT = "SendInput"  # Стандартный метод
    KEYBD_EVENT = "keybd_event"  # Старый метод
    SCANCODE = "ScanCode"  # Скан-коды (для игр)
    DIRECT_INPUT = "DirectInput"  # Для DirectX игр


@dataclass
class ActionItem:
    """Модель элемента действия"""
    type: ActionType
    display_text: str
    action_text: str
    delay: float
    rand_min: int
    rand_max: int
    repeat_count: int = 1
    input_method: InputMethod = InputMethod.SENDINPUT

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type.value,
            'type_enum': self.type.name,
            'display_text': self.display_text,
            'action_text': self.action_text,
            'delay': self.delay,
            'rand_min': self.rand_min,
            'rand_max': self.rand_max,
            'repeat_count': self.repeat_count,
            'input_method': self.input_method.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionItem':
        if 'type_enum' in data:
            action_type = ActionType[data['type_enum']]
        else:
            type_map = {
                'Текст': ActionType.TEXT,
                'Клавиша': ActionType.KEY,
                'Комбинация': ActionType.COMBINATION,
                'Мышь': ActionType.MOUSE,
                'Специальная': ActionType.SPECIAL
            }
            action_type = type_map.get(data.get('type', 'Текст'), ActionType.TEXT)

        # Обратная совместимость для input_method
        input_method = InputMethod.SENDINPUT
        if 'input_method' in data:
            try:
                input_method = InputMethod(data['input_method'])
            except:
                pass

        return cls(
            type=action_type,
            display_text=data['display_text'],
            action_text=data['action_text'],
            delay=data['delay'],
            rand_min=data['rand_min'],
            rand_max=data['rand_max'],
            repeat_count=data.get('repeat_count', 1),
            input_method=input_method
        )

    def get_total_delay(self) -> float:
        additional = random.randint(self.rand_min, self.rand_max) if self.rand_min <= self.rand_max else 0
        return self.delay + (additional / 1000.0)


@dataclass
class AppSettings:
    items: List[ActionItem]
    hotkey_mods: List[str]
    hotkey_key: str
    total_cycles: int = 0
    game_mode: bool = False
    input_method: str = "SENDINPUT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': '1.2',
            'items': [item.to_dict() for item in self.items],
            'hotkey': {
                'mods': self.hotkey_mods,
                'key': self.hotkey_key
            },
            'total_cycles': self.total_cycles,
            'game_mode': self.game_mode,
            'input_method': self.input_method
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppSettings':
        items = [ActionItem.from_dict(item_data) for item_data in data.get('items', [])]
        hotkey_data = data.get('hotkey', {'mods': ['Ctrl'], 'key': 'z'})

        return cls(
            items=items,
            hotkey_mods=hotkey_data.get('mods', ['Ctrl']),
            hotkey_key=hotkey_data.get('key', 'z'),
            total_cycles=data.get('total_cycles', 0),
            game_mode=data.get('game_mode', False),
            input_method=data.get('input_method', 'SENDINPUT')
        )


# ============================================================================
# КОНСТАНТЫ
# ============================================================================

class KeyConstants:
    """Константы виртуальных клавиш"""
    VK_CODES = {
        'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46,
        'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C,
        'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52,
        's': 0x53, 't': 0x54, 'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
        'y': 0x59, 'z': 0x5A,
        '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
        '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
        'space': 0x20, 'enter': 0x0D, 'tab': 0x09, 'backspace': 0x08,
        'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12, 'win': 0x5B,
        'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
        'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
        'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
        'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
        'pageup': 0x21, 'pagedown': 0x22, 'home': 0x24, 'end': 0x23,
        'insert': 0x2D, 'delete': 0x2E,
        'num0': 0x60, 'num1': 0x61, 'num2': 0x62, 'num3': 0x63,
        'num4': 0x64, 'num5': 0x65, 'num6': 0x66, 'num7': 0x67,
        'num8': 0x68, 'num9': 0x69,
        'multiply': 0x6A, 'add': 0x6B, 'subtract': 0x6D, 'decimal': 0x6E,
        'divide': 0x6F,
    }

    # Скан-коды для DirectInput игр
    SCAN_CODES = {
        'a': 0x1E, 'b': 0x30, 'c': 0x2E, 'd': 0x20, 'e': 0x12, 'f': 0x21,
        'g': 0x22, 'h': 0x23, 'i': 0x17, 'j': 0x24, 'k': 0x25, 'l': 0x26,
        'm': 0x32, 'n': 0x31, 'o': 0x18, 'p': 0x19, 'q': 0x10, 'r': 0x13,
        's': 0x1F, 't': 0x14, 'u': 0x16, 'v': 0x2F, 'w': 0x11, 'x': 0x2D,
        'y': 0x15, 'z': 0x2C,
        '0': 0x0B, '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05,
        '5': 0x06, '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A,
        'space': 0x39, 'enter': 0x1C, 'tab': 0x0F, 'backspace': 0x0E,
        'shift': 0x2A, 'ctrl': 0x1D, 'alt': 0x38, 'win': 0x5B,
        'f1': 0x3B, 'f2': 0x3C, 'f3': 0x3D, 'f4': 0x3E,
        'f5': 0x3F, 'f6': 0x40, 'f7': 0x41, 'f8': 0x42,
        'f9': 0x43, 'f10': 0x44, 'f11': 0x57, 'f12': 0x58,
        'up': 0x48, 'down': 0x50, 'left': 0x4B, 'right': 0x4D,
        'pageup': 0x49, 'pagedown': 0x51, 'home': 0x47, 'end': 0x4F,
        'insert': 0x52, 'delete': 0x53,
    }

    DISPLAY_NAMES = {
        'space': 'Пробел',
        'enter': 'Enter',
        'tab': 'Tab',
        'backspace': 'Backspace',
        'escape': 'Escape',
        'shift': 'Shift',
        'ctrl': 'Ctrl',
        'alt': 'Alt',
        'win': 'Win',
        'windows': 'Win',
        'up': '↑ Вверх',
        'down': '↓ Вниз',
        'left': '← Влево',
        'right': '→ Вправо',
        'pageup': 'Page Up',
        'pagedown': 'Page Down',
        'home': 'Home',
        'end': 'End',
        'insert': 'Insert',
        'delete': 'Delete',
        'num0': 'Num 0',
        'num1': 'Num 1',
        'num2': 'Num 2',
        'num3': 'Num 3',
        'num4': 'Num 4',
        'num5': 'Num 5',
        'num6': 'Num 6',
        'num7': 'Num 7',
        'num8': 'Num 8',
        'num9': 'Num 9',
        'multiply': 'Num *',
        'add': 'Num +',
        'subtract': 'Num -',
        'decimal': 'Num .',
        'divide': 'Num /',
    }

    SPECIAL_KEYS = {
        'space': ' ',
        'enter': '\n',
        'tab': '\t',
        'backspace': '\b',
        'escape': '\x1b'
    }

    KEYWORDS = {
        'пробел': 'space',
        'space': 'space',
        'enter': 'enter',
        'tab': 'tab',
        'backspace': 'backspace',
        'escape': 'escape',
        'shift': 'shift',
        'ctrl': 'ctrl',
        'alt': 'alt',
        'win': 'win',
        'up': 'up',
        'down': 'down',
        'left': 'left',
        'right': 'right',
        'pageup': 'pageup',
        'pagedown': 'pagedown',
        'home': 'home',
        'end': 'end',
        'insert': 'insert',
        'delete': 'delete',
    }

    MODIFIERS = {
        'ctrl': 0x11,
        'control': 0x11,
        'shift': 0x10,
        'alt': 0x12,
        'win': 0x5B,
        'windows': 0x5B
    }


# ============================================================================
# СИСТЕМНЫЙ ИНТЕРФЕЙС (Windows API)
# ============================================================================

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_uint)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_uint)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT_UNION),
    ]


class WindowsAPI:
    """Обертка для Windows API с поддержкой игр"""

    @staticmethod
    def is_admin() -> bool:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    @staticmethod
    def send_key_with_scancode(key_name: str, down: bool = True):
        """Отправка клавиши через скан-код (лучше для игр)"""
        user32 = ctypes.windll.user32
        KEYEVENTF_SCANCODE = 0x0008
        KEYEVENTF_KEYUP = 0x0002

        if key_name in KeyConstants.SCAN_CODES:
            scan_code = KeyConstants.SCAN_CODES[key_name]
            flags = KEYEVENTF_SCANCODE
            if not down:
                flags |= KEYEVENTF_KEYUP

            user32.keybd_event(0, scan_code, flags, 0)
            time.sleep(0.01)

    @staticmethod
    def send_key_direct(key_name: str, down: bool = True):
        """Отправка клавиши через DirectInput (для игр)"""
        user32 = ctypes.windll.user32
        if key_name in KeyConstants.VK_CODES:
            vk_code = KeyConstants.VK_CODES[key_name]
            if down:
                user32.keybd_event(vk_code, 0, 0, 0)
            else:
                user32.keybd_event(vk_code, 0, 0x0002, 0)
            time.sleep(0.01)

    @staticmethod
    def send_key_combination(text: str, method: InputMethod = InputMethod.SENDINPUT):
        """Отправка комбинации клавиш с выбором метода"""
        user32 = ctypes.windll.user32

        if '+' in text and not text.startswith('+'):
            parts = text.split('+')
            modifiers = []
            key = parts[-1].lower()

            for mod in parts[:-1]:
                mod_lower = mod.lower()
                if mod_lower in KeyConstants.MODIFIERS:
                    modifiers.append(KeyConstants.MODIFIERS[mod_lower])

            # Нажимаем модификаторы
            for vk in modifiers:
                if method == InputMethod.SCANDOCE:
                    # Для скан-кодов используем соответствующие
                    pass
                else:
                    user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.01)

            # Нажимаем основную клавишу
            if method == InputMethod.SCANDOCE:
                WindowsAPI.send_key_with_scancode(key, True)
            else:
                WindowsAPI.send_key_direct(key, True)

            time.sleep(0.02)

            # Отпускаем основную клавишу
            if method == InputMethod.SCANDOCE:
                WindowsAPI.send_key_with_scancode(key, False)
            else:
                WindowsAPI.send_key_direct(key, False)

            # Отпускаем модификаторы
            for vk in reversed(modifiers):
                if method == InputMethod.SCANDOCE:
                    pass
                else:
                    user32.keybd_event(vk, 0, 0x0002, 0)
                time.sleep(0.01)
            return True

        return False

    @staticmethod
    def send_unicode_text(text: str):
        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        inputs = []
        for char in text:
            ki_down = KEYBDINPUT()
            ki_down.wVk = 0
            ki_down.wScan = ord(char)
            ki_down.dwFlags = KEYEVENTF_UNICODE
            ki_down.time = 0
            ki_down.dwExtraInfo = None

            input_down = INPUT()
            input_down.type = INPUT_KEYBOARD
            input_down.ki = ki_down
            inputs.append(input_down)

            ki_up = KEYBDINPUT()
            ki_up.wVk = 0
            ki_up.wScan = ord(char)
            ki_up.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            ki_up.time = 0
            ki_up.dwExtraInfo = None

            input_up = INPUT()
            input_up.type = INPUT_KEYBOARD
            input_up.ki = ki_up
            inputs.append(input_up)

        if inputs:
            input_array = (INPUT * len(inputs))(*inputs)
            ctypes.windll.user32.SendInput(
                len(inputs),
                input_array,
                ctypes.sizeof(INPUT)
            )

    @staticmethod
    def send_key_sequence(text: str, method: InputMethod = InputMethod.SENDINPUT):
        """Отправка последовательности клавиш с выбором метода"""
        user32 = ctypes.windll.user32

        # Комбинация клавиш
        if WindowsAPI.send_key_combination(text, method):
            return

        # Если это специальная клавиша
        if text in KeyConstants.SPECIAL_KEYS:
            key_name = None
            for name, key_char in KeyConstants.SPECIAL_KEYS.items():
                if key_char == text:
                    key_name = name
                    break

            if key_name:
                if method == InputMethod.SCANDOCE:
                    WindowsAPI.send_key_with_scancode(key_name, True)
                    time.sleep(0.02)
                    WindowsAPI.send_key_with_scancode(key_name, False)
                else:
                    WindowsAPI.send_key_direct(key_name, True)
                    time.sleep(0.02)
                    WindowsAPI.send_key_direct(key_name, False)
                return

        # Обычный текст через Unicode
        try:
            WindowsAPI.send_unicode_text(text)
        except Exception as e:
            print(f"Ошибка отправки Unicode: {e}")
            WindowsAPI._send_text_fallback(text)

    @staticmethod
    def _send_text_fallback(text: str):
        user32 = ctypes.windll.user32
        for char in text:
            shift = 0
            if char == '\n':
                vk = 0x0D
            elif char == '\t':
                vk = 0x09
            elif char == ' ':
                vk = 0x20
            else:
                vk_code = user32.VkKeyScanW(ord(char))
                if vk_code == -1:
                    continue
                vk = vk_code & 0xFF
                shift = (vk_code >> 8) & 0xFF

                if shift & 0x01:
                    user32.keybd_event(0x10, 0, 0, 0)
                    time.sleep(0.01)

            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)
            user32.keybd_event(vk, 0, 0x0002, 0)

            if shift & 0x01:
                user32.keybd_event(0x10, 0, 0x0002, 0)
                time.sleep(0.01)

            time.sleep(0.01)

    @staticmethod
    def send_mouse_click(button: str):
        user32 = ctypes.windll.user32
        if button == "left":
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
        elif button == "right":
            user32.mouse_event(0x0008, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(0x0010, 0, 0, 0, 0)

    @staticmethod
    def get_foreground_window_info():
        """Получить информацию об активном окне"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                window_title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                return {
                    'hwnd': hwnd,
                    'title': window_title,
                    'pid': pid,
                    'process_name': process.name(),
                    'exe_path': process.exe()
                }
        except:
            return None
        return None


# ============================================================================
# УПРАВЛЕНИЕ НАСТРОЙКАМИ (Settings Manager)
# ============================================================================

class SettingsManager:
    DEFAULT_FILENAME = "autotext_settings.json"

    @staticmethod
    def get_default_path() -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), SettingsManager.DEFAULT_FILENAME)

    @staticmethod
    def save(settings: AppSettings, filename: str = None) -> bool:
        if filename is None:
            filename = SettingsManager.get_default_path()

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(settings.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
            return False

    @staticmethod
    def load(filename: str = None) -> Optional[AppSettings]:
        if filename is None:
            filename = SettingsManager.get_default_path()

        if not os.path.exists(filename):
            return None

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return AppSettings.from_dict(data)
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            return None


# ============================================================================
# БИЗНЕС-ЛОГИКА (Controller)
# ============================================================================

class AutomationController:
    """Контроллер автоматизации"""

    def __init__(self):
        self.items: List[ActionItem] = []
        self.is_running = False
        self.current_index = 0
        self.current_repeat = 0
        self.total_cycles = 0
        self.current_cycle = 0
        self.hotkey_handler = None
        self.hotkey_mods = ["Ctrl"]
        self.hotkey_key = "z"
        self.callbacks = {}
        self.current_file = None
        self.game_mode = False
        self.input_method = InputMethod.SENDINPUT

    def set_callback(self, name: str, callback):
        self.callbacks[name] = callback

    def add_item(self, item: ActionItem):
        self.items.append(item)
        self._notify_update()
        self._auto_save()

    def remove_item(self, index: int):
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._notify_update()
            self._auto_save()

    def clear_items(self):
        self.items.clear()
        self._notify_update()
        self._auto_save()

    def load_items(self, items: List[ActionItem]):
        self.items = items.copy()
        self._notify_update()

    def set_total_cycles(self, cycles: int):
        self.total_cycles = cycles
        self._auto_save()

    def set_game_mode(self, enabled: bool):
        self.game_mode = enabled
        self._auto_save()

    def set_input_method(self, method: InputMethod):
        self.input_method = method
        self._auto_save()

    def toggle(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        if not self.items:
            messagebox.showwarning("Предупреждение", "Нет элементов в последовательности")
            return

        # Если включен игровой режим, показываем информацию
        if self.game_mode:
            window_info = WindowsAPI.get_foreground_window_info()
            if window_info:
                self._notify_game_info(f"Игра: {window_info['process_name']}")

        self.is_running = True
        self.current_index = 0
        self.current_repeat = 0
        self.current_cycle = 0
        self._notify_status("АКТИВЕН", "green")
        threading.Thread(target=self._automation_loop, daemon=True).start()

    def stop(self):
        self.is_running = False
        self._notify_status("Остановлен", "red")
        self._notify_progress(0, 0)
        self._notify_game_info("")

    def update_hotkey(self, mods: List[str], key: str):
        self.hotkey_mods = mods
        self.hotkey_key = key
        self._register_hotkey()
        self._auto_save()

    def _register_hotkey(self):
        if self.hotkey_handler:
            try:
                keyboard.remove_hotkey(self.hotkey_handler)
            except:
                pass

        try:
            hotkey_str = '+'.join(self.hotkey_mods).lower() + '+' + self.hotkey_key.lower()
            self.hotkey_handler = keyboard.add_hotkey(hotkey_str, self.toggle, suppress=True)
            display = '+'.join(self.hotkey_mods) + '+' + self.hotkey_key
            self._notify_hotkey(display)
        except Exception as e:
            print(f"Ошибка регистрации хоткея: {e}")
            self._notify_hotkey("Ошибка")

    def _auto_save(self):
        settings = AppSettings(
            self.items,
            self.hotkey_mods,
            self.hotkey_key,
            self.total_cycles,
            self.game_mode,
            self.input_method.value
        )
        SettingsManager.save(settings)

    def _automation_loop(self):
        """Основной цикл автоматизации"""
        total_actions = sum(item.repeat_count for item in self.items)
        executed_actions = 0

        while self.is_running:
            if self.total_cycles > 0 and self.current_cycle >= self.total_cycles:
                self.is_running = False
                self._notify_status("Завершен", "blue")
                self._notify_progress(0, 0)
                break

            if self.current_index >= len(self.items):
                self.current_index = 0
                self.current_repeat = 0
                self.current_cycle += 1

                if self.total_cycles > 0:
                    self._notify_progress(self.current_cycle, self.total_cycles)
                continue

            item = self.items[self.current_index]

            if self.current_repeat >= item.repeat_count:
                self.current_index += 1
                self.current_repeat = 0
                continue

            self._notify_current(item, self.current_index, self.current_repeat + 1)

            # Выбор метода ввода
            method = item.input_method
            if not self.game_mode:
                method = InputMethod.SENDINPUT

            try:
                if item.type == ActionType.MOUSE:
                    if "ЛКМ" in item.display_text:
                        WindowsAPI.send_mouse_click("left")
                    elif "ПКМ" in item.display_text:
                        WindowsAPI.send_mouse_click("right")
                else:
                    WindowsAPI.send_key_sequence(item.action_text, method)
            except Exception as e:
                print(f"Ошибка выполнения: {e}")

            time.sleep(item.get_total_delay())

            self.current_repeat += 1
            executed_actions += 1

            if self.total_cycles > 0:
                total_expected = total_actions * self.total_cycles
                progress = min(100, int((executed_actions / total_expected) * 100))
                self._notify_progress(self.current_cycle, self.total_cycles, progress)

    def _notify_update(self):
        if 'update' in self.callbacks:
            self.callbacks['update'](self.items)

    def _notify_status(self, text: str, color: str):
        if 'status' in self.callbacks:
            self.callbacks['status'](text, color)

    def _notify_hotkey(self, display: str):
        if 'hotkey' in self.callbacks:
            self.callbacks['hotkey'](display)

    def _notify_current(self, item: ActionItem, index: int, repeat: int):
        if 'current' in self.callbacks:
            self.callbacks['current'](item, index, repeat)

    def _notify_progress(self, cycle: int, total: int, progress: int = 0):
        if 'progress' in self.callbacks:
            self.callbacks['progress'](cycle, total, progress)

    def _notify_game_info(self, info: str):
        if 'game_info' in self.callbacks:
            self.callbacks['game_info'](info)


# ============================================================================
# ПОЛЬЗОВАТЕЛЬСКИЙ ИНТЕРФЕЙС (View)
# ============================================================================

class MainWindow:
    """Главное окно приложения"""

    def __init__(self, controller: AutomationController):
        self.controller = controller
        self.catching_mode = False
        self.catching_hotkey_mode = False

        self.root = tk.Tk()
        self.root.title("Safe Enterprise Key & Mouse Catcher - Game Mode")
        self.root.geometry("1100x700")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Segoe UI', 10, 'bold'))
        style.configure('Status.TLabel', font=('Segoe UI', 10, 'bold'))
        style.configure('Game.TButton', foreground='orange', font=('Segoe UI', 9, 'bold'))

        self._create_widgets()

        self.controller.set_callback('update', self._update_table)
        self.controller.set_callback('status', self._update_status)
        self.controller.set_callback('hotkey', self._update_hotkey)
        self.controller.set_callback('current', self._highlight_item)
        self.controller.set_callback('progress', self._update_progress)
        self.controller.set_callback('game_info', self._update_game_info)

        self._load_settings()

        if WindowsAPI.is_admin():
            self.controller._register_hotkey()
        else:
            self.hotkey_btn.config(text="Хоткей: Нет прав", state=tk.DISABLED)

        self.root.bind_all("<KeyPress>", self._on_global_key)
        self.root.bind_all("<ButtonPress>", self._on_mouse_press)

    def _create_widgets(self):
        self._create_info_panel()

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._create_input_panel(main_frame)
        self._create_table(main_frame)
        self._create_control_panel(main_frame)
        self._create_statusbar()

    def _create_info_panel(self):
        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        is_admin = WindowsAPI.is_admin()

        if is_admin:
            label = ttk.Label(
                info_frame,
                text="✅ Запущено с правами администратора",
                foreground="green",
                font=("Segoe UI", 9, "bold")
            )
        else:
            label = ttk.Label(
                info_frame,
                text="⚠️ Запущено БЕЗ прав администратора",
                foreground="red",
                font=("Segoe UI", 9, "bold")
            )
        label.pack(side=tk.LEFT)

        # Игровой режим
        self.game_mode_var = tk.BooleanVar(value=False)
        self.game_mode_check = ttk.Checkbutton(
            info_frame,
            text="🎮 Игровой режим",
            variable=self.game_mode_var,
            command=self._toggle_game_mode,
            style='Game.TButton'
        )
        self.game_mode_check.pack(side=tk.LEFT, padx=(20, 0))

        # Метод ввода
        ttk.Label(info_frame, text="Метод ввода:").pack(side=tk.LEFT, padx=(20, 5))

        self.input_method_var = tk.StringVar(value="SENDINPUT")
        self.input_method_combo = ttk.Combobox(
            info_frame,
            textvariable=self.input_method_var,
            values=["SENDINPUT", "KEYBD_EVENT", "SCANCODE", "DIRECT_INPUT"],
            width=15,
            state="readonly"
        )
        self.input_method_combo.pack(side=tk.LEFT, padx=5)
        self.input_method_combo.bind('<<ComboboxSelected>>', self._on_input_method_change)

        if not is_admin:
            hint = ttk.Label(
                info_frame,
                text="(Перезапустите с правами администратора для полной функциональности)",
                foreground="orange",
                font=("Segoe UI", 8)
            )
            hint.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Separator(self.root, orient='horizontal').pack(fill=tk.X, padx=10, pady=5)

    def _create_input_panel(self, parent):
        frame = ttk.LabelFrame(parent, text=" Добавить элемент в последовательность ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Действие:").grid(row=0, column=0, sticky=tk.W, padx=2, pady=2)

        self.text_entry = ttk.Entry(frame, width=14)
        self.text_entry.grid(row=0, column=1, padx=2, pady=2)
        self.text_entry.insert(0, "Нажми кнопку справа ->")

        self.catch_btn = ttk.Button(frame, text="Задать", width=7, command=self._activate_catching)
        self.catch_btn.grid(row=0, column=2, padx=2, pady=2)

        ttk.Label(frame, text="Задержка (сек):").grid(row=0, column=3, sticky=tk.W, padx=2, pady=2)

        self.delay_entry = ttk.Entry(frame, width=6)
        self.delay_entry.grid(row=0, column=4, padx=2, pady=2)
        self.delay_entry.insert(0, "1.0")

        ttk.Label(frame, text="Мин (мс):").grid(row=0, column=5, sticky=tk.W, padx=2, pady=2)

        self.rand_min_entry = ttk.Entry(frame, width=5)
        self.rand_min_entry.grid(row=0, column=6, padx=2, pady=2)
        self.rand_min_entry.insert(0, "0")

        ttk.Label(frame, text="Макс (мс):").grid(row=0, column=7, sticky=tk.W, padx=2, pady=2)

        self.rand_max_entry = ttk.Entry(frame, width=5)
        self.rand_max_entry.grid(row=0, column=8, padx=2, pady=2)
        self.rand_max_entry.insert(0, "500")

        ttk.Label(frame, text="Повторов:").grid(row=0, column=9, sticky=tk.W, padx=2, pady=2)

        self.repeat_entry = ttk.Entry(frame, width=5)
        self.repeat_entry.grid(row=0, column=10, padx=2, pady=2)
        self.repeat_entry.insert(0, "1")

        self.add_btn = ttk.Button(frame, text="➕ Добавить", command=self._add_item)
        self.add_btn.grid(row=0, column=11, padx=5, pady=2)

        for i in range(12):
            frame.grid_columnconfigure(i, weight=0)
        frame.grid_columnconfigure(11, weight=1)

    def _create_table(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("Index", "Type", "Text", "Delay", "Random", "Repeat", "Method")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=8)

        self.tree.heading("Index", text="#")
        self.tree.heading("Type", text="Тип действия")
        self.tree.heading("Text", text="Действие")
        self.tree.heading("Delay", text="Баз. задержка")
        self.tree.heading("Random", text="Разброс (мс)")
        self.tree.heading("Repeat", text="Повторов")
        self.tree.heading("Method", text="Метод ввода")

        self.tree.column("Index", width=40, anchor=tk.CENTER)
        self.tree.column("Type", width=120, anchor=tk.CENTER)
        self.tree.column("Text", width=250, anchor=tk.W)
        self.tree.column("Delay", width=120, anchor=tk.CENTER)
        self.tree.column("Random", width=150, anchor=tk.CENTER)
        self.tree.column("Repeat", width=80, anchor=tk.CENTER)
        self.tree.column("Method", width=100, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_control_panel(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=5)

        left_frame = ttk.Frame(frame)
        left_frame.pack(side=tk.LEFT)

        self.remove_btn = ttk.Button(left_frame, text="🗑 Удалить", command=self._remove_item)
        self.remove_btn.pack(side=tk.LEFT, padx=2)

        self.clear_btn = ttk.Button(left_frame, text="✖ Очистить всё", command=self._clear_items)
        self.clear_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(frame, orient='vertical').pack(side=tk.LEFT, padx=5, fill=tk.Y)

        file_frame = ttk.Frame(frame)
        file_frame.pack(side=tk.LEFT, padx=5)

        self.save_btn = ttk.Button(file_frame, text="💾 Сохранить", command=self._save_settings)
        self.save_btn.pack(side=tk.LEFT, padx=2)

        self.load_btn = ttk.Button(file_frame, text="📂 Загрузить", command=self._load_settings_dialog)
        self.load_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(frame, orient='vertical').pack(side=tk.LEFT, padx=5, fill=tk.Y)

        cycle_frame = ttk.Frame(frame)
        cycle_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(cycle_frame, text="Циклов:").pack(side=tk.LEFT, padx=2)

        self.cycles_entry = ttk.Entry(cycle_frame, width=6)
        self.cycles_entry.pack(side=tk.LEFT, padx=2)
        self.cycles_entry.insert(0, "0")
        self.cycles_entry.bind('<KeyRelease>', self._on_cycles_change)

        ttk.Label(cycle_frame, text="(0=∞)", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=2)

        right_frame = ttk.Frame(frame)
        right_frame.pack(side=tk.RIGHT)

        self.status_label = ttk.Label(
            right_frame,
            text="Статус: Остановлен",
            style='Status.TLabel',
            foreground="red"
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

        self.hotkey_btn = ttk.Button(
            right_frame,
            text="⌨ Хоткей: Ctrl+z",
            command=self._activate_hotkey_catching
        )
        self.hotkey_btn.pack(side=tk.LEFT, padx=2)

        self.start_btn = ttk.Button(
            right_frame,
            text="▶ СТАРТ",
            command=self._toggle_automation,
            style='Start.TButton'
        )
        self.start_btn.pack(side=tk.LEFT, padx=2)

        style = ttk.Style()
        style.configure('Start.TButton', foreground='green')

    def _create_statusbar(self):
        statusbar = ttk.Frame(self.root)
        statusbar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)

        self.count_label = ttk.Label(statusbar, text="Элементов: 0", font=("Segoe UI", 8))
        self.count_label.pack(side=tk.LEFT)

        self.progress_label = ttk.Label(statusbar, text="Прогресс: 0%", font=("Segoe UI", 8))
        self.progress_label.pack(side=tk.LEFT, padx=20)

        self.progress_bar = ttk.Progressbar(statusbar, length=200, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, padx=10)

        self.game_info_label = ttk.Label(statusbar, text="", font=("Segoe UI", 8), foreground="orange")
        self.game_info_label.pack(side=tk.LEFT, padx=20)

        self.file_label = ttk.Label(statusbar, text="Файл: autotext_settings.json", font=("Segoe UI", 8))
        self.file_label.pack(side=tk.RIGHT)

    def _update_table(self, items: List[ActionItem]):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, item in enumerate(items, start=1):
            display = item.display_text
            if display in KeyConstants.DISPLAY_NAMES:
                display = KeyConstants.DISPLAY_NAMES[display]

            self.tree.insert(
                "",
                tk.END,
                values=(
                    idx,
                    item.type.value,
                    display,
                    f"{item.delay} сек",
                    f"от {item.rand_min} до {item.rand_max} мс",
                    item.repeat_count,
                    item.input_method.value if item.input_method else "По умолчанию"
                )
            )

        self.count_label.config(text=f"Элементов: {len(items)}")

    def _update_status(self, text: str, color: str):
        self.status_label.config(text=f"Статус: {text}", foreground=color)
        self.start_btn.config(text="⏹ СТОП" if text == "АКТИВЕН" else "▶ СТАРТ")

    def _update_hotkey(self, display: str):
        self.hotkey_btn.config(text=f"⌨ Хоткей: {display}")

    def _update_progress(self, cycle: int, total: int, progress: int = 0):
        if total > 0:
            self.progress_label.config(text=f"Цикл: {cycle}/{total} ({progress}%)")
            self.progress_bar['value'] = progress
        else:
            if cycle > 0:
                self.progress_label.config(text=f"Цикл: {cycle} (бесконечно)")
            else:
                self.progress_label.config(text="Прогресс: 0%")
            self.progress_bar['value'] = 0

    def _update_game_info(self, info: str):
        self.game_info_label.config(text=info)

    def _highlight_item(self, item: ActionItem, index: int, repeat: int):
        children = self.tree.get_children()
        if index < len(children):
            self.tree.selection_set(children[index])
            self.tree.see(children[index])

            if repeat > 1:
                self.status_label.config(
                    text=f"Статус: АКТИВЕН (повтор {repeat})",
                    foreground="green"
                )

    def _toggle_game_mode(self):
        enabled = self.game_mode_var.get()
        self.controller.set_game_mode(enabled)

        if enabled:
            self.input_method_combo.config(state="normal")
            self.game_info_label.config(text="🎮 Игровой режим активирован", foreground="orange")
        else:
            self.input_method_combo.config(state="readonly")
            self.game_info_label.config(text="")

    def _on_input_method_change(self, event):
        method_str = self.input_method_var.get()
        try:
            method = InputMethod(method_str)
            self.controller.set_input_method(method)
        except:
            pass

    def _on_cycles_change(self, event):
        try:
            cycles = int(self.cycles_entry.get())
            if cycles < 0:
                cycles = 0
            self.controller.set_total_cycles(cycles)
        except:
            pass

    def _activate_catching(self):
        if self.catching_hotkey_mode:
            return

        self.catching_mode = True
        self.text_entry.delete(0, tk.END)
        self.text_entry.insert(0, "[ Жду клик/клавишу ]")
        self.text_entry.focus_set()
        self.catch_btn.config(state=tk.DISABLED)

    def _activate_hotkey_catching(self):
        if self.catching_mode:
            return

        self.catching_hotkey_mode = True
        self.hotkey_btn.config(text="[ Нажмите хоткей... ]", state=tk.DISABLED)
        self.root.focus_set()

    def _on_global_key(self, event):
        if self.catching_hotkey_mode:
            if event.keysym in ["Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R"]:
                return "break"

            mods, key_name = self._parse_key_event(event)
            self.controller.update_hotkey(mods, key_name)
            self.catching_hotkey_mode = False
            self.hotkey_btn.config(state=tk.NORMAL)
            return "break"

        if self.catching_mode:
            if event.keysym in ["Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R"]:
                return "break"

            mods, key_name = self._parse_key_event(event)

            if key_name.lower() == 'space':
                key_name = 'Пробел'

            full = "+".join(mods) + "+" + key_name if mods else key_name

            self.catching_mode = False
            self.text_entry.delete(0, tk.END)
            self.text_entry.insert(0, full)
            self.catch_btn.config(state=tk.NORMAL)
            return "break"

    def _on_mouse_press(self, event):
        if not self.catching_mode:
            return

        action = "Клик ЛКМ" if event.num == 1 else "Клик ПКМ" if event.num == 3 else f"Клик (Кнопка {event.num})"
        self.catching_mode = False
        self.text_entry.delete(0, tk.END)
        self.text_entry.insert(0, action)
        self.catch_btn.config(state=tk.NORMAL)
        return "break"

    def _parse_key_event(self, event):
        modifiers = []
        if event.state & 0x0004:
            modifiers.append("Ctrl")
        if event.state & 0x0001:
            modifiers.append("Shift")
        if event.state & 0x0020:
            modifiers.append("Alt")

        key_name = event.keysym
        if "???" in key_name or key_name.startswith("?") or (len(key_name) == 1 and ord(key_name) == 63):
            if event.char and ord(event.char) != 63:
                key_name = event.char
            else:
                key_name = f"Key_{event.keycode}"

        return modifiers, key_name

    def _parse_action_text(self, text: str) -> tuple:
        text_lower = text.lower().strip()

        for keyword, key_name in KeyConstants.KEYWORDS.items():
            if text_lower == keyword:
                display_name = KeyConstants.DISPLAY_NAMES.get(key_name, key_name)
                return ActionType.KEY, display_name, KeyConstants.SPECIAL_KEYS.get(key_name, text)

        if '+' in text:
            return ActionType.COMBINATION, text, text

        if "клик" in text_lower or "лкм" in text_lower or "пкм" in text_lower:
            return ActionType.MOUSE, text, text

        return ActionType.TEXT, text, text

    def _add_item(self):
        display = self.text_entry.get()
        delay_str = self.delay_entry.get()
        min_str = self.rand_min_entry.get().strip()
        max_str = self.rand_max_entry.get().strip()
        repeat_str = self.repeat_entry.get().strip()

        if not display or display in ["[ Жду клик/клавишу ]", "Нажми кнопку справа ->"]:
            messagebox.showwarning("Предупреждение", "Сначала задайте действие через кнопку 'Задать'")
            return

        try:
            delay = float(delay_str)
            if delay < 0.01:
                delay = 0.01
        except:
            messagebox.showerror("Ошибка", "Неверный формат задержки")
            return

        try:
            rand_min = int(min_str) if min_str else 0
            rand_max = int(max_str) if max_str else 0
            if rand_min > rand_max:
                rand_min, rand_max = rand_max, rand_min
        except:
            messagebox.showerror("Ошибка", "Неверный формат разброса")
            return

        try:
            repeat_count = int(repeat_str) if repeat_str else 1
            if repeat_count < 1:
                repeat_count = 1
        except:
            messagebox.showerror("Ошибка", "Неверный формат повторов")
            return

        action_type, display_text, action_text = self._parse_action_text(display)

        # Выбор метода ввода
        input_method = InputMethod.SENDINPUT
        if self.game_mode_var.get():
            try:
                input_method = InputMethod(self.input_method_var.get())
            except:
                pass

        item = ActionItem(
            action_type,
            display_text,
            action_text,
            delay,
            rand_min,
            rand_max,
            repeat_count,
            input_method
        )
        self.controller.add_item(item)

        self.text_entry.delete(0, tk.END)
        self.text_entry.insert(0, "Нажми кнопку справа ->")

    def _remove_item(self):
        selected = self.tree.selection()
        if not selected:
            return

        idx = self.tree.index(selected[0])
        self.controller.remove_item(idx)

    def _clear_items(self):
        if self.controller.is_running:
            self.controller.stop()
        self.controller.clear_items()

    def _toggle_automation(self):
        self.controller.toggle()

    def _load_settings(self):
        settings = SettingsManager.load()
        if settings:
            self.controller.load_items(settings.items)
            self.controller.hotkey_mods = settings.hotkey_mods
            self.controller.hotkey_key = settings.hotkey_key
            self.controller.total_cycles = settings.total_cycles
            self.controller.game_mode = settings.game_mode
            self.controller.input_method = InputMethod(
                settings.input_method) if settings.input_method else InputMethod.SENDINPUT

            self.game_mode_var.set(settings.game_mode)
            self.input_method_var.set(settings.input_method)

            self.cycles_entry.delete(0, tk.END)
            self.cycles_entry.insert(0, str(settings.total_cycles))
            self._update_hotkey('+'.join(settings.hotkey_mods) + '+' + settings.hotkey_key)
            self.file_label.config(text=f"Файл: {SettingsManager.DEFAULT_FILENAME}")

            if settings.game_mode:
                self.game_info_label.config(text="🎮 Игровой режим активирован", foreground="orange")
                self.input_method_combo.config(state="normal")

    def _save_settings(self):
        filename = filedialog.asksaveasfilename(
            title="Сохранить настройки",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=SettingsManager.DEFAULT_FILENAME
        )

        if filename:
            try:
                cycles = int(self.cycles_entry.get())
                if cycles < 0:
                    cycles = 0
                self.controller.set_total_cycles(cycles)
            except:
                pass

            settings = AppSettings(
                self.controller.items,
                self.controller.hotkey_mods,
                self.controller.hotkey_key,
                self.controller.total_cycles,
                self.controller.game_mode,
                self.controller.input_method.value
            )
            if SettingsManager.save(settings, filename):
                messagebox.showinfo("Успех", f"Настройки сохранены в:\n{filename}")
                self.file_label.config(text=f"Файл: {os.path.basename(filename)}")
            else:
                messagebox.showerror("Ошибка", "Не удалось сохранить настройки")

    def _load_settings_dialog(self):
        filename = filedialog.askopenfilename(
            title="Загрузить настройки",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=SettingsManager.DEFAULT_FILENAME
        )

        if filename:
            settings = SettingsManager.load(filename)
            if settings:
                if self.controller.is_running:
                    self.controller.stop()

                self.controller.load_items(settings.items)
                self.controller.hotkey_mods = settings.hotkey_mods
                self.controller.hotkey_key = settings.hotkey_key
                self.controller.total_cycles = settings.total_cycles
                self.controller.game_mode = settings.game_mode
                self.controller.input_method = InputMethod(
                    settings.input_method) if settings.input_method else InputMethod.SENDINPUT

                self.game_mode_var.set(settings.game_mode)
                self.input_method_var.set(settings.input_method)

                self.cycles_entry.delete(0, tk.END)
                self.cycles_entry.insert(0, str(settings.total_cycles))
                self.controller._register_hotkey()
                self._update_hotkey('+'.join(settings.hotkey_mods) + '+' + settings.hotkey_key)
                self.file_label.config(text=f"Файл: {os.path.basename(filename)}")
                messagebox.showinfo("Успех", f"Настройки загружены из:\n{filename}")
            else:
                messagebox.showerror("Ошибка", "Не удалось загрузить настройки")

    def _on_closing(self):
        settings = AppSettings(
            self.controller.items,
            self.controller.hotkey_mods,
            self.controller.hotkey_key,
            self.controller.total_cycles,
            self.controller.game_mode,
            self.controller.input_method.value
        )
        SettingsManager.save(settings)

        self.controller.stop()
        if self.controller.hotkey_handler:
            try:
                keyboard.remove_hotkey(self.controller.hotkey_handler)
            except:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

def main():
    # Проверяем наличие необходимых библиотек для игрового режима
    try:
        import win32gui
        import win32process
        import psutil
    except ImportError:
        print("Для игрового режима установите: pip install pywin32 psutil")

    controller = AutomationController()
    app = MainWindow(controller)
    app.run()


if __name__ == "__main__":
    main()
