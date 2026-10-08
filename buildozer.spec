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
source.include_exts = py,png,jpg,jpeg,wgsl,gltf,glb,bin,json,env

# Application version
version = 0.1.0

# Application dependencies for Android NDK compilation
requirements = python3,pysdl2,wgpu,numpy,pillow,pygltflib,pyglm,python-dotenv

# Orientation and display
orientation = landscape
fullscreen = 1

# Android SDK / NDK Build Targets
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
