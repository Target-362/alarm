# main.py
import os
from datetime import datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.resources import resource_add_path, resource_find
from kivy.properties import StringProperty, BooleanProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from algebra import generate_equation, check_answer


resource_add_path("assets")
resource_add_path(".")


# ---------- Ввод: только цифры, минус, точка, запятая, пробел ----------
class DecimalInput(TextInput):
    def insert_text(self, substring, from_undo=False):
        allowed = set("0123456789-., ")
        filtered = "".join(ch for ch in substring if ch in allowed)
        return super().insert_text(filtered, from_undo=from_undo)


# ---------- Выбор файла: Android / ПК ----------
class FilePicker:
    """
    Открывает системный диалог выбора аудиофайла.
    На Android — Intent.ACTION_GET_CONTENT.
    На ПК — tkinter.filedialog.
    Возвращает путь/URI через callback(path_or_uri | None).
    """

    @staticmethod
    def pick(callback):
        if platform == "android":
            FilePicker._pick_android(callback)
        else:
            FilePicker._pick_desktop(callback)

    # --- Android ---
    @staticmethod
    def _pick_android(callback):
        from jnius import autoclass
        from android import activity as android_activity

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        activity = PythonActivity.mActivity

        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.setType("audio/*")
        intent.addCategory(Intent.CATEGORY_OPENABLE)

        REQUEST_CODE = 4242

        def on_activity_result(request_code, result_code, data):
            if request_code != REQUEST_CODE:
                return
            try:
                # RESULT_OK = -1
                if result_code != -1:
                    callback(None)
                    return
                uri = data.getData()
                if uri is None:
                    callback(None)
                    return
                callback(str(uri))
            except Exception as e:
                print(f"[picker] ошибка: {e}")
                callback(None)

        android_activity.bind(on_activity_result=on_activity_result)

        try:
            activity.startActivityForResult(intent, REQUEST_CODE)
        except Exception as e:
            print(f"[picker] не удалось открыть диалог: {e}")
            callback(None)

    # --- ПК ---
    @staticmethod
    def _pick_desktop(callback):
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Выберите звук будильника",
                filetypes=[
                    ("Аудио", "*.wav *.mp3 *.ogg *.m4a"),
                    ("Все файлы", "*.*"),
                ],
            )
            root.destroy()
            callback(path if path else None)
        except Exception as e:
            print(f"[picker] tkinter недоступен: {e}")
            callback(None)


# ---------- Копирование content:// в приватную папку (Android) ----------
def copy_to_app_dir(uri_str: str):
    """
    Копирует content:// файл в приватную папку приложения.
    Возвращает путь к локальному файлу или None при ошибке.
    Работает ТОЛЬКО на Android.
    """
    try:
        from jnius import autoclass, cast
        from android.storage import app_storage_path

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Uri = autoclass("android.net.Uri")
        BufferedInputStream = autoclass("java.io.BufferedInputStream")

        activity = PythonActivity.mActivity
        uri = Uri.parse(uri_str)

        # Открываем InputStream через ContentResolver + буферизация
        raw = activity.getContentResolver().openInputStream(
            cast("android.net.Uri", uri)
        )
        stream = BufferedInputStream(raw)

        # Куда сохраняем
        dest = os.path.join(app_storage_path(), "custom_alarm.dat")

        with open(dest, "wb") as f:
            buf = bytearray(8192)
            while True:
                n = stream.read(buf)
                if n <= 0:
                    break
                f.write(bytes(buf[:n]))
        stream.close()

        print(f"[picker] скопировано в {dest}")
        return dest

    except Exception as e:
        print(f"[picker] ошибка копирования: {e}")
        return None


