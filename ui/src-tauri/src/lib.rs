pub mod dsp;
pub mod fir;
pub mod generator;
pub mod parser;
pub mod pw;

use dsp::DAX3Profile;

#[tauri::command]
fn apply_dsp_profile(profile: DAX3Profile) -> Result<(), String> {
    pw::apply_dsp_profile(&profile)
}

#[tauri::command]
fn bypass_dsp_profile() -> Result<(), String> {
    pw::bypass_dsp_profile()
}

#[tauri::command]
fn restart_pipewire() -> Result<(), String> {
    pw::restart_pipewire()
}

#[tauri::command]
fn is_dsp_active() -> bool {
    pw::is_dsp_active()
}

#[tauri::command]
fn detect_plugins() -> Vec<String> {
    pw::detect_plugins()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            apply_dsp_profile,
            bypass_dsp_profile,
            restart_pipewire,
            is_dsp_active,
            detect_plugins
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
