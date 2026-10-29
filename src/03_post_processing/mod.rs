// #region Imports
pub mod postprocess;

pub use postprocess::PostProcessor;
// #endregion

// #region Tests
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_post_processor_defaults() {
        let mut pp = PostProcessor::new();
        assert!(!pp.is_enabled());
        pp.enabled = true;
        assert!(pp.is_enabled());
    }
}
// #endregion
