// #region Modules
pub mod config;
pub mod entry;
pub mod swapchain;

#[path = "01_preprocessing/mod.rs"]
pub mod preprocessing;

#[path = "02_gpu_execution/mod.rs"]
pub mod gpu_execution;

#[path = "03_post_processing/mod.rs"]
pub mod post_processing;
// #endregion

// #region Aliases
pub use preprocessing as step1_preprocessing;
pub use gpu_execution as step2_gpu_execution;
pub use post_processing as step3_post_processing;
pub use swapchain as step4_presentation;

pub use gpu_execution as execution;
pub use gpu_execution as render_execution;
pub use preprocessing as pre_processing;
pub use post_processing as postprocessing;
pub use swapchain as presentation;
// #endregion

// #region Exports
pub use config::Config;
pub use gpu_execution::renderer::{self, FrameUniforms, Renderer};
pub use post_processing::postprocess::{self, PostProcessor};
pub use preprocessing::gltf_loader::{self, GltfScene};
pub use preprocessing::material::{self, Material, MaterialUniforms};
pub use preprocessing::telemetry::{self, log_error, log_info, log_warn, TelemetryTracker};
pub use swapchain::Swapchain;
// #endregion

// #region Entry
#[cfg(target_os = "android")]
pub use entry::android_main;
pub use entry::run_engine;
pub use entry::create_event_loop;
// #endregion
