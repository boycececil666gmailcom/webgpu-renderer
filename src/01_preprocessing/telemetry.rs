// #region Imports
#[cfg(target_os = "android")]
use std::ffi::CString;
use std::time::{Duration, Instant};
// #endregion

// #region Types
pub const DEFAULT_HEARTBEAT_INTERVAL: Duration = Duration::from_secs(4);
#[cfg(target_os = "android")]
const TAG: &[u8] = b"WebGPU-Engine\0";

#[repr(i32)]
pub enum LogLevel {
    Info = 4,
    Warn = 5,
    Error = 6,
}

#[derive(Clone, Debug, Default)]
pub struct GpuInfo {
    pub name: String,
    pub backend: String,
    pub device_type: String,
    pub driver: String,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct VramMetrics {
    pub geometry_bytes: u64,
    pub texture_bytes: u64,
    pub render_target_bytes: u64,
}

impl VramMetrics {
    pub fn total_bytes(&self) -> u64 {
        self.geometry_bytes + self.texture_bytes + self.render_target_bytes
    }

    pub fn total_mb(&self) -> f32 {
        self.total_bytes() as f32 / (1024.0 * 1024.0)
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct FrameStats {
    pub draw_calls: u32,
    pub triangles_drawn: u64,
    pub instances_drawn: u32,
}

#[derive(Clone, Debug, Default)]
pub struct SceneMetrics {
    pub mesh_count: usize,
    pub total_instances: usize,
    pub total_triangles: u64,
    pub primitive_count: usize,
    pub material_count: usize,
    pub vram: VramMetrics,
}

pub struct TelemetryTracker {
    interval: Duration,
    last_report: Instant,
    session_start: Instant,
    seq: u64,
    frame_count: u64,
    accum_duration: Duration,
    min_frame_time: Duration,
    max_frame_time: Duration,
    accum_draw_calls: u64,
    accum_triangles: u64,
    accum_instances: u64,
    resolution: (u32, u32),
    pub gpu: GpuInfo,
    pub scene: SceneMetrics,
}
// #endregion

// #region Scaffolding
#[cfg(target_os = "android")]
#[link(name = "log")]
extern "C" {
    fn __android_log_write(prio: i32, tag: *const std::os::raw::c_char, text: *const std::os::raw::c_char) -> i32;
}

pub fn log(level: LogLevel, module: &str, function: &str, message: &str) {
    let formatted = format!("[{}-{}] {}", module, function, message);

    #[cfg(target_os = "android")]
    {
        if let Ok(c_msg) = CString::new(formatted.as_str()) {
            unsafe {
                __android_log_write(
                    level as i32,
                    TAG.as_ptr() as *const std::os::raw::c_char,
                    c_msg.as_ptr(),
                );
            }
        }
    }

    #[cfg(not(target_os = "android"))]
    {
        match level {
            LogLevel::Error => eprintln!("{}", formatted),
            _ => println!("{}", formatted),
        }
    }
}
// #endregion

// #region Engine
impl Default for TelemetryTracker {
    fn default() -> Self {
        Self::new()
    }
}

impl TelemetryTracker {
    pub fn new() -> Self {
        Self::with_interval(DEFAULT_HEARTBEAT_INTERVAL)
    }

    pub fn with_interval(interval: Duration) -> Self {
        Self {
            interval,
            last_report: Instant::now(),
            session_start: Instant::now(),
            seq: 0,
            frame_count: 0,
            accum_duration: Duration::ZERO,
            min_frame_time: Duration::from_secs(10),
            max_frame_time: Duration::ZERO,
            accum_draw_calls: 0,
            accum_triangles: 0,
            accum_instances: 0,
            resolution: (0, 0),
            gpu: GpuInfo::default(),
            scene: SceneMetrics::default(),
        }
    }

    pub fn set_gpu_info(&mut self, name: String, backend: String, device_type: String, driver: String) {
        self.gpu = GpuInfo { name, backend, device_type, driver };
    }

    pub fn set_scene_stats(
        &mut self,
        meshes: usize,
        total_instances: usize,
        total_triangles: u64,
        primitives: usize,
        materials: usize,
    ) {
        self.scene.mesh_count = meshes;
        self.scene.total_instances = total_instances;
        self.scene.total_triangles = total_triangles;
        self.scene.primitive_count = primitives;
        self.scene.material_count = materials;
    }

    pub fn set_vram_metrics(&mut self, geometry_bytes: u64, texture_bytes: u64, render_target_bytes: u64) {
        self.scene.vram = VramMetrics {
            geometry_bytes,
            texture_bytes,
            render_target_bytes,
        };
    }

    pub fn set_resolution(&mut self, width: u32, height: u32) {
        self.resolution = (width, height);
    }

    pub fn frame_count(&self) -> u64 {
        self.frame_count
    }

    pub fn resolution(&self) -> (u32, u32) {
        self.resolution
    }

    fn emit_heartbeat(&mut self, elapsed: Duration) {
        self.seq += 1;
        let frames = self.frame_count.max(1) as f64;
        let fps = if elapsed.as_secs_f64() > 0.0 {
            (self.frame_count as f64 / elapsed.as_secs_f64()) as f32
        } else {
            0.0
        };
        let avg_ms = (self.accum_duration.as_secs_f64() / frames * 1000.0) as f32;
        let min_ms = if self.min_frame_time.as_secs() < 10 {
            (self.min_frame_time.as_secs_f64() * 1000.0) as f32
        } else {
            0.0
        };
        let max_ms = (self.max_frame_time.as_secs_f64() * 1000.0) as f32;
        let uptime_secs = self.session_start.elapsed().as_secs();
        let uptime = format!("{:02}:{:02}", uptime_secs / 60, uptime_secs % 60);

        let avg_draws = (self.accum_draw_calls as f64 / frames).round() as u64;
        let avg_tris = (self.accum_triangles as f64 / frames).round() as u64;
        let avg_insts = (self.accum_instances as f64 / frames).round() as u64;

        let total_scene_tris = self.scene.total_triangles.max(1);
        let culled_tri_pct = if total_scene_tris > avg_tris {
            (total_scene_tris - avg_tris) as f32 / total_scene_tris as f32 * 100.0
        } else {
            0.0
        };

        let total_insts = (self.scene.total_instances as u64).max(1);
        let culled_inst_pct = if total_insts > avg_insts {
            (total_insts - avg_insts) as f32 / total_insts as f32 * 100.0
        } else {
            0.0
        };

        let geom_mb = self.scene.vram.geometry_bytes as f32 / (1024.0 * 1024.0);
        let tex_mb = self.scene.vram.texture_bytes as f32 / (1024.0 * 1024.0);
        let rt_mb = self.scene.vram.render_target_bytes as f32 / (1024.0 * 1024.0);
        let total_vram_mb = geom_mb + tex_mb + rt_mb;

        let gpu_desc = if !self.gpu.name.is_empty() {
            format!("{} [{}, {}]", self.gpu.name, self.gpu.backend, self.gpu.device_type)
        } else {
            "Active WebGPU Hardware Adapter".to_string()
        };

        let sep = "+-------------------------------------------------------------------------------+";
        log_info("Telemetry", "Heartbeat", sep);
        log_info("Telemetry", "Heartbeat", &format!("| REPORT #{:<4} | Uptime: {:<5} | GPU: {:<40} |", self.seq, uptime, gpu_desc));
        log_info("Telemetry", "Heartbeat", &format!("| Surface: {:<9} | FPS: {:<5.1} | FrameTime: {:<5.2}ms (min: {:<4.2}ms, max: {:<4.2}ms) |", format!("{}x{}", self.resolution.0, self.resolution.1), fps, avg_ms, min_ms, max_ms));
        log_info("Telemetry", "Heartbeat", &format!("| Draw Calls: {:<4} / frame | Meshes: {:<4} | Materials: {:<26} |", avg_draws, self.scene.mesh_count, self.scene.material_count));
        log_info("Telemetry", "Heartbeat", &format!("| Faces (Tris): {:<8} drawn / {:<8} total ({:<5.1}% culled)             |", avg_tris, self.scene.total_triangles, culled_tri_pct));
        log_info("Telemetry", "Heartbeat", &format!("| Instances:    {:<8} drawn / {:<8} total ({:<5.1}% culled)             |", avg_insts, self.scene.total_instances, culled_inst_pct));
        log_info("Telemetry", "Heartbeat", &format!("| VRAM: {:<5.1} MB (Geom: {:<4.1} MB, Textures: {:<5.1} MB, Targets: {:<4.1} MB)       |", total_vram_mb, geom_mb, tex_mb, rt_mb));
        log_info("Telemetry", "Heartbeat", sep);

        self.last_report = Instant::now();
        self.frame_count = 0;
        self.accum_duration = Duration::ZERO;
        self.min_frame_time = Duration::from_secs(10);
        self.max_frame_time = Duration::ZERO;
        self.accum_draw_calls = 0;
        self.accum_triangles = 0;
        self.accum_instances = 0;
    }

    pub fn record_frame(&mut self, frame_time: Duration, stats: FrameStats) {
        self.frame_count += 1;
        self.accum_duration += frame_time;
        if frame_time < self.min_frame_time {
            self.min_frame_time = frame_time;
        }
        if frame_time > self.max_frame_time {
            self.max_frame_time = frame_time;
        }
        self.accum_draw_calls += stats.draw_calls as u64;
        self.accum_triangles += stats.triangles_drawn;
        self.accum_instances += stats.instances_drawn as u64;

        let elapsed = self.last_report.elapsed();
        // Emit first heartbeat early (after 30 frames or 1.5s) so preview starts immediately
        let should_emit = if self.seq == 0 {
            self.frame_count >= 30 || elapsed >= Duration::from_millis(1500)
        } else {
            elapsed >= self.interval
        };

        if should_emit {
            self.emit_heartbeat(elapsed);
        }
    }
}
// #endregion

// #region Core
pub fn log_info(module: &str, function: &str, message: &str) {
    log(LogLevel::Info, module, function, message);
}

pub fn log_warn(module: &str, function: &str, message: &str) {
    log(LogLevel::Warn, module, function, message);
}

pub fn log_error(module: &str, function: &str, message: &str) {
    log(LogLevel::Error, module, function, message);
}
// #endregion
