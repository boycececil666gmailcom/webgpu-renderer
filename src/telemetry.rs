// #region Imports
use std::ffi::CString;
use std::time::{Duration, Instant};
// #endregion

// #region Types
pub const DEFAULT_HEARTBEAT_INTERVAL: Duration = Duration::from_secs(10);
const TAG: &[u8] = b"WebGPU-Engine\0";

#[repr(i32)]
pub enum LogLevel {
    Info = 4,
    Warn = 5,
    Error = 6,
}

#[derive(Clone, Debug, Default)]
pub struct SceneMetrics {
    pub mesh_count: usize,
    pub instance_count: usize,
    pub primitive_count: usize,
    pub material_count: usize,
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
    resolution: (u32, u32),
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
            resolution: (0, 0),
            scene: SceneMetrics::default(),
        }
    }

    pub fn set_scene_stats(
        &mut self,
        meshes: usize,
        instances: usize,
        primitives: usize,
        materials: usize,
    ) {
        self.scene.mesh_count = meshes;
        self.scene.instance_count = instances;
        self.scene.primitive_count = primitives;
        self.scene.material_count = materials;
    }

    pub fn set_resolution(&mut self, width: u32, height: u32) {
        self.resolution = (width, height);
    }

    fn emit_heartbeat(&mut self, elapsed: Duration) {
        self.seq += 1;
        let fps = if elapsed.as_secs_f64() > 0.0 {
            (self.frame_count as f64 / elapsed.as_secs_f64()) as f32
        } else {
            0.0
        };
        let avg_ms = if self.frame_count > 0 {
            (self.accum_duration.as_secs_f64() / self.frame_count as f64 * 1000.0) as f32
        } else {
            0.0
        };
        let min_ms = if self.min_frame_time.as_secs() < 10 {
            (self.min_frame_time.as_secs_f64() * 1000.0) as f32
        } else {
            0.0
        };
        let max_ms = (self.max_frame_time.as_secs_f64() * 1000.0) as f32;
        let uptime_secs = self.session_start.elapsed().as_secs();
        let uptime = format!("{:02}:{:02}", uptime_secs / 60, uptime_secs % 60);

        let metrics = format!(
            "#{seq} (Uptime: {uptime}) | FPS: {fps:.1} | FrameTime: {avg_ms:.2}ms (min: {min_ms:.2}ms, max: {max_ms:.2}ms) | Meshes: {meshes} | Instances: {inst} | Surface: {w}x{h} | Status: Nominal",
            seq = self.seq,
            uptime = uptime,
            fps = fps,
            avg_ms = avg_ms,
            min_ms = min_ms,
            max_ms = max_ms,
            meshes = self.scene.mesh_count,
            inst = self.scene.instance_count,
            w = self.resolution.0,
            h = self.resolution.1,
        );

        log_info("Engine", "Metrics", &metrics);

        self.last_report = Instant::now();
        self.frame_count = 0;
        self.accum_duration = Duration::ZERO;
        self.min_frame_time = Duration::from_secs(10);
        self.max_frame_time = Duration::ZERO;
    }

    pub fn record_frame(&mut self, frame_time: Duration) {
        self.frame_count += 1;
        self.accum_duration += frame_time;
        if frame_time < self.min_frame_time {
            self.min_frame_time = frame_time;
        }
        if frame_time > self.max_frame_time {
            self.max_frame_time = frame_time;
        }

        let elapsed = self.last_report.elapsed();
        if elapsed >= self.interval {
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
