[app]
title = YT Downloader
package.name = ytdownloader
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv
version = 0.1
requirements = python3,kivy==2.3.0,yt-dlp,requests,urllib3,certifi,idna,charset-normalizer,openssl
orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 1
android.archs = arm64-v8a
