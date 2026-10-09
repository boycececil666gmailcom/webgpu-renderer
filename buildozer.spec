[app]
# Application title
title = WebGPU Renderer

# Package name
package.name = webgpurenderer

# Package domain (reverse DNS format)
package.domain = org.antigravity

# Source directory containing main.py
source.dir = .

# File extensions to package into the APK
source.include_exts = py,png,jpg,jpeg,wgsl,gltf,glb,bin,json,env,so

# Application version
version = 0.1.0

# Application dependencies for Android NDK compilation
requirements = python3,cffi,pysdl2,wgpu,numpy,pillow,pygltflib,dataclasses-json,marshmallow,typing-inspect,typing-extensions,mypy-extensions,python-dotenv

# Orientation and display
orientation = landscape
fullscreen = 1

# Android SDK / NDK Build Targets
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = release-2024.01.21

# Precompiled native libraries for arm64-v8a
android.add_libs_arm64_v8a = libs/arm64-v8a/libwgpu_native.so

[buildozer]
log_level = 2
warn_on_root = 1
