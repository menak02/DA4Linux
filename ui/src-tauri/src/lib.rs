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
        .invoke_handler(tauri::generate_handler![apply_dsp_profile, detect_plugins])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