# ---------- Аудио-движок ----------
class AlarmSound:
    """
    Универсальный проигрыватель будильника.
    Приоритет:
      1. Если пользователь выбрал свой файл (custom_uri) — играем его.
      2. Иначе на Android — системный звук будильника.
      3. Иначе на ПК — локальный alarm.wav.
    """

    def __init__(self, store: JsonStore):
        self.store = store
        self.android_player = None
        self.desktop_sound = None

    # --- Настройки ---
    def get_custom_uri(self):
        if self.store.exists("settings") and "custom_uri" in self.store.get("settings"):
            return self.store.get("settings")["custom_uri"]
        return None

    def set_custom_uri(self, uri):
        if uri:
            self.store.put("settings", custom_uri=uri)
        elif self.store.exists("settings"):
            data = dict(self.store.get("settings"))
            data.pop("custom_uri", None)
            self.store.put("settings", **data)

    def reset_custom(self):
        self.set_custom_uri(None)

    def custom_name(self):
        uri = self.get_custom_uri()
        if not uri:
            return "Системный звук"
        name = os.path.basename(uri) or uri
        return name if len(name) <= 30 else name[:27] + "..."

    # --- Android ---
    def _start_android_uri(self, uri_str):
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        MediaPlayer = autoclass("android.media.MediaPlayer")
        Uri = autoclass("android.net.Uri")

        activity = PythonActivity.mActivity
        uri = Uri.parse(uri_str)

        player = MediaPlayer()
        player.setDataSource(activity, uri)
        player.setLooping(True)
        player.prepare()
        player.start()
        self.android_player = player

    def _start_android_system(self):
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        RingtoneManager = autoclass("android.media.RingtoneManager")
        MediaPlayer = autoclass("android.media.MediaPlayer")

        activity = PythonActivity.mActivity
        uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        if uri is None:
            uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)

        player = MediaPlayer()
        player.setDataSource(activity, uri)
        player.setLooping(True)
        player.prepare()
        player.start()
        self.android_player = player

    def _stop_android(self):
        player = self.android_player
        if not player:
            return
        try:
            if player.isPlaying():
                player.stop()
        except Exception:
            pass
        try:
            player.release()
        except Exception:
            pass
        self.android_player = None

    # --- ПК ---
    def _load_desktop(self, path):
        if path and os.path.exists(path):
            snd = SoundLoader.load(path)
            if snd:
                return snd
        for name in ("alarm.wav", "assets/alarm.wav"):
            p = resource_find(name)
            if p:
                snd = SoundLoader.load(p)
                if snd:
                    return snd
        return None

    def _start_desktop(self, path):
        if self.desktop_sound is None:
            self.desktop_sound = self._load_desktop(path)
        if self.desktop_sound:
            self.desktop_sound.loop = True
            self.desktop_sound.play()

    def _stop_desktop(self):
        if self.desktop_sound:
            self.desktop_sound.stop()

    # --- Публичный API ---
    def start(self):
        custom_uri = self.get_custom_uri()

        if platform == "android":
            try:
                if custom_uri:
                    self._start_android_uri(custom_uri)
                else:
                    self._start_android_system()
                return
            except Exception as e:
                print(f"[sound] Android-звук упал: {e}")

        self._start_desktop(custom_uri)

    def stop(self):
        if platform == "android":
            self._stop_android()
        self._stop_desktop()


# ---------- Вибрация ----------
def vibrate(duration_ms=1000):
    if platform != "android":
        return
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        activity = PythonActivity.mActivity
        vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
        vibrator.vibrate(duration_ms)
    except Exception as e:
        print(f"[vibrate] {e}")


