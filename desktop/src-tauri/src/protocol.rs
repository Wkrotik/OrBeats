//! Pure policy/state helpers; never log a bootstrap URL or backend output.
use std::io::{BufRead, BufReader, Read};
use tauri::Url;

pub const STARTUP_SECONDS: u64 = 30;
pub const MAX_READY: usize = 4096;

pub fn readiness(reader: impl Read) -> Option<Url> {
    let mut line = String::new();
    BufReader::new(reader)
        .take((MAX_READY + 1) as u64)
        .read_line(&mut line)
        .ok()?;
    if line.len() > MAX_READY || !line.ends_with('\n') {
        return None;
    }
    let payload: serde_json::Value = serde_json::from_str(&line).ok()?;
    if payload.as_object()?.len() != 2 || payload.get("protocol")?.as_u64()? != 1 {
        return None;
    }
    let url: Url = payload.get("url")?.as_str()?.parse().ok()?;
    let token = url.path().strip_prefix("/_desktop/bootstrap/")?;
    if url.scheme() != "http"
        || url.host_str() != Some("127.0.0.1")
        || !matches!(url.port(), Some(1..=65535))
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || token.len() != 64
        || !token.bytes().all(|b| b.is_ascii_hexdigit())
    {
        return None;
    }
    Some(url)
}

pub fn status_navigation(url: &Url) -> bool {
    url.username().is_empty()
        && url.password().is_none()
        && url.query().is_none()
        && url.fragment().is_none()
        && url.port().is_none()
        && url.path() == "/index.html"
        && ((url.scheme() == "tauri" && url.host_str() == Some("localhost"))
            || (matches!(url.scheme(), "http" | "https")
                && url.host_str() == Some("tauri.localhost")))
}

#[derive(Default)]
pub struct CloseState {
    pub stopping: bool,
    pub exit_when_stopped: bool,
    pub exited: bool,
}

impl CloseState {
    /// Idempotent pipe stop, with a later user close upgrading a timeout/error.
    pub fn request(&mut self, exit: bool) -> bool {
        self.exit_when_stopped |= exit;
        let first = !self.stopping;
        self.stopping = true;
        first
    }
    pub fn can_present(&self) -> bool {
        !self.stopping && !self.exited
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn record(url: &str) -> Vec<u8> {
        format!("{}\n", serde_json::json!({"protocol":1,"url":url})).into_bytes()
    }
    #[test]
    fn accepts_only_private_bounded_complete_readiness() {
        let url = format!(
            "http://127.0.0.1:23456/_desktop/bootstrap/{}",
            "a".repeat(64)
        );
        assert!(readiness(record(&url).as_slice()).is_some());
        for invalid in [
            url.replace("127.0.0.1", "localhost"),
            url.replace("http:", "https:"),
            url.replace(":23456", ":0"),
            url.replace("127.0.0.1", "user@127.0.0.1"),
            format!("{url}?x=1"),
            format!("{url}#fragment"),
            format!("{url}/extra"),
            url.replace("bootstrap", "untrusted"),
        ] {
            assert!(readiness(record(&invalid).as_slice()).is_none());
        }
        assert!(readiness(&b"{}"[..]).is_none());
        assert!(readiness(vec![b'x'; MAX_READY + 1].as_slice()).is_none());
        let mut partial = record(&url);
        partial.pop();
        assert!(readiness(partial.as_slice()).is_none());
        assert!(readiness(record(&url).as_slice()).is_some());
    }
    #[test]
    fn errors_never_resume_or_force_an_exit() {
        let mut state = CloseState::default();
        assert!(state.can_present());
        assert!(state.request(false));
        assert!(!state.can_present());
        assert!(!state.exit_when_stopped);
        assert!(!state.request(false));
        assert!(!state.request(true));
        assert!(state.exit_when_stopped);
        state.exited = true;
        assert!(!state.can_present());
    }
    #[test]
    fn status_window_never_navigates_to_a_remote_page() {
        for yes in [
            "tauri://localhost/index.html",
            "http://tauri.localhost/index.html",
            "https://tauri.localhost/index.html",
        ] {
            assert!(status_navigation(&yes.parse().unwrap()));
        }
        for no in [
            "https://example.com/index.html",
            "http://tauri.localhost.evil/index.html",
            "http://tauri.localhost:99/index.html",
            "tauri://localhost/other",
            "tauri://localhost/index.html?q=x",
        ] {
            assert!(!status_navigation(&no.parse().unwrap()));
        }
    }
}
