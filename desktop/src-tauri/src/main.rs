#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(any(target_os = "linux", test))]
mod cursor;
mod protocol;
use protocol::{CloseState, STARTUP_SECONDS};
use std::io::Write;
use std::process::{Child, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

struct Backend {
    child: Child,
    close: CloseState,
}

// Persistent message is applied again on load, not lost to an early eval race.
struct Status(Mutex<String>);
fn show_status(app: &tauri::AppHandle, message: &str) {
    if let Some(status) = app.try_state::<Status>() {
        *status.0.lock().expect("status poisoned") = message.to_string();
    }
    if let Some(window) = app.get_webview_window("status") {
        let text = serde_json::to_string(message).expect("constant status text");
        let _ = window.eval(format!(
            "if(document.getElementById('status'))document.getElementById('status').textContent={text};"
        ));
        let _ = window.show();
    }
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

// Only the process we spawned is owned. No discovery/kill/reuse of port8765.
fn request_stop(state: &Arc<Mutex<Backend>>, app: &tauri::AppHandle, exit: bool) {
    let mut backend = state.lock().expect("backend state poisoned");
    if backend.close.request(exit) {
        if let Some(mut stdin) = backend.child.stdin.take() {
            // EOF on drop also means graceful shutdown. Never kill active work.
            let _ = stdin.write_all(b"STOP\n");
        }
    }
    if backend.close.exited && backend.close.exit_when_stopped {
        app.exit(0);
    }
}

fn monitor(state: Arc<Mutex<Backend>>, app: tauri::AppHandle) {
    std::thread::spawn(move || loop {
        let result = {
            let mut backend = state.lock().expect("backend state poisoned");
            match backend.child.try_wait() {
                Ok(Some(code)) => {
                    backend.close.exited = true;
                    Some(Ok((backend.close.exit_when_stopped, code.success())))
                }
                Ok(None) => None,
                Err(_) => Some(Err(())),
            }
        };
        match result {
            Some(Ok((true, success))) => {
                app.exit(if success { 0 } else { 1 });
                return;
            }
            Some(Ok((false, _))) => {
                show_status(&app, "The OrBeats backend stopped. No automatic restart or retry was attempted. Pending console work may need recovery review. Close this window when ready.");
                return;
            }
            Some(Err(())) => {
                show_status(&app, "Backend status is unavailable. OrBeats will not kill an unknown or active operation. Close requests will continue to request a graceful stop.");
                return;
            }
            None => std::thread::sleep(Duration::from_millis(100)),
        }
    });
}

fn start(app: &tauri::AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let resources = app.path().resource_dir()?;
    let executable = resources.join(if cfg!(windows) {
        "backend/orbeats-backend.exe"
    } else {
        "backend/orbeats-backend"
    });
    if !executable.is_file() {
        show_status(app, "The packaged OrBeats backend is missing. No external Python or existing web service will be used. This development bundle is incomplete.");
        return Ok(());
    }
    let mut command = Command::new(executable);
    command
        .arg("--state-dir")
        .arg(app.path().app_local_data_dir()?)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW, retain private pipes.
    }
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(_) => {
            show_status(app, "The packaged OrBeats backend could not start. No external service was used. Check the local installation and close this window.");
            return Ok(());
        }
    };
    let stdout = child
        .stdout
        .take()
        .ok_or("Missing private readiness pipe")?;
    let state = Arc::new(Mutex::new(Backend {
        child,
        close: CloseState::default(),
    }));
    app.manage(state.clone());
    monitor(state.clone(), app.clone());
    let (tx, rx) = mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let _ = tx.send(protocol::readiness(stdout));
    });
    let handle = app.clone();
    std::thread::spawn(move || {
        let url = match rx.recv_timeout(Duration::from_secs(STARTUP_SECONDS)) {
            Ok(Some(url)) => url,
            _ => {
                show_status(&handle, "OrBeats did not become ready within 30 seconds, or returned an invalid private handshake. A graceful stop was requested; no process will be force-killed. Close this window to finish once the backend stops.");
                request_stop(&state, &handle, false);
                return;
            }
        };
        let window_handle = handle.clone();
        let _ = handle.run_on_main_thread(move || {
            if !state.lock().expect("backend state poisoned").close.can_present() {
                return;
            }
            let origin = url.origin();
            let created = WebviewWindowBuilder::new(&window_handle, "main", WebviewUrl::External(url))
                .title("OrBeats")
                .inner_size(1240.0, 820.0)
                .min_inner_size(760.0, 560.0)
                // No remote browsing, external browser launch, popups or file downloads.
                // BeatSaver artwork/audio fetches are subresources, not navigation.
                .on_navigation(move |next| next.origin() == origin)
                .on_download(|_, _| false)
                .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
                .build();
            match created {
                Ok(window) => {
                    #[cfg(target_os = "linux")]
                    let _ = window.with_webview(|view| {
                        use webkit2gtk::{SettingsExt, WebViewExt};
                        if let Some(settings) = view.inner().settings() {
                            settings.set_enable_smooth_scrolling(false);
                        }
                    });
                    if state.lock().expect("backend state poisoned").close.can_present() {
                        if let Some(status) = window_handle.get_webview_window("status") {
                            let _ = status.hide();
                        }
                    } else {
                        let _ = window.hide();
                    }
                }
                Err(_) => {
                    show_status(&window_handle, "The OrBeats window could not open. A graceful backend stop was requested; no automatic retry or console operation was started.");
                    request_stop(&state, &window_handle, false);
                }
            }
        });
    });
    Ok(())
}