# ---------- Экран ----------
class AlarmScreen(BoxLayout):
    status = StringProperty("Установите будильник")
    ringing = BooleanProperty(False)
    sound_name = StringProperty("Системный звук")

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=20, spacing=10, **kwargs)

        # Хранилище настроек
        self.store = JsonStore("math_alarm.json")
        self.sound = AlarmSound(self.store)
        self.sound_name = self.sound.custom_name()

        # Заголовок
        self.add_widget(Label(
            text="🧮 Математический будильник",
            font_size=24, size_hint=(1, 0.10)
        ))

        # Время
        time_row = BoxLayout(size_hint=(1, 0.09), spacing=10)
        time_row.add_widget(Label(text="Время (ЧЧ:ММ):", font_size=19))
        self.time_input = TextInput(
            text=(datetime.now() + timedelta(minutes=1)).strftime("%H:%M"),
            multiline=False, font_size=21, halign="center"
        )
        time_row.add_widget(self.time_input)
        self.add_widget(time_row)

        # Сложность
        diff_row = BoxLayout(size_hint=(1, 0.09), spacing=10)
        diff_row.add_widget(Label(text="Сложность:", font_size=19))
        self.difficulty = Spinner(
            text="easy", values=("easy", "medium", "hard"), font_size=19
        )
        diff_row.add_widget(self.difficulty)
        self.add_widget(diff_row)

        # Блок выбора звука
        sound_row = BoxLayout(size_hint=(1, 0.09), spacing=10)
        self.pick_btn = Button(text="🎵 Выбрать звук", font_size=17)
        self.pick_btn.bind(on_press=self.pick_sound)
        sound_row.add_widget(self.pick_btn)

        self.reset_btn = Button(text="↺ Сбросить", font_size=17, size_hint=(0.4, 1))
        self.reset_btn.bind(on_press=self.reset_sound)
        sound_row.add_widget(self.reset_btn)
        self.add_widget(sound_row)

        # Имя текущего звука
        self.sound_label = Label(
            text=f"🔊 {self.sound_name}",
            font_size=14, size_hint=(1, 0.06)
        )
        self.add_widget(self.sound_label)

        # Кнопка установки
        self.set_btn = Button(
            text="⏰ Установить будильник",
            font_size=21, size_hint=(1, 0.11)
        )
        self.set_btn.bind(on_press=self.set_alarm)
        self.add_widget(self.set_btn)

        # Статус
        self.status_label = Label(text=self.status, font_size=16,
                                  size_hint=(1, 0.07))
        self.add_widget(self.status_label)

        # Блок решения (скрыт)
        self.eq_label = Label(text="", font_size=32, size_hint=(1, 0.13))
        self.answer_input = DecimalInput(
            hint_text="Корни, напр.: 1.5, -0.8",
            multiline=False, font_size=19, size_hint=(1, 0.09)
        )
        self.check_btn = Button(
            text="✅ Проверить", font_size=21, size_hint=(1, 0.11)
        )
        self.check_btn.bind(on_press=self.check)

        self.add_widget(self.eq_label)
        self.add_widget(self.answer_input)
        self.add_widget(self.check_btn)

        self._hide_solver()

        self.target_time = None
        self.current_roots = None
        self._tick_event = None

    # ---------- Выбор звука ----------
    def pick_sound(self, *_):
        self.status_label.text = "📂 Открываю выбор файла..."

        def on_picked(path):
            Clock.schedule_once(lambda dt: self._on_picked(path), 0)

        FilePicker.pick(on_picked)

    def _on_picked(self, path):
        if not path:
            self.status_label.text = "❌ Файл не выбран"
            return

        # На Android копируем content:// в приватную папку,
        # чтобы доступ не пропал после перезапуска.
        if platform == "android" and path.startswith("content://"):
            self.status_label.text = "📥 Копирую файл..."
            local_path = copy_to_app_dir(path)
            if not local_path:
                self.status_label.text = "❌ Не удалось скопировать файл"
                return
            path = local_path

        self.sound.set_custom_uri(path)
        self.sound_name = self.sound.custom_name()
        self.sound_label.text = f"🔊 {self.sound_name}"
        self.status_label.text = "✅ Звук выбран"

    def reset_sound(self, *_):
        self.sound.reset_custom()
        self.sound.stop()
        self.sound.desktop_sound = None
        self.sound_name = self.sound.custom_name()
        self.sound_label.text = f"🔊 {self.sound_name}"
        self.status_label.text = "↺ Возвращён системный звук"

    # ---------- Установка будильника ----------
    def set_alarm(self, *_):
        try:
            hh, mm = map(int, self.time_input.text.split(":"))
        except ValueError:
            self.status_label.text = "❌ Неверный формат (нужно ЧЧ:ММ)"
            return
        if not (0 <= hh < 24 and 0 <= mm < 60):
            self.status_label.text = "❌ Время вне диапазона"
            return

        now = datetime.now()
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        self.target_time = target
        self.status_label.text = f"⏳ Будильник на {target.strftime('%H:%M')}"

        if self._tick_event:
            self._tick_event.cancel()
        self._tick_event = Clock.schedule_interval(self._tick, 1)
        self._tick(0)

    def _tick(self, dt):
        if self.target_time and datetime.now() >= self.target_time:
            if self._tick_event:
                self._tick_event.cancel()
                self._tick_event = None
            self.start_ringing()

    # ---------- Звонок ----------
    def start_ringing(self):
        self.ringing = True
        self.status_label.text = "🔔 РЕШИ УРАВНЕНИЕ!"

        _, _, _, roots, text = generate_equation(self.difficulty.text)
        self.current_roots = roots
        self.eq_label.text = text
        self._show_solver()

        self.sound.start()
        vibrate(2000)

    # ---------- Проверка ----------
    def check(self, *_):
        if not self.ringing:
            return
        if check_answer(self.answer_input.text, self.current_roots):
            self.sound.stop()
            self.ringing = False
            self.status_label.text = "✅ Правильно! Будильник выключен."
            self._hide_solver()
        else:
            self.status_label.text = "❌ Неверно. Новое уравнение!"
            _, _, _, roots, text = generate_equation(self.difficulty.text)
            self.current_roots = roots
            self.eq_label.text = text
            self.answer_input.text = ""
            vibrate(500)

    # ---------- Показ/скрытие ----------
    def _show_solver(self):
        for w in (self.eq_label, self.answer_input, self.check_btn):
            w.opacity = 1
            w.disabled = False
        self.answer_input.text = ""
        self.answer_input.focus = True

    def _hide_solver(self):
        for w in (self.eq_label, self.answer_input, self.check_btn):
            w.opacity = 0
            w.disabled = True

    def on_stop(self):
        if self._tick_event:
            self._tick_event.cancel()
        self.sound.stop()


# ---------- Приложение ----------
class MathAlarmApp(App):
    def build(self):
        self.title = "Math Alarm"
        self.screen = AlarmScreen()
        return self.screen

    def on_stop(self):
        if hasattr(self, "screen"):
            self.screen.on_stop()


if __name__ == "__main__":
    MathAlarmApp().run()