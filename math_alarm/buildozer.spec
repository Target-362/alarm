[app]
title = Math Alarm
package.name = mathalarm
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,mp3,ogg
source.include_patterns = assets/*,*.wav,*.mp3

version = 0.1

requirements = python3,kivy,pyjnius,android

orientation = portrait
fullscreen = 0

android.permissions = VIBRATE, POST_NOTIFICATIONS, WAKE_LOCK, USE_EXACT_ALARM, READ_MEDIA_AUDIO

android.api = 34
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.ndk_api = 21

android.accept_sdk_license = True
