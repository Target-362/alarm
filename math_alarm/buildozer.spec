[app]
title = Math Alarm
package.name = mathalarm
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,mp3,ogg
source.include_patterns = assets/*,*.wav,*.mp3

version = 0.1

# pyjnius и android подтянутся автоматически, но лучше указать явно
requirements = python3,kivy,pyjnius,android

orientation = portrait
fullscreen = 0

# Разрешения
android.permissions = VIBRATE, POST_NOTIFICATIONS, WAKE_LOCK, USE_EXACT_ALARM, READ_MEDIA_AUDIO

# API уровень: 33+ нужен для POST_NOTIFICATIONS на Android 13+
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

# Иконка (положи icon.png рядом)
# icon.filename = %(source.dir)s/icon.png