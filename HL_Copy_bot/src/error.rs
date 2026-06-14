use std::time::Duration;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("Network: {0}")]
    Network(String),

    #[error("Trading: {0}")]
    Trading(String),

    #[error("{0}")]
    Other(String),
}

impl AppError {
    pub fn is_retryable(&self) -> bool {
        matches!(self,
            AppError::Network(_) |
            AppError::Trading(_)
        )
    }
}

pub struct RetryConfig {
    pub max_retries: u32,
    pub initial_delay: Duration,
    pub max_delay: Duration,
    pub backoff_multiplier: f64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            initial_delay: Duration::from_secs(1),
            max_delay: Duration::from_secs(10),
            backoff_multiplier: 2.0,
        }
    }
}

pub async fn retry<F, Fut, T>(mut f: F, config: RetryConfig) -> Result<T, AppError>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<T, AppError>>,
{
    let mut last_err = None;
    let mut delay = config.initial_delay;

    for attempt in 1..=config.max_retries {
        match f().await {
            Ok(val) => return Ok(val),
            Err(e) => {
                if !e.is_retryable() || attempt >= config.max_retries {
                    return Err(e);
                }
                tracing::warn!("[retry] attempt {}/{} failed: {e}", attempt, config.max_retries);
                last_err = Some(e);
                tokio::time::sleep(delay).await;
                delay = (Duration::from_secs_f64(delay.as_secs_f64() * config.backoff_multiplier))
                    .min(config.max_delay);
            }
        }
    }

    Err(last_err.unwrap())
}