fn main() {
    #[cfg(target_os = "linux")]
    if let Err(error) = cursor::configure() {
        eprintln!("{error}");
        std::process::exit(1);
    }
    let app = tauri::Builder::default()
        .setup(|app| {
            app.manage(Status(Mutex::new("Starting the private OrBeats backend…".into())));
            WebviewWindowBuilder::new(app, "status", WebviewUrl::App("index.html".into()))
                .title("OrBeats")
                .inner_size(600.0, 320.0)
                .on_navigation(protocol::status_navigation)
                .on_download(|_, _| false)
                .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
                .on_page_load(|window, _| {
                    if let Some(status) = window.try_state::<Status>() {
                        let message = status.0.lock().expect("status poisoned");
                        let text = serde_json::to_string(&*message).expect("constant text");
                        let _ = window.eval(format!("if(document.getElementById('status'))document.getElementById('status').textContent={text};"));
                    }
                })
                .build()?;
            start(app.handle())?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if let Some(state) = window.try_state::<Arc<Mutex<Backend>>>() {
                    api.prevent_close();
                    show_status(window.app_handle(), "Finishing active work before closing. New work is blocked; an active publication will not be killed.");
                    request_stop(&state, window.app_handle(), true);
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Unable to initialize OrBeats desktop");
    app.run(|handle, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            if let Some(state) = handle.try_state::<Arc<Mutex<Backend>>>() {
                let exited = state.lock().expect("backend state poisoned").close.exited;
                if !exited {
                    api.prevent_exit();
                    request_stop(&state, handle, true);
                }
            }
        }
    });
}

#[cfg(test)]
mod packaging_config_tests {
    #[test]
    fn candidate_configs_use_supported_tauri_bundle_fields() {
        for source in [
            include_str!("../../packaging/windows-x64.json"),
            include_str!("../../packaging/linux-x64.json"),
        ] {
            let raw: serde_json::Value = serde_json::from_str(source).unwrap();
            let config: tauri::utils::config::BundleConfig =
                serde_json::from_value(raw["bundle"].clone()).unwrap();
            assert!(config.active);
            if source.contains("appimage") {
                assert!(config.linux.appimage.bundle_media_framework);
                let targets = serde_json::to_value(&config.targets).unwrap();
                assert_eq!(targets, serde_json::json!(["appimage", "deb"]));
            }
            assert!(matches!(
                config.create_updater_artifacts,
                tauri::utils::config::Updater::Bool(false)
            ));
        }
    }
}
