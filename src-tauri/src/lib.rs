use std::net::TcpListener;
use std::sync::Mutex;

use serde::Serialize;
use tauri::{Manager, RunEvent, State};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

/// Connection details the UI needs to talk to the local Python backend.
#[derive(Clone, Serialize)]
struct BackendInfo {
    port: u16,
    token: String,
}

struct Backend {
    info: BackendInfo,
    child: Mutex<Option<CommandChild>>,
}

#[tauri::command]
fn get_backend_info(state: State<Backend>) -> BackendInfo {
    state.info.clone()
}

/// Ask the OS for a free loopback port. There is a tiny window before the sidecar binds it,
/// which is acceptable for a local single-user app.
fn free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![get_backend_info])
        .setup(|app| {
            let port = free_port()?;
            let token = uuid::Uuid::new_v4().to_string();

            // The token goes in an environment variable rather than argv so it does not
            // show up in process listings.
            let (mut rx, child) = app
                .shell()
                .sidecar("resume-ats-backend")?
                // The backend exits when its stdin closes, so it never outlives the app.
                .args(["--port", &port.to_string(), "--exit-on-stdin-close"])
                .env("RESUME_ATS_TOKEN", &token)
                .spawn()?;

            // Drain sidecar output so its pipe never fills up and blocks the backend.
            tauri::async_runtime::spawn(async move { while rx.recv().await.is_some() {} });

            app.manage(Backend {
                info: BackendInfo { port, token },
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Resume ATS");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(backend) = handle.try_state::<Backend>() {
                if let Some(child) = backend.child.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        }
    });
}
